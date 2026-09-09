"""一次性遷移（2026-09-09）：scan_state 回到官網原貌（移除我們的分類 cat）。

背景：分類（項分類）改為**產出 coupons.js 時**才套用（`script/lib/categories.py`），
scan_state 只保留官方欄位（含官方組標題 `groupTitle`），所以舊的 `cat` 要拿掉。
好處：改分類規則只要重跑 build、不必重掃 545 碼。

用法（依序）：
    python -m script.site.migrate_item_units     # 1. scan_state 去 cat
    python -m script.site.ingest_external        # 2. 重建外部碼 coupons.js（含 cat/units/tags）
    python -m script.site.enrich_official        # 3. 官方券 items 重抓＋分類（需連網；不跑則隔日 CI 自動補）
"""
import sys

from script.lib.state import STATE_PATH, load_state, save_state


def main() -> int:
    state = load_state()
    codes = state.get("codes", {})
    removed = 0
    for rec in codes.values():
        for it in rec.get("items") or []:
            if "cat" in it:
                it.pop("cat", None)
                removed += 1
    save_state(STATE_PATH, state)
    print(f"scan_state：{len(codes)} 碼，移除 {removed} 筆 item cat（保持官網原貌）")
    print("下一步：python -m script.site.ingest_external")
    return 0


if __name__ == "__main__":
    sys.exit(main())
