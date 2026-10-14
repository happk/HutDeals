"""唯讀 probe：歸檔問題的深挖（2026-10-14）— dead 卡住、empty/官方交叉、入庫完整性

追三件事：
1. scan_state 為 dead 且 dead_since 已逾 DEAD_TO_EMPTY_DAYS=7 卻沒轉 empty 的碼，
   是沒被探、還是探到 None（unknown）→ daily.py:258-268 的分支永不觸發？
2. scan_state=empty 但在 coupons.js 屬「官方碼」的 10 筆，coupons.js 端是什麼狀態？
3. alive 的碼是否都有入 coupons.js（ingest_external 有沒有漏網）？

用法：python exp_prob/2026-10-14_search-offline-archive/probe_dead_stuck.py
"""

import datetime as dt
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEAD_TO_EMPTY_DAYS = 7


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
    print(f"state.updatedAt={state.get('updatedAt')} lastChangedAt={state.get('lastChangedAt')}"
          f"｜today={today}")

    print("\n== 1. dead 且 dead_since 逾 7 天（理論上 confirm 應轉 empty）==")
    stuck = []
    for k, r in codes.items():
        if r.get("status") != "dead":
            continue
        ds = r.get("dead_since")
        if not ds:
            continue
        age = (today - dt.date.fromisoformat(ds)).days
        if age >= DEAD_TO_EMPTY_DAYS:
            stuck.append((age, k, ds, r.get("lastChecked"), r.get("step2_error"), r.get("p_id")))
    stuck.sort(reverse=True)
    print(f"  {len(stuck)} 筆：")
    for age, k, ds, lc, se, pid in stuck:
        print(f"   {k}: dead_since={ds}（{age} 天）lastChecked={lc} p_id={pid} step2_error={se!r}")

    print("\n  對照：正常 dead（<7 天）的紀錄長相")
    normal = [(k, r) for k, r in codes.items()
              if r.get("status") == "dead" and r.get("dead_since")
              and (today - dt.date.fromisoformat(r["dead_since"])).days < DEAD_TO_EMPTY_DAYS]
    for k, r in normal[:5]:
        print(f"   {k}: dead_since={r['dead_since']} lastChecked={r.get('lastChecked')}")

    print("\n== 1b. state 是否還留有 probe 失敗痕跡（熔斷/未知）==")
    for k in ("26420", "26421", "16146", "26422"):
        r = codes.get(k)
        if r:
            print(f"   {k}: {{k: v for k,v in r.items() if k not in ('items',)}}")

    print("\n== 2. scan=empty 但 coupons.js 屬官方碼（source≠verified-external）的情形 ==")
    rows = []
    for k, r in codes.items():
        if r.get("status") != "empty":
            continue
        c = coupons.get(k)
        rows.append((k, (c or {}).get("status"), (c or {}).get("source"), r.get("dead_since"), k in coupons))
    from collections import Counter
    print("  ", Counter((str(s), str(src)) for _, s, src, _, _ in rows))
    for row in rows:
        if row[3] != "2026-09-30":  # 非 09-30 那批，看個別
            pass
    print("  dead_since 分佈：", Counter(ds for _, _, _, ds, _ in rows))

    print("\n== 3. alive 碼的入庫完整性 ==")
    alive = {k for k, r in codes.items() if r.get("status") == "alive"}
    in_js = {k for k in alive if k in coupons}
    missing = sorted(alive - in_js)
    print(f"  alive {len(alive)} 個；在 coupons.js {len(in_js)}；不在 {len(missing)}：{missing[:15]}")
    off_keys = {k for k, c in coupons.items() if c.get("source") != "verified-external"}
    print(f"  其中屬官網集（official_keys，ingest 會跳過）：{len(set(missing) & off_keys)}")
    print(f"  其中 9 前綴（ingest 擋）：{len([k for k in missing if k.startswith('9')])}")
    print(f"  真正漏網（alive、不在 coupons.js、非官網、非 9 前綴）："
          f"{[k for k in missing if k not in off_keys and not k.startswith('9')][:15]}")

    print("\n== 4. external 券的 lastSeen 分佈（freeze 徵兆）==")
    ext = {k: c for k, c in coupons.items() if c.get("source") == "verified-external"}
    from collections import Counter as C
    print("  lastSeen：", C(c["lastSeen"] for c in ext.values()).most_common(6))
    frozen = [k for k, c in ext.items()
              if (c.get("verifiedAt") or "") != payload["last_update"][:10]]
    print(f"  verifiedAt ≠ 今日（未經今日 ingest 覆寫）{len(frozen)} 筆；"
          f"其 lastSeen 最舊：{sorted((ext[k]['lastSeen'] for k in frozen))[:3]}")


if __name__ == "__main__":
    main()