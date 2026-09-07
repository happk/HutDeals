"""HutDeals 一次性工具 — parse_meal v2 規則表全量重 parse（2026-09-06）。

背景：parse_meal 重構為規則表驅動（docs/parse-rules.md），舊資料的 items/price
是 v1 parser 產物（價格黏品項/主項沒切開/飲料組沒觸發）。本工具離線重算：

    1. data/scan_state.json  有 desc_head/desc 的碼 → items=parse_meal(...)、
       price/msrp 由 desc 重抽（extract_text_price/extract_msrp,抽不到保留原值）
    2. public/coupons.js     官方碼（無 source 欄位）items 由 description 重算
       （description 是真值,enrich_official 規矩）；外部碼交給 ingest_external 重建
    3. 報告 before/after 品質統計（grouped/flat/none）

之後手動跑 `python -m script.site.ingest_external` 重建外部碼入庫。
用法：python -m script.support.tools.refresh_meal_parse
"""
import json
import sys

from script.lib.coupons import load_coupons_js, write_coupons_js
from script.lib.repo import REPO
from script.lib.state import STATE_PATH
from script.scan.parse_meal import parse_meal
from script.scan.parse_step2 import extract_msrp, extract_text_price


def quality(items: list | None) -> str:
    if not items:
        return "none"
    return "grouped" if any(i["choices"] for i in items) else "flat"


def stats_note(d: dict) -> str:
    return " ".join(f"{k}={v}" for k, v in sorted(d.items()))


def main() -> int:
    changed_items = changed_price = 0
    before: dict[str, int] = {}
    after: dict[str, int] = {}

    # ---- 1. scan_state ----
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    codes = state.get("codes", {})
    for code, rec in codes.items():
        text = rec.get("desc") or rec.get("desc_head") or ""
        if not text:
            continue
        old_items = rec.get("items") or []
        before[quality(old_items)] = before.get(quality(old_items), 0) + 1
        items = parse_meal(text)
        if json.dumps(items, ensure_ascii=False, sort_keys=True) != json.dumps(
                rec.get("items") or [], ensure_ascii=False, sort_keys=True):
            changed_items += 1
        rec["items"] = items or []
        # price/msrp 重抽（抽不到保留原值——desc 缺價格時 HTML L0 才有,離線拿不到）
        price, fixed = extract_text_price(text)
        if price is not None:
            if rec.get("price") != price:
                changed_price += 1
            rec["price"] = price
        msrp = extract_msrp(text, price, fixed)
        if msrp is not None:
            rec["msrp"] = msrp
        after[quality(rec["items"])] = after.get(quality(rec["items"]), 0) + 1

    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"scan_state: {len(codes)} codes | items 改動 {changed_items} | price 改動 {changed_price}")
    print(f"  before: {stats_note(before)}")
    print(f"  after : {stats_note(after)}")

    # ---- 2. coupons.js 官方碼 items 重算（外部碼由 ingest_external 重建,不在此動）----
    coupons = load_coupons_js()
    official_fixed = 0
    for c in coupons.values():
        if c.get("source"):  # verified-external → ingest_external 管
            continue
        desc = c.get("description")
        if not desc:
            continue
        items = parse_meal(desc)
        if items and items != c.get("items"):
            c["items"] = items
            official_fixed += 1
    if official_fixed:
        from datetime import datetime
        write_coupons_js(list(coupons.values()),
                         datetime.now().isoformat(timespec="seconds"))
    print(f"coupons.js 官方碼 items 更新: {official_fixed}")
    print("下一步: python -m script.site.ingest_external")
    return 0


if __name__ == "__main__":
    sys.exit(main())
