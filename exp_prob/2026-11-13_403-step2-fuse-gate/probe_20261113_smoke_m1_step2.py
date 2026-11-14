"""probe 2026-11-13：小批量煙霧測試——官網是否仍 403。

兩階段（各最多 N 發）：
  1. M1 單發（get_dgtAll）——scan CI 昨晚全程 627 發未擋的端點
  2. step_2 orderflow session（新增 OrderFlowSession → prepare → fetch_menu）——
     昨晚兩場被 403 擋住的端點；只抓 1 張活碼

唯讀原則：不寫 state/coverage/alerts，只印結果。輸出會貼進 probe 報告。
"""
import json
import sys
import urllib.error

sys.path.insert(0, r"D:\Desktop\work\project\20260908_PizzaHut-Coupon-Scraper_Public")

from script.lib.net import m1_probe                      # noqa: E402
from script.lib.orderflow import OrderFlowSession        # noqa: E402
from script.lib.repo import REPO                         # noqa: E402

CODE_M1 = "15809"    # state 首個 alive（CI 昨日確認 alive）
CODE_S2 = "15809"    # 同碼做 step_2 選單版抓取

print("=== Phase 1: M1 smoke ===")
try:
    d = m1_probe(CODE_M1)
    ok = (d or {}).get("success")
    print(f"M1 {CODE_M1}: success={ok} raw={json.dumps(d, ensure_ascii=False)[:160]}")
except urllib.error.HTTPError as e:
    print(f"M1 {CODE_M1}: HTTP {e.code}（403/429 = 仍被擋；其他碼=端點性問題）")
except Exception as e:  # noqa: BLE001
    print(f"M1 {CODE_M1}: {type(e).__name__}: {e}"[:200])

print("=== Phase 2: step_2 orderflow session smoke ===")
try:
    s = OrderFlowSession()
    s.prepare(CODE_S2)
    html = s.fetch_menu(CODE_S2)
    menu = len(html) > 180_000 and "ctidss" in html
    print(f"step_2 {CODE_S2}: html_len={len(html)} menu_page={menu}（True=官網已解封）")
except urllib.error.HTTPError as e:
    print(f"step_2 {CODE_S2}: HTTP {e.code} at session step（403 = 擋點確認）")
except Exception as e:  # noqa: BLE001
    print(f"step_2 {CODE_S2}: {type(e).__name__}: {e}"[:200])
