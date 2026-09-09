"""HutDeals site — 外部碼入庫：把掃號驗證的外部碼併進 coupons.js。

原 ingest_external.py。coupons.js 讀寫改用 lib/coupons（消 load_coupons_js/
寫入/排序三份重複）；official_keys 也進 lib。

資料來源：data/scan_state.json（scan_run 產出，status=alive 且不在官網列表 = 外部碼）。
對映（scan_state → Coupon）：
    code         → key/code（5 位碼即 key）
    title        → name；desc_head → description（去「外帶/外送」前綴）
    price/msrp   → price（msrp 存 priceNote「原價$XXX」）
    channels     → orderType；partner → 獨立欄位（不進 tags）
    orderUrl     → step_2 兌換網址；無 image → null（圖源在 IG）
    startDate/endDate/igShortcode/igAuthor → IG 錄入回填欄位

用法：python -m script.site.build_coupons 之後接 python -m script.site.ingest_external
"""
import datetime as dt
import json
import re
import sys

from script.lib import coupons as coupons_lib
from script.lib.categories import DRINK_KW, SIZE_TAG, cat_tags, classify_units
from script.lib.coupons import COUPONS_JS, official_keys
from script.lib.repo import REPO
from script.lib.state import STATE_PATH

STEP2_URL = "https://www.pizzahut.com.tw/order/?mode=step_2&type_id=1025&cno={code}"

_CONTENT_TAG_KW = {
    "比薩": ["比薩", "披薩", "鬆厚比薩"],
    "副食": ["副食", "薯金幣", "QQ球", "雞軟骨"],
    "買一送一": ["買1送1", "買1送4", "買大送大", "送1個", "送2個", "買大送小", "加33元即享"],
    "折扣": ["折", "特價"],
    # 飲料詞彙與項分類共用同一份（script/lib/categories.DRINK_KW），不另立清單
    "飲料": ["飲料", *DRINK_KW],
}

# 內容 tag 尺寸關鍵字（fallback：僅在無結構化項分類時用）
_SIZE_RULES = [(tag, kws) for tag, kws in SIZE_TAG.items()]


def _size_tags(text: str) -> list[str]:
    """依 desc 的比薩尺寸字樣補 tag；含「比薩/鬆厚」才適用尺寸判別。

    fallback（2026-09-07）：結構化 cat 才是尺寸主要來源；此函式只在無 cat 時用。
    """
    if not ("比薩" in text or "披薩" in text):
        return []
    return [tag for tag, kws in _SIZE_RULES if any(k in text for k in kws)]


def _content_tags(text: str) -> list[str]:
    tags = [t for t, kws in _CONTENT_TAG_KW.items() if any(k in text for k in kws)]
    tags.extend(_size_tags(text))
    return sorted(set(tags))


