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
                          capture_output=True, text=True)
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


class TestCat(unittest.TestCase):
    """組分類 cat（2026-09-07）：main 依組標題尺寸、second 全飲料→飲料/否則副食。"""

    def _groups(self, code):
        _, _, _, items = load(code)
        out = {}
        for it in items:
            if it["group"] == "add":
                continue
            k = (it["group"], it["groupIdx"])
            out.setdefault(k, (it["cat"], it["groupTitle"]))
        return out

    def test_26868_personal(self):
        g = self._groups("26868")
        # 兩組 main 皆「請選擇1個個人比薩」→ 個人比薩
        self.assertEqual(g[("main", 1)][0], "個人比薩")
        self.assertEqual(g[("main", 2)][0], "個人比薩")
        self.assertEqual(g[("main", 1)][1], "請選擇1個個人比薩")

    def test_16010_drink_group(self):
        g = self._groups("16010")
        self.assertEqual(g[("main", 1)][0], "個人比薩")   # 6吋券官方稱個人
        self.assertEqual(g[("second", 1)][0], "飲料")     # 百事可樂/七喜 全飲料

    def test_94199_13inch_large(self):
        g = self._groups("94199")
        self.assertEqual(g[("main", 1)][0], "大比薩")     # 「13吋大比薩」

    def test_26880_mixed_sizes(self):
        g = self._groups("26880")
        self.assertEqual(g[("main", 1)][0], "大比薩")
        self.assertEqual(g[("main", 2)][0], "個人比薩")
        self.assertEqual(g[("second", 1)][0], "副食")


class TestCatRules(unittest.TestCase):
    """組標題 → cat 分類規則（2026-09-07 使用者確認）。"""

    def test_size(self):
        from script.scan.parse_orderflow import _cat_of_subject
        self.assertEqual(_cat_of_subject("請選擇1個大比薩"), "大比薩")
        self.assertEqual(_cat_of_subject("請選擇1個13吋大比薩"), "大比薩")
        self.assertEqual(_cat_of_subject("請選擇1個小比薩"), "小比薩")
        self.assertEqual(_cat_of_subject("請選擇1個9吋小比薩"), "小比薩")
        self.assertEqual(_cat_of_subject("請選擇1個個人比薩"), "個人比薩")

    def test_pasta(self):
        from script.scan.parse_orderflow import _cat_of_subject
        self.assertEqual(_cat_of_subject("請選擇1份義大利麵/飯"), "義大利麵/飯")
        self.assertEqual(_cat_of_subject("請選擇1份筆管麵"), "義大利麵/飯")
        self.assertEqual(_cat_of_subject("請選擇1份私廚系列飯麵/千層麵"), "義大利麵/飯")

    def test_side(self):
        from script.scan.parse_orderflow import _cat_of_subject
        self.assertEqual(_cat_of_subject("請選擇1份副食"), "副食")
        self.assertEqual(_cat_of_subject("請選擇1個韓式海鮮煎餅"), "副食")
        self.assertEqual(_cat_of_subject("請選擇第1個點心"), "副食")

    def test_special_pizza(self):
        from script.scan.parse_orderflow import _cat_of_subject
        self.assertEqual(_cat_of_subject("請選擇1份手工義式薄比薩"), "特殊比薩")

    def test_neutral_pizza(self):
        from script.scan.parse_orderflow import _cat_of_subject
        self.assertIsNone(_cat_of_subject("請選擇1份無關文字"))


if __name__ == "__main__":
    unittest.main()
