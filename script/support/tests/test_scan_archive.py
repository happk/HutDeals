"""HutDeals scan_archive 測試：掃號紀錄自動歸檔（公開版 data/scan-records/）。

用 data/scan-records/ 的初始檔複本測（不動原檔）：
- append_history_row：在「執行批次」表尾加列。
- update_coverage：marker 區塊整段取代；無 marker 時檔尾新增。
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from script.scan.scan_archive import (HISTORY_PATH, append_history_row,
                                      update_coverage)

REPO = Path(__file__).resolve().parents[3]


class TestAppendHistoryRow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.hist = Path(self.tmp) / "scan-history.md"
        shutil.copy(HISTORY_PATH, self.hist)

    def test_inserts_row(self):
        ok = append_history_row(
            {"time": "09-08 01:00", "source": "daily.confirm", "count": "3",
             "alive": 2, "dead": 1, "scope": "26xxx×3", "note": "測試"},
            path=self.hist)
        self.assertTrue(ok)
        after = self.hist.read_text(encoding="utf-8")
        # 新列在「執行批次」表尾
        self.assertIn("| 09-08 01:00 | daily.confirm | 3 | 2 | 1 | 26xxx×3 | 測試 |", after)
        # 表頭仍在
        self.assertIn("## 執行批次", after)
        self.assertIn("| 時間 | 腳本/來源", after)


class TestUpdateCoverage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cov = Path(self.tmp) / "coverage-map.md"
        shutil.copy(REPO / "data" / "scan-records" / "coverage-map.md", self.cov)

    def test_replaces_marker_block(self):
        ok = update_coverage("## 自動掃描回報\n\n- 26xxx 活 227", path=self.cov)
        self.assertTrue(ok)
        after = self.cov.read_text(encoding="utf-8")
        self.assertIn("- 26xxx 活 227", after)
        # 取代後重跑同內容 → 不 rewrite（無變化）
        ok2 = update_coverage("## 自動掃描回報\n\n- 26xxx 活 227", path=self.cov)
        self.assertFalse(ok2)

    def test_appends_when_no_marker(self):
        bare = Path(self.tmp) / "bare.md"
        bare.write_text("# 空檔\n", encoding="utf-8")
        ok = update_coverage("- 測試行", path=bare)
        self.assertTrue(ok)
        after = bare.read_text(encoding="utf-8")
        self.assertIn("<!-- auto-scan-start -->", after)
        self.assertIn("- 測試行", after)


if __name__ == "__main__":
    unittest.main()
