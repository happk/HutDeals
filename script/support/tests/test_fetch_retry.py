"""HutDeals tests — fetch_and_parse 重試（2026-09-08）。

守護：瞬時錯誤重試至多 3 次（線性退避由呼叫端注入 sleep 驗證）；
429/403 熔斷直拋不重試；持續失敗回 None。

執行：python -m unittest script.support.tests.test_fetch_retry -v
"""
import os
import sys
import unittest
import urllib.error
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from script.lib.orderflow import fetch_and_parse  # noqa: E402

FIXTURE = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "fixtures", "orderflow",
    "91113.html"))


class _Flaky:
    """前 fail_times 次丟錯，之後回 fixture HTML。"""

    def __init__(self, fail_times, err):
        self.fail_times = fail_times
        self.err = err
        with open(FIXTURE, encoding="utf-8") as f:
            self.html = f.read()
        self.calls = 0

    def fetch(self, code):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise self.err
        return self.html


def _http_error(code):
    return urllib.error.HTTPError("https://example.invalid/", code, "x", {}, None)


class TestFetchRetry(unittest.TestCase):
    def test_retry_then_success(self):
        """瞬時錯誤 2 次後成功：第 3 次回正確解析（price=199）。"""
        fetcher = _Flaky(2, urllib.error.URLError("boom"))
        sleeps = []
        r = fetch_and_parse("91113", fetcher, sleep=sleeps.append)
        self.assertIsNotNone(r)
        self.assertEqual(r["meta"]["price"], 199)
        self.assertEqual(fetcher.calls, 3)
        self.assertEqual(sleeps, [1, 2])  # 線性退避 attempt 序

    def test_rate_limit_no_retry(self):
        """429 直拋且只打 1 次（不重試）。"""
        fetcher = _Flaky(99, _http_error(429))
        with self.assertRaises(urllib.error.HTTPError):
            fetch_and_parse("91113", fetcher, sleep=lambda _: None)
        self.assertEqual(fetcher.calls, 1)

    def test_persistent_failure_none(self):
        """持續傳輸失敗 → 3 次後回 None。"""
        fetcher = _Flaky(99, urllib.error.URLError("down"))
        r = fetch_and_parse("91113", fetcher, sleep=lambda _: None)
        self.assertIsNone(r)
        self.assertEqual(fetcher.calls, 3)

    def test_empty_html_retries_then_none(self):
        """空回應視為瞬時失敗：重試 3 次後回 None。"""

        class _Empty:
            def __init__(self):
                self.calls = 0

            def fetch(self, code):
                self.calls += 1
                return ""

        fetcher = _Empty()
        r = fetch_and_parse("91113", fetcher, sleep=lambda _: None)
        self.assertIsNone(r)
        self.assertEqual(fetcher.calls, 3)


if __name__ == "__main__":
    unittest.main()
