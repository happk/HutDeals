"""HutDeals scan — 掃號 runner（production，scan.yml CI 每週）。

流程：讀 `data/scan_candidates.txt` → 逐碼 M1 驗活（lib/net）→ 活碼打 step_2 →
`parse_step2` 解析（partner/通路/價格/items）→ 合併進 `data/scan_state.json`。
網路/節奏/state 讀寫統一吃 lib/（net/pacing/state/repo），不重複定義。

狀態檔 `data/scan_state.json`：{updatedAt, codes: {CODE: {firstSeen, lastSeen,
status: alive|dead|unknown, p_id, title, partner, ig_hint, channels, price, msrp,
desc_head, desc, items}}} — 07（號段分析）吃歷史、08（入庫）吃 partner/price/channels。

用法：
    python -m script.scan.scan_run                 # 讀 scan_candidates.txt 全掃
    python -m script.scan.scan_run --codes 26975,26880
    python -m script.scan.scan_run --sleep 2 --jitter 2 --max 30

節奏（掃號策略 2026-09-04）：間隔預設 2s + 每發 U(0,jitter) 浮動（lib/pacing）；
換號段額外休息、每 N 發中場休息；429/403 立即熔斷（不寫 state 避免半套 commit）；
傳輸失敗記 unknown 不記 dead。
"""
import argparse
import datetime as dt
import json
import sys
import urllib.error

from script.lib import net, pacing, state as state_lib
from script.lib.net import is_rate_limited, m1_probe
from script.lib.orderflow import BatchFetcher, fetch_and_parse
from script.lib.repo import REPO
from script.scan.parse_step2 import parse_step2

RAW_DIR = REPO / "data" / "raw"
CANDIDATES = REPO / "data" / "scan_candidates.txt"
STATE_FILE = REPO / "data" / "scan_state.json"


def load_candidates(path) -> list[str]:
    if not path.exists():
        return []
    codes = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        if ln not in codes:
            codes.append(ln)
    return codes


def scan_one(code: str, fetcher: BatchFetcher | None = None) -> dict:
    """單碼掃描，回 {code, status, p_id?, title?, partner?, ...}。
    fetcher：BatchFetcher 共用 session（None = 每碼新 session）。"""
    rec: dict = {"code": code}
    try:
        m1 = m1_probe(code)
    except urllib.error.HTTPError as e:
        if is_rate_limited(e):
            return {"code": code, "abort": True, "reason": f"HTTP {e.code}"}
        return {"code": code, "status": "unknown", "error": f"HTTP {e.code}"}
    except Exception as err:  # noqa: BLE001
        return {"code": code, "status": "unknown", "error": str(err)[:150]}

    if m1.get("success") is not True:
        return {"code": code, "status": "dead"}

    rec["status"] = "alive"
    rec["p_id"] = (m1.get("data") or {}).get("p_id")
    try:
        r = fetch_and_parse(code, fetcher)
        if r is None:
            rec["step2_error"] = "fetch/parse 失敗"
            return rec
        parsed = r["meta"]
        rec.update({k: parsed[k] for k in ("title", "partner", "ig_hint",
                                           "channels", "price", "msrp",
                                           "desc_head", "desc")})
        rec["items"] = r["items"] or []
    except urllib.error.HTTPError as e:
        if is_rate_limited(e):
            return {"code": code, "status": "alive", "p_id": rec["p_id"],
                    "abort": True, "reason": f"HTTP {e.code} step2"}
        rec["status"] = "alive"
        rec["step2_error"] = f"HTTP {e.code}"
    except Exception as err:  # noqa: BLE001
        rec["step2_error"] = str(err)[:150]
    return rec


def merge_record(state: dict, rec: dict) -> None:
    code = rec["code"]
    today = dt.date.today().isoformat()
    codes = state.setdefault("codes", {})
    prev = codes.get(code, {})
    merged = dict(prev)
    merged["firstSeen"] = prev.get("firstSeen", today)
    merged["lastSeen"] = today
    merged["status"] = rec.get("status", prev.get("status", "unknown"))
    for k in ("p_id", "title", "partner", "ig_hint", "channels", "price", "msrp",
              "desc_head", "desc", "items"):
        if k in rec:
            merged[k] = rec[k]
    if rec.get("step2_error"):
        merged["step2_error"] = rec["step2_error"]
    else:
        merged.pop("step2_error", None)
    codes[code] = merged


