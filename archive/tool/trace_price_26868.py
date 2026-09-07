# -*- coding: utf-8 -*-
"""實證 26868(+49加購型) 的 price 是怎麼被抓成 95，而不是 descPrice 的 144。
用 scan 線現役解析器 parse_step2 跑在真實存檔的 promo/step_2 HTML 上。
結論應顯示：desc 文本的 L1『=NT$95』先命中→ price=95；L0 descPrice($144) 因文本已命中而從未被使用。
"""
import re
import sys
from pathlib import Path

REPO = Path(r"D:\Desktop\work\project\20260903_PizzaHut-Coupon-Scraper")
sys.path.insert(0, str(REPO))
from script.scan.parse_step2 import (
    _FIXED_PRICE_PATTERNS,
    _VARIABLE_PRICE_PATTERNS,
    _HTML_PRICE_PATTERNS,
    _first_amount,
    parse_step2,
    extract_html_price,
)

FP = REPO / ".scratch" / "ph-orderflow-probe" / "cno-26868.html"
html = FP.read_text(encoding="utf-8", errors="ignore")
print("檔:", FP.name, "len", len(html))

# 1) 頁面結構化 L0：descPrice 在不在
hp = extract_html_price(html)
print("\n[L0 結構化 HTML] descPrice/套餐價格 命中:", hp)

# 2) og:desc 文本 + 逐樣式看哪個先命中
m = re.search(r'property="og:description" content="([^"]+)"', html)
og = m.group(1) if m else ""
print("\nog:desc 前 160 字:\n ", og[:160])
print("\n[逐樣式命中]")
for name, pats in (("L1 文本固定價", _FIXED_PRICE_PATTERNS),
                   ("L2 變價起價", _VARIABLE_PRICE_PATTERNS)):
    for p in pats:
        mm = re.search(p, og)
        print(f"  {name}: {p!r} -> {mm.group(1) if mm else '未命中'}")

# 3) parse_step2 實際輸出（現役解析器行為）
out = parse_step2(html, "26868")
print("\n[parse_step2 實際輸出] price =", out["price"], "| msrp =", out["msrp"])
print("  (頁面 descPrice 為 144，卻輸出 95 → L0 被文本先命中而忽略)")
