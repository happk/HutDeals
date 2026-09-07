# -*- coding: utf-8 -*-
"""評估 parse_orderflow 跨卡誤抓 bug 的影響範圍：多少 second/main 卡的 priceAdd 可能是誤抓。

誤抓特徵：候選名以 pdName data-name 標(非 pdpop-name/pd_name)，_card_name_price_raw
抓不到 name → fallback 整卡找價 → 可能誤抓他卡。
但 scan_state 已存「解析後的 items」，無法直接重算；只能以「疑似誤抓」間接估計：
  - second 候選 name 是「純飲料/點心」卻 priceAdd>0（飲料通常 +0）→ 高機率誤抓
  - 或對照選單版 HTML 才有真相。先看 scan_state 現況分佈。
"""
import json
import re
from collections import Counter
from pathlib import Path

REPO = Path(r"D:\Desktop\work\project\20260903_PizzaHut-Coupon-Scraper")
state = json.loads((REPO / "data" / "scan_state.json").read_text(encoding="utf-8"))
codes = state["codes"]

# 全站 second/main 候選 priceAdd>0 比例
stat = Counter()
drink_like_paid = []  # 疑似飲料卻加價(高機率誤抓)
for code, rec in codes.items():
    for it in rec.get("items") or []:
        g = it.get("group")
        pa = it.get("priceAdd", 0) or 0
        stat[(g, "total")] += 1
        if pa > 0:
            stat[(g, "paid")] += 1
        # 疑似飲料(名稱含可樂/七喜/紅茶/綠茶/咖啡/濃湯/雪碧/汽水/果汁)卻加價
        if g in ("second", "main") and pa > 0 and re.search(
                r"可樂|七喜|雪碧|汽水|紅茶|綠茶|咖啡|玉米濃湯|濃湯|果汁", it.get("text", "")):
            drink_like_paid.append((code, g, it.get("groupIdx"), it.get("text"), pa))

print("候選 priceAdd 統計:", dict(stat))
print(f"\n疑似飲料卻加價(高機率誤抓): {len(drink_like_paid)}")
for code, g, gi, text, pa in drink_like_paid[:15]:
    print(f"  {code} {g}{gi} | {text[:24]} priceAdd={pa}")
