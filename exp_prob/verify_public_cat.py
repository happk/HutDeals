# -*- coding: utf-8 -*-
"""唯讀：公開版 16166 / 飲料標籤 / cat 現況。

用法：python exp_prob/verify_public_cat.py "D:/.../20260908_PizzaHut-Coupon-Scraper_Public"
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
active = [c for c in lst if c.get("status") == "active"]
c = next(x for x in lst if x["code"] == "16166")
print("=== 公開版 16166 ===")
print("tags:", c["tags"], "| desc:", c["description"])
for it in c.get("items") or []:
    print(f"  {it.get('group')}{it.get('groupIdx')} cat={it.get('cat'):<6} {it.get('text')}")

print("\n有『飲料』tag 的 active:", sum(1 for x in active if "飲料" in (x.get("tags") or [])))
print("items cat=飲料 的券:", sum(1 for x in active if any(i.get("cat") == "飲料" for i in x.get("items") or [])))
print("items cat 分布:", Counter(i.get("cat") for x in active for i in x.get("items") or []).most_common())

st = json.load(open(root / "data" / "scan_state.json", encoding="utf-8"))["codes"]
r = st.get("16166") or {}
print("\nscan_state 16166 items:")
for i in (r.get("items") or []):
    if i.get("group") == "second":
        print(f"  second{i.get('groupIdx')} cat={i.get('cat')!r} title={i.get('groupTitle')!r} {i.get('text')}")
