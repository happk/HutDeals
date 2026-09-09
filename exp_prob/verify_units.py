# -*- coding: utf-8 -*-
"""驗證：項分類（units）在 coupons.js 的結果。

用法：python exp_prob/verify_units.py "D:/.../20260908_..._Public"
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


def dump(code):
    c = by.get(code)
    if not c:
        print(f"{code}: 不在 coupons.js")
        return
    print(f"\n=== {code} {c['name']} ===")
    print("  tags:", c["tags"])
    print("  units:", c.get("units"))
    g = defaultdict(list)
    for it in c.get("items") or []:
        g[(it.get("group"), it.get("groupIdx"))].append(it)
    for k in sorted(g, key=lambda x: (str(x[0]), x[1])):
        cats = sorted({i.get("cat") for i in g[k]})
        print(f"    {k[0]}{k[1]} cats={cats}")
        for i in g[k]:
            print(f"        [{i.get('cat')}] {i.get('text')}")


for code in ("16166", "16161", "16010", "92001", "16181", "93014"):
    dump(code)

print("\n=== 全站統計 ===")
print("  有 units 的券:", sum(1 for c in lst if c.get("units")))
print("  有 items 但無 units 的券:", [c["code"] for c in lst if c.get("items") and not c.get("units")][:20])
print("  有飲料 tag 的 active:", sum(1 for c in lst if c.get("status") == "active" and "飲料" in (c.get("tags") or [])))
print("  item cat 分布:", Counter(i.get("cat") for c in lst for i in (c.get("items") or [])).most_common())
print("  項分類分布:", Counter(tuple(u["cats"]) for c in lst for u in (c.get("units") or [])).most_common(8))
