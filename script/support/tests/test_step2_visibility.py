"""HutDeals tests — step2 失敗可見性（2026-09-08）。

守護：
- `merge_step2_failures`：新失敗 upsert、成功者清除、依 code 排序、損壞檔不 throw。
- `step2_of`：失敗寫 rec step2_error/step2At；成功清除舊痕。

執行：python -m unittest script.support.tests.test_step2_visibility -v
"""
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from script.lib.state import merge_step2_failures  # noqa: E402
from script.scan import daily  # noqa: E402


class TestMergeStep2Failures(unittest.TestCase):
    def test_upsert_and_clear_and_sort(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "alerts.json"
            merge_step2_failures(
                [{"code": "91113", "error": "boom", "at": "t1"},
                 {"code": "91112", "error": "x", "at": "t1"}], (), p)
            merged = merge_step2_failures(
                [{"code": "91113", "error": "boom2", "at": "t2"}], ["91112"], p)
            self.assertEqual([e["code"] for e in merged], ["91113"])
            self.assertEqual(merged[0]["error"], "boom2")  # 同 code 覆寫
            self.assertEqual(merged[0]["at"], "t2")

    def test_corrupt_file_starts_fresh(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "alerts.json"
            p.write_text("{oops", encoding="utf-8")
            merged = merge_step2_failures(
                [{"code": "91113", "error": "e", "at": "t"}], (), p)
            self.assertEqual(len(merged), 1)


class TestStep2OfRecords(unittest.TestCase):
    def setUp(self):
        self._orig = daily.fetch_and_parse

    def tearDown(self):
        daily.fetch_and_parse = self._orig

    def test_exception_recorded(self):
        def _boom(code, fetcher):
            raise RuntimeError("boom")
        daily.fetch_and_parse = _boom
        rec = {"code": "91113", "at": "t"}
        self.assertIsNone(daily.step2_of(rec))
        self.assertEqual(rec["step2_error"], "boom")
        self.assertIn("step2At", rec)

    def test_none_recorded(self):
        daily.fetch_and_parse = lambda code, fetcher: None
        rec = {"code": "91113", "at": "t"}
        self.assertIsNone(daily.step2_of(rec))
        self.assertEqual(rec["step2_error"], "fetch/parse 失敗")

    def test_success_clears(self):
        daily.fetch_and_parse = lambda code, fetcher: {
            "meta": {"title": "t", "channels": []}, "items": [], "struct": {}}
        rec = {"code": "91113", "at": "t",
               "step2_error": "old", "step2At": "old"}
        out = daily.step2_of(rec)
        self.assertIsNotNone(out)
        self.assertNotIn("step2_error", rec)
        self.assertNotIn("step2At", rec)


if __name__ == "__main__":
    unittest.main()
