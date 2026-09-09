# -*- coding: utf-8 -*-
"""唯讀：組標題 vs 組內項目的衝突案例（公開版 scan_state）。

用法：python exp_prob/probe_subject_conflict.py "D:/.../20260908_..._Public"
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
root = Path(sys.argv[1]).resolve()
st = json.load(open(root / "data" / "scan_state.json", encoding="utf-8"))
codes = st["codes"]

DRINK_KW = ("可樂", "七喜", "雪碧", "汽水", "紅茶", "綠茶", "烏龍茶", "柚茶",
            "咖啡", "濃湯", "果汁")


def is_drink(n):
    return any(k in (n or "") for k in DRINK_KW)


print("=== 組標題含『飲料』但組內有非飲料項（抽樣）===")
n = 0
for code, rec in codes.items():
    groups = defaultdict(list)
    for it in rec.get("items") or []:
        if it.get("group") == "second":
            groups[it.get("groupIdx")].append(it)
    for gidx, items in groups.items():
        subj = next((i.get("groupTitle") or "" for i in items if i.get("groupTitle")), "")
        if "飲料" not in subj:
            continue
        drinks = [i["text"] for i in items if is_drink(i["text"])]
        others = [i["text"] for i in items if not is_drink(i["text"])]
        if others and drinks:
            n += 1
            if n <= 8:
                print(f"  {code} second{gidx} subj={subj!r}")
                print(f"      飲料={drinks[:3]} 其他={others[:4]}")
print(f"  共 {n} 組")

print("\n=== 組標題含『副食』但組內全是飲料 ===")
m = 0
for code, rec in codes.items():
    groups = defaultdict(list)
    for it in rec.get("items") or []:
        if it.get("group") == "second":
            groups[it.get("groupIdx")].append(it)
    for gidx, items in groups.items():
        subj = next((i.get("groupTitle") or "" for i in items if i.get("groupTitle")), "")
        if "副食" not in subj:
            continue
        names = [i["text"] for i in items]
        if names and all(is_drink(x) for x in names):
            m += 1
            if m <= 8:
                print(f"  {code} second{gidx} subj={subj!r} items={names[:4]}")
print(f"  共 {m} 組")
