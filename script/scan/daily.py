"""HutDeals scan — 每日掃號三工（2026-09-05 使用者定稿，取代週日 scan_run 主排程）。

三個獨立子命令 = CI 三個順行 job（未來可個別優化，如 explore 換掃描窗）：
    confirm  軌道①：確認現有碼死活＋內容更動；死碼 dead_since 滿 7 天 → 空號
    explore  軌道②：16/26 全段 M1 普查（現階段段窄全掃；掃描窗留作未來引子）
    sample   軌道③：潛在未知號段抽樣（16/26 ±1/±2，每日隨機重抽，防長期券遺漏；
             命中活碼 → admin 警告）

共用：lib/pacing 保守檔節奏、429/403 熔斷 exit 3（已完成部分仍入庫）、
結果寫 scan_state / scan_coverage / scan_alerts，逐 job append scan-history。
本模組不碰 coupons.js——網站入庫交給每日 update.yml 的 ingest_external。

用法：
    python -m script.scan.daily confirm
    python -m script.scan.daily explore [--limit N]
    python -m script.scan.daily sample  [--limit N]
"""
import argparse
import datetime as dt
import json
import random
import sys
import urllib.error

from script.lib.net import is_rate_limited, m1_probe
from script.lib.orderflow import BatchFetcher, fetch_and_parse
from script.lib.pacing import sleep_scan
from script.lib.repo import REPO
from script.lib.state import STATE_PATH, load_state, save_state
from script.scan.coverage_sync import merge_alive_records
from script.scan.parse_step2 import parse_step2
from script.scan.scan_archive import append_history_row

COV_PATH = REPO / "data" / "scan_coverage.json"
ALERTS_PATH = REPO / "data" / "scan_alerts.json"
ACTIVE_RANGES = [(16000, 16999), (26000, 26999)]
# 潛在未知號段：±1 抽 20%、±2 抽 10%（含 15/25——防「去年發的今年還能用」長期券遺漏）
SAMPLE_PLAN = {  # prefix: (rate, 敘述)
    "15": (0.20, "16±1"), "17": (0.20, "16±1"),
    "25": (0.20, "26±1"), "27": (0.20, "26±1"),
    "14": (0.10, "16±2"), "18": (0.10, "16±2"),
    "24": (0.10, "26±2"), "28": (0.10, "26±2"),
}
DEAD_TO_EMPTY_DAYS = 7
# 內容更動偵測比對的欄位
CONTENT_FIELDS = ["title", "price", "msrp", "channels", "desc_head", "desc"]


def log(msg: str) -> None:
    print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def probe_batch(codes: list[str]) -> tuple[list[dict], bool]:
    """逐碼 M1（保守檔節奏）。回 (results, 是否熔斷)；熔斷時已完成部分仍回傳。"""
    out: list[dict] = []
    for i, code in enumerate(codes):
        rec = {"code": code, "at": dt.datetime.now().isoformat(timespec="seconds")}
        try:
            m1 = m1_probe(code)
            rec["m1_success"] = m1.get("success") is True
            rec["p_id"] = (m1.get("data") or {}).get("p_id") if m1.get("success") else None
        except urllib.error.HTTPError as e:
            if is_rate_limited(e):
                log(f"ABORT: {code} HTTP {e.code}（熔斷，已完成部分仍入庫）")
                return out, True
            rec["m1_error"] = f"HTTP {e.code}"
        except Exception as err:  # noqa: BLE001
            rec["m1_error"] = str(err)[:150]
        out.append(rec)
        if rec.get("m1_success") is True:
            log(f"{code}: alive")
        elif rec.get("m1_success") is False:
            log(f"{code}: dead")
        else:
            log(f"{code}: FAIL {rec.get('m1_error')}")
        sleep_scan(i, codes)
    return out, False


def step2_of(rec: dict, fetcher: BatchFetcher | None = None) -> dict | None:
    """活碼抓選單版並解析；失敗回 None（不擋批次）。

    回 parse_step2 的 meta dict + items（結構化候選）併入：
        {..., items: 結構化候選 | None, struct: 完整中介 | None}
    fetcher：BatchFetcher 共用 session；None = 每碼新 session。
    429/403（熔斷）原樣往上拋由 cmd 層處理。
    """
    try:
        r = fetch_and_parse(rec["code"], fetcher)
    except urllib.error.HTTPError:
        raise  # 熔斷（fetch_and_parse 已只放行 rate-limited）
    except Exception as err:  # noqa: BLE001
        log(f"  {rec['code']} step_2 FAIL {err}")
        return None
    if r is None:
        return None
    out = dict(r["meta"])
    out["items"] = r["items"]
    return out


