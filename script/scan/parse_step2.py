"""HutDeals — step_2 套餐頁解析（掃號→聯名方→通路→價格的可靠固定規則）。

唯一目的：把官網 step_2 HTML 穩定解析成結構化 dict，供 scan_run/scan_probe 與後續 08 入庫用。
規則由 `script/support/tests/test_parse_step2.py` 守護（真實 HTML fixture），改版不得破壞既有欄位。

輸入：step_2 完整 HTML（`GET /order/?mode=step_2&type_id=1025&cno={code}` 的回應）。
輸出 dict 欄位（全部有預設，parse 失敗不 throw，回 None）：

    code        5 位碼（由參數帶入）
    title       標題（og:title，去「| Pizza Hut 必勝客」尾巴）
    partner     聯名方（PARTNERS 詞典命中；季節/純官網 = None）
    ig_hint     聯名方 IG 查詢關鍵字（未命中 = None）
    channels    通路集合：{'外帶','外送'}（從 og:desc/套餐內容 開頭判定）
    price       主價格 int（**純結構化 HTML**：descPrice div／套餐價格 li／price_selling；無→None）
    msrp        原價/最高價值 int（**純顯示備用註記**，來自 desc 文案），無 = None
    desc_head   og:description 前 200 字（人工核對用）

通路判定規則（2026-09-04 實測四樣本）：
    og:desc / 套餐內容 開頭帶「外帶/外送」或「外送/外帶」→ {外帶, 外送}
    og:title 前綴「平日外帶-」且 desc 開頭直接品項 → {外帶}（如 94199）
    其餘：掃 desc_head 是否含「限外帶」「僅供外帶」「外送」等字樣補判。
價格判定規則（2026-09-07 改版：**desc 退出結構化欄位**）：
    price 只從結構化 HTML（descPrice/套餐價格/price_selling）；起價/無 → None。
    msrp 保留 desc 文案（原價/最高價值/現省）當**純顯示註記**，不進結構化判定。
"""

import json
import re
from pathlib import Path

from script.lib.text import clean_text

# 聯名詞典（掃號核心價值：把碼→聯名方→IG 帳號）。人工可擴充，命中第一個即停。
# ig_hint 為「查詢方向」非保證正確 handle；實際 IG 以 partner_accounts.json 為準。
PARTNERS = [
    {"kw": ["兆豐證券"], "name": "兆豐證券", "ig_hint": "megasec"},
    {"kw": ["兆豐"], "name": "兆豐銀行", "ig_hint": "mega bank 兆豐"},
    {"kw": ["中國信託", "中信"], "name": "中國信託", "ig_hint": "ctbcbank"},
    {"kw": ["國泰世華", "國泰"], "name": "國泰世華", "ig_hint": "cubc_card"},
    {"kw": ["台新"], "name": "台新銀行", "ig_hint": "taishinbank"},
    {"kw": ["玉山"], "name": "玉山銀行", "ig_hint": "esunbank"},
    {"kw": ["富邦"], "name": "台北富邦", "ig_hint": "taipeifubon"},
    {"kw": ["全支付"], "name": "全支付", "ig_hint": "全支付"},
    {"kw": ["foodpanda", "熊貓"], "name": "foodpanda", "ig_hint": "foodpanda_taiwan"},
    {"kw": ["中華電信"], "name": "中華電信", "ig_hint": "emome"},
    {"kw": ["全曜"], "name": "全曜", "ig_hint": "全曜"},
    {"kw": ["Goodlife", "goodlife"], "name": "Goodlife", "ig_hint": "goodlife"},
    {"kw": ["素易", "素", "蔬食", "奶素"], "name": "素易", "ig_hint": "suiistw"},
    {"kw": ["寶可夢", "Pokémon", "pokemon"], "name": "寶可夢", "ig_hint": "pokemon_tw"},
    {"kw": ["LINE"], "name": "LINE Pay", "ig_hint": "linepay_tw"},
    {"kw": ["街口"], "name": "街口支付", "ig_hint": "jko_pay"},
    {"kw": ["Uber Eats", "UberEats"], "name": "Uber Eats", "ig_hint": "ubereats_tw"},
    {"kw": ["屋馬"], "name": "屋馬燒肉", "ig_hint": "woomabarbq"},
    {"kw": ["魔物獵人"], "name": "魔物獵人", "ig_hint": "monsterhunter"},
    {"kw": ["漢來"], "name": "漢來美食", "ig_hint": "hilai"},
]


