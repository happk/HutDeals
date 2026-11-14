"""HutDeals tests — ⑦b 節流呼叫計數（2026-11-14 節流統一，計畫 v6 Phase 1.2）。

守護：daily 四個抓詳情迴圈（confirm alive／confirm dead revive／explore fresh／
sample hits）逐碼呼叫 sleep_scan(i, <同一份字串清單>)——explore/sample 的
fresh/hits 是 rec dict 清單，須先轉字串清單（直接傳會 KeyError：d[:2] 以 slice
當 key 查找）。本檔後續收錄 Phase 3/4 的熔斷案例（cmd 三案例＋dead 防護等）。

離線 mock：不打官網、不寫真 data 檔（沿 test_confirm_revive 的屬性替換慣例；
⑦c 的 45s 休息以 mock.patch 攔截自動還原，零真實等待）。

執行：python -m unittest script.support.tests.test_step2_fuse -v
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from script.scan import daily  # noqa: E402


def _rec(code, verdict):
    """probe_batch 結果列。"""
    return {"code": code, "at": "t", "m1_success": verdict}


class ThrottleCallsTest(unittest.TestCase):
    """四迴圈的 sleep_scan 呼叫形狀：每碼一次、第二參數＝enumerate 同源字串清單。"""

    def setUp(self):
        self.state = {"updatedAt": None, "codes": {}}
        self._orig = {k: getattr(daily, k) for k in (
            "load_state", "save_state", "update_alerts", "history_row",
            "merge_step2_failures", "update_coverage", "probe_batch",
            "merge_alive_records", "step2_of", "sleep_scan", "BatchFetcher")}
        self.sleep_calls = []
        self._sampled = []
        daily.load_state = lambda: self.state
        daily.save_state = lambda path, s: None
        daily.update_alerts = lambda section, entries: None
        daily.history_row = lambda *a: None
        daily.merge_step2_failures = lambda fails, clears: None
        daily.update_coverage = lambda recs: None
        daily.merge_alive_records = lambda recs, source: (0, 0)
        daily.step2_of = lambda rec, fetcher: None  # 不打網路；回 None 走留痕分支
        daily.BatchFetcher = lambda *a, **kw: None
        daily.sleep_scan = lambda i, codes: self.sleep_calls.append(
            (i, list(codes)))

    def tearDown(self):
        for k, v in self._orig.items():
            setattr(daily, k, v)

    def _sample_probe(self, codes):
        """sample 用：記下抽出的碼清單，回「首碼命中」。"""
        self._sampled = list(codes)
        return [_rec(codes[0], True)], False

    @mock.patch("script.scan.daily.time.sleep")
    def test_confirm_alive_loop(self, _sleep):
        """alive 迴圈：每個抓詳情碼呼叫一次，第二參數＝alive 字串清單。"""
        self.state["codes"] = {"16001": {"status": "alive"},
                               "16002": {"status": "alive"}}
        daily.probe_batch = lambda codes: (
            [_rec("16001", True), _rec("16002", True)], False)
        rc = daily.cmd_confirm(SimpleNamespace(limit=0))
        self.assertEqual(rc, 0)
        self.assertEqual(self.sleep_calls, [(0, ["16001", "16002"]),
                                            (1, ["16001", "16002"])])

    @mock.patch("script.scan.daily.time.sleep")
    def test_confirm_dead_revive_loop(self, _sleep):
        """dead 迴圈：僅 revive 分支（會打 step2_of）呼叫，第二參數＝dead 字串清單。"""
        self.state["codes"] = {"16001": {"status": "alive"},
                               "16311": {"status": "dead"}}
        daily.probe_batch = lambda codes: (
            [_rec("16001", True), _rec("16311", True)], False)
        rc = daily.cmd_confirm(SimpleNamespace(limit=0))
        self.assertEqual(rc, 0)
        self.assertEqual(self.sleep_calls, [(0, ["16001"]), (0, ["16311"])])

    def test_explore_fresh_loop(self):
        """explore 迴圈：fresh（新活碼）逐碼呼叫，第二參數＝fresh 碼字串清單。"""
        daily.probe_batch = lambda codes: (
            [_rec("16002", True), _rec("16003", False)], False)
        rc = daily.cmd_explore(SimpleNamespace(limit=0))
        self.assertEqual(rc, 0)
        self.assertEqual(self.sleep_calls, [(0, ["16002"])])

    def test_sample_hits_loop(self):
        """sample 迴圈：hits（未知號段命中）逐碼呼叫，第二參數＝hits 碼字串清單。"""
        daily.probe_batch = self._sample_probe
        rc = daily.cmd_sample(SimpleNamespace(limit=0))
        self.assertEqual(rc, 0)
        self.assertEqual(self.sleep_calls, [(0, [self._sampled[0]])])


if __name__ == "__main__":
    unittest.main()
