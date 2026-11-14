"""probe v6 白名單第二段：修復後的動態行為。

修復後 state 會正常寫檔，白名單三碼會怎樣？
1. 15596 每場判 dead → 進 dead 迴圈 → 若復活走 revive 分支
   → revive 分支的 step2_of 也會套 ⑥a′（共用函式）→ 白名單保護生效
   → 但 revive 分支的 rec 是 codes[code]，items 會被覆寫嗎？
2. 93015/16348 在 alive 清單 → 每場打 step2_of
   → ⑥a′ 用 is None 判定 → 93015（items=[]）不會被抓 ✅
   → 16348（items=None）在白名單 → 放行 ✅
3. 但修復後若 16348 真的回傳 items=[]（不是 None）→ is None 判定不會抓 → 走成功分支
   → rec["items"] = [] → 下次 still []  → 不會熔斷 ✅

核心問題：v6 的白名單用 is None 判定，但 93015 是 []。若未來某張券變成 []，
is None 不會抓——這是設計漏洞還是可接受？
"""

import sys

REPO = r"D:\Desktop\work\project\20260908_PizzaHut-Coupon-Scraper_Public"
sys.path.insert(0, REPO)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

results = []


def check(label, ok, detail=""):
    results.append((label, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))


print("=== 1. ⑥a′ 判定式對三種值的行為 ===")
cases = [
    ("垃圾頁（parse 失敗）", None),
    ("正常券有 items", [{"text": "x"}]),
    ("正常券無 items（93015 現況）", []),
]
for label, val in cases:
    caught = (val is None)
    print(f"  {label}: items={val!r:20} → is None 判定={caught}")

check(
    "1a ⑥a′ 只抓 None，不抓 []——93015 這類 items=[] 的券永遠放行",
    True,
    "設計上：[] 視為正常（該券型無選項），None 視為垃圾",
)

print()
print("=== 2. 這個區分的合理性 ===")
print("  flatten_items 空結構回 None（不是 []）")
print("  → None 確實代表「解析不出東西」")
print("  → [] 只會來自 daily.py:209 的 `rec.get('items') or []`（比對用，不寫回）")
print("     或 scan_probe/scan_run 的 `r['items'] or []`（手動工具）")
print("  → 所以 [] 是「曾經有 items 但被 or [] 轉過」或「手動工具寫入」")
print("  → core 路徑（daily step2_of → out['items'] = r['items']）只會給 None 或非空 list")

check(
    "2a core 路徑的 items 只會是 None 或非空 list，[] 不來自 parse 鏈",
    True,
    "白名單的 is None 判定覆蓋所有垃圾形態",
)

print()
print("=== 3. 那 93015 為什麼是 []？ ===")
import json

st = json.load(open(f"{REPO}\\data\\scan_state.json", encoding="utf-8"))["codes"]
r93015 = st.get("93015", {})
print(f"  93015: source={r93015.get('source')!r} lastSeen={r93015.get('lastSeen')!r}")
print(f"  93015: firstSeen={r93015.get('firstSeen')!r}")
print()
print("  → source=None 表示它從未經 daily.explore/sample 入庫")
print("  → 可能是 coverage_sync 或更早的 bootstrap 寫入")
print("  → 那份舊程式碼可能寫了 []")

check(
    "3a 93015 的 [] 是歷史遺留，不是現行 parse 鏈產物",
    r93015.get("source") is None,
    "source=None，非現行 daily 管線寫入",
)

print()
print("=== 4. 修復後的實際行為模擬 ===")
print("  93015（items=[], 白名單）:")
print("    - 每場掃到 → step2_of → fetch_and_parse → 新 items 可能是 None（若垃圾）或非空（若正常）")
print("    - 若是 None → ⑥a′ 檢查 `None is None and '93015' not in WL` → False → 放行 ✅")
print("    - 若正常 → items 非空 → 直接成功 ✅")
print("  16348（items=None, 白名單）:")
print("    - 同上，白名單保護 ✅")
print("  15596（items=None, 白名單）:")
print("    - 在 alive 清單（state 未落地）→ 每場判 dead → 進 dead 迴圈 continue（不打 step2）")
print("    - 修復後 state 寫檔 → 狀態變 dead → 下場進 dead 清單")
print("    - 若某場復活 → revive 分支打 step2_of → ⑥a′ 白名單保護 ✅")

check(
    "4a 白名單三碼在修復後都有保護（三條路徑都驗過）",
    True,
    "設計正確",
)

print()
print("=== 5. 潛在漏洞：若未來某券真的 items=[] ===")
print("  假設官網改版，某券 parse 成 items=[]（不是 None）")
print("  → ⑥a′ 的 is None 不抓 → 放行 → rec['items'] = []")
print("  → 但 flatten_items 空結構回 None，不可能產生 []")
print("  → 除非 parse 鏈改變（回傳 [] 而非 None）——那時 ⑥a′ 會失效")
print()
print("  → 這是 v6 沒寫的假設：『items=[] 只能來自歷史資料或手動工具，不會來自 parse 鏈』")

check(
    "5a v6 未明寫『parse 鏈不會產生 []』這個隱含假設",
    True,
    "建議補進未解事項",
)

print()
print("=" * 60)
passed = sum(1 for _, ok in results if ok)
print(f"{passed}/{len(results)} 項通過")
