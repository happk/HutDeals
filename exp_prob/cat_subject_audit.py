# -*- coding: utf-8 -*-
"""唯讀查證 6：second 組的官方組標題(groupTitle) vs 現行 cat 的一致性。

發現：second 組的 groupTitle 官方原文就寫了「請選擇1份飲料」/「請選擇1份副食」，
但現行程式只拿 groupTitle 判 main 尺寸，second 一律用 _all_drink(項目名) 推導。
本腳本統計：
  A. second 組標題字樣分布
  B. 標題說飲料、現行 cat 卻不是飲料 的組
  C. 標題說副食、組內卻有飲料項 的組
  D. 各券「逐項獨立分類」後會新增哪些 cat（影響 tags/篩選）
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent

DRINK_KW = ("可樂", "七喜", "雪碧", "汽水", "紅茶", "綠茶", "烏龍茶", "咖啡",
            "玉米濃湯", "濃湯", "果汁", "柚茶", "奶茶", "果茶", "氣泡", "原萃", "水")
NOT_DRINK_KW = ("茶碗蒸", "雞翅", "雞塊", "薯", "QQ球", "腿排", "煎餅", "湯餃", "鱈魚", "杏鮑菇", "起司塔", "樂事")


def looks_drink(name: str) -> bool:
    if any(k in name for k in NOT_DRINK_KW):
        return False
    return any(k in name for k in DRINK_KW)


st = json.load(open(ROOT / "data" / "scan_state.json", encoding="utf-8"))
codes = st["codes"]

# A
print("=" * 70)
print("A. second 組標題字樣分布（scan_state groupTitle）")
subj_counter = Counter()
for code, rec in codes.items():
    for it in rec.get("items") or []:
        if it.get("group") == "second":
            subj_counter[it.get("groupTitle")] += 1
for k, v in subj_counter.most_common(12):
    print(f"  {k!r}: {v} items")

# B / C
print("\n" + "=" * 70)
print("B. 組標題說「飲料」但現行 cat 不是飲料")
b = []
print("\nC. 組標題說「副食」但組內有飲料項（逐項分類後會變成混組）")
c = []
for code, rec in codes.items():
    groups = defaultdict(list)
    for it in rec.get("items") or []:
        if it.get("group") == "second":
            groups[(it.get("group"), it.get("groupIdx"))].append(it)
    for key, items in groups.items():
        subj = next((i.get("groupTitle") or "" for i in items if i.get("groupTitle")), "")
        cat = items[0].get("cat")
        names = [i.get("text") or "" for i in items]
        drinks = [n for n in names if looks_drink(n)]
        if "飲料" in subj and cat != "飲料":
            b.append((code, key[1], subj, cat, names[:5]))
        if "副食" in subj and drinks:
            c.append((code, key[1], subj, cat, drinks[:4], [n for n in names if not looks_drink(n)][:3]))
print(f"  B 組數: {len(b)}")
for x in b[:12]:
    print(f"    {x[0]} second{x[1]} 標題={x[2]!r} cat={x[3]} 項目={x[4]}")
print(f"  C 組數: {len(c)}")
for x in c[:12]:
    print(f"    {x[0]} second{x[1]} 標題={x[2]!r} cat={x[3]} 飲料={x[4]} 其他={x[5]}")

# D
print("\n" + "=" * 70)
print("D. 逐項獨立分類後，每券 cat 集合的變化（只看外部碼）")
gain_drink, changed = [], []
for code, rec in codes.items():
    if rec.get("status") != "alive" or code.startswith("9"):
        continue
    items = rec.get("items") or []
    if not items:
        continue
    old_cats = sorted({i.get("cat") for i in items if i.get("cat")})
    new_cats = set()
    for i in items:
        if i.get("group") == "second":
            new_cats.add("飲料" if looks_drink(i.get("text") or "") else "副食")
        else:
            new_cats.add(i.get("cat") or ("比薩" if i.get("group") == "main" else None))
    new_cats = sorted(x for x in new_cats if x)
    if "飲料" in new_cats and "飲料" not in old_cats:
        gain_drink.append(code)
    if new_cats != old_cats:
        changed.append((code, old_cats, new_cats))
print(f"  逐項分類後新獲得『飲料』cat 的券: {len(gain_drink)}")
print("   ", gain_drink[:30])
print(f"  cat 集合有變的券: {len(changed)}")
for code, o, n in changed[:12]:
    print(f"    {code}: {o} → {n}")
