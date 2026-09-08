"""HutDeals tests — cmd_confirm 組分類(cat/groupTitle)含 None 不崩潰（2026-09-09）。

離線 mock：不打官網、不寫真 data 檔。守護：
- 官網回傳 items 比舊版多「無群組選項」(cat/groupTitle = None，如 26975 實況)，
  cats diff 排序不會 TypeError（修復：sorted(key=str)，None 與 str 不能直接比）。
- diff["cats"] 仍正常寫入 content_changes alerts、state 收新版 items。

執行：python -m unittest script.support.tests.test_confirm_cats_none -v
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from script.scan import daily  # noqa: E402


def _probe_rec(code):
    return {"code": code, "at": "t", "m1_success": True}


class ConfirmCatsNoneTest(unittest.TestCase):
    """cmd_confirm：新 items 比舊多出無群組選項 → 組分類含 None 仍不炸。"""

    def setUp(self):
        state = {"updatedAt": None, "codes": {
            "16010": {"status": "alive", "title": "標題", "price": 199,
                      "channels": [],
                      "items": [{"cat": "大比薩", "groupTitle": "group",
                                 "name": "x"}]},
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
        daily.probe_batch = lambda codes: ([_probe_rec("16010")], False)
        # 官網回傳：原本的有群組選項 + 一筆無群組選項（cat/groupTitle = None）
        daily.fetch_and_parse = lambda code, fetcher: {
            "meta": {"title": "標題", "price": 199, "msrp": None,
                     "channels": [], "desc_head": None, "desc": None},
            "items": [{"cat": "大比薩", "groupTitle": "group", "name": "x"},
                      {"cat": None, "groupTitle": None, "name": "加點選項"}]}

    def tearDown(self):
        for k, v in self._orig.items():
            setattr(daily, k, v)

    def test_cats_diff_with_none_does_not_crash(self):
        rc = daily.cmd_confirm(SimpleNamespace(limit=0))
        self.assertEqual(rc, 0)  # 不熔斷、不崩潰
        # cats 更動被記錄（新 items 多一組 None 分類）
        cats_diffs = [e for sec, e in self.alerts if sec == "content_changes"]
        self.assertTrue(any("16010" in str(e) and "cats" in str(e)
                            for e in cats_diffs))
        # state 已收新版 items（含 None 群組那筆）
        self.assertEqual(len(self.saved["codes"]["16010"]["items"]), 2)
        # diff 的 cats 值兩側皆已排序（list），不殘留 set
        for e in cats_diffs:
            for ch in e:
                if ch.get("code") == "16010":
                    self.assertIsInstance(ch["diff"]["cats"], list)
                    self.assertEqual(len(ch["diff"]["cats"]), 2)


if __name__ == "__main__":
    unittest.main()
