# -*- coding: utf-8 -*-
"""唯讀：以「項＝前端一個選項組(group+groupIdx)」的定義，檢查現行分類哪裡會出錯。

用法：python exp_prob/probe_item_units.py "D:/.../20260908_..._Public"
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
            "咖啡", "濃湯", "果汁", "奶茶", "果茶", "氣泡", "飲")
PIZZA_KW = ("比薩", "披薩")
PASTA_KW = ("義大利麵", "筆管麵", "千層麵", "飯")


def is_drink(n):
    return any(k in (n or "") for k in DRINK_KW)


def is_pizza(n):
    return any(k in (n or "") for k in PIZZA_KW)


def is_pasta(n):
    return any(k in (n or "") for k in PASTA_KW)


# 收集所有「項」：group+groupIdx → (組型, 組標題, 品名清單, 現行 cat 集合)
units = []
for code, rec in codes.items():
    g = defaultdict(list)
    for it in rec.get("items") or []:
        g[(it.get("group"), it.get("groupIdx"))].append(it)
    for (gtype, gidx), items in g.items():
        subj = next((i.get("groupTitle") for i in items if i.get("groupTitle")), None)
        units.append({
            "code": code, "gtype": gtype, "gidx": gidx, "subj": subj,
            "names": [i.get("text") or "" for i in items],
            "cats": sorted({i.get("cat") for i in items if i.get("cat")}),
        })

print(f"總項數（group+groupIdx）: {len(units)}")
print("組型 × 現行 cat 集合（前 15）：")
mx = Counter((u["gtype"], tuple(u["cats"])) for u in units)
for (gt, cats), n in mx.most_common(15):
    print(f"  {str(gt):<7} {list(cats)}  ×{n}")

print("\n=== main 項：組標題判不出尺寸/麵飯/副食（現行 fallback → 比薩）===")
n = 0
for u in units:
    if u["gtype"] != "main":
        continue
    if u["cats"] == ["比薩"]:
        n += 1
        if n <= 12:
            print(f"  {u['code']} main{u['gidx']} subj={u['subj']!r}")
            print(f"      品名={u['names'][:5]}")
print(f"  共 {n} 項")

print("\n=== main 項但品名含飲料字樣（現行會標成比薩尺寸）===")
n = 0
for u in units:
    if u["gtype"] == "main" and any(is_drink(x) for x in u["names"]):
        n += 1
        if n <= 8:
            print(f"  {u['code']} main{u['gidx']} subj={u['subj']!r} cats={u['cats']} 品名={u['names'][:4]}")
print(f"  共 {n} 項")

print("\n=== second 項但品名是比薩/麵飯（現行會標副食/飲料）===")
n = 0
for u in units:
    if u["gtype"] == "second" and any(is_pizza(x) or is_pasta(x) for x in u["names"]):
        n += 1
        if n <= 8:
            print(f"  {u['code']} second{u['gidx']} subj={u['subj']!r} cats={u['cats']} 品名={u['names'][:4]}")
print(f"  共 {n} 項")

print("\n=== 組標題為 None 的項（現行 main→比薩、second→副食/飲料）===")
n = 0
for u in units:
    if not u["subj"]:
        n += 1
        if n <= 10:
            print(f"  {u['code']} {u['gtype']}{u['gidx']} cats={u['cats']} 品名={u['names'][:4]}")
print(f"  共 {n} 項")
