"""HutDeals site — 官網碼 step_2 補全：給 91-94xxx 官方券補通路/原價/cno 直連/items。

官網列表（build_coupons）只有品名/價格/分類；外部碼入庫後卡片帶 orderType/priceNote/
step_2 直連，官方碼相比之下是純文字（使用者 2026-09-05 指正）。本腳本在每日 CI
build → ingest 之後跑：對 coupons.js 的官方碼（無 source 欄位）逐碼抓 step_2「選單版」
（orderflow session 流程），補齊缺的欄位——官方列表是名稱/價格/分類的真值來源，
**只補缺不覆蓋**：
    orderType    ← step_2 channels（官網列表無通路資訊）
    priceNote    ← step_2 msrp（原價）
    orderUrl     ← cno 直連兌換頁（取代通用 ct=9 訂餐頁；08 法務定位）
    items        ← 結構化候選（orderflow，取代 parse_meal 文字拆解）
    description  ← 官網已有就不動；缺才用 step_2 desc_head 補
禮節：每發 2s + U(0,2) 浮動（lib/pacing 保守檔）；step_2 失敗跳過不寫、不影響退出碼。

用法：python -m script.site.enrich_official
"""
import datetime as dt
import sys

from script.lib.coupons import load_coupons_js, write_coupons_js
from script.lib.orderflow import fetch_and_parse
from script.lib.pacing import sleep_scan
from script.lib.repo import REPO

try:  # admin 全量檔（前端線 2026-09-05 加入；未合併前優雅降級）
    from script.lib.coupons import write_coupons_full
except ImportError:  # pragma: no cover
    write_coupons_full = None


def main() -> int:
    coupons = load_coupons_js()
    official = [c for c in coupons.values() if not c.get("source")
                and str(c.get("code", "")).startswith(("91", "92", "93", "94"))]
    targets = [c for c in official
               if not c.get("orderType") or not (c.get("msrp") or c.get("priceNote"))]
    print(f"官方碼 {len(official)}，待補全 {len(targets)}")
    if not targets:
        return 0

    codes = [c["code"] for c in targets]
    filled = failed = 0
    for i, c in enumerate(targets):
        code = c["code"]
        try:
            r = fetch_and_parse(code)  # session 流程 → 選單版 → meta + items
        except Exception as err:  # noqa: BLE001
            print(f"  SKIP {code}: step_2 FAIL {err}")
            failed += 1
            sleep_scan(i, codes)
            continue
        if r is None:
            print(f"  SKIP {code}: step_2 空回應")
            failed += 1
            sleep_scan(i, codes)
            continue
        d = r["meta"]
        if d.get("channels") and not c.get("orderType"):
            c["orderType"] = "/".join(d["channels"]) or None
        if d.get("msrp") and not c.get("msrp"):
            c["msrp"] = d["msrp"]
        if not c.get("description") and d.get("desc_head"):
            c["description"] = d["desc_head"]
        # items：結構化候選（選單版真值；拆不出不寫 → 前端 fallback description）
        if r.get("items"):
            c["items"] = r["items"]
        c["orderUrl"] = f"https://www.pizzahut.com.tw/order/?mode=step_2&type_id=1025&cno={code}"
        filled += 1
        print(f"  + {code} {c['name']} | 通路:{c.get('orderType')} | {c.get('priceNote')}")
        sleep_scan(i, codes)

    last_update = dt.datetime.now().isoformat(timespec="seconds")
    write_coupons_js(list(coupons.values()), last_update)
    if write_coupons_full is not None:
        write_coupons_full(list(coupons.values()), last_update)
    print(f"補全 {filled} / 失敗 {failed} -> coupons.js"
          + (" + coupons_full.js" if write_coupons_full else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
