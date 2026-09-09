# -*- coding: utf-8 -*-
"""唯讀查證：公開版是否同樣存在三個問題（93014 搜不到 / 散點 0 點 / 入庫趨勢單點）。

用法：python exp_prob/verify_public_issues.py "D:/Desktop/work/project/20260908_PizzaHut-Coupon-Scraper_Public"
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()


def load(p):
    src = p.read_text(encoding="utf-8")
    return json.loads(re.search(r"window\.HUTDEALS_\w+\s*=\s*(\{.*\})\s*;?\s*$", src, re.S).group(1))


lst = load(root / "public" / "coupons.js")["coupon_list"]
full = load(root / "public" / "coupons_full.js")["coupon_list"]
print("repo:", root)
print("coupons.js 筆數:", len(lst), "| full:", len(full))

c = next((x for x in lst if str(x.get("code")) == "93014"), None)
print("\n93014 存在:", bool(c), "| name:", c["name"] if c else None)
nocode = [
    x["code"] for x in lst
    if x.get("status") == "active"
    and str(x["code"]).lower() not in f"{x.get('name','')} {x.get('description') or ''}".lower()
]
print("code 不在 name/description 的 active 券:", nocode)

print("\nmsrp 非空:", sum(1 for x in full if x.get("msrp") is not None))
print("priceNote 非空樣本:", [x.get("priceNote") for x in full if x.get("priceNote")][:5])
old = sum(1 for x in full
          if x.get("price") is not None and re.search(r"原價\$(\d+)", x.get("priceNote") or ""))
new = sum(1 for x in full if x.get("price") is not None and x.get("msrp") is not None)
print("散點現行條件(priceNote)點數:", old, "| 改讀 msrp 點數:", new)
print("firstSeen 不同日期數:", len({x.get("firstSeen") for x in full if x.get("firstSeen")}))
