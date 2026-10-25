"""唯讀 probe：外部碼離線歸檔修復前的獨立複核與修法模擬（2026-10-25）

不信任既有報告的數字，直接對 data/scan_state.json × public/coupons.js 重算：
1. stale active 外部碼（coupons active、scan dead/empty）重新分類，含 9 前綴檢查
2. dead 卻不在 coupons.js 的碼：狀態歷史（firstSeen/lastSeen/source）— 為何沒入庫
3. 復活殘留：alive 卻仍帶 dead_since 的 state 紀錄（merge_alive_records 不清）
4. empty 紀錄缺 dead_since 的邊界（offlineSince 取值來源）
5. 修法模擬：dead/empty 一律離線（展示不分——2026-10-25 拍板）、offlineSince=dead_since，
   驗證 (a) 沒有任何 alive 碼被誤離線 (b) 每筆離線都有 dead_since 可用
6. sitemap.xml 現況：stale 碼有多少在裡面
7. status=None 的 state 紀錄、15595（非 9 前綴無 source）的歸屬

分析結論見同目錄 README.md。

用法：python exp_prob/2026-10-25_search-offline-archive/probe_fix_sim.py
"""

import datetime as dt
import json
import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def load_coupons():
    src = (REPO / "public" / "coupons.js").read_text(encoding="utf-8")
    m = re.search(r"window\.HUTDEALS_COUPONS\s*=\s*(\{.*\})\s*;?\s*$", src, re.S)
    payload = json.loads(m.group(1))
    return payload, {c["key"]: c for c in payload["coupon_list"]}


