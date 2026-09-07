"""HutDeals site — 官網原始項目 → Coupon 物件 → 合併 → public/coupons.js。

原 build_coupons.py。改吃 lib/coupons(讀寫合一)、lib/net(fetch)、lib/repo；
extract_price → extract_coupon_price（消與 scan/parse_step2.extract_step2_price 同名衝突）。

資料流:
    fetch_promos.parse_page() → raw items
    → enrich(price/tags/order_type/order_url)
    → merge(既有 coupons.js: firstSeen/lastSeen/status/offlineSince, 60 天清除)
    → public/coupons.js  (window.HUTDEALS_COUPONS = {...})

安全設計:任何解析/合併階段的失敗都不會覆蓋既有 public/coupons.js(非零結束碼)。
"""
import datetime as dt
import json
import sys
from pathlib import Path

from script.lib import coupons as coupons_lib
from script.lib.net import fetch_html
from script.lib.repo import REPO
from script.site.fetch_promos import PROMO_URL, parse_page

PUBLIC = REPO / "public"
TAGS_PATH = Path(__file__).resolve().parent / "tags.json"
COUPONS_JS = PUBLIC / "coupons.js"

# 官網訂購頁的「優惠券兌換」入口;pdpop 變體沒有靜態 href,先一律導到此頁讓使用者輸入代碼
ORDER_URL = "https://www.pizzahut.com.tw/order/?mode=step_2&ct=9&cu=804"

KEEP_OFFLINE_DAYS = 60  # offline 超過天數即清除

PRICE_RE = __import__("re").compile(r"\$\s*(\d{2,4})\s*(起)?")


def extract_coupon_price(name: str, description: str | None) -> tuple[int | None, str | None]:
    """best-effort 從名稱(優先)再敘述抓 $NNN;多個取最低;「起」記到 priceNote。"""
    for text in (name, description or ""):
        matches = PRICE_RE.findall(text)
        if matches:
            prices = [int(n) for n, _ in matches]
            note = "起" if any(up for _, up in matches) else None
            return min(prices), note
    return None, None


def extract_order_type(name: str, description: str | None) -> str | None:
    text = f"{name}{description or ''}"
    if "APP" in name:
        return "APP專屬"
    if "外送" in text:
        return "外送"
    if "外帶" in text:
        return "外帶"
    return None


def build_tags(name: str, description: str | None, table: dict[str, list[str]]) -> list[str]:
    text = f"{name} {description or ''}"
    return [
        tag
        for tag, keywords in table.items()
        if any(kw in text for kw in keywords)
    ]


def enrich(raw_item: dict, tags_table: dict[str, list[str]]) -> dict:
    name = raw_item.get("name") or ""
    description = raw_item.get("description")
    price, price_note = extract_coupon_price(name, description)
    key = raw_item.get("code") or f"pid:{raw_item.get('id')}"
    return {
        "key": key,
        "code": raw_item.get("code"),
        "name": name,
        "description": description,
        "price": price,
        "priceNote": price_note,
        "image": raw_item.get("image"),
        "category": raw_item.get("category"),
        "orderType": extract_order_type(name, description),
        "orderUrl": raw_item.get("orderUrl") or ORDER_URL,
        "tags": build_tags(name, description, tags_table),
    }


def merge(
    existing: dict[str, dict],
    new_coupons: list[dict],
    today: str,
    keep_offline_days: int = KEEP_OFFLINE_DAYS,
) -> tuple[list[dict], dict]:
    """合併新舊:更新 lastSeen、標記 offline、清除過期 offline;回 (列表, 統計)。"""
    stats = {"new": 0, "updated": 0, "went_offline": 0, "dropped": 0, "revived": 0}
    today_dt = dt.date.fromisoformat(today)

    # 清除超過保留期的 offline
    kept: dict[str, dict] = {}
    for key, coupon in existing.items():
        if coupon.get("status") == "offline" and coupon.get("offlineSince"):
            offline_dt = dt.date.fromisoformat(coupon["offlineSince"])
            if (today_dt - offline_dt).days > keep_offline_days:
                stats["dropped"] += 1
                continue
        kept[key] = coupon

    result: list[dict] = []
    seen_keys: set[str] = set()
    for coupon in new_coupons:
        key = coupon["key"]
        seen_keys.add(key)
        old = kept.get(key)
        coupon["lastSeen"] = today
        if old is None:
            coupon["firstSeen"] = today
            coupon["status"] = "active"
            stats["new"] += 1
        else:
            coupon["firstSeen"] = old.get("firstSeen", today)
            if old.get("status") == "offline":
                coupon["status"] = "active"
                coupon.pop("offlineSince", None)
                stats["revived"] += 1
            else:
                coupon["status"] = "active"
                stats["updated"] += 1
        result.append(coupon)

    for key, old in kept.items():
        if key in seen_keys:
            continue
        # 外部碼(source=verified-external)不在官網列表是常態——死活由 scan_state
        # (ingest_external) 決定,不被每日官網 build 誤標 offline(08 入庫規則)。
        if old.get("source") == "verified-external":
            result.append(old)
            continue
        if old.get("status") != "offline":
            old["status"] = "offline"
            old["offlineSince"] = today
            stats["went_offline"] += 1
        old.setdefault("lastSeen", today)
        result.append(old)

    result.sort(key=coupons_lib.coupon_sort_key)
    return result, stats


def main() -> int:
    tags_table = json.loads(TAGS_PATH.read_text(encoding="utf-8"))
    existing = coupons_lib.load_coupons_js(COUPONS_JS)
    today = dt.date.today().isoformat()

    all_raw: list[dict] = []
    for page_type in ("plu", "dgt"):
        all_raw.extend(parse_page(fetch_html(PROMO_URL.format(type=page_type))))
    if not all_raw:
        print("ERROR: official pages yielded 0 items; keeping existing coupons.js untouched",
              file=sys.stderr)
        return 1

    coupons = [enrich(item, tags_table) for item in all_raw]
    merged, stats = merge(existing, coupons, today)
    last_update = dt.datetime.now().isoformat(timespec="seconds")
    coupons_lib.write_coupons_js(merged, last_update)
    coupons_lib.write_coupons_full(merged, last_update)  # admin 分頁全量檔(2-3)
    print(f"coupons: {len(merged)} (stats={stats}) last_update={last_update} -> {COUPONS_JS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
