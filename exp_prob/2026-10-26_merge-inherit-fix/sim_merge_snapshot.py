"""快照模擬測試（c5d1634-1，2026-10-26）：真實 coupons.js × 真實 merge() 的掉殼逆向驗證。

模擬明日 update 鏈的 build 步驟——官券（無 source 欄位）用 build 自己的 enrich()
重建為「列表殼」（品名/描述/價格/分類同源，無 items/flavorSets/units/msrp、
orderUrl 回通用訂餐頁），再與真實 existing 跑真 merge()，驗證：

1. 補全官券（原有 items）的 items/flavorSets/units/msrp 100% 保留（掉殼消除）。
2. flavorIdx 無懸空（繼承 items 必連 flavorSets）。
3. orderUrl：舊 cno 直連全數保留（不被通用頁降級）。
4. 外部券（verified-external）零變動（不進繼承邏輯）。

斷言語意化（不鎖鍵名、不鎖張數），資料每日 CI 重寫不破壞。
用法：python exp_prob/2026-10-26_merge-inherit-fix/sim_merge_snapshot.py
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from script.lib.coupons import load_coupons_js  # noqa: E402
from script.site.build_coupons import enrich, merge  # noqa: E402

TAGS = json.loads((REPO / "script" / "site" / "tags.json").read_text(encoding="utf-8"))
TODAY = "2026-10-26"


def main() -> int:
    src = (REPO / "public" / "coupons.js").read_text(encoding="utf-8")
    last_update = re.search(r'"last_update":"([^"]+)"', src).group(1)
    existing = load_coupons_js()
    officials = [c for c in existing.values() if not c.get("source")]
    externals = {k for k, c in existing.items() if c.get("source") == "verified-external"}
    print(f"資料基準 {last_update}：官券 {len(officials)}（補全 {sum(1 for c in officials if c.get('items'))}）"
          f"｜外部券 {len(externals)}")

    # build 模擬：用 build 自己的 enrich() 從列表欄位重建殼（與每日 update 同一條路徑）
    shells = [
        enrich({"source": "pdpop", "code": c.get("code") or str(c["key"]).removeprefix("pid:"),
                "name": c["name"], "description": c.get("description"),
                "image": c.get("image"), "category": c.get("category")}, TAGS)
        for c in officials
    ]
    before_filled = {c["key"]: c for c in officials if c.get("items")}
    assert len(before_filled) > 0, "資料中無補全官券，快照失去意義"

    merged, stats = merge(existing, shells, TODAY)
    print(f"merge 完成：stats={stats}")

    by_key = {c["key"]: c for c in merged}
    fails = []

    # 1. 補全券四欄 100% 保留
    for key, old in before_filled.items():
        new = by_key.get(key)
        if new is None:
            fails.append(f"{key} 消失於 merge 結果")
            continue
        for f in ("items", "flavorSets", "units", "msrp"):
            if (old.get(f) or None) != (new.get(f) or None):
                fails.append(f"{key} 欄位 {f} 未保留：舊 {bool(old.get(f))} → 新 {bool(new.get(f))}")

    # 2. flavorIdx 無懸空
    for c in merged:
        fs_len = len(c.get("flavorSets") or [])
        for it in c.get("items") or []:
            fi = it.get("flavorIdx")
            if fi is not None and not (0 <= fi < fs_len):
                fails.append(f"{c['key']} flavorIdx={fi} 懸空（flavorSets 長度 {fs_len}）")

    # 3. orderUrl：舊 cno 直連保留
    for key, old in before_filled.items():
        if "cno=" in (old.get("orderUrl") or "") and "cno=" not in (by_key[key].get("orderUrl") or ""):
            fails.append(f"{key} orderUrl 被降級為通用頁")

    # 4. 外部券零變動（物件同一性＋欄位快照）
    for key in externals:
        if by_key.get(key) is not existing[key]:
            fails.append(f"外部券 {key} 物件被重建（應原樣保留）")

    if fails:
        print(f"\nFAIL（{len(fails)}）:")
        for f in fails[:20]:
            print(f"  - {f}")
        return 1

    kept = len(before_filled)
    print(f"\nPASS：補全官券 {kept} 張四欄全保留｜flavorIdx 無懸空｜"
          f"cno 直連保留｜外部券 {len(externals)} 張零變動")
    return 0


if __name__ == "__main__":
    sys.exit(main())
