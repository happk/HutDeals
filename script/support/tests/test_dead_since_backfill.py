"""HutDeals tests — cmd_confirm 對缺 dead_since 的 dead 落地補值（cb13be8-1，2026-10-26）。

離線 mock（同 test_confirm_revive 模式）：不打官網、不寫真 data 檔。系統性涵蓋補值的
完整輸入空間與副作用邊界：
- 補值觸發：欄位不存在／存在但 None（falsy 謂詞）→ 補今天、觀察窗重起算（days=0 不退役）
- 不覆蓋：已有有效日期者原值不動、滿 7 天照常退役
- 崩潰防護：None 形狀在舊碼會 fromisoformat(None) TypeError——補值後自癒
- 副作用邊界：alive 碼（含無 dead_since 的 654 筆同形狀）不流經 dead 分支不被補值；
  empty 碼不在 confirm 探測集合；alive 標死時由既有標死路徑寫 dead_since（不靠補值）
- 生命週期：補值 → （跨日）→ 滿 7 天退役轉 empty；期間復活則清欄位

執行：python -m unittest script.support.tests.test_dead_since_backfill -v
"""
import datetime as dt
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from script.scan import daily  # noqa: E402

TODAY = dt.date.today()
TODAY_S = TODAY.isoformat()
D8 = (TODAY - dt.timedelta(days=8)).isoformat()


def _rec(code, verdict, at="t"):
    return {"code": code, "at": at, "m1_success": verdict}


def _content(title="補抓內容"):
    return {"meta": {"title": title, "price": 199, "msrp": None,
                     "channels": [], "desc_head": None, "desc": None},
            "items": [{"cat": "大比薩", "groupTitle": "group", "name": "x"}]}


class DeadSinceBackfillTest(unittest.TestCase):
    """cmd_confirm 全流程 mock；state 覆蓋 dead_since 的全部形狀。"""

    def setUp(self):
        self.state = {"updatedAt": None, "codes": {
            # —— dead 三種缺值/有值形狀 ——
            "15140": {"status": "dead", "title": "遺留：欄位不存在"},       # absent
            "15260": {"status": "dead", "dead_since": None, "title": "遺留：None"},
            "15331": {"status": "dead", "dead_since": D8, "title": "已滿 7 天"},
            # —— 復活案例：缺欄位的 dead 探測成功 ——
            "16138": {"status": "dead", "title": "復活前的舊內容"},
            # —— alive 副作用邊界 ——
            "16136": {"status": "alive", "title": "活碼無 dead_since"},     # 670 筆同形狀
            "16137": {"status": "alive", "title": "會死的碼"},
            # —— empty 副作用邊界（confirm 不探）——
            "26999": {"status": "empty", "dead_since": D8, "title": "已退役"},
        }}
        self._orig = {k: getattr(daily, k) for k in (
            "load_state", "save_state", "update_alerts", "history_row",
            "merge_step2_failures", "update_coverage", "probe_batch",
            "fetch_and_parse")}
        daily.load_state = lambda: self.state
        self.saved = {}
        daily.save_state = lambda path, s: self.saved.update(s)
        daily.update_alerts = lambda section, entries: None
        daily.merge_step2_failures = lambda fails, clears: None
        daily.history_row = lambda *a: None
        daily.update_coverage = lambda recs: None
        self.probed: list[str] = []
        daily.probe_batch = self._probe_batch
        daily.fetch_and_parse = lambda code, fetcher: _content()

    def tearDown(self):
        for k, v in self._orig.items():
            setattr(daily, k, v)

    def _probe_batch(self, codes):
        self.probed = list(codes)
        verdict = {"15140": False, "15260": False, "15331": False,
                   "16136": True, "16137": False, "16138": True}
        return [_rec(c, verdict.get(c, False)) for c in codes], False

    def _run(self):
        return daily.cmd_confirm(SimpleNamespace(limit=0))

    def test_absent_backfilled_today_not_retired(self):
        """欄位不存在：補值=今天、days=0 不退役、status 維持 dead。"""
        self._run()
        c = self.saved["codes"]["15140"]
        self.assertEqual(c["dead_since"], TODAY_S)
        self.assertEqual(c["status"], "dead")

    def test_none_backfilled_no_crash(self):
        """存在但 None：補值今天且不炸（舊碼 fromisoformat(None) 會 TypeError）。"""
        self._run()
        c = self.saved["codes"]["15260"]
        self.assertEqual(c["dead_since"], TODAY_S)
        self.assertEqual(c["status"], "dead")

    def test_valid_date_not_overwritten_and_retires(self):
        """已有有效值：不覆蓋，滿 7 天照常退役轉 empty。"""
        self._run()
        c = self.saved["codes"]["15331"]
        self.assertEqual(c["dead_since"], D8)  # 原值不動
        self.assertEqual(c["status"], "empty")

    def test_absent_revived_clean(self):
        """缺欄位的 dead 探測成功：照常復活＋清欄位，補值不阻擋復活路徑。"""
        self._run()
        c = self.saved["codes"]["16138"]
        self.assertEqual(c["status"], "alive")
        self.assertNotIn("dead_since", c)
        self.assertEqual(c["title"], "補抓內容")

    def test_alive_never_backfilled(self):
        """alive 碼（無 dead_since 的 654 筆同形狀）不被補值：探測成功走 alive 分支。"""
        self._run()
        c = self.saved["codes"]["16136"]
        self.assertEqual(c["status"], "alive")
        self.assertNotIn("dead_since", c)

    def test_alive_death_uses_mark_dead_not_backfill(self):
        """alive→死由既有標死路徑寫 dead_since=today（補值非此路徑的依賴）。"""
        self._run()
        c = self.saved["codes"]["16137"]
        self.assertEqual(c["status"], "dead")
        self.assertEqual(c["dead_since"], TODAY_S)

    def test_empty_not_probed_not_touched(self):
        """empty 不在 confirm 探測集合（explore 的域），紀錄原樣。"""
        self._run()
        self.assertNotIn("26999", self.probed)
        c = self.saved["codes"]["26999"]
        self.assertEqual(c["status"], "empty")
        self.assertEqual(c["dead_since"], D8)

    def test_backfill_lifecycle_then_retire(self):
        """完整生命週期：首跑補值（不退役）→ 撥快 8 天再跑 → 退役轉 empty。"""
        self._run()
        self.assertEqual(self.saved["codes"]["15140"]["dead_since"], TODAY_S)
        self.assertEqual(self.saved["codes"]["15140"]["status"], "dead")
        # 模擬時間流逝：補值日撥到 8 天前（dt.date.today() 為真實時鐘，以資料撥快）
        self.state["codes"]["15140"]["dead_since"] = D8
        self.state["codes"]["15260"]["dead_since"] = D8
        self._run()
        self.assertEqual(self.saved["codes"]["15140"]["status"], "empty")
        self.assertEqual(self.saved["codes"]["15260"]["status"], "empty")

    def test_same_day_rerun_idempotent(self):
        """同日重跑：已補值者不重寫（值不變）、不誤退役。"""
        self._run()
        self._run()
        c = self.saved["codes"]["15140"]
        self.assertEqual(c["dead_since"], TODAY_S)
        self.assertEqual(c["status"], "dead")


if __name__ == "__main__":
    unittest.main()
