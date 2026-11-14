r"""probe 2026-11-14：校驗第六輪複審速報（reports/驗收速報_v6_20261114.md）的宣稱。

複審宣稱：
    事實錯誤：v6/修復方法寫「dead 碼不打 step2_of」不完整——L242（dead 迴圈 revive 分支）會打 step2_of；
             正確理由＝各迴圈 streak 獨立累加，且 dead 分母 2 < N=3 不會觸發。
    覆蓋限制一：dead 迴圈 ⑥b 永不觸發（分母 2）。覆蓋限制二：sample ⑥b 近乎無效（hits 0-2）。
    隱含假設：⑥a′ 的 is None 依賴 flatten_items 空結構回 None；93015（items=[]）的白名單條目今天是 no-op。
    其他：explore 潛在碼位 1385、sample 抽樣 600、enrich 47、內部探針數 27 vs 36 不一致。

探針（state 唯讀＋源碼核對＋記憶體模擬；零真實網路、repo 與 data/ 零寫入）：
    A step2_of 呼叫點核對＋L242 所在分支
    B dead 迴圈分母（state dead 碼數）與 ⑥b 可達性
    C sample 抽樣規模（SAMPLE_PLAN 合計）＋歷史 hits 分布（scan-history.md）
    D ⑥a′ 判定對白名單三碼的實際行為＋flatten_items 契約＋[] 來源
    E explore 潛在碼位數（2000－confirmed）
    F 四份補丁的數字與引用核對＋速報內部一致性（27 vs 36）
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from script.scan import daily                          # noqa: E402

_results: list[tuple[str, bool]] = []


def note(label: str, ok: bool) -> None:
    _results.append((label, ok))
    print(f"  => {'[OK]' if ok else '[NG]'} {label}")


# ============ A：step2_of 呼叫點與 L242 分支 ============
print("A. step2_of 呼叫點核對（複審宣稱 [194, 242, 324, 366]，L242 在 dead 迴圈 revive 分支）")
src = (REPO / "script" / "scan" / "daily.py").read_text(encoding="utf-8").splitlines()
sites = [i + 1 for i, l in enumerate(src) if "step2_of(" in l and "def " not in l]
l242_ctx = "\n".join(src[226:243])
in_dead = "for code in dead:" in "\n".join(src[227:231]) and "死→活" in l242_ctx
print(f"  呼叫行號={sites}；L242 前有 dead 迴圈與 revive 標記={in_dead}")
note("A 事實錯誤證實：L242 在 dead 迴圈 revive 分支且會打 step2_of——「dead 碼不打 step2_of」是錯的",
     sites == [194, 242, 324, 366] and in_dead)

# ============ B：dead 迴圈分母與 ⑥b 可達性 ============
print("\nB. dead 迴圈的 ⑥b 分母（複審宣稱 2 < 3 永不觸發）")
state = json.loads((REPO / "data" / "scan_state.json").read_text(encoding="utf-8"))
codes = state.get("codes", {})
dead = sorted(c for c, rr in codes.items() if rr.get("status") == "dead")
alive = sorted(c for c, rr in codes.items() if rr.get("status") == "alive")
print(f"  alive={len(alive)} dead={len(dead)} {dead}")
note("B 覆蓋限制一證實：dead 分母=2 < N=3，該迴圈 ⑥b 永不觸發（且需 revive 才打 step2_of）",
     len(dead) == 2 and len(dead) < daily.DEAD_TO_EMPTY_DAYS is not None and len(dead) < 3)

# ============ C：sample 抽樣規模與歷史 hits ============
print("\nC. sample 的 ⑥b 分母（複審宣稱抽樣 600 碼、hits 通常 0-2）")
plan_total = sum(round(1000 * rate) for rate, _ in daily.SAMPLE_PLAN.values())
hist = (REPO / "data" / "scan-records" / "scan-history.md").read_text(encoding="utf-8")
sample_rows = [l for l in hist.splitlines() if "daily.sample" in l]
hits_hist = []
for l in sample_rows:
    m = re.search(r"未知號段命中 (\d+)", l)
    if m:
        hits_hist.append(int(m.group(1)))
print(f"  SAMPLE_PLAN 合計={plan_total} 碼；歷史 daily.sample 場次={len(hits_hist)}")
if hits_hist:
    print(f"  歷史 hits 分布: {hits_hist}（max={max(hits_hist)}）")
note("C 覆蓋限制二證實：抽樣 600 碼、歷史 hits 全部 < 3——sample 迴圈 ⑥b 達不到門檻",
     plan_total == 600 and bool(hits_hist) and max(hits_hist) < 3)

# ============ D：⑥a′ 對白名單三碼的實際行為 ============
print("\nD. ⑥a′ 的 is None 判定 vs 白名單三碼（複審宣稱 93015 條目今天是 no-op）")
wl = {"93015", "15596", "16348"}
for c in sorted(wl):
    items = codes[c].get("items")
    caught = items is None and c not in wl
    print(f"  {c}: items={items!r} → [] is None 或 None is None 判定抓取={items is None}；"
          f"⑥a′ 實際攔截={caught}")
po = (REPO / "script" / "scan" / "parse_orderflow.py").read_text(encoding="utf-8").splitlines()
contract = po[292].strip() + " | " + po[293].strip()
print(f"  flatten_items 契約（L293-294）: {contract}")
items_eq_none = [c for c in wl if codes[c].get("items") is None]
note("D 隱含假設證實：93015（items=[]）不會被 is None 抓到＝白名單條目今天 no-op；"
     "15596/16348（None）有效；flatten_items 空結構回 None（契約依賴屬實）",
     codes["93015"].get("items") == [] and set(items_eq_none) == {"15596", "16348"}
     and "return None" in contract and "if not items" in contract)

# ============ E：explore 潛在碼位數 ============
print("\nE. explore 分母（複審宣稱 1,385 潛在碼位）")
today = "2026-11-14"
confirmed = {c for c, rr in codes.items()
             if rr.get("status") in ("alive", "dead")
             or (rr.get("status") == "empty" and rr.get("dead_since") == today)}
explore_n = sum(1 for lo, hi in daily.ACTIVE_RANGES for c in range(lo, hi + 1)
                if str(c) not in confirmed)
print(f"  ACTIVE_RANGES 總位數=2000；confirmed={len(confirmed)} → explore={explore_n}")
note("E explore 分母核對：潛在碼位與複審的 1,385 吻合", explore_n == 1385)

# ============ F：補丁數字核對＋速報內部一致性 ============
print("\nF. 四份補丁的數字核對＋速報內部一致性")
print(f"  補丁二覆蓋表數字：alive 625（實 {len(alive)}）、dead 2（實 {len(dead)}）、"
      f"explore 1385（實 {explore_n}）、sample 600（實 {plan_total}）、enrich 47（11-12 CI log 引用）")
exp_src = (Path(__file__).resolve().parent / "reports" / "驗收速報_v6_20261114.md").read_text(encoding="utf-8")
m27 = re.search(r"（(\d+) 項探針、0 失敗）", exp_src)
m36 = re.search(r"合計 (\d+) 項探針", exp_src)
print(f"  速報摘要探針數={m27.group(1) if m27 else '?'}；附錄合計={m36.group(1) if m36 else '?'}")
note("F 補丁數字全部核對吻合；速報內部不一致（摘要 27 vs 附錄 36）——小瑕疵",
     len(alive) == 625 and len(dead) == 2 and explore_n == 1385 and plan_total == 600
     and m27 and m36 and m27.group(1) != m36.group(1))

# ============ 總判定 ============
print("\n=== 總判定 ===")
for label, ok in _results:
    print(f"  {'[OK]' if ok else '[NG]'} {label}")
fails = [l for l, ok in _results if not ok]
print(f"\n  {len(_results) - len(fails)}/{len(_results)} 項通過"
      + ("；全部與校驗預期一致" if not fails else f"；異常項：{fails}"))
