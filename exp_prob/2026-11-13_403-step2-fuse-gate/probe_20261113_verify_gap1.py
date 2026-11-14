"""probe 2026-11-13：驗證第三方驗收的缺口一——RuntimeError 路徑重試 3 次不停。

模擬「官網以 200+錯誤頁表達限流」：prepare() 的 step_1_update 回應不含 success:true
→ RuntimeError（非 HTTPError）→ fetch_and_parse 通用重試分支會重試 3 次嗎？
驗收報告宣稱：3 次重試、返回 None、迴圈繼續跑（配額放大器）。本 probe 以 mock 重現。
"""
import sys

sys.path.insert(0, r"D:\Desktop\work\project\20260908_PizzaHut-Coupon-Scraper_Public")

from script.lib.orderflow import fetch_and_parse        # noqa: E402

calls = {"n": 0}


class FakeFetcher:
    """prepare() 對 200 錯誤頁丟 RuntimeError 的替身（與 orderflow.py:115 同型）。"""

    def fetch(self, code: str) -> str:
        calls["n"] += 1
        raise RuntimeError("step_1_update 失敗: mock（200 錯誤頁）")


sleeps: list[int] = []


def fake_sleep(n: int) -> None:
    sleeps.append(n)


r = fetch_and_parse("15809", fetcher=FakeFetcher(), sleep=fake_sleep)
print(f"RESULT {r} CALLS {calls['n']} SLEEPS {sleeps}")
if r is None and calls["n"] == 3:
    print("=> 缺口一證實：RuntimeError 重試 3 次後返回 None，無熔斷訊號，呼叫端迴圈會繼續")
else:
    print("=> 與驗收報告宣稱不符，需回查")