def load_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return default


def update_alerts(section: str, entries: list) -> None:
    """scan_alerts.json 每工更新自己的區塊（admin 進度分頁的警告資料源）。"""
    data = load_json(ALERTS_PATH, {})
    data[section] = entries
    data["updatedAt"] = dt.datetime.now().isoformat(timespec="seconds")
    ALERTS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                           encoding="utf-8")


def update_coverage(recs: list[dict]) -> None:
    """探測結果併入三態地圖（只記探過的位置；alive 帶 step_2 欄位者由 merge 入 state）。"""
    cov = load_json(COV_PATH, {"codes": {}})
    codes = cov.setdefault("codes", {})
    for r in recs:
        if r.get("m1_success") is None:
            continue  # unknown 不改地圖
        codes[r["code"]] = {**codes.get(r["code"], {}),
                            "status": "alive" if r["m1_success"] else "empty",
                            "last_checked": r["at"]}
    cov["updatedAt"] = dt.datetime.now().isoformat(timespec="seconds")
    COV_PATH.write_text(json.dumps(cov, ensure_ascii=False, indent=1),
                        encoding="utf-8")


def history_row(source: str, recs: list[dict], note: str) -> None:
    from collections import Counter
    alive = sum(1 for r in recs if r.get("m1_success") is True)
    dead = sum(1 for r in recs if r.get("m1_success") is False)
    scope = "、".join(f"{k}xxx×{v}" for k, v in
                      sorted(Counter(r["code"][:2] for r in recs).items()))
    append_history_row({"source": source, "count": len(recs), "alive": alive,
                        "dead": dead, "scope": scope, "note": note})


# ---------------- 軌道①：確認現有碼 ----------------

def cmd_confirm(args) -> int:
    state = load_state()
    codes = state.setdefault("codes", {})
    alive = sorted(c for c, r in codes.items() if r.get("status") == "alive")
    dead = sorted(c for c, r in codes.items() if r.get("status") == "dead")
    if args.limit:
        alive, dead = alive[:args.limit], dead[:args.limit]
    log(f"confirm：alive {len(alive)} + dead（觀察中）{len(dead)}")
    recs, blown = probe_batch(alive + dead)
    today = dt.date.today().isoformat()
    by_code = {r["code"]: r for r in recs}
    changes: list[dict] = []
    retired: list[str] = []
    revived: list[str] = []

    fetcher = BatchFetcher()  # 共用 session：所有 alive 碼共享前置
    for code in alive:
        r = by_code.get(code)
        rec = codes[code]
        if r is None:
            continue  # 熔斷沒掃到
        if r.get("m1_success") is False:
            rec.update(status="dead", dead_since=today)
            log(f"  {code} 活→死（觀察期開始）")
            continue
        if r.get("m1_success") is None:
            continue
        d = step2_of(r, fetcher)
        if d is None:
            continue
        # 組分類（cat/groupTitle）更動 → 也算內容變更（2026-09-07；需先於 items 覆寫比對）
        old_items = rec.get("items") or []
        new_items = d.get("items") or []
        cats_old = {(i.get("cat"), i.get("groupTitle")) for i in old_items}
        cats_new = {(i.get("cat"), i.get("groupTitle")) for i in new_items}
        if cats_new and cats_new != cats_old:
            diff["cats"] = [sorted(cats_old), sorted(cats_new)]
        for f in CONTENT_FIELDS:
            old, new = rec.get(f), d.get(f)
            if old != new and new is not None:
                diff[f] = [old, new]
                rec[f] = new
        if d.get("items") is not None:
            rec["items"] = d["items"]
        if diff:
            rec["contentChangedAt"] = today
            changes.append({"code": code,
                            "diff": {k: v for k, v in diff.items()}})
            log(f"  {code} 內容更動: {list(diff)}")

    for code in dead:
        r = by_code.get(code)
        if r is None:
            continue
        if r.get("m1_success") is True:
            codes[code].update(status="alive")
            codes[code].pop("dead_since", None)
            revived.append(code)
            log(f"  {code} 死→活（觀察期復活）")
        elif r.get("m1_success") is False:
            since = codes[code].get("dead_since", today)
            days = (dt.date.today() - dt.date.fromisoformat(since)).days
            if days >= DEAD_TO_EMPTY_DAYS:
                codes[code].update(status="empty")
                log(f"  {code} 死→空號（退役，死亡 {days} 天）")
                retired.append(code)

    state["updatedAt"] = dt.datetime.now().isoformat(timespec="seconds")
    save_state(STATE_PATH, state)
    update_alerts("content_changes", changes)
    update_alerts("pending_empty", retired)
    history_row("daily.confirm", recs,
                f"內容更動 {len(changes)}、復活 {len(revived)}、退役空號 {len(retired)}"
                + ("；熔斷" if blown else ""))
    n_alive = sum(1 for v in codes.values() if v.get("status") == "alive")
    print(f"confirm 完成：alive {n_alive} / dead "
          f"{sum(1 for v in codes.values() if v.get('status') == 'dead')} / "
          f"empty {sum(1 for v in codes.values() if v.get('status') == 'empty')}")
    return 3 if blown else 0


