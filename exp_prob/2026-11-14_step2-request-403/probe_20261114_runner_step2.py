"""probe_20261114_runner_step2.py — runner 端決定性實驗：M1×627→45s→step2×10。

目的：完全重現今晨（11-14 03:26 UTC）失敗場的 step2 前置序列——
M1×627（生產 probe_batch 同款迴圈：m1_probe＋sleep_scan 節流，含每 50 發
中場休息）→ ⑦c 45s → step2×10（前 10 個 alive 碼、共用 session、prepare 3 發）。

與生產 confirm 的唯一差異＝step2 截斷到 10 碼（今晨觸發點在前幾發，10 碼足以
觀察）＋不做 coverage/state 寫入、commit、dead 迴圈復活補抓（現狀零請求）。
M1 逐碼 log 改每 50 發一行（log 可讀性；請求序列與生產逐位一致）。
M1 若也被 403＝重大發現，停止 M1 但仍走完 step2 段（僅多 13 發，觀察用）。

判讀：step2 被擋＝量型實錘（403 回應體/headers 完整印進 log）；全過＝今晨是
衰減中的計數器，機制更微妙。

跑法：由 .github/workflows/diag-step2-probe.yml 於 push 自動觸發
（checkout 本分支，cwd=repo 根）。時長估計 ~30-40 分。
"""
import importlib.util
import json
import sys
import time
import urllib.error
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROBE_DIR = Path(__file__).resolve().parent
REPO = PROBE_DIR.parent.parent
sys.path.insert(0, str(REPO))

from script.lib.net import is_rate_limited, m1_probe  # noqa: E402
from script.lib.pacing import sleep_scan  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "probe_local", PROBE_DIR / "probe_20261114_step2_first_request.py")
probe_local = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe_local)
probe_local.REQUEST_CAP = 40  # 3 前置＋10 menu＋容許 fetch_menu 內部重配一次

M1_REST_SECONDS = 45  # ⑦c 生產同款


def m1_phase(codes: list[str]) -> dict:
    """生產 probe_batch 同款迴圈（m1_probe＋sleep_scan，請求序列逐位一致）。"""
    t0 = time.monotonic()
    ok = dead = err = blocked = 0
    m1_blocked = False
    for i, code in enumerate(codes):
        try:
            r = m1_probe(code)
            if r.get("success") is True:
                ok += 1
            elif r.get("success") is False:
                dead += 1
            else:
                err += 1
        except urllib.error.HTTPError as e:
            if is_rate_limited(e):
                blocked += 1
                m1_blocked = True
                print(f"ABORT: {code} HTTP {e.code}——M1 也被擋（重大發現，停止 M1 階段）")
                break
            err += 1
        except Exception as e:  # noqa: BLE001
            err += 1
            print(f"[M1 {i + 1}/{len(codes)}] {code}: {type(e).__name__}: {str(e)[:80]}")
        if (i + 1) % 50 == 0 or i + 1 == len(codes):
            print(f"[M1 {i + 1}/{len(codes)}] t={int(time.monotonic() - t0)}s "
                  f"alive={ok} dead={dead} err={err}")
        sleep_scan(i, codes)
    return {"sent": ok + dead + err + blocked, "alive": ok, "dead": dead,
            "err": err, "blocked_403": blocked, "elapsed_s": round(time.monotonic() - t0, 1),
            "m1_blocked": m1_blocked}


def main() -> int:
    state = json.loads((REPO / "data" / "scan_state.json").read_text(encoding="utf-8"))
    alive_all = sorted(c for c, r in state["codes"].items()
                       if r.get("status") == "alive")
    dead_all = sorted(c for c, r in state["codes"].items()
                      if r.get("status") == "dead")
    m1_codes = alive_all + dead_all  # 生產同款：probe_batch(alive + dead)
    step2_codes = alive_all[:10]
    print("=== runner 決定性實驗：M1×全部 → 45s → step2×10 ===")
    print(f"M1 對象 {len(m1_codes)} 碼（alive {len(alive_all)}＋dead {len(dead_all)}，"
          f"生產同款順序）")
    print(f"step2 對象 {len(step2_codes)} 碼＝{step2_codes}\n")

    m1 = m1_phase(m1_codes)
    print(f"\nM1 階段摘要：{m1}\n")

    print(f"⑦c 抓詳情前休息 {M1_REST_SECONDS}s（生產同款）…")
    time.sleep(M1_REST_SECONDS)
    print("45s 休息完成，開始 step2 段\n")

    s = probe_local.MonitoredSession(probe_local.DEFAULT_STORE)
    ok = blocked = other = 0
    try:
        s.prepare(step2_codes[0])
        print("prepare 前置 1-3：OK\n")
    except urllib.error.HTTPError as e:
        print(f"prepare 階段即 HTTP {e.code}——連 step2-form 的 session GET 都被擋\n")
    except Exception as e:  # noqa: BLE001
        print(f"prepare 失敗：{type(e).__name__}: {e}\n")

    for i, code in enumerate(step2_codes):
        try:
            html = s.fetch_menu(code)
            print(f"[{i + 1}/{len(step2_codes)}] {code}: 200 len={len(html)} "
                  f"is_menu_page={probe_local.is_menu_page(html)}")
            ok += 1
        except urllib.error.HTTPError as e:
            print(f"[{i + 1}/{len(step2_codes)}] {code}: HTTP {e.code} ←被擋")
            blocked += 1
        except Exception as e:  # noqa: BLE001
            print(f"[{i + 1}/{len(step2_codes)}] {code}: {type(e).__name__}: {e}")
            other += 1
        sleep_scan(i, step2_codes)

    print(f"\n=== 總結：step2 200×{ok}、被擋×{blocked}、其他錯誤×{other} ===")
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

    if m1["m1_blocked"]:
        verdict = "M1 即被擋（形態升級——M1 端點也進入被擋）"
    elif blocked:
        verdict = "BLOCKED：M1×全部→step2 觸發被擋＝量型實錘（今晨形態重現）"
    elif ok == len(step2_codes):
        verdict = "PASS：同形態下 runner 沒事——指向今晨是衰減中的計數器"
    else:
        verdict = "MIXED（見逐步紀錄）"
    print(f"\noutcome：{verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
