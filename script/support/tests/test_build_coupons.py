"""HutDeals build_coupons 測試(unittest,無外部依賴)。

執行:python -m unittest discover -s script/tests -v
"""

import datetime as dt
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from script.lib.coupons import compact_coupon_items, load_coupons_js, now_stamp, write_coupons_js  # noqa: E402
from script.site.build_coupons import (  # noqa: E402
    build_tags,
    enrich,
    extract_coupon_price,
    extract_order_type,
    merge,
)
from script.site.fetch_promos import parse_page  # noqa: E402
from script.site import build_coupons as bc  # noqa: E402

TEST_DIR = Path(__file__).resolve().parent
FIXTURE = TEST_DIR / "fixtures" / "plu_pdpop.html"
TAGS = json.loads((TEST_DIR.parents[1] / "site" / "tags.json").read_text(encoding="utf-8"))



class TestPriceExtraction(unittest.TestCase):
    def test_price_in_name(self):
        price, note = extract_coupon_price("93034大比薩送副食/飲料$198", "-13吋大比薩1個")
        self.assertEqual(price, 198)
        self.assertIsNone(note)

    def test_price_with_note(self):
        price, note = extract_coupon_price("開學優惠！小比薩+烤雞買1送1", "指定口味小比薩+BBQ烤雞 買一送一 $639起")
        self.assertEqual(price, 639)
        self.assertEqual(note, "起")

    def test_no_price(self):
        price, note = extract_coupon_price("平日外帶限定- 私廚系列單點6折", "-13吋大比薩1個,私廚頂級美味")
        self.assertIsNone(price)
        self.assertIsNone(note)

    def test_name_wins_over_description_and_min(self):
        price, _ = extract_coupon_price("雙人餐$499", "單點價$520,加購$550")
        self.assertEqual(price, 499)


class TestOrderType(unittest.TestCase):
    def test_app(self):
        self.assertEqual(extract_order_type("APP專屬-個人比薩3個 $259", ""), "APP專屬")

    def test_delivery(self):
        self.assertEqual(extract_order_type("外送限定-94700單點大比薩7折", ""), "外送")

    def test_takeout(self):
        self.assertEqual(extract_order_type("93020-外帶買一送五", ""), "外帶")

    def test_none(self):
        self.assertIsNone(extract_order_type("中秋小套餐$599起", ""))


class TestTags(unittest.TestCase):
    def test_basic_tags(self):
        tags = build_tags("93020-外帶買一送五", "外帶買大比薩,送2個小比薩+副食5選2+可樂1.25L", TAGS)
        self.assertIn("比薩", tags)
        self.assertIn("買一送一", tags)
        self.assertIn("飲料", tags)

    def test_no_match(self):
        self.assertEqual(build_tags("某某活動", "內容毫無關鍵字", TAGS), [])


class TestEnrich(unittest.TestCase):
    def test_enrich_shape(self):
        coupon = enrich(
            {"source": "pdpop", "code": "93034", "name": "93034大比薩送副食/飲料$198",
             "description": "-13吋大比薩1個,再送副食/飲料三選一!", "image": "x.jpg",
             "category": "神級優惠3折起"},
            TAGS,
        )
        self.assertEqual(coupon["key"], "93034")
        self.assertEqual(coupon["price"], 198)
        self.assertIsNone(coupon["orderType"])  # 名稱與敘述皆無外帶/外送/APP 字樣
        self.assertEqual(extract_order_type("93020-外帶買一送五", ""), "外帶")
        self.assertIn("比薩", coupon["tags"])
        self.assertTrue(coupon["orderUrl"].startswith("https://www.pizzahut.com.tw/"))

    def test_enrich_without_code_uses_pid(self):
        coupon = enrich({"source": "promotion_list", "code": None, "id": "17904", "name": "外帶買一送五"}, TAGS)
        self.assertEqual(coupon["key"], "pid:17904")


class TestParseFixture(unittest.TestCase):
    """用真實官網回應當 fixture,確保解析器對變體 A markup 有效。"""

    def test_fixture_items(self):
        html = FIXTURE.read_text(encoding="utf-8")
        items = parse_page(html)
        self.assertTrue(len(items) >= 20, f"expected >=20 items, got {len(items)}")
        codes = {it["code"] for it in items}
        self.assertIn("93034", codes)
        self.assertIn("93020", codes)
        first = next(it for it in items if it["code"] == "93034")
        self.assertIn("大比薩", first["name"])
        self.assertEqual(first["category"], "神級優惠3折起")
        self.assertTrue(all(it["name"] for it in items))


