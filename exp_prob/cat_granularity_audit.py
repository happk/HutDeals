# -*- coding: utf-8 -*-
"""唯讀查證 5：cat 分類粒度審查。

問題：`cat` 目前是「組層級」算一次、複製到組內每個 item
（script/scan/parse_orderflow.py:275-286 + :336），不是逐項分類。
本腳本用實際資料檢查：
  A. second 組的組標題 / 組內項目 / 現行 cat 對照
  B. 逐項獨立分類 vs 現行 cat 的落差（同組混類 = 模型問題）
  C. 16166 逐項應該長什麼樣
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent

DRINK_KW = ("可樂", "七喜", "雪碧", "汽水", "紅茶", "綠茶", "烏龍茶", "咖啡",
            "玉米濃湯", "濃湯", "果汁", "柚茶", "奶茶", "果茶", "氣泡", "水")
NOT_DRINK_KW = ("茶碗蒸", "雞翅", "雞塊", "薯", "QQ球", "腿排", "煎餅", "湯餃")


def load(path):
    src = path.read_text(encoding="utf-8")
    m = re.search(r"window\.HUTDEALS_\w+\s*=\s*(\{.*\})\s*;?\s*$", src, re.S)
    return json.loads(m.group(1))


def looks_drink(name: str) -> bool:
    if any(k in name for k in NOT_DRINK_KW):
        return False
    return any(k in name for k in DRINK_KW)


def looks_pizza(name: str) -> bool:
    return any(k in name for k in ("比薩", "披薩"))


pub = load(ROOT / "public" / "coupons.js")
lst = pub["coupon_list"]

# ---------- A. second 組：組標題 / 組內項目 / cat ----------
print("=" * 70)
print("A. second 組（副食/飲料）實際樣貌 — 依組標題彙總")
buckets = defaultdict(Counter)
for c in lst:
    groups = defaultdict(list)
    for it in c.get("items") or []:
        groups[(it.get("group"), it.get("groupIdx"))].append(it)
    for key, items in groups.items():
        if key[0] != "second":
            continue
        title = next((i.get("groupTitle") for i in items if i.get("groupTitle")), None)
        cat = items[0].get("cat")
        names = tuple(sorted({i.get("text") for i in items}))
        buckets[(title, cat)][names] += 1

for (title, cat), combos in sorted(buckets.items(), key=lambda kv: str(kv[0])):
    print(f"\n  組標題={title!r} 現行cat={cat}")
    for names, n in combos.most_common(6):
        print(f"    ×{n}  {', '.join(names[:6])}{' …' if len(names) > 6 else ''}")

# ---------- B. 同組混類（逐項獨立分類 vs 組 cat） ----------
print("\n" + "=" * 70)
print("B. 同一個 second 組內「有飲料也有非飲料」→ 現行一律同一 cat")
mixed = []
for c in lst:
    groups = defaultdict(list)
    for it in c.get("items") or []:
        groups[(it.get("group"), it.get("groupIdx"))].append(it)
    for (gtype, gidx), items in groups.items():
        if gtype != "second":
            continue
        drinks = [i["text"] for i in items if looks_drink(i["text"])]
        others = [i["text"] for i in items if not looks_drink(i["text"])]
        if drinks and others:
            mixed.append((c["code"], items[0].get("cat"), drinks, others))
print(f"  混類 second 組數: {len(mixed)}（每組內飲料與非飲料並存 → 飲料項被迫掛非飲料 cat）")
for code, cat, drinks, others in mixed[:25]:
    print(f"    {code} cat={cat} 飲料={drinks[:3]} 其他={others[:3]}")

# ---------- B2. 逐項獨立分類 ≠ 現行 cat 的 item 總數 ----------
print("\n" + "=" * 70)
print("B2. 逐項獨立分類與現行 cat 不一致的 item 統計")
mismatch = Counter()
examples = defaultdict(list)
for c in lst:
    for it in c.get("items") or []:
        name, cat = it.get("text") or "", it.get("cat")
        if it.get("group") != "second":
            continue
        want = "飲料" if looks_drink(name) else "副食"
        if cat != want:
            mismatch[f"{cat}→應為{want}"] += 1
            if len(examples[f"{cat}→應為{want}"]) < 8:
                examples[f"{cat}→應為{want}"].append(f"{c['code']}:{name}")
for k, v in mismatch.most_common():
    print(f"  {k}: {v} 筆")
    print(f"     例: {examples[k]}")

# ---------- C. 16166 逐項 ----------
print("\n" + "=" * 70)
print("C. 16166 逐項（現行 cat vs 逐項獨立）")
c = next(x for x in lst if x["code"] == "16166")
groups = defaultdict(list)
for it in c.get("items") or []:
    groups[(it.get("group"), it.get("groupIdx"))].append(it)
for key in sorted(groups, key=lambda k: (k[0], k[1])):
    items = groups[key]
    title = next((i.get("groupTitle") for i in items if i.get("groupTitle")), None)
    print(f"  {key[0]}{key[1]} 組標題={title!r} cat={items[0].get('cat')}")
    for i in items:
        want = "飲料" if looks_drink(i["text"]) else "副食"
        flag = "" if items[0].get("cat") == want else f"   ← 應為 {want}"
        print(f"      {i['text']}{flag}")
