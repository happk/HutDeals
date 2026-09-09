# -*- coding: utf-8 -*-
"""唯讀：確認分類是否真的「逐項」——同一組內不同項是否有不同 cat。

用法：python exp_prob/verify_per_item.py "D:/.../20260908_..._Public"
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
root = Path(sys.argv[1]).resolve()


def load(p):
    src = p.read_text(encoding="utf-8")
    return json.loads(re.search(r"window\.HUTDEALS_\w+\s*=\s*(\{.*\})\s*;?\s*$", src, re.S).group(1))


lst = load(root / "public" / "coupons.js")["coupon_list"]
by = {c["code"]: c for c in lst}


def dump(code, only_second=False):
    c = by[code]
    print(f"\n=== {code} {c['name']} ===")
    print(f"    tags={c['tags']}")
    groups = defaultdict(list)
    for it in c.get("items") or []:
        groups[(it.get("group"), it.get("groupIdx"))].append(it)
    for k in sorted(groups, key=lambda x: (str(x[0]), x[1])):
        if only_second and k[0] != "second":
            continue
        items = groups[k]
        cats = [i.get("cat") for i in items]
        mixed = "  ← 同組內不同 cat（逐項分類生效）" if len(set(cats)) > 1 else ""
        print(f"  {k[0]}{k[1]} 組 cat 集合={sorted(set(cats))}{mixed}")
        for i in items:
            print(f"      [{i.get('cat')}] {i.get('text')}")


dump("16161", only_second=True)   # 混組：同組有可樂與薯金幣
dump("16166")                     # 原始回報案例

print("\n=== 全站：同一個 second 組內出現多種 cat 的組數 ===")
n = 0
for c in lst:
    groups = defaultdict(set)
    for it in c.get("items") or []:
        if it.get("group") == "second":
            groups[it.get("groupIdx")].add(it.get("cat"))
    n += sum(1 for cats in groups.values() if len(cats) > 1)
print(f"  {n} 組（這些組在舊版會被迫全部同一 cat）")

print("\n=== add（加購）項目的 cat 現況 ===")
add_cats = Counter(it.get("cat") for c in lst for it in (c.get("items") or []) if it.get("group") == "add")
print("  ", dict(add_cats))
