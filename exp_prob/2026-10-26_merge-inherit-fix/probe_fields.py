"""唯讀 probe（2026-10-26）：c5d1634-1 修復前的事實核查——官券補全欄位的實際形狀。

問題來源：todo c5d1634-1 記錄於 2026-09-08，修法方向寫「繼承 items/orderType/msrp」三欄。
本 probe 對當前 coupons.js 的官券（無 source 欄位者）逐一核查：
1. 已補全官券（有 items）實際帶哪些「列表殼不會有」的欄位——繼承集合的真值。
2. flavorIdx→flavorSets 完整性（繼承 items 若不帶 flavorSets 會造出懸空索引）。
3. 模擬：明日 merge 產生列表殼時，各候選欄位各有幾張官券需要繼承。

用法：python exp_prob/2026-10-26_merge-inherit-fix/probe_fields.py
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
src = (REPO / "public" / "coupons.js").read_text(encoding="utf-8")
data = json.loads(re.search(r"window\.HUTDEALS_COUPONS\s*=\s*(\{.*\})\s*;?\s*$", src, re.S).group(1))
officials = [c for c in data["coupon_list"] if not c.get("source")]
filled = [c for c in officials if c.get("items")]
shells = [c for c in officials if not c.get("items")]
print(f"官券 {len(officials)}（補全 {len(filled)}／殼 {len(shells)}）"
      f"｜pid: 鍵 {sum(1 for c in officials if str(c['key']).startswith('pid'))}")

FIELDS = ["items", "flavorSets", "units", "orderType", "msrp", "priceNote", "description"]


def have(c, f):
    v = c.get(f)
    if f in ("items", "flavorSets", "units"):
        return bool(v)  # 空陣列視同無
    return v is not None and v != ""


print("\n== 1. 欄位存在率（已補全官券 vs 殼）==")
for f in FIELDS:
    n_f = sum(1 for c in filled if have(c, f))
    n_s = sum(1 for c in shells if have(c, f))
    print(f"  {f:12s} 補全 {n_f:2d}/{len(filled)}  殼 {n_s:2d}/{len(shells)}")

print("\n== 2. orderUrl 形態（cno 直連 vs 通用頁）==")
for label, group in (("補全", filled), ("殼", shells)):
    cno = sum(1 for c in group if "cno=" in (c.get("orderUrl") or ""))
    print(f"  {label}: cno 直連 {cno}／通用頁 {len(group) - cno}")

print("\n== 3. flavorIdx→flavorSets 完整性（繼承 items 必須連 flavorSets）==")
bad = []
for c in filled:
    fs_len = len(c.get("flavorSets") or [])
    for it in c.get("items") or []:
        fi = it.get("flavorIdx")
        if fi is not None and not (0 <= fi < fs_len):
            bad.append((c["key"], fi, fs_len))
            break
print(f"  懸空 flavorIdx：{len(bad)} 張" + (f" -> {bad[:5]}" if bad else "（全體一致）"))
no_fs_with_items = [c["key"] for c in filled if not c.get("flavorSets")]
print(f"  有 items 無 flavorSets：{len(no_fs_with_items)} 張 -> {no_fs_with_items[:5]}")

print("\n== 4. msrp／orderType 補全官券實況 ==")
print(f"  msrp 有值：{[c['key'] for c in filled if have(c, 'msrp')]}")
print(f"  orderType 有值：{sum(1 for c in filled if have(c, 'orderType'))} 張"
      f"（值分佈 {dict(Counter(c.get('orderType') for c in filled if have(c, 'orderType')))}）")
print(f"  殼的 orderType（build 名稱解析而來）："
      f"{sum(1 for c in shells if have(c, 'orderType'))} 張"
      f"（值分佈 {dict(Counter(c.get('orderType') for c in shells if have(c, 'orderType')))}）")

print("\n== 5. 模擬繼承影響（明日列表殼 vs 今日補全，各欄需繼承張數）==")


def _name_has_channel(c):
    # build 的 extract_order_type 只認名稱前綴字樣；名稱含「外帶/外送/APP」即殼自帶 orderType
    n = c.get("name") or ""
    return bool(re.search(r"(外帶|外送|APP)", n))


# 列表殼會有的欄位（build enrich 產出）：name/description/price/priceNote/category/tags/
# orderUrl(通用)/orderType(僅名稱含通路字樣)。殼不會有：items/flavorSets/units/msrp。
for f in ("items", "flavorSets", "units", "orderType", "msrp"):
    need = sum(1 for c in filled
               if have(c, f) and not (f == "orderType" and _name_has_channel(c)))
    print(f"  {f:12s} 需繼承 {need:2d} 張")
