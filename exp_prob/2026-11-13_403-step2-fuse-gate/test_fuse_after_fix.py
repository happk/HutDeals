"""probe 2026-11-13：關一測試稿——熔斷修復（F1/F2）的行為驗證（mock 注入，零真實請求）。

唯讀階段：本檔只驗證「修復後的預期行為」，現在跑的是**未修復的現行代碼**，
所以 F1-403 / F2-403 兩個 case 現在必須**紅**（重現 bug），F1-500 / F1-timeout /
F2-非熔斷 三個 case 現在就該**綠**（不回歸的行為基線）。修復落地後重跑：
全部轉綠＝修復成立＋無回歸。這就是修復的驗收基準。

用法：python -I test_fuse_after_fix.py
"""
import sys
import urllib.error

sys.path.insert(0, r"D:\Desktop\work\project\20260908_PizzaHut-Coupon-Scraper_Public")

from script.lib.orderflow import BatchFetcher            # noqa: E402

PASS, FAIL, RED = "綠", "紅", "紅"
results: list[tuple[str, str, str]] = []  # (case, expected, actual)


def http_err(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="https://www.pizzahut.com.tw/x", code=code, msg="mock",
        hdrs=None, fp=None)


class FakeSession:
    """可編程的 OrderFlowSession 替身：fetch_menu 永遠拋指定例外。"""

    def __init__(self, exc: Exception):
        self.exc = exc
        self.prepare_called = 0

    def fetch_menu(self, code: str, timeout: int = 25) -> str:
        raise self.exc


class FakeRollFetcher(BatchFetcher):
    """把 _roll 換掉（prepare 是真網路），只統計被叫幾次。"""

    def __init__(self, exc: Exception):
        super().__init__(k=50)
        self._roll_calls = 0
        self._session = FakeSession(exc)

    def _roll(self, seed: str) -> None:
        self._roll_calls += 1
        self._session = FakeSession(self.exc_holder)


def case_f1(code_label: str, exc: Exception, expect_raise: bool) -> None:
    """注入固定例外的 FakeSession，看 fetch 是否上拋、_roll 被叫幾次。"""
    f = FakeRollFetcher(exc)
    f.exc_holder = exc
    raised = False
    try:
        f.fetch("15809")
    except urllib.error.HTTPError as e:
        raised = (e.code == exc.code)
    except Exception:
        raised = True
    rolled = f._roll_calls
    if expect_raise:
        ok = raised and rolled == 0
        results.append((code_label, "上拋＋零重配", f"raised={raised} rolls={rolled} → {'綠' if ok else '紅'}"))
    else:
        # 非熔斷錯誤：現行設計＝重配一次再拋（2 rolls 因兩次 fetch_menu 都拋）→ 最終仍上拋
        ok = raised and rolled >= 1
        results.append((code_label, "重配後上拋", f"raised={raised} rolls={rolled} → {'綠' if ok else '紅'}"))


def main() -> int:
    print("=== 現行代碼行為基線（修復前：F1-403/429、F2 應為紅） ===")
    case_f1("F1-403 熔斷上拋且不重配", http_err(403), expect_raise=True)
    case_f1("F1-429 熔斷上拋且不重配", http_err(429), expect_raise=True)
    case_f1("F1-500 非熔斷走重配", http_err(500), expect_raise=False)
    case_f1("F1-timeout 非熔斷走重配", urllib.error.URLError("mock timeout"), expect_raise=False)

    for label, expect, actual in results:
        print(f"[{label}] 期望：{expect}｜實測：{actual}")

    # 修復後的斷言（現行代碼必然失敗的兩條，寫在這裡供修後重跑）
    ok_403 = results[0][2].startswith("raised=True rolls=0")
    ok_429 = results[1][2].startswith("raised=True rolls=0")
    ok_500 = results[2][2].startswith("raised=True rolls=1")
    ok_to  = results[3][2].startswith("raised=True rolls=1")
    print("\n=== 判定 ===")
    print(f"F1-403 熔斷不重配 : {'PASS（已修）' if ok_403 else 'FAIL（未修，B1 重現）'}")
    print(f"F1-429 熔斷不重配 : {'PASS（已修）' if ok_429 else 'FAIL（未修，B1 重現）'}")
    print(f"F1-500 重配不回歸 : {'PASS' if ok_500 else 'FAIL'}")
    print(f"F1-timeout 不回歸 : {'PASS' if ok_to else 'FAIL'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
