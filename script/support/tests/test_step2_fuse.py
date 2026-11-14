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
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from script.lib import orderflow  # noqa: E402
from script.lib.orderflow import MARK_GARBAGE_PAGE  # noqa: E402
from script.scan import daily  # noqa: E402
from script.site import enrich_official  # noqa: E402


def _rec(code, verdict):
    """probe_batch 結果列。"""
    return {"code": code, "at": "t", "m1_success": verdict}


def _http_err(code):
    """最小可用 HTTPError（hdrs/fp 為 None；is_rate_limited 只看 code）。"""
    return urllib.error.HTTPError("https://www.pizzahut.com.tw/x", code,
                                  "mock", None, None)


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


class FusePathTest(unittest.TestCase):
    """③c cmd 層熔斷案例＋dead 迴圈防護（計畫 v6 Phase 3.5）。"""

    def setUp(self):
        self.state = {"updatedAt": None, "codes": {}}
        self.saved = {}
        self.calls: list[str] = []
        self._orig = {k: getattr(daily, k) for k in (
            "load_state", "save_state", "update_alerts", "history_row",
            "merge_step2_failures", "update_coverage", "probe_batch",
            "merge_alive_records", "step2_of", "sleep_scan", "BatchFetcher",
            "fetch_and_parse")}
        daily.load_state = lambda: self.state
        daily.save_state = lambda path, s: self.saved.update(s)
        daily.update_alerts = lambda section, entries: None
        daily.history_row = lambda *a: None
        daily.merge_step2_failures = lambda fails, clears: None
        daily.update_coverage = lambda recs: None
        daily.merge_alive_records = lambda recs, source: (0, 0)
        daily.BatchFetcher = lambda *a, **kw: None
        daily.sleep_scan = lambda i, codes: None

    def tearDown(self):
        for k, v in self._orig.items():
            setattr(daily, k, v)

    def _fake_step2(self, behavior):
        """daily.fetch_and_parse 換成可編程替身（step2_of 為真實版，驗 ③b 貫通）。"""
        def _fap(code, fetcher=None):
            self.calls.append(code)
            return behavior(code)
        daily.fetch_and_parse = _fap

    @mock.patch("script.scan.daily.time.sleep")
    def test_http_fuse_exits_3(self, _sleep):
        """HTTP 形態熔斷（403）：cmd_confirm 回 3（②＋③c 貫通），只打一碼即停。"""
        self.state["codes"] = {"16001": {"status": "alive"}}
        daily.probe_batch = lambda codes: ([_rec("16001", True)], False)

        def _boom(code):
            raise _http_err(403)
        self._fake_step2(_boom)
        rc = daily.cmd_confirm(SimpleNamespace(limit=0))
        self.assertEqual(rc, 3)
        self.assertEqual(self.calls, ["16001"])

    @mock.patch("script.scan.daily.time.sleep")
    def test_runtime_fuse_exits_3(self, _sleep):
        """錯誤頁形態（前置三關鍵字 RuntimeError）：③a→③b→③c 三層全通 → 回 3。"""
        self.state["codes"] = {"16001": {"status": "alive"}}
        daily.probe_batch = lambda codes: ([_rec("16001", True)], False)

        def _boom(code):
            raise RuntimeError("step_1_update 失敗: <html>busy page</html>")
        self._fake_step2(_boom)
        rc = daily.cmd_confirm(SimpleNamespace(limit=0))
        self.assertEqual(rc, 3)
        self.assertEqual(self.calls, ["16001"])

    @mock.patch("script.scan.daily.time.sleep")
    def test_non_fuse_runtime_recorded(self, _sleep):
        """非熔斷 RuntimeError：語意不變——回 0、step2_error 留痕（既有守門員同向）。"""
        self.state["codes"] = {"16001": {"status": "alive"}}
        daily.probe_batch = lambda codes: ([_rec("16001", True)], False)

        def _boom(code):
            raise RuntimeError("boom")
        self._fake_step2(_boom)
        rc = daily.cmd_confirm(SimpleNamespace(limit=0))
        self.assertEqual(rc, 0)
        self.assertIn("step2_error", self.saved["codes"]["16001"])

    @mock.patch("script.scan.daily.time.sleep")
    def test_dead_revive_skipped_when_blown(self, _sleep):
        """dead 防護：alive 熔斷後，revive 分支只做判定不做補抓（③c）。"""
        self.state["codes"] = {"16001": {"status": "alive"},
                               "16311": {"status": "dead"}}
        daily.probe_batch = lambda codes: (
            [_rec("16001", True), _rec("16311", True)], False)

        def _boom(code):
            raise _http_err(403)
        self._fake_step2(_boom)
        rc = daily.cmd_confirm(SimpleNamespace(limit=0))
        self.assertEqual(rc, 3)
        # 復活判定照做（status 翻 alive）；補抓沒打（fetch_and_parse 只被 alive 碼叫一次）
        self.assertEqual(self.saved["codes"]["16311"]["status"], "alive")
        self.assertEqual(self.calls, ["16001"])

    @mock.patch("script.scan.daily.time.sleep")
    def test_garbage_intercepted_non_whitelist(self, _sleep):
        """⑥a′：繞過頁（meta 正常但 items=None）在上游攔下 → step2_error＝疑似垃圾頁。"""
        self.state["codes"] = {"16001": {"status": "alive"}}
        daily.probe_batch = lambda codes: ([_rec("16001", True)], False)
        daily.fetch_and_parse = lambda code, fetcher=None: {
            "meta": {"title": "標題", "price": 199}, "items": None,
            "struct": None, "html": "<html>x</html>"}
        rc = daily.cmd_confirm(SimpleNamespace(limit=0))
        self.assertEqual(rc, 0)
        rec = self.saved["codes"]["16001"]
        self.assertEqual(rec.get("step2_error"), MARK_GARBAGE_PAGE)
        self.assertNotIn("contentChangedAt", rec)  # 假成功不寫內容不告警

    @mock.patch("script.scan.daily.time.sleep")
    def test_garbage_whitelist_passthrough(self, _sleep):
        """⑥a′：白名單碼（15596，items=None 的正常無選項券）照常成功不攔。"""
        self.state["codes"] = {"15596": {"status": "alive"}}
        daily.probe_batch = lambda codes: ([_rec("15596", True)], False)
        daily.fetch_and_parse = lambda code, fetcher=None: {
            "meta": {"title": "標題", "price": 199}, "items": None,
            "struct": None, "html": "<html>x</html>"}
        rc = daily.cmd_confirm(SimpleNamespace(limit=0))
        self.assertEqual(rc, 0)
        self.assertNotIn("step2_error", self.saved["codes"]["15596"])

    @mock.patch("script.scan.daily.time.sleep")
    def test_parse_streak_aborts_at_3(self, _sleep):
        """⑥b 形態一：連續 3 碼 fetch/parse 失敗 → 第 3 碼熔斷回 3。"""
        codes3 = ("16001", "16002", "16003")
        self.state["codes"] = {c: {"status": "alive"} for c in codes3}
        daily.probe_batch = lambda cs: ([_rec(c, True) for c in codes3], False)
        self._fake_step2(lambda code: None)
        rc = daily.cmd_confirm(SimpleNamespace(limit=0))
        self.assertEqual(rc, 3)
        self.assertEqual(self.calls, list(codes3))  # 第 3 碼觸發即停

    @mock.patch("script.scan.daily.time.sleep")
    def test_parse_streak_reset_by_success(self, _sleep):
        """⑥b 形態二：2 碼失敗＋真成功 → 歸零不熔斷，回 0。"""
        codes3 = ("16001", "16002", "16003")
        self.state["codes"] = {c: {"status": "alive"} for c in codes3}
        daily.probe_batch = lambda cs: ([_rec(c, True) for c in codes3], False)
        daily.fetch_and_parse = lambda code, fetcher=None: (
            None if code in ("16001", "16002")
            else {"meta": {"title": "t", "price": 1}, "items": [],
                  "struct": None, "html": "<html>x</html>"})
        rc = daily.cmd_confirm(SimpleNamespace(limit=0))
        self.assertEqual(rc, 0)