def external_to_coupon(rec: dict, today: str) -> dict:
    code = rec["code"]
    title = rec.get("title") or f"{code} 優惠"
    desc = rec.get("desc") or rec.get("desc_head") or ""
    # 去前綴通路字樣（外帶/外送…），保留餐點內容
    desc = re.sub(r"^(外帶|外送)(/外帶|/外送)?\s*", "", desc).strip()
    order_type = "/".join(rec.get("channels") or []) or None
    msrp = rec.get("msrp")
    items = rec.get("items") or []  # 結構化餐點（hutdeals#08；拆不出 → []）
    # P2（2026-09-07）：coupons.js 的 description 只在「結構化 items 拆不出」時才用
    # desc 當內容（純顯示）；items 成功時 description 不帶 desc（結構化優先）。
    if items:
        description = None
    else:
        # 去前綴通路字樣；保留餐點內容
        description = re.sub(r"^(外帶|外送)(/外帶|/外送)?\s*", "", desc).strip() or None
    # 方案甲（2026-09-07）：結構化 price 缺 → desc「$N 元起」兜底，priceNote="起"
    # （標明是 desc 推測；見 docs/crawler-data-sources.md 價格規則）
    price = rec.get("price")
    price_note = None
    if price is None and desc:
        m = re.search(r"\$\s*(\d+)\s*元?\s*起", desc)
        if m:
            price = int(m.group(1).replace(",", ""))
            price_note = "起"
    # 項分類（2026-09-09）：以「項」為單位在產出 coupons.js 時算（scan_state 不含 cat）。
    # classify_units 會就地寫回每筆候選的 cat，並回傳項層分類 [{group,groupIdx,cats}]。
    units = classify_units(items)
    # tags：內容關鍵字（標題/描述）+ 項分類（尺寸類與白名單 cat，如飲料/副食）
    tags = _content_tags(title + " " + desc)
    ct = cat_tags(units)
    if ct:
        tags = [t for t in tags if t not in SIZE_TAG] + ct
    return {
        "key": code,
        "code": code,
        "name": title,
        "description": description,
        "price": price,
        "msrp": msrp,
        "priceNote": price_note,
        "image": None,
        "category": None,
        "orderType": order_type,
        "orderUrl": STEP2_URL.format(code=code),
        "tags": sorted(set(tags)),
        "source": "verified-external",
        "partner": rec.get("partner"),
        "verifiedAt": today,
        "p_id": rec.get("p_id"),
        "items": items,
        "units": units,
        # 期限（IG 錄入回填，見 ig_ingest；單碼自動，多碼留 09）
        "startDate": rec.get("startDate"),
        "endDate": rec.get("endDate"),
        "igShortcode": rec.get("ig_shortcode"),
        "igAuthor": rec.get("ig_author"),
        "firstSeen": today,
        "lastSeen": today,
        "status": "active",
    }


def main() -> int:
    if not STATE_PATH.exists():
        print("no scan_state.json — run scan_run first", file=sys.stderr)
        return 1
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    today = dt.date.today().isoformat()

    coupons = coupons_lib.load_coupons_js()
    off_keys = official_keys(coupons)

    external = [
        {**rec, "code": code} for code, rec in state.get("codes", {}).items()
        if rec.get("status") == "alive" and code not in off_keys
    ]
    if not external:
        print("no external alive codes to ingest")
        return 0

    new_count = 0
    for rec in external:
        code = rec["code"]
        if code.startswith("9"):
            # 官方公開池（91-94xxx）永遠不當外部碼入庫——即使 coupons.js 官方集異常
            # 也不得讓官方碼被外部格式覆寫（2026-09-05 實測事故防呆）
            print(f"  SKIP {code}: 官方池 9 前綴，不當外部碼")
            continue
        if code in off_keys:
            # 同碼官網優先：外部碼不覆蓋（08 規則）
            print(f"  SKIP {code}: 已在官網列表（官網優先）")
            continue
        coupon = external_to_coupon(rec, today)
        old = coupons.get(code)
        if old:  # 既有外部碼：保留 firstSeen/offline 歷史
            coupon["firstSeen"] = old.get("firstSeen", today)
            if old.get("status") == "offline":
                coupon["status"] = "active"
                coupon.pop("offlineSince", None)
        coupons[code] = coupon
        new_count += 1
        tag = f"  <<{coupon['partner']}" if coupon["partner"] else ""
        print(f"  + {code} {coupon['name']} | ${coupon['price']} | {coupon['orderType']}{tag}")

    coupon_list = sorted(coupons.values(), key=coupons_lib.coupon_sort_key)
    last_update = dt.datetime.now().isoformat(timespec="seconds")
    coupons_lib.write_coupons_js(coupon_list, last_update)
    coupons_lib.write_coupons_full(coupon_list, last_update)  # admin 分頁全量檔(2-3)
    print(f"coupons: {len(coupon_list)} (official {len(off_keys)}"
          f" + external {new_count}) -> {COUPONS_JS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
