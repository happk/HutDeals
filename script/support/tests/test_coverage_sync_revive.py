"""HutDeals tests — merge_alive_records 復活清理（cb13be8-2，2026-10-26）。

守護：復活（dead→alive）清殘留 dead_since，與 daily.py confirm 復活路徑一致；
全新碼無 dead_since 可清（pop 冪等）。state 讀寫導向暫存檔，不碰真 scan_state.json。

執行：python -m unittest script.support.tests.test_coverage_sync_revive -v
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from script.lib.state import load_state, save_state  # noqa: E402
from script.scan.coverage_sync import merge_alive_records  # noqa: E402

REC = {"code": "26868", "m1_success": True, "title": "x", "at": "2026-10-26T00:00:00"}


class MergeAliveReviveTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "scan_state.json"

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, existing_codes: dict, source="test") -> dict:
        # load_state 的預設參數在 def 時綁定 STATE_PATH——patch 模組屬性無效，
        # 須直接換掉 coverage_sync 命名空間裡的 load_state；save_state 帶明確
        # path 引數（coverage_sync.STATE_PATH），patch 名稱即可
        save_state(self.path, {"codes": existing_codes})
        with mock.patch("script.scan.coverage_sync.STATE_PATH", self.path), \
             mock.patch("script.scan.coverage_sync.load_state",
                        lambda: load_state(self.path)):
            merge_alive_records([dict(REC)], source)
        return load_state(self.path)["codes"]["26868"]

    def test_revive_clears_dead_since(self):
        """dead 帶 dead_since → 收活後 status=alive 且 dead_since 已清。"""
        rec = self._run({"26868": {"firstSeen": "2026-09-01", "status": "dead",
                                   "dead_since": "2026-10-01", "title": "舊"}})
        self.assertEqual(rec["status"], "alive")
        self.assertNotIn("dead_since", rec)
        self.assertEqual(rec["firstSeen"], "2026-09-01")  # 既有碼保留 firstSeen
        self.assertEqual(rec["title"], "x")  # 內容欄位照常更新

    def test_new_code_has_no_dead_since(self):
        """全新碼入池：本來就沒有 dead_since，路徑冪等。"""
        rec = self._run({})
        self.assertEqual(rec["status"], "alive")
        self.assertNotIn("dead_since", rec)
        self.assertEqual(rec["firstSeen"], rec["lastSeen"])


if __name__ == "__main__":
    unittest.main()