# ---------------- 軌道②：活躍區段全段普查 ----------------

def cmd_explore(args) -> int:
    codes = [str(c) for lo, hi in ACTIVE_RANGES for c in range(lo, hi + 1)]
    if args.limit:
        codes = codes[:args.limit]
    log(f"explore：16/26 全段 {len(codes)} 碼")
    recs, blown = probe_batch(codes)
    update_coverage(recs)
    # 新活碼（state 沒有或非 alive）→ step_2 → 入 state
    state = load_state()
    known = {c for c, r in state.get("codes", {}).items() if r.get("status") == "alive"}
    fresh = [r for r in recs if r.get("m1_success") is True and r["code"] not in known]
    new_alerts: list[dict] = []
    if fresh:
        log(f"新活碼 {len(fresh)}，補 step_2")
        fetcher = BatchFetcher()
        for r in fresh:
            d = step2_of(r, fetcher)
            if d:
                r.update(d)
                new_alerts.append({"code": r["code"], "title": d.get("title"),
                                   "partner": d.get("partner")})
    added, updated = merge_alive_records(recs, "daily.explore")
    update_alerts("new_codes", new_alerts)
    history_row("daily.explore", recs, f"新入庫 {added}" + ("；熔斷" if blown else ""))
    print(f"explore 完成：alive {sum(1 for r in recs if r.get('m1_success'))}，"
          f"新入庫 {added} / 更新 {updated}")
    return 3 if blown else 0


# ---------------- 軌道③：潛在未知號段抽樣 ----------------

def cmd_sample(args) -> int:
    today = dt.date.today().isoformat()
    rng = random.Random(today)  # seed=日期：每日重抽、當日可重現
    codes: list[str] = []
    for prefix, (rate, _) in SAMPLE_PLAN.items():
        lo = int(prefix) * 1000
        n = round(1000 * rate)
        codes += [str(c) for c in rng.sample(range(lo, lo + 1000), n)]
    codes.sort()
    if args.limit:
        codes = codes[:args.limit]
    log(f"sample：潛在未知號段 {len(codes)} 碼（seed={today}）")
    recs, blown = probe_batch(codes)
    update_coverage(recs)
    hits = [r for r in recs if r.get("m1_success") is True]
    hit_alerts: list[dict] = []
    if hits:
        log(f"未知號段命中 {len(hits)}，補 step_2")
        fetcher = BatchFetcher()
        for r in hits:
            d = step2_of(r, fetcher)
            if d:
                r.update(d)
                hit_alerts.append({"code": r["code"], "title": d.get("title"),
                                   "partner": d.get("partner"),
                                   "zone": SAMPLE_PLAN.get(r["code"][:2], ("", "?"))[1]})
    added, updated = merge_alive_records(recs, "daily.sample")
    update_alerts("unknown_hits", hit_alerts)
    history_row("daily.sample", recs,
                f"未知號段命中 {len(hits)}（新入庫 {added}）" + ("；熔斷" if blown else ""))
    print(f"sample 完成：命中 {len(hits)}，新入庫 {added}")
    return 3 if blown else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="每日掃號三工")
    sub = ap.add_subparsers(dest="job", required=True)
    for name, fn in (("confirm", cmd_confirm), ("explore", cmd_explore),
                     ("sample", cmd_sample)):
        p = sub.add_parser(name)
        p.set_defaults(fn=fn)
        p.add_argument("--limit", type=int, default=0,
                       help="只掃前 N 碼（煙霧測試用）")
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