def main():
    payload, coupons = load_coupons()
    state = json.loads((REPO / "data" / "scan_state.json").read_text(encoding="utf-8"))
    codes = state["codes"]
    today = dt.date.fromisoformat(payload["last_update"][:10])
    ext = {k: c for k, c in coupons.items() if c.get("source") == "verified-external"}
    print(f"基準日（coupons last_update）={today}｜外部碼 {len(ext)} 筆｜state {len(codes)} 碼")

    # ── 1. stale active 重新分類 ─────────────────────────────
    print("\n== 1. stale active 外部碼（coupons=active、state 非 alive）==")
    stale = []
    for k, c in ext.items():
        if c.get("status") != "active":
            continue
        rec = codes.get(k)
        s = (rec or {}).get("status")
        if s not in ("alive", None):
            stale.append((k, s, rec.get("dead_since"), rec.get("lastSeen"), c["lastSeen"]))
    print(f"  共 {len(stale)} 筆；state 狀態分佈 {Counter(s for _, s, *_ in stale)}")
    print(f"  9 前綴（不該出現，ingest 擋）：{[k for k, *_ in stale if k.startswith('9')]}")
    ds_missing = [k for k, s, ds, *_ in stale if not ds]
    print(f"  缺 dead_since（offlineSince 需 fallback）：{len(ds_missing)} 筆 {ds_missing}")
    mismatch = [(k, sl, cl) for k, s, ds, sl, cl in stale if sl != cl]
    print(f"  state.lastSeen ≠ coupon.lastSeen：{len(mismatch)} 筆（凍結徵兆）{mismatch[:5]}")
    after_death = [k for k, s, ds, sl, cl in stale if ds and cl > ds]
    print(f"  coupon.lastSeen > dead_since（死後仍入庫＝異常，應為 0）：{len(after_death)} 筆 {after_death}")

    # ── 2. dead 未入庫的碼 ───────────────────────────────────
    print("\n== 2. state=dead 但不在 coupons.js 的碼（為何沒入庫）==")
    dead_notin = [(k, r) for k, r in codes.items()
                  if r.get("status") == "dead" and k not in coupons]
    print(f"  共 {len(dead_notin)} 筆；前綴分佈 {Counter(k[:2] for k, _ in dead_notin)}")
    for k, r in sorted(dead_notin):
        fs, ds = r.get("firstSeen"), r.get("dead_since")
        gap = ((dt.date.fromisoformat(ds) - dt.date.fromisoformat(fs)).days
               if fs and ds else None)
        print(f"   {k}: firstSeen={fs} lastSeen={r.get('lastSeen')} "
              f"dead_since={ds} 活存天數={gap} src={r.get('source')}")

    # ── 3. 復活殘留 dead_since ──────────────────────────────
    print("\n== 3. alive 卻仍帶 dead_since（復活未清；naive 修法會誤判）==")
    alive_with_ds = [(k, r.get("dead_since")) for k, r in codes.items()
                     if r.get("status") == "alive" and r.get("dead_since")]
    print(f"  {len(alive_with_ds)} 筆：{alive_with_ds[:10]}"
          f"{' …' if len(alive_with_ds) > 10 else ''}")

    # ── 4. empty 紀錄的 dead_since 完整性 ────────────────────
    print("\n== 4. state=empty 的 dead_since 完整性 ==")
    empties = [(k, r) for k, r in codes.items() if r.get("status") == "empty"]
    no_ds = [(k, r.get("firstSeen"), r.get("lastSeen")) for k, r in empties if not r.get("dead_since")]
    print(f"  empty 共 {len(empties)}；缺 dead_since {len(no_ds)} 筆 {no_ds[:8]}")

    # ── 5. 修法模擬 ─────────────────────────────────────────
    print("\n== 5. 修法模擬（dead/empty 一律離線——展示不分；offlineSince=dead_since）==")
    to_offline, keep_active, revive_case, no_rec = [], [], [], []
    for k, c in ext.items():
        rec = codes.get(k)
        if rec is None:
            no_rec.append(k)
            continue
        s = rec.get("status")
        ds = rec.get("dead_since")
        if s == "alive":
            (revive_case if c.get("status") == "offline" else keep_active).append(k)
        elif s in ("dead", "empty"):
            # 展示上 dead 與 empty 無差異（2026-10-25 使用者拍板）：
            # 差異只是掃號池內部預留（dead=觀察窗、empty=退役歸檔）
            to_offline.append((k, s, ds))
        else:  # status=None 等罕見形狀
            keep_active.append(k)
    print(f"  將標 offline：{len(to_offline)} 筆（empty {sum(1 for _, s, _ in to_offline if s == 'empty')}"
          f" / dead {sum(1 for _, s, _ in to_offline if s == 'dead')}）")
    print(f"  維持 active：{len(keep_active)} 筆；無 state 紀錄：{len(no_rec)} 筆 {no_rec}")
    print(f"  本應復活（state=alive、coupon=offline）：{len(revive_case)} 筆 {revive_case}")
    wrong = [k for k, s, _ in to_offline if s == "alive"]
    print(f"  誤離線檢查（state=alive 卻被標 offline）：應為 0 → {len(wrong)} 筆 {wrong}")
    purge_dates = Counter((dt.date.fromisoformat(ds) + dt.timedelta(days=60)).isoformat()
                          for _, _, ds in to_offline if ds)
    print(f"  60 天清除日（merge KEEP_OFFLINE_DAYS）分佈：{dict(sorted(purge_dates.items()))}")

    # ── 6. sitemap 現況 ─────────────────────────────────────
    print("\n== 6. sitemap.xml 含多少 stale 碼 ==")
    sm = (REPO / "public" / "sitemap.xml").read_text(encoding="utf-8")
    in_sm = [k for k, s, ds, *_ in stale if f"?code={k}" in sm]
    print(f"  stale {len(stale)} 筆中 {len(in_sm)} 筆在 sitemap（deep link 可達）")

    # ── 7. 雜項邊界 ────────────────────────────────────────
    print("\n== 7. 雜項 ==")
    none_status = [(k, {f: v for f, v in r.items() if f != 'items'})
                   for k, r in codes.items() if r.get("status") is None]
    print(f"  state status=None：{len(none_status)} 筆 {none_status[:3]}")
    c15595 = coupons.get("15595")
    r15595 = codes.get("15595")
    print(f"  15595：coupon(source={c15595.get('source') if c15595 else '不在'}, "
          f"status={c15595.get('status') if c15595 else '-'})｜"
          f"state(status={(r15595 or {}).get('status')}, dead_since={(r15595 or {}).get('dead_since')})")
    full = (REPO / "public" / "coupons_full.js").read_text(encoding="utf-8")
    m2 = re.search(r"window\.HUTDEALS_FULL\s*=\s*(\{.*\})\s*;?\s*$", full, re.S)
    flist = json.loads(m2.group(1))["coupon_list"] if m2 else []
    stale_keys = {k for k, *_ in stale}
    print(f"  coupons_full.js：{len(flist)} 筆（coupons.js {len(coupons)}）；"
          f"stale 在 full 亦 active："
          f"{sum(1 for c in flist if c.get('key') in stale_keys and c.get('status') == 'active')}"
          f"／{len(stale_keys)}")


if __name__ == "__main__":
    main()
