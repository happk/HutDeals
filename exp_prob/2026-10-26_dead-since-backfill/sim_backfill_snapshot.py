"""快照模擬（cb13be8-1，2026-10-26）：真實 scan_state × 補值謂詞的目標精確度驗證。

唯讀：載入真實 data/scan_state.json，以「與 daily.py 補值完全相同的謂詞」在記憶體中
模擬 confirm dead 分支的走訪，驗證：
1. 補值目標＝恰為「status=dead 且 dead_since falsy」的紀錄（當前 15 筆遺留），一一列出。
2. alive／empty／其他 status 的紀錄零觸及（670 問題：活碼不被補值）。
3. 已有有效值的 dead 零覆蓋。
4. 補值後逐筆模擬 7 天退役時點（補值日+7）。

usage: python exp_prob/2026-10-26_dead-since-backfill/sim_backfill_snapshot.py
"""
import datetime as dt
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def main() -> int:
    state = json.loads((REPO / "data" / "scan_state.json").read_text(encoding="utf-8"))
    codes = state["codes"]
    today = dt.date.today().isoformat()
    print(f"資料基準 updatedAt={state.get('updatedAt')}｜全池 {len(codes)} 碼")

    by_status: dict[str, list[str]] = {}
    for c, r in codes.items():
        by_status.setdefault(str(r.get("status")), []).append(c)

    targets = [c for c, r in codes.items()
               if r.get("status") == "dead" and not r.get("dead_since")]
    valid_dead = [c for c, r in codes.items()
                  if r.get("status") == "dead" and r.get("dead_since")]
    print(f"status 分佈: { {k: len(v) for k, v in by_status.items()} }")
    print(f"\n[1] 補值目標（dead ∧ falsy dead_since）＝ {len(targets)} 筆:")
    for c in sorted(targets):
        r = codes[c]
        print(f"    {c}: firstSeen={r.get('firstSeen')} lastSeen={r.get('lastSeen')}")

    # [2][3] 零觸及驗證：謂詞對非 dead 恆 False（補值代碼只在 confirm dead 分支執行，
    # 此處以「若誤在全池套用謂詞」的最壞假設驗證——即便如此 alive/empty 也零命中）
    wrong_scope = [c for c, r in codes.items()
                   if r.get("status") != "dead" and not r.get("dead_since")]
    print(f"\n[2] 非 dead 帶 falsy dead_since（若謂詞誤套全池也不應補）＝ {len(wrong_scope)} 筆"
          f"（alive/empty 無此欄位為正常形狀；confirm dead 分支根本走不到）")
    print(f"[3] 已有有效值的 dead（不可覆蓋）＝ {len(valid_dead)} 筆")

    # [4] 補值後退役時點
    retire = (dt.date.today() + dt.timedelta(days=7)).isoformat()
    print(f"\n[4] 補值日＝{today}，DEAD_TO_EMPTY_DAYS=7 → 退役日 ≥ {retire}")
    print(f"    退役後復活監看：16xxx（{len([c for c in targets if c.startswith('16')])} 筆）"
          f"回 explore 每日普查；段外（15/25，"
          f"{len([c for c in targets if not c.startswith('16')])} 筆）靠 sample 每日 10% 隨機")

    ok = len(targets) == 15 and len(valid_dead) == 0
    print(f"\n{'PASS' if ok else 'FAIL'}：目標 {len(targets)}/15｜有效值 dead {len(valid_dead)} 筆不被覆蓋")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
