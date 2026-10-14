"""唯讀 probe：歸檔（外部碼離線）問題的完整現況盤點（2026-10-14）

對照 data/scan_state.json（掃號真相）與 public/coupons.js（網站輸出），
把外部碼（source=verified-external）的落差分類、量化，並列出修法會碰到的邊界。

用法：python exp_prob/2026-10-14_search-offline-archive/probe_archive.py
"""

import datetime as dt
import json
import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEAD_TO_EMPTY_DAYS = 7  # script/scan/daily.py:44


def load_coupons():
    src = (REPO / "public" / "coupons.js").read_text(encoding="utf-8")
    m = re.search(r"window\.HUTDEALS_COUPONS\s*=\s*(\{.*\})\s*;?\s*$", src, re.S)
    payload = json.loads(m.group(1))
    return payload, {c["key"]: c for c in payload["coupon_list"]}


def main():
    payload, coupons = load_coupons()
    state = json.loads((REPO / "data" / "scan_state.json").read_text(encoding="utf-8"))
    codes = state.get("codes", {})
    cov = json.loads((REPO / "data" / "scan_coverage.json").read_text(encoding="utf-8")).get("codes", {})
    today = dt.date.fromisoformat(payload["last_update"][:10])

    print(f"coupons.js: {len(coupons)} 筆（active {sum(1 for c in coupons.values() if c['status']=='active')}）"
          f" last_update={payload['last_update']}")
    print(f"scan_state: {len(codes)} 個碼 狀態分佈 {Counter(r.get('status') for r in codes.values())}")
    print(f"coverage : {len(cov)} 個碼 狀態分佈 {Counter(r.get('status') for r in cov.values())}")

    ext = {k: c for k, c in coupons.items() if c.get("source") == "verified-external"}
    off = {k: c for k, c in coupons.items() if c.get("status") != "active"}
    print(f"\ncoupons.js 外部碼 {len(ext)} 筆（其中 offline {sum(1 for c in ext.values() if c['status']!='active')}）"
          f"；offline 券共 {len(off)} 筆全部 source 分佈 {Counter(str(c.get('source')) for c in off.values())}")

    # ── 落差分類 ────────────────────────────────────────────────
    print("\n== 外部碼落差分類（scan_state × coupons.js）==")
    buckets = Counter()
    detail = {"stale_active": [], "orphan_active": [], "revive_pending": [], "never_ingested": []}
    for k, c in ext.items():
        rec = codes.get(k)
        s = (rec or {}).get("status")
        if rec is None:
            buckets["① coupons 有、scan_state 無（無死生命令來源）"] += 1
            detail["orphan_active"].append(k)
        elif s == "alive":
            buckets["② 兩邊都活（正常）"] += 1
            if c["status"] != "active":
                buckets["   ↳ 其中 coupons 標 offline（待復活）"] += 1
                detail["revive_pending"].append(k)
        elif s in ("dead", "empty"):
            buckets[f"③ coupons 仍 active、scan={s}（離線未歸檔＝本 bug）"] += 1
            detail["stale_active"].append((k, s, rec.get("dead_since")))
        else:
            buckets[f"④ scan status={s}"] += 1
    for s in ("dead", "empty", "unknown"):
        n = sum(1 for r in codes.values() if r.get("status") == s)
        notin = sum(1 for code, r in codes.items() if r.get("status") == s and code not in coupons)
        print(f"  scan={s:<7} {n:>3} 個，其中不在 coupons.js：{notin} 個")
    for line, n in buckets.items():
        print(f"  {line}: {n}")

    # ── stale 券的死亡時距（決定離線寬限要給幾天）────────────────
    print("\n== ③ 類（掃號已死卻仍顯示）的死亡時距 ==")
    ages = []
    for k, s, ds in detail["stale_active"]:
        if ds:
            ages.append(((today - dt.date.fromisoformat(ds)).days, k, s, ds))
    ages.sort(reverse=True)
    buckets_age = Counter()
    for a, k, s, ds in ages:
        buckets_age[f"死 {a} 天" if a >= 14 else (f"死 {a} 天（觀察期 ≤{DEAD_TO_EMPTY_DAYS}）" if a <= DEAD_TO_EMPTY_DAYS else f"死 {a} 天")] += 1
    for line, n in sorted(buckets_age.items(), key=lambda kv: -int(re.search(r"\d+", kv[0]).group())):
        print(f"  {line}: {n} 筆")
    print(f"  最久的 5 筆：{[(k, s, ds, f'{a}天') for a, k, s, ds in ages[:5]]}")
    print(f"  這些券的 coupons.js lastSeen／verifiedAt："
          f"{Counter((ext[k]['lastSeen'], ext[k].get('verifiedAt')) for k, s, ds in detail['stale_active']).most_common(3)}")

    # ── 邊界：非 9 前綴卻沒有 source（會被 build_coupons 當官網碼誤標 offline）──
    print("\n== 邊界檢查 ==")
    nosrc_ext = [k for k, c in coupons.items() if not c.get("source") and not k.startswith("9")]
    print(f"  ① 非 9 前綴但無 source 欄位（build_coupons 會當官網碼、下架即離線）：{len(nosrc_ext)} 筆 {nosrc_ext[:8]}")
    nine_ext = [k for k in ext if k.startswith("9")]
    print(f"  ② 9 前綴卻被當外部碼入庫（ingest 應擋）：{len(nine_ext)} 筆 {nine_ext[:8]}")
    ext_in_off_keys = [k for k in ext if k in {c2 for c2, c in coupons.items() if c.get('source') != 'verified-external'}]
    print(f"  ③ 同時存在官方與外部兩筆：{len(ext_in_off_keys)} 筆 {ext_in_off_keys[:8]}")

    # ── 邊界：coverage 與 state 衝突（coverage 說活、state 說死 → 可能誤判）────────
    conflict = [(k, cov[k].get("status"), codes[k].get("status"), cov[k].get("last_checked"), codes[k].get("lastChecked"))
                for k, s, ds in detail["stale_active"]
                if k in cov and cov[k].get("status") == "alive"]
    print(f"  ④ stale 券中 coverage 仍說 alive（掃號結果衝突，可能誤判為死）：{len(conflict)} 筆")
    for c in conflict[:5]:
        print(f"       {c[0]}: coverage={c[1]}@{c[3]}  state={c[2]}@{c[4]}")

    # ── 邊界：外部碼與 60 天清除（build_coupons 會丟棄過期 offline）───────────
    print("\n== 修法影響預估 ==")
    print(f"  · 若 dead/empty 一律標 offline：{len(detail['stale_active'])} 筆立即從網站消失"
          f"（全站 active 由 {sum(1 for c in coupons.values() if c['status']=='active')} 降到 "
          f"{sum(1 for c in coupons.values() if c['status']=='active') - len(detail['stale_active'])}）")
    print(f"  · 若 dead 給寬限、empty 才離線：立即消失 {sum(1 for a, k, s, ds in ages if s == 'empty')} 筆")
    print(f"  · 若只加『已失效』標示不離線：{len(detail['stale_active'])} 筆留在列表但需前端新增 badge")
    print(f"  · 60 天清除（KEEP_OFFLINE_DAYS）：標 offline 後最遲 60 天自動從 coupons.js 移除")
    print(f"  · ① 類（scan_state 無紀錄、仍 active，無從判死）：{len(detail['orphan_active'])} 筆"
          f" {detail['orphan_active'][:8]}")


if __name__ == "__main__":
    main()