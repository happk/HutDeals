"""HutDeals tests — cmd_confirm 死活轉移 + 復活當日補 step_2（2026-09-08）。

離線 mock：不打官網、不寫真 data 檔。守護：
- 活碼 M1 失敗 → status=dead + 清殘留 step2_error/step2At（不再重試）
- 死碼 M1 成功 → 復活當日即補 step_2（內容不落後一天，87f70b4）
- step2 失敗（復活補抓）仍留痕 alerts（隔日 alive 迴圈重試）

執行：python -m unittest script.support.tests.test_confirm_revive -v
"""
import datetime as dt
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from script.scan import daily  # noqa: E402


def _probe_rec(code, verdict, at="t"):
    """probe_batch 結果列：verdict None/True/False。"""
    return {"code": code, "at": at, "m1_success": verdict}


def _content(title="標題", price=199):
    return {"meta": {"title": title, "price": price, "msrp": None,
                     "channels": [], "desc_head": None, "desc": None},
            "items": [{"cat": "大比薩", "groupTitle": "group", "name": "x"}]}


class ConfirmReviveTest(unittest.TestCase):
    """cmd_confirm 全流程（mock 外網與檔案），一次驗證三種轉移。"""

    def setUp(self):
        state = {"updatedAt": None, "codes": {
            "16001": {"status": "alive", "title": "舊標題", "price": 199,
                      "channels": [],
                      "items": [{"cat": "大比薩", "groupTitle": "group",
                                 "name": "x"}],
                      "step2_error": "昨日失敗殘留", "step2At": "2026-09-07T10:00:00"},
            "16002": {"status": "alive", "title": "會死的碼"},
            "16003": {"status": "dead", "dead_since": "2026-08-25",
                      "title": "復活前的舊內容"},
        }}
        self._orig = {k: getattr(daily, k) for k in (
            "load_state", "save_state", "update_alerts", "history_row",
            "merge_step2_failures", "probe_batch", "fetch_and_parse")}
        daily.load_state = lambda: state
        self.saved = {}
        daily.save_state = lambda path, s: self.saved.update(s)
        self.alerts = []
        daily.update_alerts = lambda section, entries: self.alerts.append(
            (section, entries))
        self.merges = []
        daily.merge_step2_failures = lambda fails, clears: self.merges.append(
            (list(fails), list(clears)))
        self.history = []
        daily.history_row = lambda *a: self.history.append(a)
        # 16001 活著內容更新；16002 活→死；16003 死→活（復活）
        daily.probe_batch = lambda codes: ([
            _probe_rec("16001", True), _probe_rec("16002", False),
            _probe_rec("16003", True)], False)
        daily.fetch_and_parse = lambda code, fetcher: (
            _content("新標題", 199) if code == "16001"
            else _content("復活補抓內容", 199) if code == "16003" else None)

    def tearDown(self):
        for k, v in self._orig.items():
            setattr(daily, k, v)

    def test_transitions(self):
        rc = daily.cmd_confirm(SimpleNamespace(limit=0))
        codes = self.saved["codes"]

        # 16001 活著：內容更新（新標題）、清昨日失敗殘留
        self.assertEqual(codes["16001"]["status"], "alive")
        self.assertEqual(codes["16001"]["title"], "新標題")
        self.assertNotIn("step2_error", codes["16001"])
        self.assertNotIn("step2At", codes["16001"])
        # 內容更動 alert 有 16001（title 差異）
        self.assertTrue(any("16001" in str(e)
                            for _, e in self.alerts))

        # 16002 活→死：翻死 + 起算觀察期 + 清殘留（即使原本無殘留也不誤留）
        self.assertEqual(codes["16002"]["status"], "dead")
        self.assertEqual(codes["16002"]["dead_since"],
                         dt.date.today().isoformat())

        # 16003 死→活：復活當日即補 step_2，內容不落後一天
        self.assertEqual(codes["16003"]["status"], "alive")
        self.assertNotIn("dead_since", codes["16003"])
        self.assertEqual(codes["16003"]["title"], "復活補抓內容")

        # merge_step2_failures(new_failures, clear_codes)：failures 空；
        # clear_codes = step2_ok(16001,16003) + step2_clear(16002)
        self.assertEqual(len(self.merges), 1)
        fails, clears = self.merges[0]
        self.assertEqual(fails, [])
        self.assertEqual(set(clears), {"16001", "16002", "16003"})

    def _failure_entries(self):
        # update_alerts 只收 content_changes/pending_empty；failures 走 merge
        return [f for fails, _ in self.merges for f in fails]

    def test_revive_step2_fail_leaves_trace(self):
        """死→活但 step_2 失敗：仍復活 + 留 step2_error 待隔日重試。"""
        daily.probe_batch = lambda codes: ([_probe_rec("16003", True)], False)
        daily.fetch_and_parse = lambda code, fetcher: None
        rc = daily.cmd_confirm(SimpleNamespace(limit=0))
        codes = self.saved["codes"]
        self.assertEqual(codes["16003"]["status"], "alive")
        self.assertNotIn("dead_since", codes["16003"])
        self.assertIn("step2_error", codes["16003"])
        fails = [f for fails, _ in self.merges for f in fails]
        self.assertEqual([f["code"] for f in fails], ["16003"])
        self.assertIn("error", fails[0])


if __name__ == "__main__":
    unittest.main()
