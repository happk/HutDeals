"""HutDeals site — 產生爬蟲可見的 SEO 片段（noscript 清單 + JSON-LD）。

背景：首頁是 Vite SPA，<body> 只有 <div id="root">，不跑 JS 的爬蟲
（及 Bing 背後的 AI 搜尋）看不到優惠內容。本腳本讀 public/coupons.js
的活躍券，產出兩個片段；deploy 時由 inject_seo.py 灌入 dist/index.html：

    public/seo-noscript.html  — <noscript> 內層：全部活躍券「名稱＋價格」明文連結
    public/seo-ld.json        — ItemList + Offer JSON-LD（raw JSON，由注入端包 script 標籤）

在 update.yml 每日 build_coupons/ingest/enrich 之後跑。
安全設計：0 活躍券（解析失敗或資料異常）即非零結束，不覆蓋既有檔。

用法：python -m script.site.gen_seo
"""
import html
import json
import sys
from urllib.parse import quote

from script.lib import coupons as coupons_lib
from script.lib.repo import REPO

PUBLIC = REPO / "public"
COUPONS_JS = PUBLIC / "coupons.js"
NOSCRIPT_PATH = PUBLIC / "seo-noscript.html"
LD_PATH = PUBLIC / "seo-ld.json"

# GitHub Pages 部署網址
BASE = "https://happk.github.io/HutDeals/"

HEADER = "<!-- 由 script/site/gen_seo.py 每日產生；勿手改 -->\n"


def coupon_url(code: str | None, key: str | None) -> str:
    """深連結；code 缺時回退 key（與 sitemap 共用，兩者政策一致）。"""
    target = code or key
    if not target:
        return BASE
    return f"{BASE}?code={quote(str(target), safe='')}"


def build_noscript(active: list[dict]) -> str:
    lines = [HEADER.rstrip("\n"), "<ul>"]
    for c in active:
        name = c.get("name") or c.get("key") or ""
        price = c.get("price")
        label = name if price is None else f"{name} — ${price}"
        url = coupon_url(c.get("code"), c.get("key"))
        lines.append(
            f'  <li><a href="{html.escape(url, quote=True)}">'
            f"{html.escape(label)}</a></li>"
        )
    lines.append("</ul>")
    return "\n".join(lines) + "\n"


def build_ld(active: list[dict], last_update: str) -> str:
    elements: list[dict] = []
    for i, c in enumerate(active, start=1):
        name = c.get("name") or c.get("key") or ""
        url = coupon_url(c.get("code"), c.get("key"))
        product: dict = {"@type": "Product", "name": name, "url": url}
        if c.get("price") is not None:
            product["offers"] = {
                "@type": "Offer",
                "price": c["price"],
                "priceCurrency": "TWD",
                "availability": "https://schema.org/InStock",
            }
        elements.append(
            {"@type": "ListItem", "position": i, "url": url, "item": product}
        )
    payload: dict = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": "HutDeals — 必勝客優惠整理",
        "description": "台灣必勝客 Pizza Hut 優惠整理：每日自動同步官網優惠與聯名優惠碼。",
        "numberOfItems": len(elements),
        "itemListElement": elements,
    }
    if last_update:
        payload["dateModified"] = last_update
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    # JSON-LD 將被包進 <script>：把 < 轉為 \u003c（合法 JSON 跳脫，解析還原為 <）。
    # < 不存在則 </script> 與 <!-- 都無法形成，券名再惡意也閉合不了 script 區塊。
    body = body.replace("<", "\\u003c")
    return body + "\n"


def load_payload() -> dict:
    try:
        text = COUPONS_JS.read_text(encoding="utf-8")
    except OSError:
        raise SystemExit("coupons.js 缺檔或不可讀")
    idx = text.find(coupons_lib.DATA_MARKER)
    if idx < 0:
        raise SystemExit("coupons.js 解析失敗：找不到 DATA_MARKER")
    return json.JSONDecoder().raw_decode(text[idx + len(coupons_lib.DATA_MARKER):])[0]


def main() -> int:
    payload = load_payload()
    raw = payload.get("coupon_list") or []
    active = sorted(
        (c for c in raw if c.get("status") == "active"),
        key=coupons_lib.coupon_sort_key,
    )
    if not active:
        print(
            "ERROR: 活躍券為 0，不覆蓋既有 SEO 片段",
            file=sys.stderr,
        )
        return 1
    last_update = payload.get("last_update") or ""
    NOSCRIPT_PATH.write_text(build_noscript(active), encoding="utf-8")
    LD_PATH.write_text(build_ld(active, last_update), encoding="utf-8")
    print(f"seo: {len(active)} 張活躍券 -> {NOSCRIPT_PATH.name} + {LD_PATH.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
