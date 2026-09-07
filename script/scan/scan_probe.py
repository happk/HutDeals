"""HutDeals scan — 批次掃號探測（stateless，研究用；production 用 scan_run）。

原 scan_codes.py。角色 = scan_run 的「無狀態批次探測版」：不 merge scan_state、
可吃任意碼清單檔、支援 --m1-only（大批死活普查）。網路/節奏統一吃 lib/。

輸出每碼一條寫 `data/raw/scan_codes_{stamp}.json`：
    code, at, m1_success, p_id, [m1_error|step2_error] + (非 m1-only) title/partner/
    ig_hint/channels/price/msrp/desc_head

結果**每碼增量落檔**（同一 stamp 檔整檔重寫）：大批次跑到一半 Ctrl+C / 熔斷，
已完成的部分不丟（各碼自帶 at 時戳，部分結果可辨識）。熔斷仍 exit 3。

用法：
    python -m script.scan.scan_probe --codes 16231,26880
    python -m script.scan.scan_probe --file data/raw/codes.txt --m1-only

節奏（掃號策略）：間隔預設 2s + 每發 U(0,jitter)（lib/pacing）；換號段休息、中場休息；
M1 429/403 熔斷（exit 3 不寫檔）。
"""
import argparse
import datetime as dt
import json
import sys
import urllib.error
from pathlib import Path

from script.lib import pacing
from script.lib.net import is_rate_limited, m1_probe
from script.lib.orderflow import BatchFetcher, fetch_and_parse
from script.lib.repo import REPO

RAW_DIR = REPO / "data" / "raw"


def main() -> int:
    parser = argparse.ArgumentParser(description="HutDeals batch scan probe")
    parser.add_argument("--codes", default=None, help="逗號分隔候選碼")
    parser.add_argument("--file", default=None, help="每行一碼的檔案")
    parser.add_argument("--sleep", type=float, default=pacing.DEFAULT_SLEEP)
    parser.add_argument("--jitter", type=float, default=pacing.DEFAULT_JITTER)
    parser.add_argument("--seg-gap", type=float, default=pacing.DEFAULT_SEG_GAP)
    parser.add_argument("--break-every", type=int, default=pacing.DEFAULT_BREAK_EVERY)
    parser.add_argument("--break-base", type=float, default=pacing.DEFAULT_BREAK_BASE)
    parser.add_argument("--m1-only", action="store_true",
                        help="只打 M1 驗活(不抓 step_2)；適用大批次死活普查")
    parser.add_argument("--save-html", action="store_true", help="存 step_2 HTML 供除錯")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")

    codes: list[str] = []
    if args.codes:
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    if args.file:
        p = Path(args.file)
        if not p.exists():
            print(f"file not found: {p}", file=sys.stderr)
            return 2
        codes += [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines()
                  if ln.strip() and not ln.startswith("#")]
    seen: set[str] = set()
    codes = [c for c in codes if not (c in seen or seen.add(c))]
    if not codes:
        print("no codes given (--codes or --file)", file=sys.stderr)
        return 2

    results = []
    fetcher = BatchFetcher()
    out = RAW_DIR / f"scan_codes_{stamp}.json"

    def add(rec: dict) -> None:
        results.append(rec)
        out.write_text(json.dumps({"fetched_at": stamp, "count": len(results),
                                   "results": results},
                                  ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        for i, code in enumerate(codes):
            rec = {"code": code, "at": dt.datetime.now().isoformat(timespec="seconds")}
            try:
                m1 = m1_probe(code)
                rec["m1_success"] = m1.get("success") is True
                rec["p_id"] = (m1.get("data") or {}).get("p_id") if m1.get("success") else None
            except urllib.error.HTTPError as e:
                if is_rate_limited(e):
                    print(f"ABORT: {code} HTTP {e.code}（熔斷，已完成部分已存檔）", file=sys.stderr)
                    return 3
                rec["m1_error"] = f"HTTP {e.code}"
                add(rec)
                print(f"{code}: M1 FAIL HTTP {e.code}")
                pacing.sleep_scan(i, codes, sleep=args.sleep, jitter=args.jitter,
                                  seg_gap=args.seg_gap, break_every=args.break_every,
                                  break_base=args.break_base)
                continue
            except Exception as err:  # noqa: BLE001
                rec["m1_error"] = str(err)[:150]
                add(rec)
                print(f"{code}: M1 FAIL {err}")
                pacing.sleep_scan(i, codes, sleep=args.sleep, jitter=args.jitter,
                                  seg_gap=args.seg_gap, break_every=args.break_every,
                                  break_base=args.break_base)
                continue

            if not rec["m1_success"]:
                print(f"{code}: M1 dead")
                add(rec)
                pacing.sleep_scan(i, codes, sleep=args.sleep, jitter=args.jitter,
                                  seg_gap=args.seg_gap, break_every=args.break_every,
                                  break_base=args.break_base)
                continue

            if args.m1_only:
                print(f"{code}: M1 alive p_id={rec['p_id']}")
                add(rec)
                pacing.sleep_scan(i, codes, sleep=args.sleep, jitter=args.jitter,
                                  seg_gap=args.seg_gap, break_every=args.break_every,
                                  break_base=args.break_base)
                continue

            try:
                r = fetch_and_parse(code, fetcher)
                if r is None:
                    rec["step2_error"] = "fetch/parse 失敗"
                else:
                    if args.save_html:
                        (RAW_DIR / f"step2_{code}.html").write_text(
                            r["html"], encoding="utf-8")
                    d = r["meta"]
                    rec.update(d)  # title/partner/ig_hint/channels/price/msrp/desc_head
                    rec["items"] = r["items"] or []
                    tag = f"  << 聯名:{d['partner']}" if d["partner"] else ""
                    print(f"{code}: 活 p_id={rec['p_id']} | {d['title']}"
                          f" | 通路:{'/'.join(d['channels'])} | ${d['price']}"
                          + (f" (原價${d['msrp']})" if d["msrp"] else "") + tag)
            except Exception as err:  # noqa: BLE001
                rec["step2_error"] = str(err)[:150]
                print(f"{code}: step2 FAIL {err}")
            add(rec)
            pacing.sleep_scan(i, codes, sleep=args.sleep, jitter=args.jitter,
                              seg_gap=args.seg_gap, break_every=args.break_every,
                              break_base=args.break_base)
    except KeyboardInterrupt:
        print(f"ABORT: Ctrl+C（已完成 {len(results)} 碼已存檔）", file=sys.stderr)
        return 4

    print(f"-> {out.relative_to(REPO)}")
    partners = [r for r in results if r.get("partner")]
    print(f"聯名命中: {len(partners)}/{len(results)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