class TestMerge(unittest.TestCase):
    def setUp(self):
        self.coupon_a = enrich({"source": "pdpop", "code": "93034", "name": "93034大比薩送副食/飲料$198"}, TAGS)
        self.coupon_b = enrich({"source": "pdpop", "code": "93020", "name": "93020-外帶買一送五"}, TAGS)

    def test_new_and_updated(self):
        existing = {self.coupon_a["key"]: dict(self.coupon_a, firstSeen="2026-09-01", lastSeen="2026-09-01", status="active")}
        merged, stats = merge(existing, [dict(self.coupon_a), dict(self.coupon_b)], "2026-09-03")
        keys = {c["key"] for c in merged}
        self.assertEqual(keys, {"93034", "93020"})
        a = next(c for c in merged if c["key"] == "93034")
        self.assertEqual(a["firstSeen"], "2026-09-01")
        self.assertEqual(a["lastSeen"], "2026-09-03")
        self.assertEqual(stats["new"], 1)
        self.assertEqual(stats["updated"], 1)

    def test_went_offline(self):
        existing = {c["key"]: dict(c, firstSeen="2026-09-01", lastSeen="2026-09-01", status="active")
                    for c in (self.coupon_a, self.coupon_b)}
        merged, stats = merge(existing, [dict(self.coupon_a)], "2026-09-03")
        b = next(c for c in merged if c["key"] == "93020")
        self.assertEqual(b["status"], "offline")
        self.assertEqual(b["offlineSince"], "2026-09-03")
        self.assertEqual(stats["went_offline"], 1)

    def test_revived(self):
        offline = dict(self.coupon_b, status="offline", offlineSince="2026-09-02", firstSeen="2026-09-01")
        merged, stats = merge({"93020": offline}, [dict(self.coupon_b)], "2026-09-03")
        self.assertEqual(merged[0]["status"], "active")
        self.assertNotIn("offlineSince", merged[0])
        self.assertEqual(stats["revived"], 1)

    def test_dropped_after_keep_days(self):
        offline = dict(self.coupon_b, status="offline", offlineSince="2026-06-01", firstSeen="2026-06-01")
        merged, stats = merge({"93020": offline}, [dict(self.coupon_a)], "2026-09-03")
        self.assertNotIn("93020", {c["key"] for c in merged})
        self.assertEqual(stats["dropped"], 1)

    def test_offline_within_keep_days_kept(self):
        offline = dict(self.coupon_b, status="offline", offlineSince="2026-08-20", firstSeen="2026-08-01")
        merged, _ = merge({"93020": offline}, [dict(self.coupon_a)], "2026-09-03")
        self.assertIn("93020", {c["key"] for c in merged})

    def test_sort_null_price_last(self):
        a = dict(self.coupon_a, price=198)          # 93034
        b = dict(self.coupon_b, price=None)         # 93020
        merged, _ = merge({}, [b, a], "2026-09-03")
        self.assertEqual([c["key"] for c in merged], ["93034", "93020"])


