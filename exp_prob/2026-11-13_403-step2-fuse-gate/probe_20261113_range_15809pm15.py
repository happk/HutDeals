"""probe 2026-11-13：中斷點區段掃號——15809±15（15794-15824，31 碼）× 2 輪。

背景：11-12 兩場 scan 都在 step2 迴圈第一個目標 15809 吃 403 炸出。
指示（使用者 2026-11-13）：中斷號碼前後 ±15 共 31 碼、間隔 1 秒、掃一次後
再做一次測試確保。

流程：
  Pass 1：M1 逐碼 15794-15824，間隔 1s
  Pass 2：同上重掃一次（確保穩定性）
  尾段：對 Pass 2 找到的 alive 碼逐一跑 step_2 orderflow session
        （昨天炸掉的路徑；alive 預期 ≤ 3 碼，每碼 4 發）
唯讀：不寫 state/coverage/alerts，只印結果。
"""
import json
import sys
import time
import urllib.error

sys.path.insert(0, r"D:\Desktop\work\project\20260908_PizzaHut-Coupon-Scraper_Public")

from script.lib.net import m1_probe                      # noqa: E402
from script.lib.orderflow import OrderFlowSession        # noqa: E402

CENTER = 15809
SPAN = 15
CODES = [str(c) for c in range(CENTER - SPAN, CENTER + SPAN + 1)]
GAP = 1.0  # 指示：間隔 1 秒


def m1_pass(tag: str) -> dict[str, str]:
    print(f"=== {tag}: M1 x {len(CODES)} codes, gap={GAP}s ===")
    result: dict[str, str] = {}
    blocked = False
    for i, code in enumerate(CODES):
        try:
            d = m1_probe(code)
            ok = (d or {}).get("success")
            result[code] = "alive" if ok else "dead"
        except urllib.error.HTTPError as e:
            result[code] = f"HTTP{e.code}"
            if e.code in (403, 429):
                print(f"[{tag}] {code}: HTTP {e.code}（熔斷——中止本輪）")
                blocked = True
                break
        except Exception as e:  # noqa: BLE001
            result[code] = f"{type(e).__name__}"
            print(f"[{tag}] {code}: FAIL {type(e).__name__}: {str(e)[:80]}")
        print(f"[{tag}] {code}: {result[code]}")
        if i < len(CODES) - 1:
            time.sleep(GAP)
    alive = [c for c, s in result.items() if s == "alive"]
    dead = [c for c, s in result.items() if s == "dead"]
    other = {c: s for c, s in result.items() if s not in ("alive", "dead")}
    print(f"[{tag}] alive {len(alive)} / dead {len(dead)} / other {other}")
    return result


p1 = m1_pass("Pass1")
p2 = m1_pass("Pass2")

# 確保：兩輪結果一致性
diff = {c: (p1.get(c), p2.get(c)) for c in CODES if p1.get(c) != p2.get(c)}
print(f"=== 兩輪差異：{diff if diff else '無（一致）'} ===")

# 尾段：alive 碼走 step_2 orderflow session（昨天炸掉的路徑）
alive2 = [c for c, s in p2.items() if s == "alive"]
print(f"=== step_2 session x {len(alive2)} alive codes ===")
for code in alive2:
    try:
        s = OrderFlowSession()
        s.prepare(code)
        html = s.fetch_menu(code)
        menu = len(html) > 180_000 and "ctidss" in html
        print(f"step_2 {code}: html_len={len(html)} menu_page={menu}")
    except urllib.error.HTTPError as e:
        print(f"step_2 {code}: HTTP {e.code}")
    except Exception as e:  # noqa: BLE001
        print(f"step_2 {code}: {type(e).__name__}: {str(e)[:120]}")
    time.sleep(GAP)
print("=== done ===")
