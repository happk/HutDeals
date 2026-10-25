"""HutDeals tests — ingest_external 判死歸檔（2026-10-25）。

離線 mock：不打官網、不寫真 public 檔。守護：
- scan_state=dead/empty → 既有外部碼標 offline，offlineSince=dead_since（展示不分）
- 缺 dead_since 的遺留形狀 → fallback 券 lastSeen → 當天
- 不動的三種情況：state=alive、查無紀錄、非 verified-external（官網碼歸 merge 管）
- 冪等：同輸入跑兩次，第二次零翻轉
- 復活：舊條目 offline、state 翻 alive → main() 翻回 active 並清 offlineSince

執行：python -m unittest script.support.tests.test_ingest_offline -v
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from script.site import ingest_external  # noqa: E402


def _coupon(key="26910", status="active", last_seen="2026-09-30", **over):
    c = {"key": key, "code": key, "name": "測試券", "source": "verified-external",
         "status": status, "lastSeen": last_seen, "firstSeen": "2026-09-05"}
    c.update(over)
    return c


class MarkOfflineTest(unittest.TestCase):
    """_mark_offline_by_state：對帳三規則＋冪等。"""

    def test_dead_and_empty_both_offline_with_dead_since(self):
        coupons = {"26910": _coupon(), "26821": _coupon("26821")}
        state = {"26910": {"status": "dead", "dead_since": "2026-10-01"},
                 "26821": {"status": "empty", "dead_since": "2026-09-30"}}
        flipped = ingest_external._mark_offline_by_state(coupons, state, "2026-10-02")
        self.assertEqual(flipped, 2)
        for k, since in (("26910", "2026-10-01"), ("26821", "2026-09-30")):
            self.assertEqual(coupons[k]["status"], "offline")
            self.assertEqual(coupons[k]["offlineSince"], since)

    def test_legacy_missing_dead_since_falls_back(self):
        coupons = {"15140": _coupon("15140", last_seen="2026-09-04"),
                   "15260": _coupon("15260", last_seen=None)}
        state = {"15140": {"status": "dead"},  # 09-04 遺留形狀：缺 dead_since
                 "15260": {"status": "empty"}}
        ingest_external._mark_offline_by_state(coupons, state, "2026-10-25")
        self.assertEqual(coupons["15140"]["offlineSince"], "2026-09-04")  # 券 lastSeen
        self.assertEqual(coupons["15260"]["offlineSince"], "2026-10-25")  # 再沒有 → 當天

    def test_untouched_cases(self):
        alive_offline = _coupon("26100", status="offline", offlineSince="2026-09-30")
        no_record = _coupon("26200")
        official = _coupon("91113")
        official["source"] = None  # 官網碼：state 判死也不碰
        coupons = {"26100": alive_offline, "26200": no_record, "91113": official}
        state = {"26100": {"status": "alive"},        # 復活翻回是活碼迴圈的職責
                 "91113": {"status": "empty", "dead_since": "2026-10-01"}}
        flipped = ingest_external._mark_offline_by_state(coupons, state, "2026-10-25")
        self.assertEqual(flipped, 0)
        self.assertEqual(alive_offline["status"], "offline")       # 不動
        self.assertEqual(no_record["status"], "active")            # 查無紀錄不動
        self.assertEqual(official["status"], "active")             # 非 external 不動

    def test_idempotent_second_run_zero_flips(self):
        coupons = {"26910": _coupon()}
        state = {"26910": {"status": "empty", "dead_since": "2026-09-30"}}
        first = ingest_external._mark_offline_by_state(coupons, state, "2026-10-25")
        snapshot = dict(coupons["26910"])
        second = ingest_external._mark_offline_by_state(coupons, state, "2026-10-26")
        self.assertEqual((first, second), (1, 0))
        self.assertEqual(coupons["26910"], snapshot)  # 值不漂移（含換日重跑）


class MainReviveTest(unittest.TestCase):
    """main()：觀察期波動——判死標離線後掃號翻活，隔天翻回 active。"""

    def test_revive_flips_offline_back_to_active(self):
        state = {"codes": {"26910": {"status": "alive", "title": "復活券",
                                     "channels": [], "items": []}}}
        coupons = {"26910": _coupon("26910", status="offline",
                                    offlineSince="2026-09-30")}
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "scan_state.json"
            state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
            with mock.patch.object(ingest_external, "STATE_PATH", state_path), \
                 mock.patch.object(ingest_external.coupons_lib, "load_coupons_js",
                                   return_value=coupons), \
                 mock.patch.object(ingest_external.coupons_lib, "write_coupons_js") as wjs, \
                 mock.patch.object(ingest_external.coupons_lib, "write_coupons_full"):
                rc = ingest_external.main()
        self.assertEqual(rc, 0)
        written = wjs.call_args[0][0]
        revived = next(c for c in written if c["key"] == "26910")
        self.assertEqual(revived["status"], "active")
        self.assertNotIn("offlineSince", revived)


if __name__ == "__main__":
    unittest.main()
