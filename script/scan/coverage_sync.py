"""HutDeals scan — 掃號結果入庫橋：step_2 raw → data/scan_state.json（ticket 08）。

bootstrap/scan_probe 的 step_2 產出（data/raw/scan_codes_*.json）merge 進 scan_state
（status=alive + title/partner/channels/price/msrp/desc_head/p_id），讓既有每日 CI
（build_coupons → ingest_external）自動把外部碼併進網站——入庫不需要新管線，補資料源即可。

規則（08）：
- 只收 m1_success=True 的碼；M1 false = 空號，**不入 state**（留在 scan_coverage.json 三態地圖）
- 既有碼保留 firstSeen，更新 lastSeen 與 step_2 欄位；新碼 firstSeen=lastSeen=今天
- 官網 91-94xxx 若出現在 raw 會被收進 state，但 ingest_external 會依「官網優先」跳過
- 冪等：同輸入重跑結果相同

items 來源（orderflow 2026-09-07）：掃號端（daily step2_of / scan_probe）已用
session 流程抓到結構化候選 items 併進 rec；本橋只負責寫入，不再自行 parse_meal
重算文字（parse_meal 已退役至 archive/parse/）。

用法：
    python -m script.scan.coverage_sync --json data/raw/scan_codes_20260905-151403.json
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from script.lib.state import STATE_PATH, load_state, save_state

# step_2 解析欄位（parse_step2 產出；scan_state rec 的外部碼欄位集）
STEP2_FIELDS = ["p_id", "title", "partner", "ig_hint", "channels",
                "price", "msrp", "desc_head", "desc", "items"]


def merge_alive_records(recs: list[dict], source: str) -> tuple[int, int]:
    """把 step_2 結果 merge 進 scan_state（只收 m1_success=True），回 (新增, 更新)。

    daily.py 的 explore/sample 也走此函式入庫——掃號結果入 state 的唯一入口。
    """
    state = load_state()
    codes = state.setdefault("codes", {})
    today = dt.date.today().isoformat()
    added = updated = 0
    for r in recs:
        if r.get("m1_success") is not True:
            continue  # 空號不進 state
        code = r["code"]
        old = codes.get(code)
        rec = dict(old) if old else {"firstSeen": today}
        for f in STEP2_FIELDS:
            if r.get(f) is not None:
                rec[f] = r[f]
        rec.update(status="alive", lastSeen=today,
                   lastChecked=r.get("at"), source=source)
        codes[code] = rec
        if old:
            updated += 1
        else:
            added += 1
    state["updatedAt"] = dt.datetime.now().isoformat(timespec="seconds")
    if added:
        # 新碼入池＝池實質變更 → 與 confirm 同規則記 lastChangedAt（純更新不算）
        state["lastChangedAt"] = state["updatedAt"]
    save_state(STATE_PATH, state)
    return added, updated


def main() -> int:
    ap = argparse.ArgumentParser(description="掃號結果 → scan_state 入庫橋")
    ap.add_argument("--json", required=True, help="scan_probe step_2 輸出（scan_codes_*.json）")
    ap.add_argument("--source", default="coverage_sync",
                    help="標記來源批次（寫入每碼 source 欄）")
    args = ap.parse_args()

    path = Path(args.json)
    if not path.exists():
        print(f"file not found: {path}", file=sys.stderr)
        return 2
    recs = json.loads(path.read_text(encoding="utf-8")).get("results", [])
    added, updated = merge_alive_records(recs, args.source)
    codes = load_state().get("codes", {})
    print(f"scan_state: 新增 {added} / 更新 {updated} → 共 {len(codes)} 碼（alive "
          f"{sum(1 for v in codes.values() if v.get('status') == 'alive')}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
