# -*- coding: utf-8 -*-
"""唯讀查證（2026-09-09）三個回報問題：

1. 16166 篩「飲料」被屏蔽 —— tags 沒飲料，但 items 內有飲料品
2. 93014 沒出現在網站 —— 資料在、但代碼搜尋查不到 + 排序位置很後面
3. admin 散點圖沒顯示 —— 散點條件仍讀 priceNote「原價$N」，資料已改存 msrp

只讀不寫。用法：python exp_prob/inspect_three_issues.py
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent


def load(path):
    src = path.read_text(encoding="utf-8")
    m = re.search(r"window\.HUTDEALS_\w+\s*=\s*(\{.*\})\s*;?\s*$", src, re.S)
    return json.loads(m.group(1))


def sort_key(c):
    p = c.get("price")
    return (1, 0, c["key"]) if p is None else (0, p, c["key"])


pub = load(ROOT / "public" / "coupons.js")
full = load(ROOT / "public" / "coupons_full.js")
lst = pub["coupon_list"]
active = [c for c in lst if c.get("status") == "active"]

print("=" * 60)
print(f"coupons.js: 全部 {len(lst)} / active {len(active)}")

# ---------- 1) 16166 篩飲料 ----------
print("\n[1] 16166 篩「飲料」被屏蔽")
c = next(c for c in lst if c["code"] == "16166")
print("  name:", c["name"], "| description:", c["description"], "| category:", c["category"])
print("  tags:", c["tags"])
for it in c.get("items") or []:
    print(f"    {it.get('group')}{it.get('groupIdx')} cat={it.get('cat'):<6} {it.get('text')}")

DRINK_KW = ("可樂", "七喜", "雪碧", "汽水", "紅茶", "綠茶", "烏龍茶", "咖啡", "濃湯", "果汁", "茶")
print("\n  「飲料」tag 的 active 券:", sum(1 for x in active if "飲料" in (x.get("tags") or [])))
print("  items 內含飲料字樣的 active 券:",
      sum(1 for x in active if any(k in " ".join(i.get("text") or "" for i in x.get("items") or []) for k in DRINK_KW)))
miss = []
for x in active:
    txt = " ".join(i.get("text") or "" for i in x.get("items") or [])
    if any(k in txt for k in DRINK_KW) and "飲料" not in (x.get("tags") or []):
        drinks = [i["text"] for i in x.get("items") or [] if any(k in (i.get("text") or "") for k in DRINK_KW)]
        cats = sorted({i.get("cat") for i in x.get("items") or [] if i.get("cat")})
        miss.append((x["code"], cats, drinks[:3]))
print(f"  有飲料品但沒「飲料」tag 的 active 券: {len(miss)}")
for code, cats, drinks in miss:
    print(f"    {code} cats={cats} 飲料品={drinks}")

# ---------- 2) 93014 ----------
print("\n[2] 93014 沒出現在網站")
codes = [x["code"] for x in sorted(active, key=sort_key)]
print("  在 coupons.js:", any(x["code"] == "93014" for x in lst),
      "| active:", next(x["status"] for x in lst if x["code"] == "93014"),
      "| 價格升冪排名:", codes.index("93014") + 1, "/", len(codes))
hits = [x["code"] for x in active
        if "93014" in f"{x.get('name','')} {x.get('description') or ''}".lower()]
print("  前端搜尋(只查 name+description) '93014' →", len(hits), "筆")
nocode = [x["code"] for x in active
          if str(x["code"]).lower() not in f"{x.get('name','')} {x.get('description') or ''}".lower()]
print(f"  code 不在 name/description 的 active 券: {len(nocode)} →", nocode)
print("  orderType=null 的 active 券:",
      sum(1 for x in active if not x.get("orderType")), "（選自取/外送時會消失）")

# ---------- 3) admin 散點 ----------
print("\n[3] admin 散點圖沒顯示")
old = [x for x in full["coupon_list"]
       if x.get("price") is not None and re.search(r"原價\$(\d+)", x.get("priceNote") or "")]
new = [x for x in full["coupon_list"]
       if x.get("price") is not None and x.get("msrp") is not None]
print("  散點現行條件(priceNote 含「原價$N」)點數:", len(old))
print("  改用 msrp 欄位點數:", len(new))
print("  priceNote 非空樣本:", [x.get("priceNote") for x in full["coupon_list"] if x.get("priceNote")][:5])
print("  msrp 非空筆數:", sum(1 for x in full["coupon_list"] if x.get("msrp") is not None))

# ---------- 附：items cat 分布 ----------
print("\n[附] items cat 值分布")
for k, v in Counter(i.get("cat") for x in lst for i in x.get("items") or []).most_common():
    print(f"  {k}: {v}")
