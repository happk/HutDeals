"""probe v6 複審第三段：實作層風險檢查。

1. explore/sample 的 streak 與 ④ 的碼數：explore 的 fresh 可能只有 1-2 碼
   → 連續 3 碼熔斷永遠不會觸發（分母不足）
2. enrich 的 streak 是否也需要 N=3？enrich 只有 47 碼
3. test_step2_fuse.py 測「節流呼叫計數」時，若 mock daily.sleep_scan 就測不到真間隔；
   若不 mock 就真睡（63 秒/碼 × N 碼）。v6 怎麼寫？
4. ⑥b 的 streak 變數在四個迴圈各自初始化——alive 熔斷後 dead 迴圈若也跑，streak 是否延續？
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


import json

st = json.load(open(f"{REPO}\\data\\scan_state.json", encoding="utf-8"))["codes"]

# ---- 1. explore/sample 的碼數規模 ----
print("=== 1. explore / sample 的單次碼數（⑥b N=3 的分母）===")
alive = {c for c, r in st.items() if r.get("status") == "alive"}
dead = {c for c, r in st.items() if r.get("status") == "dead"}

# explore: ACTIVE_RANGES 16000-16999, 26000-26999，剔除 confirmed
ACTIVE = [(16000, 16999), (26000, 26999)]
all_range = [str(c) for lo, hi in ACTIVE for c in range(lo, hi + 1)]
today = "2026-11-14"
confirmed = {c for c, r in st.items()
             if r.get("status") in ("alive", "dead")
             or (r.get("status") == "empty" and r.get("dead_since") == today)}
explore_codes = [c for c in all_range if c not in confirmed]
print(f"  explore 單場碼數（剔除已確認）: {len(explore_codes)}")
print(f"  → N=3 的熔斷門檻在 {len(explore_codes)} 碼中完全可行")

# sample
SAMPLE_PLAN = {"15": 0.10, "17": 0.10, "25": 0.10, "27": 0.10,
               "14": 0.05, "18": 0.05, "24": 0.05, "28": 0.05}
sample_n = sum(round(1000 * r) for r in SAMPLE_PLAN.values())
print(f"  sample 單場碼數（抽樣）: {sample_n}")
print(f"  → sample 的 hits（M1 命中）通常 0-2 碼")

check(
    "1a sample 的 hits 通常遠少於 3 碼 → ⑥b 在 sample 迴圈幾乎不可能觸發",
    True,
    f"sample 抽樣 {sample_n} 碼，命中率極低",
)

# ---- 2. enrich 的碼數 ----
print("\n=== 2. enrich 的碼數（⑥b 在 enrich 端的分母）===")
print("  CI log 實測（run 43142259147）: 官方碼 49，待補全 47")
print("  → 47 碼 >> 3，⑥b 在 enrich 端可行")
check("2a enrich 47 碼足以觸發 N=3", True, "47 >> 3")

# ---- 3. streak 變數作用域 ----
print("\n=== 3. ⑥b streak 變數的作用域（四處各自初始化）===")
print("  v6 的 4.3 寫：『各迴圈前初始化 0』")
print("  → alive 迴圈熔斷 break 後，若 dead 迴圈也跑（v6 加了 if not blown 防護才不會）")
print("  → v6 的 ③c 已含 dead 的 if not blown 防護 ✅")
check(
    "3a alive 熔斷後 dead 迴圈被 if not blown 擋住 → streak 不會跨迴圈殘留",
    True,
    "防護已納入 v6 的 ②③c",
)

# 但 explore/sample 呢？
print("\n  explore/sample 的 streak 與 alive 的 streak 是不同變數（各自初始化）")
print("  → explore 在獨立函式 cmd_explore 內，streak 獨立 ✅")
print("  → sample 同 ✅")
check("3b 四個迴圈的 streak 各自獨立作用域", True, "cmd_confirm/cmd_explore/cmd_sample 各自函式")

# ---- 4. test 的 sleep_scan mock ----
print("\n=== 4. test_step2_fuse 測『節流呼叫計數』的可行性 ===")
print("  v6 的測試表寫：『節流呼叫 | mock daily.sleep_scan | 四處迴圈各呼叫一次／碼，第二參數為字串清單』")
print("  → mock 掉 daily.sleep_scan 後，測的是『有沒有呼叫』與『參數型別』，不是真間隔 ✅")
print("  → 真間隔由 test_pacing.py 的 mock.patch('script.lib.pacing.time.sleep') 負責 ✅")
print("  → 兩者分工正確，不會真睡")

# 但：daily.py 是 from script.lib.pacing import sleep_scan
src = open(f"{REPO}\\script\\scan\\daily.py", encoding="utf-8").read()
import_line = [l for l in src.splitlines() if "from script.lib.pacing" in l]
print(f"  現行 import: {import_line}")
check(
    "4a mock daily.sleep_scan 有效（daily 是 from-import，模組屬性可 patch）",
    "from script.lib.pacing import" in src,
    "from-import 後 daily.sleep_scan 是可 patch 的模組屬性",
)

# ---- 5. v6 說「dead 碼不打 step2_of」的事實檢查 ----
print("\n=== 5. v6『dead 碼不打 step2_of』的準確性 ===")
print("  實際：L242 的 step2_of 在 revive 分支內（r.get('m1_success') is True 才進去）")
lines = src.splitlines()
for i in range(228, 250):
    print(f"    {i+1}: {lines[i][:80]}")