def clean(text: str | None) -> str:
    """委派 lib.text.clean_text（保留名稱供 _og/_h1 內部呼叫）。"""
    return clean_text(text or "")


def _og(body: str, prop: str) -> str | None:
    m = re.search(rf'property="{re.escape(prop)}" content="([^"]+)"', body)
    return clean(m.group(1)) if m else None


def _h1(body: str) -> str | None:
    m = re.search(r"<h1[^>]*>(.*?)</h1>", body, re.S)
    return clean(re.sub(r"<[^>]+>", "", m.group(1))) if m else None


def _desc_text(body: str) -> str:
    """og:desc 缺時退回頁面『套餐內容』文字。"""
    m = re.search(r"套餐內容[：:]\s*(.*?)(?:\s*套餐說明|\s*注意事項|$)", body, re.S)
    return clean(re.sub(r"<[^>]+>", "", m.group(1))) if m else ""


def match_partner(text: str) -> dict | None:
    for p in PARTNERS:
        if any(kw in text for kw in p["kw"]):
            return p
    return None


def extract_channels(title: str, desc: str) -> list[str]:
    """通路判定。回 ['外帶','外送'] 子集。"""
    head = (desc or "")[:120]
    t = (title or "")
    # 明確「外帶/外送」「外送/外帶」
    if re.search(r"(外帶|外送)\s*/\s*(外帶|外送)", head):
        pair = re.search(r"(外帶|外送)\s*/\s*(外帶|外送)", head)
        return sorted({pair.group(1), pair.group(2)})
    # title 前綴「平日外帶-」→ 外帶
    if re.search(r"^(平日|期間|限定)?外帶[- ]", t):
        return ["外帶"]
    if re.search(r"^外送[- ]", t):
        return ["外送"]
    # 限外帶 / 僅供外帶 → 外帶
    if "限外帶" in head or "僅供外帶" in head:
        return ["外帶"]
    if "限外送" in head or "僅供外送" in head:
        return ["外送"]
    # 兜底：含字樣就給（供人工核對）
    out = set()
    if "外帶" in desc[:200]:
        out.add("外帶")
    if "外送" in desc[:400]:
        out.add("外送")
    return sorted(out)


# ============ 價格解析（2026-09-07 改版：純結構化，desc 退出）============
#
# 原則（使用者 2026-09-07）：**結構化欄位一律只從結構化 HTML 拿，不用 desc 文字 parse**。
# desc（og:description）只當備用/人核對；過往 price 誤抓（26898「=NT$95起」被 L1 文本
# 當固定價抓到 95，頁面 descPrice=$144 反被忽略）都是 desc-text 引起。
#
# 主價格 price 來源（結構化 HTML，先到先得）：
#   L0a  descPrice div（`<div class="descPrice">$ 144</div>`）→ 加價型套餐固定價
#   L0b  套餐價格：$N li（說明區）
#   L0c  getCbData 的 price_selling>0（內嵌 JS JSON）         → 基準型 package（16013→399）
#   以上皆無 → price = None（不從 desc 撈；前端顯示「價格未知」）
#
# 原價 msrp：**純顯示備用註記**（前端刪除線「原價$XXX」），來源仍是 desc 文案
# （官網無結構化原價欄位）：
#   直接型  原價／最高價值 → 關鍵字後金額即原價
#   差額型  現省           → price + 省額（僅 price 為結構化固定價時成立）
# 金額群組一律 (?![\d,]) 防回溯誤拆（16172：$333 被拆成 33+3 的教訓）。