class TestMergeInherit(unittest.TestCase):
    """c5d1634-1（2026-10-26）：merge 繼承 enrich 補全欄位。

    欄位集合經 exp_prob/2026-10-26_merge-inherit-fix/probe_fields.py 對當前資料實測：
    items＋flavorSets（同進同出，flavorIdx 指向 flavorSets）、units、msrp、
    orderType（防禦名稱改版邊角）＋orderUrl（cno 直連，舊者勝出）。
    """

    def setUp(self):
        self.shell = enrich({"source": "pdpop", "code": "93034",
                             "name": "93034大比薩送副食/飲料$198"}, TAGS)
        self.items = [
            {"text": "四小福", "group": "main", "groupIdx": 1, "priceAdd": 0, "flavorIdx": 0},
            {"text": "可樂", "group": "second", "groupIdx": 1, "priceAdd": 0, "flavorIdx": None},
        ]

    def _old(self, **extra):
        base = dict(self.shell, firstSeen="2026-09-01", lastSeen="2026-09-02", status="active")
        base.update(extra)
        return base

    def test_inherits_all_fill_fields(self):
        old = self._old(items=list(self.items),
                        flavorSets=[[{"name": "鬆厚", "priceAdd": 0}]],
                        units=[{"group": "main", "groupIdx": 1, "cats": ["小比薩"]}],
                        msrp=456, orderType="外帶/外送",
                        orderUrl="https://www.pizzahut.com.tw/order/?mode=step_2&type_id=1025&cno=93034")
        merged, _ = merge({"93034": old}, [dict(self.shell)], "2026-10-26")
        c = merged[0]
        self.assertEqual(c["items"], self.items)
        self.assertEqual(c["flavorSets"], [[{"name": "鬆厚", "priceAdd": 0}]])
        self.assertEqual(c["units"], [{"group": "main", "groupIdx": 1, "cats": ["小比薩"]}])
        self.assertEqual(c["msrp"], 456)
        self.assertEqual(c["orderType"], "外帶/外送")
        self.assertIn("cno=93034", c["orderUrl"])

    def test_items_without_flavor_sets_is_legal(self):
        # 實況形狀（probe_fields：5 張）：items 候選全無口味 → 無 flavorSets。
        # 繼承 items 不得無中生有 flavorSets、也不得因此丟 items。
        items = [{"text": "夏威夷比薩", "group": "main", "groupIdx": 1,
                  "priceAdd": 0, "flavorIdx": None}]
        merged, _ = merge({"93034": self._old(items=items)}, [dict(self.shell)], "2026-10-26")
        self.assertEqual(merged[0]["items"], items)
        self.assertNotIn("flavorSets", merged[0])

    def test_new_value_wins(self):
        # 防禦：未來列表若開始供應欄位，新值不被舊值覆蓋（繼承只在殼缺時墊底）
        shell = dict(self.shell, orderType="外送")
        merged, _ = merge({"93034": self._old(orderType="外帶")}, [shell], "2026-10-26")
        self.assertEqual(merged[0]["orderType"], "外送")

    def test_name_change_drops_parsed_type_inherits_old(self):
        # 名稱改版拿掉通路字樣 → 殼不自帶 orderType → 繼承舊值（實測 0 張觸發的防禦邊角）
        shell = enrich({"source": "pdpop", "code": "93034", "name": "93034 歡樂分享餐"}, TAGS)
        self.assertIsNone(shell.get("orderType"))
        merged, _ = merge({"93034": self._old(orderType="外帶")}, [dict(shell)], "2026-10-26")
        self.assertEqual(merged[0]["orderType"], "外帶")

    def test_new_coupon_no_inherit(self):
        merged, stats = merge({}, [dict(self.shell)], "2026-10-26")
        self.assertNotIn("items", merged[0])
        self.assertNotIn("flavorSets", merged[0])
        self.assertEqual(stats["new"], 1)

    def test_revived_keeps_fill(self):
        old = self._old(status="offline", offlineSince="2026-10-01",
                        items=list(self.items), msrp=500)
        merged, stats = merge({"93034": old}, [dict(self.shell)], "2026-10-26")
        self.assertEqual(merged[0]["status"], "active")
        self.assertEqual(merged[0]["items"], self.items)
        self.assertEqual(merged[0]["msrp"], 500)
        self.assertEqual(stats["revived"], 1)

    def test_external_branch_untouched(self):
        # 外部碼不在官網 new_coupons → 走 kept-not-seen 原樣保留分支，不進繼承邏輯
        ext = {"key": "26868", "code": "26868", "name": "x", "source": "verified-external",
               "items": list(self.items), "status": "active",
               "firstSeen": "2026-09-01", "lastSeen": "2026-09-02"}
        merged, _ = merge({"26868": ext}, [dict(self.shell)], "2026-10-26")
        e = next(c for c in merged if c["key"] == "26868")
        self.assertEqual(e["items"], self.items)
        self.assertEqual(e["source"], "verified-external")

    def test_order_url_old_wins_over_generic(self):
        old = self._old(orderUrl="https://www.pizzahut.com.tw/order/?mode=step_2&type_id=1025&cno=93034")
        merged, _ = merge({"93034": old}, [dict(self.shell)], "2026-10-26")
        self.assertIn("cno=93034", merged[0]["orderUrl"])

    def test_inherit_roundtrip_preserves_flavor_sets(self):
        # 繼承(compact 格式) → write_coupons_js → load：flavorIdx 仍指向有效 flavorSets
        old = self._old(items=list(self.items),
                        flavorSets=[[{"name": "鬆厚", "priceAdd": 0}]])
        merged, _ = merge({"93034": old}, [dict(self.shell)], "2026-10-26")
        tmp = REPO / "public" / "coupons.inherit-test.js"
        write_coupons_js(merged, "2026-10-26T00:00:00", path=tmp)
        loaded = load_coupons_js(tmp)
        it = loaded["93034"]["items"][0]
        fs = loaded["93034"]["flavorSets"]
        self.assertEqual(it["flavorIdx"], 0)
        self.assertLess(it["flavorIdx"], len(fs))
        tmp.unlink()