class GateTest(unittest.TestCase):
    """⑥a 閘門（orderflow 層）：mock 只放下游回傳值（測試層級三規則）。"""

    def test_non_menu_page_rejected(self):
        """文字版頁（is_menu_page 不過）即使 parse 回成功 dict 也判失敗：None＋3 發。"""

        class _Short:
            def __init__(self):
                self.calls = 0

            def fetch(self, code):
                self.calls += 1
                return "<html>" + "x" * 1000 + "</html>"  # 短且無 ctidss＝非選單版

        fetcher = _Short()
        with mock.patch.object(
                orderflow, "parse_menu_html",
                return_value={"meta": {"title": "垃圾"}, "items": None,
                              "struct": None}) as fake_parse:
            r = orderflow.fetch_and_parse("16001", fetcher, sleep=lambda _: None)
        self.assertIsNone(r)                 # ⑥a：不放行假成功
        self.assertEqual(fetcher.calls, 3)   # 門檻失敗＝瞬時失敗語意（重試 3 次）
        self.assertEqual(fake_parse.call_count, 3)


class EnrichFuseTest(unittest.TestCase):
    """enrich 端：③c 熔斷形態中止＋⑥b 連續解析失敗計數（Phase 3.4／4.4）。"""

    def setUp(self):
        self.enrich = enrich_official
        self._orig = {k: getattr(enrich_official, k) for k in (
            "load_coupons_js", "write_coupons_js", "write_coupons_full",
            "merge_step2_failures", "fetch_and_parse", "sleep_scan")}
        enrich_official.load_coupons_js = lambda: {
            c: {"code": c, "name": f"券{c}"} for c in ("91001", "91002", "91003")}
        enrich_official.write_coupons_js = lambda rows, stamp: None
        enrich_official.write_coupons_full = lambda rows, stamp: None
        enrich_official.merge_step2_failures = lambda fails, clears: None
        enrich_official.sleep_scan = lambda i, codes: None
        self.calls: list[str] = []

    def tearDown(self):
        for k, v in self._orig.items():
            setattr(self.enrich, k, v)

    def test_parse_streak_aborts(self):
        """3 碼連續 None → ⑥b 熔斷，main() 回 3。"""
        def _fap(code, fetcher=None):
            self.calls.append(code)
            return None
        self.enrich.fetch_and_parse = _fap
        rc = self.enrich.main()
        self.assertEqual(rc, 3)
        self.assertEqual(self.calls, ["91001", "91002", "91003"])

    def test_runtime_fuse_aborts(self):
        """前置關鍵字 RuntimeError → ③c 中止補全，回 3。"""
        def _fap(code, fetcher=None):
            self.calls.append(code)
            raise RuntimeError("step_1_update 失敗: busy page")
        self.enrich.fetch_and_parse = _fap
        rc = self.enrich.main()
        self.assertEqual(rc, 3)
        self.assertEqual(self.calls, ["91001"])


if __name__ == "__main__":
    unittest.main()
