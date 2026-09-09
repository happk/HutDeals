# -*- coding: utf-8 -*-
"""遷移後驗證：飲料 cat 是否只落在真飲料、混組是否逐項、有無回歸。

用法：python exp_prob/verify_migration.py "D:/.../20260908_..._Public"
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
root = Path(sys.argv[1]).resolve()


def load(p):
    src = p.read_text(encoding="utf-8")
    return json.loads(re.search(r"window\.HUTDEALS_\w+\s*=\s*(\{.*\})\s*;?\s*$", src, re.S).group(1))


lst = load(root / "public" / "coupons.js")["coupon_list"]
full = load(root / "public" / "coupons_full.js")["coupon_list"]

print("=== 被判為『飲料』的品名（應全為飲料）===")
drink_names = Counter()
for c in lst:
    for it in c.get("items") or []:
        if it.get("cat") == "飲料":
            drink_names[it.get("text")] += 1
for n, k in drink_names.most_common():
    print(f"  {k:>4}  {n}")

print("\n=== 被判為『副食』但名字像飲料（回歸檢查）===")
bad = [n for n in {it.get("text") for c in lst for it in (c.get("items") or [])
                   if it.get("cat") == "副食"}
       if any(k in (n or "") for k in ("可樂", "七喜", "茶", "咖啡", "果汁", "汽水"))]
print("  ", bad or "無")

print("\n=== 混組券（同組同時有副食與飲料）抽樣 ===")
n = 0
for c in lst:
    groups = {}
    for it in c.get("items") or []:
        groups.setdefault((it.get("group"), it.get("groupIdx")), set()).add(it.get("cat"))
    for k, cats in groups.items():
        if k[0] == "second" and {"副食", "飲料"} <= cats:
            n += 1
            if n <= 6:
                print(f"  {c['code']} second{k[1]} cats={sorted(cats)} tags={c['tags']}")
print(f"  混組券總數: {n}")

print("\n=== 統計 ===")
print("  有飲料 tag 的 active:", sum(1 for c in lst if c.get("status") == "active" and "飲料" in (c.get("tags") or [])))
print("  cat 分布:", Counter(it.get("cat") for c in lst for it in c.get("items") or []).most_common())
print("  官方券 main cat 抽樣:", {c["code"]: Counter(i.get("cat") for i in c["items"] if i.get("group") == "main").most_common(1)
                                 for c in lst if not c.get("source") and c.get("items")})
