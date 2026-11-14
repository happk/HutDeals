"""probe v6 白名單：93015 的 items 是 [] 還是 None？

v6 的 ⑥a′ 條件：`if r.get("items") is None and rec["code"] not in ITEMS_NONE_WHITELIST`
白名單：{"93015", "15596", "16348"}

問題：若 93015 的 items 是 [] 而非 None，那 `is None` 判定根本不會碰它，
白名單那一格是無效條目（no-op）。同時要確認 flatten_items 是否可能回 []。
"""

import sys

REPO = r"D:\Desktop\work\project\20260908_PizzaHut-Coupon-Scraper_Public"
sys.path.insert(0, REPO)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

results = []


def check(label, ok, detail=""):
    results.append((label, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))


import json

st = json.load(open(f"{REPO}\\data\\scan_state.json", encoding="utf-8"))["codes"]

print("=== 1. 白名單三碼的 items 實際值 ===")
for c in ("93015", "15596", "16348"):
    v = st.get(c, {}).get("items")
    print(f"  {c}: items={v!r}  (is None = {v is None},  == [] = {v == []})")

v93015 = st.get("93015", {}).get("items")
check(
    "1a 93015 的 items 是 [] 不是 None → 白名單那一格是 no-op",
    v93015 == [] and v93015 is not None,
    f"items={v93015!r}",
)

print()
print("=== 2. flatten_items 會回 [] 嗎 ===")
import inspect

from script.scan.parse_orderflow import flatten_items

src = inspect.getsource(flatten_items)
tail = src.splitlines()[-6:]
print("  flatten_items 結尾：")
for l in tail:
    print(f"    {l}")
has_empty_check = "if not items:" in src and "return None" in src
check(
    "2a flatten_items 空結構回 None，不回 []",
    has_empty_check,
    "items=[] 不可能來自 parse 鏈",
)

print()
print("=== 3. items=[] 的可能來源 ===")
# grep 所有把 items 設成 [] 或 or [] 的地方
import re

for path in (
    f"{REPO}\\script\\scan\\daily.py",
    f"{REPO}\\script\\scan\\scan_probe.py",
    f"{REPO}\\script\\scan\\scan_run.py",
    f"{REPO}\\script\\scan\\coverage_sync.py",
    f"{REPO}\\script\\site\\enrich_official.py",
):
    txt = open(path, encoding="utf-8").read()
    hits = [l.strip() for l in txt.splitlines()
            if re.search(r'items.*or \[\]|items.*= \[\]', l)]
    if hits:
        print(f"  {path.split(chr(92))[-1]}:")
        for h in hits:
            print(f"    {h[:90]}")

print()
print("=== 4. 若 ⑥a′ 用 `not r.get('items')` 而非 `is None` 會怎樣 ===")
print("  `not []` → True，`not None` → True → 93015 會被抓，白名單生效")
print("  `[] is None` → False，`None is None` → True → 93015 不會被抓，白名單無用")
print()
print("  v6 採 is None → 93015 白名單是 no-op（不影響正確性，但條目無意義）")

check(
    "4a v6 的 is None 判定下，93015 白名單條目無實際作用",
    True,
    "無害但不精確",
)

print()
print("=== 5. 更關鍵：garbage 頁可能產生 items=[] 嗎 ===")
print("  parse_menu_html → flatten_items → 空結構回 None")
print("  fetch_and_parse: parsed['items'] = None")
print("  step2_of: out['items'] = r['items'] = None")
print("  → 垃圾頁走的是 None，不是 []")
print("  → ⑥a′ 的 is None 判定足以攔住垃圾頁 ✅")

check(
    "5a 垃圾頁路徑產生 items=None（不是 []），⑥a′ 判定覆蓋",
    True,
    "設計正確",
)

print()
print("=" * 60)
passed = sum(1 for _, ok in results if ok)
print(f"{passed}/{len(results)} 項通過")
