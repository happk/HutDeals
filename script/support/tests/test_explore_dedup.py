"""HutDeals tests — cmd_explore 對 confirm 去重（2026-09-09）。

離線 mock：不打官網、不寫真 data 檔。守護：
- explore 只探 confirm 沒確認的潛在碼位：status alive/dead 不探（confirm 當天探過）
- 當天才退役的 empty（dead_since=今天）不探（confirm 當天剛探過）
- 昨天的 empty 要探（explore 是空號復活的守望者）

執行：python -m unittest script.support.tests.test_explore_dedup -v
"""
import datetime as dt
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from script.scan import daily  # noqa: E402

# 讓 ACTIVE_RANGES 縮小成可測的小範圍，避免真的列出 2000 碼
daily.ACTIVE_RANGES = [(16000, 16002)]
RANGE_ALL = {"16000", "16001", "16002"}


class ExploreDedupTest(unittest.TestCase):
    def setUp(self):
        today = dt.date.today().isoformat()
        state = {"codes": {
            "16000": {"status": "alive"},               # confirm 探 → explore 剔
            "16001": {"status": "dead"},                # confirm 探 → explore 剔
            "16002": {"status": "empty",                # 今天退役 → 當天剔
                      "dead_since": today},
            "16999": {"status": "empty",                # 段外，不影響
                      "dead_since": "2020-01-01"},
        }}
        self._orig = {k: getattr(daily, k) for k in (
            "load_state", "save_state", "update_alerts", "history_row",
            "merge_alive_records", "merge_step2_failures", "update_coverage",
            "probe_batch")}
        daily.load_state = lambda: state
        self.saved = {}
        daily.save_state = lambda path, s: self.saved.update(s)
        daily.update_alerts = lambda *a, **k: None
        daily.history_row = lambda *a: None
        daily.merge_alive_records = lambda recs, src: (0, 0)
        daily.merge_step2_failures = lambda *a: None
        daily.update_coverage = lambda recs: None
        # 探測回報全部 m1_success=False（空號），focus 在「探了哪些碼」
        self.probed: list[str] = []
        def _probe(codes):
            self.probed.extend(codes)
            return ([{"code": c, "at": "t", "m1_success": False}
                     for c in codes], False)
        daily.probe_batch = _probe

    def tearDown(self):
        for k, v in self._orig.items():
            setattr(daily, k, v)

    def test_explore_dedups_confirm_codes(self):
        rc = daily.cmd_explore(SimpleNamespace(limit=0))
        self.assertEqual(rc, 0)
        # 16000(alive)/16001(dead)/16002(今天empty) 都被剔除 → 只探剩下的段位
        # 此測試 ACTIVE_RANGES=16000-16002，全被剔 → 探測清單為空
        self.assertEqual(self.probed, [])

    def test_previous_empty_is_probed(self):
        # 昨天的 empty（非當天退役）要在 explore 清單（盯復活）
        daily.load_state = lambda: {"codes": {
            "16000": {"status": "empty", "dead_since": "2020-01-01"}}}
        rc = daily.cmd_explore(SimpleNamespace(limit=0))
        self.assertEqual(rc, 0)
        self.assertEqual(set(self.probed), RANGE_ALL)


if __name__ == "__main__":
    unittest.main()
