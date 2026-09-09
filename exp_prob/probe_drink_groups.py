# -*- coding: utf-8 -*-
"""唯讀：確認『請選擇1份飲料』（無「或」）組裡到底裝了什麼；以及關鍵字覆蓋率。

用法：python exp_prob/probe_drink_groups.py "D:/.../20260908_..._Public"
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
root = Path(sys.argv[1]).resolve()
st = json.load(open(root / "data" / "scan_state.json", encoding="utf-8"))
codes = st["codes"]

DRINK_KW = ("可樂", "七喜", "雪碧", "汽水", "紅茶", "綠茶", "烏龍茶", "柚茶",
            "咖啡", "玉米濃湯", "濃湯", "果汁")


def is_drink(n):
    return any(k in (n or "") for k in DRINK_KW)


print("=== 出現『飲料』且無『或』的組標題 → 組內品名（前 15 種）===")
by_subj = defaultdict(Counter)
for code, rec in codes.items():
    for it in rec.get("items") or []:
        if it.get("group") != "second":
            continue
        subj = it.get("groupTitle") or ""
        if "飲料" in subj and "或" not in subj:
            by_subj[subj][it.get("text")] += 1
for subj, names in sorted(by_subj.items()):
    print(f"\n  組標題={subj!r}")
    for n, c in names.most_common(15):
        flag = "飲" if is_drink(n) else "非"
        print(f"    [{flag}] {c:>4}  {n}")

print("\n\n=== 全部 second 品名：關鍵字判定分布 ===")
allnames = Counter()
for rec in codes.values():
    for it in rec.get("items") or []:
        if it.get("group") == "second":
            allnames[it.get("text")] += 1
drinks = {n: c for n, c in allnames.items() if is_drink(n)}
others = {n: c for n, c in allnames.items() if not is_drink(n)}
print(f"  命中飲料關鍵字 {len(drinks)} 種:")
for n, c in sorted(drinks.items(), key=lambda kv: -kv[1]):
    print(f"    {c:>4}  {n}")
print(f"  未命中 {len(others)} 種（前 25）:")
for n, c in sorted(others.items(), key=lambda kv: -kv[1])[:25]:
    print(f"    {c:>4}  {n}")
