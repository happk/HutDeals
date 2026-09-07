# -*- coding: utf-8 -*-
"""驗證跨卡誤抓修正後：scan_state 中「疑似飲料卻加價」的筆數應大幅下降。
重抓前 172 筆 → 修正後應趨近 0(真加價飲料如「加價升級大杯」除外)。
"""
import json
import re
from pathlib import Path

REPO = Path(r"D:\Desktop\work\project\20260903_PizzaHut-Coupon-Scraper")
state = json.loads((REPO / "data" / "scan_state.json").read_text(encoding="utf-8"))
codes = state["codes"]

drink_like_paid = []
for code, rec in codes.items():
    for it in rec.get("items") or []:
        g = it.get("group")
        pa = it.get("priceAdd", 0) or 0
        if g in ("second", "main") and pa > 0 and re.search(
                r"可樂|七喜|雪碧|汽水|紅茶|綠茶|咖啡|玉米濃湯|濃湯|果汁", it.get("text", "")):
            drink_like_paid.append((code, g, it.get("groupIdx"), it.get("text"), pa))

print(f"疑似飲料卻加價(誤抓殘留): {len(drink_like_paid)}")
for code, g, gi, text, pa in drink_like_paid[:15]:
    print(f"  {code} {g}{gi} | {text[:24]} priceAdd={pa}")
