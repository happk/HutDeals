# -*- coding: utf-8 -*-
"""唯讀：公開版飲料詞彙表來源檢查 + 官方券 items 現況。

用法：python exp_prob/probe_public_lexicon.py "D:/.../20260908_..._Public"
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
root = Path(sys.argv[1]).resolve()
st = json.load(open(root / "data" / "scan_state.json", encoding="utf-8"))
codes = st["codes"]

# 單一類別飲料組（subject 含飲料、不含「或」）的品名
lex = Counter()
mixed = Counter()
for code, rec in codes.items():
    for it in rec.get("items") or []:
        if it.get("group") != "second":
            continue
        subj = it.get("groupTitle") or ""
        if "飲料" in subj and "或" not in subj:
            lex[it.get("text")] += 1
        elif "飲料" in subj:
            mixed[it.get("text")] += 1

print("=== 單一類別飲料組的品名（詞彙表來源）===")
for name, n in lex.most_common():
    print(f"  {n:>4}  {name}")
print(f"  共 {len(lex)} 種品名 / {sum(lex.values())} 筆")

print("\n=== 含「或」的飲料組品名（不進詞彙表；點心混在其中）===")
for name, n in mixed.most_common(20):
    print(f"  {n:>4}  {name}")

# 官方券 items 現況
src = (root / "public" / "coupons.js").read_text(encoding="utf-8")
data = json.loads(re.search(r"window\.HUTDEALS_\w+\s*=\s*(\{.*\})\s*;?\s*$", src, re.S).group(1))
off = [c for c in data["coupon_list"] if not c.get("source")]
print(f"\n=== 官方券 {len(off)} 張，有 items 的：===")
for c in off:
    items = c.get("items") or []
    if items:
        cats = Counter(i.get("cat") for i in items)
        print(f"  {c['code']} items={len(items)} cats={dict(cats)} tags={c['tags']}")
print("有 items 的官方券:", sum(1 for c in off if c.get("items")))
