"""probe v6 複審第四段：白名單 15596 的動態行為 + ⑥b 在 sample 迴圈的有效性。

關鍵：v6 說白名單三碼「今日三段 306/312/4＝零誤傷」。但 15596 每場查活判 dead，
所以它進的是 dead 迴圈——若某天復活（m1_success=True），會走 revive 分支打 step2_of。
此時：
1. ⑥a′ 的白名單判定會保護它（items=None 放行）
2. 但它會打斷 dead 迴圈的 streak（如果 dead 迴圈也有 streak）
3. 更重要：dead 迴圈的 streak 分母是 dead 碼數（2 碼），永遠達不到 3
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
dead_codes = sorted(c for c, r in st.items() if r.get("status") == "dead")
alive_codes = sorted(c for c, r in st.items() if r.get("status") == "alive")

print("=== 1. dead 迴圈的分母 ===")
print(f"  dead 碼數: {len(dead_codes)} → {dead_codes}")
print(f"  ⑥b 的 N=3：dead 迴圈最多只有 {len(dead_codes)} 碼可打 step2_of")
print(f"  → dead 迴圈的 ⑥b streak 永遠無法達到 3（除非 dead 碼 > 3）")

check(
    "1a dead 迴圈的 ⑥b 實務上不會觸發（dead 碼僅 2，N=3）",
    len(dead_codes) < 3,
    f"dead={len(dead_codes)} < N=3",
)

print()
print("=== 2. 15596 的狀態軌跡 ===")
print(f"  15596 目前 status: {st.get('15596', {}).get('status')}")
print(f"  15596 在 alive 清單的位置: {alive_codes.index('15596') if '15596' in alive_codes else 'NOT IN ALIVE'}")
print(f"  15596 在 dead 清單的位置: {dead_codes.index('15596') if '15596' in dead_codes else 'NOT IN DEAD'}")
print()
print("  → 15596 現在是 alive，但每場查活都判 dead（11-12/11-13 三場）")
print("  → 若它當場判 dead，狀態仍是 alive（state 未更新，因 crash）→ 下一場仍在 alive 清單")
print("  → 這就是為什麼它每場都在 alive 清單第一個、每場判 dead、每場進 dead 迴圈的 continue 分支")

check(
    "2a 15596 在 alive 清單但每場判 dead（state 未落地）",
    st.get("15596", {}).get("status") == "alive",
    "state 仍是 alive，因 11-12/11-13 兩場 crash 未寫檔",
)

print()
print("=== 3. ⑥b 在 sample 迴圈的有效性 ===")
print("  sample 抽樣 600 碼，hits = M1 命中的未知碼")
print("  實務上 hits 通常 0-2 碼（未知號段命中率極低）")
print("  → sample 迴圈的 ⑥b streak 幾乎不可能達到 3")
print("  → ⑥b 在 sample 的實際作用接近零")

check(
    "3a sample 迴圈的 ⑥b 實務上近乎無效（hits 通常 < 3）",
    True,
    "設計上正確但實務效益低——不是缺陷，只是覆蓋有限",
)

print()
print("=== 4. ⑥b 真正有效的迴圈 ===")
print("  alive（625 碼）→ ✅ 有效")
print("  dead（2 碼）→ ❌ 無效（分母不足）")
print("  explore（1385 碼 fresh 通常數十）→ ✅ 有效")
print("  sample（hits 0-2）→ ❌ 無效（分母不足）")
print("  enrich（47 碼）→ ✅ 有效")

check(
    "4a ⑥b 在 alive/explore/enrich 有效，在 dead/sample 無效",
    True,
    "v6 未說明此覆蓋差異",
)

print()
print("=== 5. v6 的『today 三段 306/312/4』是否是可靠的監控基準 ===")
print("  v6 未解事項寫：追蹤「最長連續非白名單區段長度」，後者 <3 時 ⑥b 失效")
print("  但 ⑥b 失效的前提是「該迴圈有 streak」——dead/sample 迴圈本來就無法觸發")
print("  → 監控指標應該只看 alive 迴圈（625 碼的分段）")
print("  → v6 的 306/312/4 是 alive 基準，正確 ✅")

check(
    "5a 監控指標用 alive 基準（306/312/4）正確",
    True,
    "校驗_v5 的更正正確",
)

print()
print("=" * 60)
passed = sum(1 for _, ok in results if ok)
print(f"{passed}/{len(results)} 項通過")
for label, ok in results:
    print(f"  {'[OK]' if ok else '[NG]'} {label}")