class TestNowStamp(unittest.TestCase):
    """last_update＝執行時帶本地時區的 aware 字串（2026-10-26，使用者指示：不能假設
    工作機在 +8 時區）。歷史事故：本機重建寫 naive 台北時間，前端視為 UTC 再 +8h
    顯示未來時間（可信度事故）。"""

    def test_format_aware(self):
        # aware ISO 秒級：帶執行環境時差後綴（+08:00／+00:00／-05:00…）
        self.assertRegex(now_stamp(), r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$")

    def test_instant_correct_in_any_timezone(self):
        # 解析後的真實時刻與 UTC 現在差 < 5 分鐘——時區無關，任何機器上必過；
        # 若退回 naive 本地時鐘寫法，非 UTC 機器上必差數小時、此測試必抓。
        s = dt.datetime.fromisoformat(now_stamp())
        self.assertIsNotNone(s.utcoffset())
        now_utc = dt.datetime.now(dt.timezone.utc)
        self.assertLess(abs((s - now_utc).total_seconds()), 300)

    def test_offset_is_machine_local(self):
        # 後綴時差＝執行機器的實際時區（自描述；CI 為 +00:00）
        s = dt.datetime.fromisoformat(now_stamp())
        self.assertEqual(s.utcoffset(), dt.datetime.now().astimezone().utcoffset())


class TestCouponsJsRoundtrip(unittest.TestCase):
    def test_write_and_load(self):
        tmp = REPO / "public" / "coupons.test.js"
        base = enrich({"code": "93034", "name": "93034大比薩$198"}, TAGS)
        coupons = [dict(base, key="93034", firstSeen="2026-09-03", lastSeen="2026-09-03", status="active")]
        write_coupons_js(coupons, "2026-09-03T08:00:00", path=tmp)
        loaded = load_coupons_js(tmp)
        self.assertIn("93034", loaded)
        self.assertEqual(loaded["93034"]["price"], 198)
        tmp.unlink()

    def test_load_missing_file(self):
        self.assertEqual(load_coupons_js(REPO / "public" / "definitely-missing.js"), {})


class TestCompactIdempotent(unittest.TestCase):
    """compact_coupon_items 冪等性（2026-09-08 修 flavorSets 丟失 bug）。"""

    def test_full_format_compacts(self):
        # scan_state 完整格式(帶 flavors) → compact 產生 flavorSets/flavorIdx
        coup = {"items": [
            {"text": "四小福", "group": "main", "groupIdx": 1, "priceAdd": 0,
             "flavors": [{"name": "鬆厚", "priceAdd": 0}, {"name": "芝心", "priceAdd": 30}]},
            {"text": "千島", "group": "main", "groupIdx": 1, "priceAdd": 40,
             "flavors": [{"name": "鬆厚", "priceAdd": 0}]},
        ]}
        out = compact_coupon_items(coup)
        self.assertEqual(len(out.get("flavorSets") or []), 2)
        self.assertTrue(all(i.get("flavorIdx") is not None for i in out["items"]))
        # add 被濾掉
        coup2 = {"items": [
            {"text": "薯金幣", "group": "add", "groupIdx": 1, "priceAdd": 79, "add": 79},
        ]}
        out2 = compact_coupon_items(coup2)
        self.assertEqual(out2.get("items"), [])

    def test_compact_format_unchanged(self):
        # 已是 compact 格式(flavorIdx、無 flavors) → 不再二次 compact 弄丟
        coup = {"items": [
            {"text": "四小福", "group": "main", "groupIdx": 1, "priceAdd": 0, "flavorIdx": 0},
        ], "flavorSets": [[{"name": "鬆厚", "priceAdd": 0}]]}
        out = compact_coupon_items(coup)
        self.assertEqual(out["items"][0].get("flavorIdx"), 0)
        self.assertEqual(len(out.get("flavorSets") or []), 1)


if __name__ == "__main__":
    unittest.main()
