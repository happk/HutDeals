"""唯讀 probe：驗證使用者回報的兩個問題（2026-10-09）

問題 1：搜尋無法命中卡片「內容物」——例 26821 有「黃金雞軟骨」，搜「雞軟骨」查不到。
問題 2：26821 已失效；正常瀏覽不顯示，但條件篩選/搜尋仍查得到，且無任何標示。

驗證方式：
- 以本地 public/coupons.js（與已部署站同版本，last_update 相同）為資料源。
- 用 npm test 同源的 src/lib/filter.ts 邏輯（本檔內重演，避免前端依賴）。
- 以 data/scan_state.json 驗證 26821 的真實死活。

線上交叉驗證（2026-10-09，已下載核對後移除大檔）：
- https://happk.github.io/HutDeals/coupons.js  last_update 與本地相同；
  26821 同樣 status=active；搜『雞軟骨』命中 1 筆(26763)、『黃金雞軟骨』0 筆。
- https://happk.github.io/HutDeals/assets/index-vMjgFIP8.js
  bundle 內 filterCoupons 含 status!=="active" 排除、haystack 同樣只有 name/description/code
  （與 src/lib/filter.ts 一致，非舊版行為）。

用法：python exp_prob/2026-10-14_search-offline-archive/probe.py
"""

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
COUPONS_JS = REPO / "public" / "coupons.js"
SCAN_STATE = REPO / "data" / "scan_state.json"


def load_coupons():
    src = COUPONS_JS.read_text(encoding="utf-8")
    m = re.search(r"window\.HUTDEALS_COUPONS\s*=\s*(\{.*\})\s*;?\s*$", src, re.S)
    return json.loads(m.group(1))


def load_scan_state():
    return json.loads(SCAN_STATE.read_text(encoding="utf-8"))


# ---- 重演 src/lib/filter.ts:filterCoupons 的相關條件（其餘條件不影響本 probe） ----
def frontend_search(list_, q):
    terms = q.strip().lower().split()
    hits = []
    for c in list_:
        if c.get("status") != "active":
            continue
        haystack = f"{c.get('name') or ''} {c.get('description') or ''} {c.get('code') or ''}".lower()
        if all(t in haystack for t in terms):
            hits.append(c)
    return hits


def items_text_hits(list_, kw):
    """內容物（items[].text）命中 kw 的券（不限 active）——即卡片上看得到、搜尋卻不到的。"""
    out = []
    for c in list_:
        for it in c.get("items") or []:
            if kw in (it.get("text") or ""):
                out.append(c)
                break
    return out


def main():
    data = load_coupons()
    coupons = data["coupon_list"]
    state = load_scan_state()
    codes = state.get("codes", {})

    print(f"== 資料源 == coupons.js count={data['count']} last_update={data['last_update']}")
    active = [c for c in coupons if c.get("status") == "active"]
    offline = [c for c in coupons if c.get("status") != "active"]
    print(f"   active={len(active)} 非active={len(offline)}")

    print("\n== 問題 1：搜尋索引是否含 items（內容物）==")
    print("   filter.ts haystack = name + description + code（不含 items[].text / tags）")
    c21 = next((c for c in coupons if c.get("key") == "26821"), None)
    if c21:
        print(f"   26821: name={c21['name']!r} description={c21['description']!r} "
              f"items數={len(c21.get('items') or [])}")
        print(f"   26821 items 含『雞軟骨』: "
              f"{[it['text'] for it in c21.get('items') or [] if '雞軟骨' in it.get('text','')]}")
    for q in ("雞軟骨", "黃金雞軟骨"):
        hits = frontend_search(coupons, q)
        print(f"   前端搜尋 {q!r} → {len(hits)} 筆: {[h['key'] for h in hits]}")
    item_hits = items_text_hits(coupons, "黃金雞軟骨")
    print(f"   內容物(items)含『黃金雞軟骨』的券 → {len(item_hits)} 筆"
          f"（前端搜尋全部漏掉，只有 desc 剛好也寫到的才會中）")
    desc_hits = [c for c in item_hits if "黃金雞軟骨" in (c.get("description") or "")]
    print(f"   其中 description 也含『黃金雞軟骨』→ 可被搜尋的只有 {len(desc_hits)} 筆")

    print("\n== 問題 2：26821 是否真的失效 / 篩選是否外洩非 active ==")
    rec = codes.get("26821")
    print(f"   scan_state 26821: status={rec.get('status')!r} dead_since={rec.get('dead_since')!r} "
          f"lastChecked={rec.get('lastChecked')!r}")
    if c21:
        print(f"   coupons.js 26821: status={c21.get('status')!r} lastSeen={c21.get('lastSeen')!r} "
              f"source={c21.get('source')!r} verifiedAt={c21.get('verifiedAt')!r}")
        print(f"   → 正常瀏覽(無條件)是否顯示: {'是' if c21.get('status')=='active' else '否'}")
    leaked = [c["key"] for c in offline if frontend_search([c], "") and c.get("status") != "active"]
    print(f"   模擬 filterCoupons：非 active 券能通過搜尋/篩選的筆數 = {len(leaked)}"
          f"（程式碼 src/lib/filter.ts:60 一律排除非 active）")

    print("\n== 問題 2 延伸：掃號已死/退役但 coupons.js 仍 active 的外部碼 ==")
    stale = []
    for c in coupons:
        if c.get("source") != "verified-external" or c.get("status") != "active":
            continue
        r = codes.get(c["key"])
        if r and r.get("status") in ("dead", "empty"):
            stale.append((c["key"], r.get("status"), r.get("dead_since"), c["lastSeen"]))
    print(f"   共 {len(stale)} 筆（ingest_external 只處理 status==alive，empty/dead 不會被標 offline）")
    for key, st, ds, ls in sorted(stale, key=lambda x: x[2] or "")[:15]:
        print(f"     {key}: scan={st} dead_since={ds} coupons.js lastSeen={ls}")
    if len(stale) > 15:
        print(f"     ...另 {len(stale)-15} 筆")

    official_offline = [c for c in offline if c.get("source") == "official"]
    print(f"\n   對照：coupons.js 裡 {len(offline)} 筆 offline 全部來自官網下架"
          f"（official={len(official_offline)}）——外部碼沒有離線標記機制")
    by_src = {}
    for c in offline:
        by_src[str(c.get("source"))] = by_src.get(str(c.get("source")), 0) + 1
    print(f"   22 筆 offline 的 source 分佈：{by_src}")
    nonalive_state = {
        k: v.get("status") for k, v in codes.items()
        if v.get("status") not in ("alive", "unknown")
    }
    print(f"   scan_state 非 alive/unknown 的碼：{len(nonalive_state)} / {len(codes)}")


if __name__ == "__main__":
    sys.exit(main())
