# -*- coding: utf-8 -*-
"""調查：coupons.js 中「副食/飲料(second) 組」在卡片預覽的顯示現況。
看 second 組候選的 priceAdd 分佈 —— 若候選全 >0，MealItems compact 只顯示 +0 前4 → 該組無選項。
"""
import json
import re
from pathlib import Path

REPO = Path(r"D:\Desktop\work\project\20260903_PizzaHut-Coupon-Scraper")
txt = (REPO / "public" / "coupons.js").read_text(encoding="utf-8")
obj = json.loads(re.search(r"window\.HUTDEALS_COUPONS\s*=\s*(\{.*?\});?\s*$", txt, re.S).group(1))
lst = obj["coupon_list"]

for code in ("16010", "16013", "26701", "26880", "16051"):
    c = next((x for x in lst if x.get("code") == code), None)
    if not c:
        print(f"== {code} 缺"); continue
    print(f"\n== {code} {c.get('name')[:20]} | items#={len(c.get('items') or [])}")
    # 依組分
    from collections import defaultdict
    grp = defaultdict(list)
    for it in (c.get("items") or []):
        grp[(it.get("group"), it.get("groupIdx"))].append(it)
    for (g, gi), its in grp.items():
        free = [i for i in its if i.get("priceAdd") == 0]
        paid = [i for i in its if i.get("priceAdd", 0) > 0]
        cats = {i.get("cat") for i in its}
        print(f"  {g}{gi} cat={cats} 候選{len(its)} (+0:{len(free)} / 加價:{len(paid)})")
        # 印前幾候選名稱+加價
        for i in its[:3]:
            pa = i.get("priceAdd")
            print(f"     - {i.get('text')[:22]} priceAdd={pa}")

# 全站：second 組有「全加價(無+0)」的券數量（這類卡片預覽 second 會空白）
print("\n===== 全站 second 組全加價(卡片會無選項) 統計 =====")
count_nozero = count_total = 0
ex = []
for c in lst:
    seen = set()
    for it in (c.get("items") or []):
        if it.get("group") != "second":
            continue
        k = (c.get("code"), it.get("groupIdx"))
        if k in seen:
            continue
        seen.add(k)
        count_total += 1
        # 該組候選
        gits = [x for x in (c.get("items") or [])
                if x.get("group") == "second" and x.get("groupIdx") == it.get("groupIdx")]
        if gits and all((x.get("priceAdd", 0) or 0) > 0 for x in gits):
            count_nozero += 1
            if len(ex) < 6:
                ex.append(c.get("code"))
print(f"second 組總數 {count_total}，其中全加價(卡片預覽無選項) {count_nozero}")
print("例:", ex)
