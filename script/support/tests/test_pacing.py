"""HutDeals tests — sleep_scan 參數行為（修復⑦a，2026-11-14 節流統一）。

守護（計畫 v6 Phase 1.4）：每發 base 1.0＋U(0,2)、號段等待停用
（DEFAULT_SEG_GAP=0.0）、每 50 發中場 30s×U(0.8,1.5)、末碼不睡；
顯式傳 seg_gap 仍有效（CLI 相容——scan_probe/scan_run 的 --seg-gap
傳 args.seg_gap，常數停用≠參數失效）。
time.sleep 以 mock.patch 攔截（context 自動還原，零真實等待）。

執行：python -m unittest script.support.tests.test_pacing -v
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from script.lib.pacing import sleep_scan  # noqa: E402


def _delays(fn):
    """攔 pacing 模組的 time.sleep（mock.patch 自動還原），回延遲清單。"""
    with mock.patch("script.lib.pacing.time.sleep") as fake_sleep:
        fn()
    return [c.args[0] for c in fake_sleep.call_args_list]


class TestSleepScanDefaults(unittest.TestCase):
    """⑦a 預設參數行為（M1/step2/enrich 同套）。"""

    def test_per_call_range_and_last_code(self):
        """每發延遲 ∈ [1.0, 3.0]（base 1.0＋U(0,2)）；末碼不睡。"""
        codes = [f"16{i:03d}" for i in range(10)]
        delays = _delays(lambda: [sleep_scan(i, codes) for i in range(10)])
        self.assertEqual(len(delays), 9)  # 第 10 發（末碼）不睡
        for d in delays:
            self.assertGreaterEqual(d, 1.0)
            self.assertLessEqual(d, 3.0)

    def test_base_is_one(self):
        """預設 base＝1.0（⑦ 整體減半——防止悄悄回調 2.0）。"""
        delays = _delays(lambda: sleep_scan(0, ["16000", "16001"], jitter=0.0))
        self.assertEqual(delays, [1.0])

    def test_no_seg_gap(self):
        """跨號段不加成（DEFAULT_SEG_GAP=0.0 停用）——回歸 15.0 必炸出 3.0 上限。"""
        delays = _delays(lambda: sleep_scan(1, ["16999", "26000", "26001"]))
        self.assertEqual(len(delays), 1)
        self.assertGreaterEqual(delays[0], 1.0)
        self.assertLessEqual(delays[0], 3.0)

    def test_break_every_50(self):
        """第 50 發追加中場休息 ∈ [24, 45]（30×U(0.8,1.5)）。"""
        codes = [f"16{i:03d}" for i in range(51)]
        delays = _delays(lambda: [sleep_scan(i, codes) for i in range(51)])
        self.assertEqual(len(delays), 51)  # 50 主間隔＋第 50 發的中場；末碼不睡
        self.assertGreaterEqual(delays[49], 1.0)
        self.assertLessEqual(delays[49], 3.0)    # 第 50 發主間隔
        self.assertGreaterEqual(delays[50], 24.0)
        self.assertLessEqual(delays[50], 45.0)   # 中場追加
        for d in delays[:49]:
            self.assertGreaterEqual(d, 1.0)
            self.assertLessEqual(d, 3.0)


class TestSegGapExplicit(unittest.TestCase):
    """seg_gap 顯式傳值仍有效（CLI 相容）。"""

    def test_explicit_seg_gap_adds(self):
        delays = _delays(lambda: sleep_scan(1, ["16999", "26000", "26001"],
                                            sleep=2.0, jitter=0.0, seg_gap=15.0))
        self.assertEqual(len(delays), 1)
        self.assertGreaterEqual(delays[0], 9.5)   # 2.0＋15×0.5
        self.assertLessEqual(delays[0], 24.5)     # 2.0＋15×1.5


if __name__ == "__main__":
    unittest.main()