def main() -> int:
    parser = argparse.ArgumentParser(description="HutDeals scan runner (Actions)")
    parser.add_argument("--codes", default=None, help="逗號分隔覆蓋候選清單")
    parser.add_argument("--sleep", type=float, default=pacing.DEFAULT_SLEEP,
                        help="每發基礎間隔(秒)")
    parser.add_argument("--jitter", type=float, default=pacing.DEFAULT_JITTER,
                        help="每發隨機浮動上限(秒): 實際等 sleep+U(0,jitter)")
    parser.add_argument("--seg-gap", type=float, default=pacing.DEFAULT_SEG_GAP,
                        help="換號段(前2碼改變)額外隨機休息基礎(秒): ×U(0.5,1.5)")
    parser.add_argument("--break-every", type=int, default=pacing.DEFAULT_BREAK_EVERY,
                        help="每 N 發中場長休息(0=不休息)")
    parser.add_argument("--break-base", type=float, default=pacing.DEFAULT_BREAK_BASE,
                        help="中場休息基礎秒數: ×U(0.8,1.5)")
    parser.add_argument("--max", type=int, default=45, help="單次上限(禮節)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")

    codes = [c.strip() for c in args.codes.split(",") if c.strip()] if args.codes \
        else load_candidates(CANDIDATES)
    if not codes:
        print(f"no candidates in {CANDIDATES} (或 --codes)", file=sys.stderr)
        return 2
    if len(codes) > args.max:
        print(f"candidates {len(codes)} > --max {args.max}，截斷（禮節紅線）", file=sys.stderr)
        codes = codes[: args.max]

    state = state_lib.load_state(STATE_FILE)
    scanned = []
    aborted = None
    transport_fail_streak = 0

    if args.dry_run:
        print(f"DRY-RUN: {len(codes)} codes, sleep={args.sleep}s jitter={args.jitter}s")
        for c in codes:
            print(" ", c)
        return 0

    fetcher = BatchFetcher()
    for i, code in enumerate(codes):
        rec = scan_one(code, fetcher)
        scanned.append(rec)
        if rec.get("abort"):
            aborted = rec
            break
        if rec.get("status") == "unknown":
            transport_fail_streak += 1
        else:
            transport_fail_streak = 0
        # 前 10 發內 5 次 unknown → 停
        if i + 1 <= 10 and transport_fail_streak >= 5:
            aborted = {"reason": f"前 {i+1} 發 {transport_fail_streak} 次傳輸失敗，已停"}
            break
        tag = (f"| {rec.get('partner') or ''}" if rec.get("status") == "alive" else "")
        print(f"[{i+1}/{len(codes)}] {code}: {rec.get('status')}{tag}")
        if not aborted:
            pacing.sleep_scan(i, codes, sleep=args.sleep, jitter=args.jitter,
                              seg_gap=args.seg_gap, break_every=args.break_every,
                              break_base=args.break_base)

    if aborted:
        # 熔斷：不寫 state（避免半套當完整 commit），只留 raw 快照供查
        (RAW_DIR / f"scan_aborted_{stamp}.json").write_text(
            json.dumps({"aborted": aborted["reason"], "scanned": scanned},
                       ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"ABORT: {aborted['reason']}")
        return 3

    for rec in scanned:
        merge_record(state, rec)
    state["updatedAt"] = dt.datetime.now().isoformat(timespec="seconds")
    state_lib.save_state(STATE_FILE, state)

    # 自動歸檔：寫 scan-history 執行批次一列 + coverage-map 回報（容錯，不影響結果）
    try:
        from script.scan.scan_archive import archive_scan_run
        _arch = archive_scan_run(scanned, codes)
        print(f"歸檔: history={_arch['history']} coverage={_arch['coverage']}")
    except Exception as err:  # noqa: BLE001 — 歸檔失敗不該讓掃描被當失敗
        print(f"WARN: 自動歸檔失敗（掃描結果已寫好）: {err}", file=sys.stderr)

    # raw 快照（gitignored，細節證據）
    (RAW_DIR / f"scan_{stamp}.json").write_text(
        json.dumps({"fetched_at": stamp, "scanned": scanned, "count": len(scanned)},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    alive = [r for r in scanned if r.get("status") == "alive"]
    dead = [r for r in scanned if r.get("status") == "dead"]
    partners = sorted({r.get("partner") for r in alive if r.get("partner")})
    delivery = [r["code"] for r in alive if "外送" in (r.get("channels") or [])]
    print(f"-> {STATE_FILE.relative_to(REPO)}")
    print(f"alive {len(alive)} / dead {len(dead)} / unknown "
          f"{sum(1 for r in scanned if r.get('status')=='unknown')}")
    print(f"聯名方: {partners}")
    print(f"支援外送({len(delivery)}): {delivery}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
