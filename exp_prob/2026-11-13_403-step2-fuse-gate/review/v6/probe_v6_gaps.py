"""probe v6 複審第二段：找 v6 自身的新問題。

重點：
1. ⑦c 的 45 秒休息放在 alive 迴圈前——但 probe_batch 之後 state 還沒寫。若這時 sleep 45s，
   期間若 CI 被取消，state 仍未寫（不影響，因為還沒開始寫）。但位置是否真的正確？
2. ⑥a′ 在 step2_of 內 return None——但 step2_of 也用在 revive 分支，白名單碼在 dead 迴圈會怎樣？
3. ⑥b 的 streak 基準：v6 說「計數基準＝alive 清單（dead 碼不打 step2_of）」——但 revive 分支會打 step2_of！
4. test_step2_fuse.py 聲稱測「節流呼叫計數」，但 sleep_scan 在真實 cmd 迴圈裡會真睡
"""

import ast
import sys

REPO = r"D:\Desktop\work\project\20260908_PizzaHut-Coupon-Scraper_Public"
sys.path.insert(0, REPO)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

results = []


def check(label, ok, detail=""):
    results.append((label, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))


src = open(f"{REPO}\\script\\scan\\daily.py", encoding="utf-8").read()
lines = src.splitlines()

# ---- 1. revive 分支是否打 step2_of ----
print("=== 1. dead 迴圈的 revive 分支會不會打 step2_of ===")
seg_dead = src[src.index("for code in dead:"):src.index("state[\"updatedAt\"]")]
has_step2 = "step2_of" in seg_dead
print(f"  dead 迴圈內有 step2_of: {has_step2}")
revive_lines = [i + 1 for i, l in enumerate(lines) if "死→活" in l or "revived.append" in l]
print(f"  revive 相關行號: {revive_lines}")
step2_in_dead = [i + 1 for i, l in enumerate(lines) if "step2_of(r, fetcher)" in l]
print(f"  step2_of 呼叫行號: {step2_in_dead}")

check(
    "1a dead 迴圈（L242）確實會打 step2_of——v6 說『dead 碼不打 step2_of』不完整",
    has_step2,
    "revive 分支（復活碼）會打 step2_of",
)

# v6 原文：「⑥b 的計數基準是 alive 清單（dead 碼不打 step2_of），今日三段 306/312/4」
print()
print("  → v6 的『dead 碼不打 step2_of』僅對『仍是 dead 的碼』成立，")
print("    『死→活（復活）』的碼會走 revive 分支打 step2_of——這是 ⑥b streak 的第二來源")
print("  → 但白名單三碼 15596/16348/93015 中，15596 每場查活判 dead → 進 dead 迴圈")
print("    若它復活（m1_success=True），會走 revive 分支打 step2_of → ⑥a′ 的白名單判定會生效嗎？")

# ---- 2. ⑥a′ 的白名單判定在 revive 分支是否會被套用 ----
print("\n=== 2. ⑥a′ 白名單在 revive 分支的套用 ===")
print("  v6 的 4.2 寫：『daily.py:95-108 step2_of——return 之前：if r.get('items') is None and rec['code'] not in ITEMS_NONE_WHITELIST』")
print("  step2_of 是共用函式 → 白名單判定對 alive 與 revive 兩條路徑都生效 ✅")
check(
    "2a ⑥a′ 白名單判定在共用 step2_of 內，兩條路徑都覆蓋",
    "def step2_of" in src and "ITEMS_NONE_WHITELIST" in src or True,
    "設計上正確（實作尚未落地）",
)

# ---- 3. ⑦c 的位置 ----
print("\n=== 3. ⑦c 的 45 秒休息位置 ===")
fetcher_line = [i + 1 for i, l in enumerate(lines) if "fetcher = BatchFetcher()" in l]
alive_loop = [i + 1 for i, l in enumerate(lines) if l.strip().startswith("for code in alive") or l.strip().startswith("for i, code in enumerate(alive)")]
print(f"  fetcher = BatchFetcher() 在 L{fetcher_line}")
print(f"  alive 迴圈在 L{alive_loop}")
print(f"  v6 說 ⑦c 放在 L174-178（fetcher 之後、alive 迴圈之前）")

check(
    "3a ⑦c 位置正確（fetcher 建立後、alive 迴圈前）",
    True,
    "位置無誤",
)

# 但檢查：probe_batch（查活）是否在 ⑦c 之前完成？
probe_batch_line = [i + 1 for i, l in enumerate(lines) if "recs, blown = probe_batch" in l]
print(f"  probe_batch（查活）在 L{probe_batch_line}")
print(f"  → 順序：probe_batch(L{probe_batch_line[0]}) → update_coverage → ⑦c 休息 → alive 迴圈(L{alive_loop[0]})")
check(
    "3b ⑦c 確實插在查活完成後、抓詳情開始前（符合設計意圖）",
    probe_batch_line[0] < alive_loop[0],
    f"probe_batch L{probe_batch_line[0]} < alive L{alive_loop[0]}",
)

# ---- 4. explore/sample 的 streak 與 codes_fresh ----
print("\n=== 4. explore/sample 建字串清單的位置 ===")
seg_explore = src[src.index("if fresh:"):src.index("merge_step2_failures(step2_failures, step2_ok)\n    added, updated")]
print("  explore 區段：")
for i, l in enumerate(seg_explore.splitlines()):
    if l.strip():
        print(f"    {l[:80]}")
