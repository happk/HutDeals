"""HutDeals tests — merge_alive_records 新碼入池才寫 lastChangedAt（2026-09-13）。

離線 mock：不打官網、不寫真 data 檔。守護：
- 有新碼（added>0）→ lastChangedAt 抄本次 updatedAt（admin 上次更動時間用）
- 純更新既有碼（added=0）→ lastChangedAt 不動
- 空號（m1_success=False）不入 state、不觸發寫入

執行：python -m unittest script.support.tests.test_last_changed_at -v
"""
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from script.scan import coverage_sync  # noqa: E402


class MergeLastChangedTest(unittest.TestCase):
    """merge_alive_records 的 lastChangedAt 寫入規則（與 confirm 同規則）。"""

    def setUp(self):
        self.state = {"updatedAt": None, "codes": {
            "16001": {"status": "alive", "firstSeen": "2026-09-01",
                      "lastSeen": "2026-09-01", "title": "舊標題"}}}
        self._orig = {k: getattr(coverage_sync, k)
                      for k in ("load_state", "save_state", "STATE_PATH")}
        coverage_sync.load_state = lambda: self.state
        self.saved = {}
        coverage_sync.save_state = lambda path, s: self.saved.update(s)

    def tearDown(self):
        for k, v in self._orig.items():
            setattr(coverage_sync, k, v)

    def test_new_code_sets_last_changed(self):
        rec = {"code": "26999", "at": "2026-09-13T10:00:00",
               "m1_success": True, "title": "新碼"}
        added, updated = coverage_sync.merge_alive_records([rec], "test")
        self.assertEqual((added, updated), (1, 0))
        self.assertEqual(self.saved["lastChangedAt"], self.saved["updatedAt"])

    def test_update_only_keeps_last_changed(self):
        self.state["lastChangedAt"] = "2026-09-10T09:00:00"
        rec = {"code": "16001", "at": "2026-09-13T10:00:00",
               "m1_success": True, "title": "換標題"}
        added, updated = coverage_sync.merge_alive_records([rec], "test")
        self.assertEqual((added, updated), (0, 1))
        self.assertEqual(self.saved["lastChangedAt"], "2026-09-10T09:00:00")

    def test_empty_code_not_counted(self):
        rec = {"code": "26998", "at": "2026-09-13T10:00:00", "m1_success": False}
        added, updated = coverage_sync.merge_alive_records([rec], "test")
        self.assertEqual((added, updated), (0, 0))
        self.assertNotIn("lastChangedAt", self.saved)


if __name__ == "__main__":
    unittest.main()
