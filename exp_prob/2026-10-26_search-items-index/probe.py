"""唯讀 probe：修復搜尋問題——現況量測與兩個修法方向的成本估算（2026-10-26）。

問題（docs/todo.md 6a7ec13 §1）：filterCoupons 的 haystack 只組 name/description/code，
卡片實際顯示的餐點候選 items[].text 不在內；ingest_external 在 items 拆得出來時把
description 設 None，內容物對搜尋完全隱形。

本 probe 對「當前」public/coupons.js（723 券，v1.1.0 後）量測：
1. 缺口規模：數個代表詞的現行命中 vs items 命中 vs 漏掉。
2. 方案 A（產出端 searchText 欄位）：payload/gzip 成本。
3. 方案 B（前端把 items 併入搜尋字串）：每鍵掃描量、預組後成本。
4. 範圍參考：flavorSets 口味名是否也有同樣缺口（供範圍拍板，非本 todo 範圍）。

用法：python exp_prob/2026-10-26_search-items-index/probe.py
"""
import gzip
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
COUPONS_JS = REPO / "public" / "coupons.js"


def load_coupons():
    src = COUPONS_JS.read_text(encoding="utf-8")
    m = re.search(r"window\.HUTDEALS_COUPONS\s*=\s*(\{.*\})\s*;?\s*$", src, re.S)
    return json.loads(m.group(1)), src


def cur_haystack(c):
    return f"{c.get('name') or ''} {c.get('description') or ''} {c.get('code') or ''}".lower()


def items_text(c):
    return " ".join(sorted({i.get("text") or "" for i in c.get("items") or [] if i.get("text")}))


def flavor_text(c):
    return " ".join(f.get("name") or "" for fs in c.get("flavorSets") or [] for f in fs)


def main() -> int:
    data, src = load_coupons()
    L = data["coupon_list"]
    print(f"== 資料源 == coupons.js count={data['count']} last_update={data['last_update']}")
    print(f"   raw {len(src.encode('utf-8')) // 1024} KB, gzip {len(gzip.compress(src.encode('utf-8'))) // 1024} KB")
    act = [c for c in L if c["status"] == "active"]
    print(f"   active={len(act)} offline={len(L) - len(act)}")

    with_items = [c for c in L if c.get("items")]
    with_desc = [c for c in L if c.get("description")]
    print(f"   has items={len(with_items)} has description={len(with_desc)} neither={len([c for c in L if not c.get('items') and not c.get('description')])}")
    print(f"   items by source: {dict(Counter(str(c.get('source')) for c in with_items))}")
    uniq = {i.get("text") for c in with_items for i in c["items"] if i.get("text")}
    print(f"   items[].text 不重複值 {len(uniq)} 個")

    print("\n== 1. 缺口規模（現行 haystack=name+description+code）==")
    for q in ("黃金雞軟骨", "雞軟骨", "薯金幣", "可樂", "比薩"):
        hits, miss = [], []
        for c in L:
            in_cur = q.lower() in cur_haystack(c)
            in_items = q.lower() in items_text(c).lower()
            if in_cur:
                hits.append(c["key"])
            elif in_items:
                miss.append(c["key"])
        off_miss = sum(1 for k in miss
                       if next(c for c in L if c["key"] == k)["status"] != "active")
        print(f"   搜 {q!r}: 現行 {len(hits)} 筆 | items 另有 {len(miss)} 筆搜不到（含 offline {off_miss}）")
        if miss:
            print(f"      例: {miss[:6]}")

    print("\n== 2. 方案 A：產出端 searchText 欄位 ==")
    L2 = []
    for c in L:
        c2 = dict(c)
        if c.get("items"):
            c2["searchText"] = items_text(c2)
        L2.append(c2)
    body2 = json.dumps({"coupon_list": L2, "count": data["count"],
                        "last_update": data["last_update"]},
                       ensure_ascii=False, separators=(",", ":"))
    src2 = f"window.HUTDEALS_COUPONS = {body2};\n"
    gz, gz2 = (len(gzip.compress(s.encode("utf-8"))) for s in (src, src2))
    print(f"   raw {len(src.encode()) // 1024} → {len(src2.encode()) // 1024} KB"
          f"（+{(len(src2.encode()) - len(src.encode())) // 1024} KB）")
    print(f"   gzip {gz // 1024} → {gz2 // 1024} KB（+{(gz2 - gz) // 1024} KB 傳輸）")
    print("   註：admin coupons_full.js 可在 write 端拔欄位不增量；但 repo 每日 diff +290 KB")

    print("\n== 3. 方案 B：前端把 items 併入搜尋字串 ==")
    cur_chars = sum(len(cur_haystack(c)) for c in L)
    add_chars = sum(len(items_text(c)) for c in with_items)
    print(f"   每鍵掃描量：現行 {cur_chars:,} 字元 → 併入 items {cur_chars + add_chars:,} 字元")
    print("   預組（載入時或 WeakMap 懶快取每券 haystack 一次）後，每鍵僅 includes 無重建")
    print(f"   payload 增量 0（items[].text 本就在 coupons.js 全量下載）")

    print("\n== 4. 範圍參考：flavorSets 口味名缺口（非本 todo 範圍）==")
    for q in ("芝心", "起司"):
        cur_n = sum(1 for c in L if q.lower() in cur_haystack(c))
        fl_n = sum(1 for c in L if q in flavor_text(c) and q.lower() not in cur_haystack(c))
        print(f"   搜 {q!r}: 現行 {cur_n} 筆 | flavorSets 另有 {fl_n} 筆搜不到")
    return 0


if __name__ == "__main__":
    sys.exit(main())
