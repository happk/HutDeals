"""HutDeals tests — parse_orderflow 結構化輸出測試。

守護：選單版 HTML（真實抓取 fixture）→ parse_orderflow → 結構化候選清單
的欄位完整性與正確性。改爬取/解析不得破壞既有輸出語意。

執行：python -m unittest script.support.tests.test_parse_orderflow -v
"""
import json
import os
import subprocess
import unittest

from script.scan.parse_orderflow import flatten_items, parse_orderflow

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "orderflow")
NODE = os.path.join(os.path.dirname(__file__), "..", "..", "..", "script",
                    "scan", "extract_js.cjs")


def load(code: str):
    """抓 fixture 並跑 node extract → (html, extract, struct, items)。"""
    hp = os.path.join(FIXTURES, f"{code}.html")
    with open(hp, encoding="utf-8") as f:
        html = f.read()
    proc = subprocess.run(["node", os.path.normpath(NODE), hp],
                          capture_output=True, text=True, encoding="utf-8")
    extract = json.loads(proc.stdout)
    struct = parse_orderflow(html, extract)
    items = flatten_items(struct)
    return html, extract, struct, items


class TestOrderflow(unittest.TestCase):
    def test_16010_fullexpand(self):
        """16010 全展開：4 主餐 + 2 副食 + 11 加購。"""
        _, _, _, items = load("16010")
        mains = [i for i in items if i["group"] == "main"]
        seconds = [i for i in items if i["group"] == "second"]
        adds = [i for i in items if i["group"] == "add"]
        self.assertEqual(len(mains), 4)
        self.assertEqual(len(seconds), 2)
        self.assertEqual(len(adds), 11)
        # 主餐全 +0，含餅皮 flavors
        self.assertTrue(all(i["priceAdd"] == 0 for i in mains))
        self.assertEqual(mains[0]["flavors"][0]["name"], "鬆厚")
        # 副食可樂/七喜
        self.assertEqual({i["text"] for i in seconds},
                         {"百事可樂330ml", "七喜330ml"})
        # 加購有價
        self.assertTrue(all(i["add"] > 0 for i in adds))

    def test_26868_gateway(self):
        """26868 闖關式：15 + 5 主餐(兩組) + 11 加購，候選帶升級價差。"""
        _, _, _, items = load("26868")
        mains = [i for i in items if i["group"] == "main"]
        adds = [i for i in items if i["group"] == "add"]
        self.assertEqual(len(mains), 20)   # 15(組1) + 5(組2)
        self.assertEqual(len(adds), 11)
        # 組1 有升級候選（千島+40）
        g1 = [i for i in mains if i["groupIdx"] == 1]
        qd = next(i for i in g1 if i["text"] == "千島海鮮盛宴")
        self.assertEqual(qd["priceAdd"], 40)
        # +0 的候選存在（四小福等）
        zero = [i for i in g1 if i["priceAdd"] == 0]
        self.assertGreaterEqual(len(zero), 4)

    def test_94199_single(self):
        """94199 單點大比薩：10 口味候選皆 +0（口味價差在 flavors）。"""
        _, _, _, items = load("94199")
        mains = [i for i in items if i["group"] == "main"]
        self.assertEqual(len(mains), 10)
        self.assertTrue(all(i["priceAdd"] == 0 for i in mains))
        # 口味含火山起司(加價)
        first = mains[0]
        self.assertTrue(any(f["priceAdd"] > 0 for f in first["flavors"]))

    def test_26880_bigcombo(self):
        """26880 大組合：30 主餐候選(含 +268 高價)+ 4 副食 + 13 加購。"""
        _, _, _, items = load("26880")
        mains = [i for i in items if i["group"] == "main"]
        self.assertEqual(len(mains), 30)
        self.assertTrue(any(i["priceAdd"] > 0 for i in mains))
        top = max(i["priceAdd"] for i in mains)
        self.assertGreaterEqual(top, 200)   # 極炙厚牛干貝 +268


class TestRawShape(unittest.TestCase):
    """scan_state 保持官網原貌（2026-09-09）：解析輸出不含我們的分類，只帶官方組標題。

    分類（項分類）改在產出 coupons.js 時由 script/lib/categories.py 判定，
    見 test_categories.py。
    """

    def test_16010_no_cat_has_groupTitle(self):
        _, _, _, items = load("16010")
        self.assertTrue(all("cat" not in i for i in items))
        mains = [i for i in items if i["group"] == "main"]
        self.assertEqual(mains[0]["groupTitle"], "請選擇1個個人比薩")
        seconds = [i for i in items if i["group"] == "second"]
        self.assertEqual(seconds[0]["groupTitle"], "請選擇1份副食")

    def test_26880_two_main_subjects(self):
        _, _, _, items = load("26880")
        subjects = {i["groupIdx"]: i["groupTitle"] for i in items if i["group"] == "main"}
        self.assertEqual(subjects[1], "請選擇1個大比薩")
        self.assertEqual(subjects[2], "請選擇1個個人比薩")

    def test_94199_subject(self):
        _, _, _, items = load("94199")
        mains = [i for i in items if i["group"] == "main"]
        self.assertIn("13吋", mains[0]["groupTitle"])

    def test_91113_drink_group_subject(self):
        _, _, _, items = load("91113")
        g4 = [i for i in items if i["group"] == "second" and i["groupIdx"] == 4]
        self.assertTrue(g4)
        self.assertEqual(g4[0]["groupTitle"], "請選擇1份飲料")
        self.assertIn("茉香柚茶", {i["text"] for i in g4})


if __name__ == "__main__":
    unittest.main()
