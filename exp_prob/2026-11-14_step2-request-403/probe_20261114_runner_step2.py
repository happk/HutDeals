"""probe_20261114_runner_step2.py — runner 端 step2×10 診斷（零 M1 前置）。

目的：runner IP 上直接走生產 session 鏈打 10 發 step2 menu GET（前置 3 發共用
session），判「第二層長期懲罰是否仍在」與「403 的真面目」——回應體與 headers
完整印進 Actions log（生產代碼只留狀態碼，這裡補全）。

重現方式＝本地 probe 同款：繼承生產 OrderFlowSession（prepare/fetch_menu 用
生產方法，payload 順序零改動），MonitoredSession 類別從
probe_20261114_step2_first_request.py 載入（同一份擷取邏輯）。

跑法：由 .github/workflows/diag-step2-probe.yml 於手動 dispatch 時執行
（checkout 本分支，cwd=repo 根）。
請求預算：前置 3＋menu 10＝13 發 step2 形態、零 M1（上限 40，容許內部重配）。
"""
import importlib.util
import json
import sys
import urllib.error
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROBE_DIR = Path(__file__).resolve().parent
REPO = PROBE_DIR.parent.parent
sys.path.insert(0, str(REPO))

from script.lib.pacing import sleep_scan  # noqa: E402

# 載入本地 probe 的 MonitoredSession／is_menu_page／CAPTURES（同一份擷取邏輯）
spec = importlib.util.spec_from_file_location(
    "probe_local", PROBE_DIR / "probe_20261114_step2_first_request.py")
probe_local = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe_local)
probe_local.REQUEST_CAP = 40  # 3 前置＋10 menu＋容許 fetch_menu 內部重配一次


def main() -> int:
    state = json.loads((REPO / "data" / "scan_state.json").read_text(encoding="utf-8"))
    alive = sorted(c for c, r in state["codes"].items()
                   if r.get("status") == "alive")[:10]
    print("=== runner diag：step2×10、零 M1 前置 ===")
    print(f"codes={alive}\n")

    s = probe_local.MonitoredSession(probe_local.DEFAULT_STORE)
    ok = blocked = other = 0
    try:
        s.prepare(alive[0])
        print("prepare 前置 1-3：OK\n")
    except urllib.error.HTTPError as e:
        print(f"prepare 階段即 HTTP {e.code}——連 step2-form 的 session GET 都被擋\n")
    except Exception as e:  # noqa: BLE001
        print(f"prepare 失敗：{type(e).__name__}: {e}\n")

    for i, code in enumerate(alive):
        try:
            html = s.fetch_menu(code)
            print(f"[{i + 1}/10] {code}: 200 len={len(html)} "
                  f"is_menu_page={probe_local.is_menu_page(html)}")
            ok += 1
        except urllib.error.HTTPError as e:
            print(f"[{i + 1}/10] {code}: HTTP {e.code} ←被擋")
            blocked += 1
        except Exception as e:  # noqa: BLE001
            print(f"[{i + 1}/10] {code}: {type(e).__name__}: {e}")
            other += 1
        sleep_scan(i, alive)

    print(f"\n=== 總結：200×{ok}、被擋×{blocked}、其他錯誤×{other} ===")
    print("\n=== 逐步紀錄 ===")
    for r in s.records:
        mk = r.get("markers") or {}
        print(f"[{r['tag']}] {r['method']} → HTTP {r.get('status')}"
              f"｜len={r.get('body_len')}｜{r.get('elapsed_s')}s"
              f"｜關鍵字={mk.get('keyword_hits')}｜title={mk.get('title')}"
              f"｜檔={r.get('file')}")

    for r in [x for x in s.records if x.get("status") != 200]:
        print(f"\n=== 非 200 詳情：[{r['tag']}] HTTP {r['status']} url={r['url']} ===")
        for k, v in r.get("response_headers", []):
            print(f"  {k}: {v}")
        body = (probe_local.CAPTURES / r["file"]).read_bytes().decode(
            "utf-8", errors="replace")
        print(f"--- 回應體前 2000 字 ---\n{body[:2000]}")

    verdict = ("BLOCKED（runner 仍被擋＝第二層長期懲罰與量無關）" if blocked
               else "PASS（runner 可打 step2＝懲罰已衰解除）" if ok == 10
               else "MIXED（部分過部分拒——形態見上方逐步紀錄）")
    print(f"\noutcome：{verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
