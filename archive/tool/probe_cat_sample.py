# -*- coding: utf-8 -*-
"""抽樣驗證 cat 分類規則：跨類別號碼重抓→parse，輸出每組 subject→cat 給使用者確認。

涵蓋：正常比薩(26898/26868/94199/16010)、義大利麵/飯(16188/91112/16358)、
副食當main(16202/92117)、煎餅(92114)、點心(92002)、手工義式薄比薩(16167)、
個人(16015)、大比薩(93022)。
"""
import sys
from pathlib import Path

REPO = Path(r"D:\Desktop\work\project\20260903_PizzaHut-Coupon-Scraper")
sys.path.insert(0, str(REPO))

from script.lib.orderflow import BatchFetcher, fetch_and_parse  # noqa: E402
from script.lib.pacing import sleep_scan  # noqa: E402

SAMPLE = ["26898", "26868", "94199", "16010", "16188", "91112", "16358",
          "16202", "92117", "92114", "92002", "16167", "16015", "93022"]


def main() -> int:
    print(f"抽樣 {len(SAMPLE)} 張重抓驗證 cat…", flush=True)
    fetcher = BatchFetcher()
    for i, code in enumerate(SAMPLE):
        try:
            r = fetch_and_parse(code, fetcher)
        except Exception as e:  # noqa: BLE001
            print(f"  {code}: FAIL {e}", flush=True)
            sleep_scan(i, SAMPLE)
            continue
        if r is None:
            print(f"  {code}: None", flush=True)
            sleep_scan(i, SAMPLE)
            continue
        items = r["items"] or []
        # 每組輸出 cat + groupTitle
        seen = set()
        lines = []
        for it in items:
            if it.get("group") == "add":
                continue
            k = (it.get("group"), it.get("groupIdx"))
            if k in seen:
                continue
            seen.add(k)
            lines.append(f"      {k[0]}{k[1]} cat={it.get('cat'):6} |「{it.get('groupTitle')}」"
                         f"| 例:{it.get('text','')[:16]}")
        print(f"\n== {code}")
        for l in lines:
            print(l)
        sleep_scan(i, SAMPLE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