_MONEY = r"(?:NT\\?\$|\$)\s*([\d,]+)"

# 結構化 HTML 價格來源（先到先得）
_HTML_PRICE_PATTERNS = (
    r'class="descPrice[^"]*"[^>]*>\s*(?:NT\\?\$)?\$\s*([\d,]+)',
    r'套餐價格[：:]\s*(?:NT\\?\$)?\$\s*([\d,]+)',
)

# 基準型 package：getCbData() 內嵌 JS 的 price_selling（>0 才算數；0=非固定價）
_PRICE_SELLING_RE = r'price_selling\s*[:=]\s*"?(\d+)"?'

# 原價直接型關鍵詞（原價／最高價值；支援括號包裹與「元」尾）
_MSRP_DIRECT_PATTERNS = (
    r'[（({]\s*(?:最高價值|原價)\s*[:：]?\s*' + _MONEY + r'\s*元?\s*[）)}]',
    r'(?:最高價值|原價)\s*[:：]?\s*' + _MONEY,
)

# 原價差額型關鍵詞（現省；「最多」= 上限估計，一併接受）
_MSRP_DIFF_PATTERN = r'(?:最多)?現省\s*' + _MONEY


def _to_int(s: str) -> int:
    return int(s.replace(",", ""))


def _first_amount(text: str, patterns) -> int | None:
    """依序套用樣式表，回第一個命中的金額群組。"""
    for p in patterns:
        m = re.search(p, text)
        if m:
            return _to_int(m.group(1))
    return None


def extract_html_price(html: str) -> int | None:
    """結構化 HTML 價格：descPrice div → 套餐價格 li → price_selling(>0)。

    純結構化來源，不用 desc 文字。起價/無結構化價格 → None。
    """
    p = _first_amount(html, _HTML_PRICE_PATTERNS)
    if p is not None:
        return p
    for m in re.finditer(_PRICE_SELLING_RE, html):
        val = _to_int(m.group(1))
        if val > 0:
            return val
    return None


def extract_msrp(desc: str, price: int | None) -> int | None:
    """原價（純顯示備用註記，來自 desc 文案）：直接型關鍵詞優先；差額型
    （現省）僅在 price 為結構化固定價（非 None）時成立。"""
    direct = _first_amount(desc, _MSRP_DIRECT_PATTERNS)
    if direct is not None:
        return direct
    if price is not None:
        m = re.search(_MSRP_DIFF_PATTERN, desc)
        if m:
            return price + _to_int(m.group(1))
    return None


def parse_step2(html: str, code: str) -> dict:
    """step_2 HTML → 結構化 dict（不 throw，欄位缺回 None/空）。"""
    og_title = _og(html, "og:title") or _h1(html) or ""
    # 去「| Pizza Hut 必勝客」尾巴
    title = re.sub(r"\s*\|\s*Pizza Hut 必勝客\s*$", "", og_title).strip()

    og_desc = _og(html, "og:description") or _desc_text(html)

    partner = match_partner(title + " " + og_desc[:200])
    # price 純結構化；msrp 顯示註記（見模組級價格解析說明）
    price = extract_html_price(html)
    msrp = extract_msrp(og_desc, price)
    channels = extract_channels(title, og_desc)

    return {
        "code": code,
        "title": title,
        "partner": partner["name"] if partner else None,
        "ig_hint": partner["ig_hint"] if partner else None,
        "channels": channels,
        "price": price,
        "msrp": msrp,
        "desc_head": og_desc[:200],
        "desc": og_desc,
    }


def main() -> int:  # 手動驗單檔：python -m script.scan.parse_step2 <html> <code>
    import sys
    if len(sys.argv) < 3:
        print("usage: parse_step2.py <html_file> <code>", file=sys.stderr)
        return 2
    html = Path(sys.argv[1]).read_text(encoding="utf-8")
    print(json.dumps(parse_step2(html, sys.argv[2]), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
