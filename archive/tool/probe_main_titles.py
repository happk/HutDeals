# -*- coding: utf-8 -*-
"""盤點全站 main 組標題詞彙分佈，確保 cat 分類表完整。

從 scan_state 收集所有 group=main 的 groupTitle(官網組標題)，
統計不同字樣，供設計「組標題 → cat」完整對照。
"""
import json
import re
from collections import Counter
from pathlib import Path

REPO = Path(r"D:\Desktop\work\project\20260903_PizzaHut-Coupon-Scraper")
state = json.loads((REPO / "data" / "scan_state.json").read_text(encoding="utf-8"))
codes = state["codes"]

# 收集所有 main 組標題
titles = Counter()
examples = {}
for code, r in codes.items():
    seen = set()
    for it in r.get("items") or []:
        if it.get("group") == "main" and it.get("groupTitle"):
            gt = it["groupTitle"]
            if gt not in seen:
                seen.add(gt)
                titles[gt] += 1
                examples.setdefault(gt, []).append(code)

print(f"不同 main 組標題: {len(titles)} 種\n")
for gt, cnt in titles.most_common():
    print(f"  [{cnt:3}] {gt}  (例: {examples[gt][:3]})")

# 整理成規則關鍵字看覆蓋
print("\n== 分類關鍵字分組 ==")
buckets = {
    "比薩尺寸(大/小/個人/13/9/6吋)": r"大比薩|小比薩|個人比薩|13吋|9吋|6吋",
    "比薩(無尺寸)": r"比薩|披薩",
    "義大利麵/飯/筆管麵/千層麵": r"義大利麵|飯|筆管麵|千層麵|飯麵",
    "副食/煎餅/點心": r"副食|煎餅|點心",
    "其它(未分類)": r".*",
}
for code, r in codes.items():
    pass
# 統計哪些標題落入哪桶
import collections
bucket_counter = collections.Counter()
uncategorized = []
for gt in titles:
    matched = None
    for bname, pat in buckets.items():
        if bname == "其它(未分類)":
            continue
        if re.search(pat, gt):
            matched = bname
            break
    if matched:
        bucket_counter[matched] += titles[gt]
    else:
        bucket_counter["其它(未分類)"] += titles[gt]
        uncategorized.append(gt)
for b, c in bucket_counter.most_common():
    print(f"  {b}: {c} 組")
if uncategorized:
    print("  未分類標題:", uncategorized)
