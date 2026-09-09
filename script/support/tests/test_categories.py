"""HutDeals tests — 項分類（script/lib/categories.py）。

守護 2026-09-09 使用者拍板的模型：
- 分類掛在「項」（一個選項組）；不看官網組型 main/second。
- 飲料／副食／義大利麵飯 ← 候選品名；大／小／個人／特殊比薩 ← 官方組標題。
- 混類項同時掛多類（副食/飲料）；加購（add）不參與分類。

執行：python -m unittest script.support.tests.test_categories -v
"""
import unittest

from script.lib.categories import (
    cat_of_candidate,
    cat_tags,
    classify_units,
    looks_drink,
    looks_pasta,
    size_cats_of_subject,
)


def item(text, group="second", groupIdx=1, groupTitle=None):
    return {"text": text, "group": group, "groupIdx": groupIdx,
            "priceAdd": 0, "groupTitle": groupTitle}


class TestCandidate(unittest.TestCase):
    def test_looks_drink(self):
        for n in ("百事可樂330ml", "七喜1.25L", "茉香柚茶", "原萃綠茶580ml", "OO氣泡飲"):
            self.assertTrue(looks_drink(n), n)
        for n in ("茶碗蒸", "黃金雞軟骨(小份)", "薯金幣(小份)", "巧克力QQ球5顆"):
            self.assertFalse(looks_drink(n), n)

    def test_looks_pasta(self):
        for n in ("青醬干貝鱈魚筆管麵", "松露鮮蝦干貝燉飯", "五倍起司焗烤千層麵"):
            self.assertTrue(looks_pasta(n), n)
        self.assertFalse(looks_pasta("黃金雞柳條8條"))

    def test_cat_of_candidate(self):
        self.assertEqual(cat_of_candidate("百事可樂330ml"), "飲料")
        self.assertEqual(cat_of_candidate("奶油燻雞燉飯"), "義大利麵/飯")
        self.assertIsNone(cat_of_candidate("黃金雞軟骨(小份)"))
        self.assertIsNone(cat_of_candidate("和風章魚燒"))  # 比薩名不含尺寸/品類字


class TestSizeCats(unittest.TestCase):
    def test_sizes(self):
        self.assertEqual(size_cats_of_subject("請選擇1個大比薩"), ["大比薩"])
        self.assertEqual(size_cats_of_subject("請選擇1個13吋大比薩"), ["大比薩"])
        self.assertEqual(size_cats_of_subject("請選擇1個小比薩"), ["小比薩"])
        self.assertEqual(size_cats_of_subject("請選擇1個個人比薩"), ["個人比薩"])
        self.assertEqual(size_cats_of_subject("請選擇1份手工義式薄比薩"), ["特殊比薩"])
        self.assertEqual(size_cats_of_subject("請選擇1份比薩"), ["比薩"])

    def test_non_size_returns_empty(self):
        # 副食／飲料／麵飯一律由候選品名判定，組標題不參與
        for s in ("請選擇1份副食", "請選擇1份飲料", "請選擇1份副食或飯麵",
                  "請選擇1份飲料或點心", "請選擇1份義大利麵/飯", None):
            self.assertEqual(size_cats_of_subject(s), [], repr(s))


class TestClassifyUnits(unittest.TestCase):
    def test_pizza_unit_gets_size_from_subject(self):
        items = [item("和風章魚燒", "main", 1, "請選擇1個個人比薩"),
                 item("鐵板雙牛", "main", 1, "請選擇1個個人比薩")]
        units = classify_units(items)
        self.assertEqual(units, [{"group": "main", "groupIdx": 1, "cats": ["個人比薩"]}])
        self.assertEqual({i["cat"] for i in items}, {"個人比薩"})

    def test_two_main_units_different_sizes(self):
        # 套餐 1 大比薩 + 1 小比薩 = 2 項，不可「通用 main」
        items = [item("口味A", "main", 1, "請選擇1個大比薩"),
                 item("口味B", "main", 2, "請選擇1個小比薩")]
        units = classify_units(items)
        self.assertEqual([u["cats"] for u in units], [["大比薩"], ["小比薩"]])

    def test_mixed_unit_gets_both(self):
        items = [item("薯金幣(小份)", "second", 1, "請選擇1份副食"),
                 item("百事可樂330ml", "second", 1, "請選擇1份副食")]
        units = classify_units(items)
        self.assertEqual(units[0]["cats"], ["副食", "飲料"])
        self.assertEqual(items[0]["cat"], "副食")
        self.assertEqual(items[1]["cat"], "飲料")

    def test_all_drinks_ignores_food_subject(self):
        # 16010 second1：組標題寫「副食」但組內只有飲料 → 依候選判為飲料
        items = [item("百事可樂330ml", "second", 1, "請選擇1份副食"),
                 item("七喜330ml", "second", 1, "請選擇1份副食")]
        units = classify_units(items)
        self.assertEqual(units[0]["cats"], ["飲料"])

    def test_pasta_and_side_in_one_unit(self):
        # 16181「副食或飯麵」：麵飯靠品名、雞柳靠預設副食
        items = [item("青醬干貝鱈魚筆管麵", "second", 1, "請選擇1份副食或飯麵"),
                 item("黃金雞柳條8條", "second", 1, "請選擇1份副食或飯麵")]
        units = classify_units(items)
        self.assertEqual(units[0]["cats"], ["義大利麵/飯", "副食"])

    def test_main_without_subject_defaults_side(self):
        # 92001 main1「酥炸嫩雞球」：無組標題且品名判不出 → 副食（不可因 main 誤判比薩）
        items = [item("酥炸嫩雞球", "main", 1, None)]
        units = classify_units(items)
        self.assertEqual(units[0]["cats"], ["副食"])

    def test_add_group_not_classified(self):
        items = [item("薯金幣(大份)", "add", 1, None)]
        units = classify_units(items)
        self.assertEqual(units, [])
        self.assertIsNone(items[0]["cat"])

    def test_cat_tags(self):
        units = [{"group": "second", "groupIdx": 1, "cats": ["副食", "飲料"]},
                 {"group": "main", "groupIdx": 1, "cats": ["大比薩"]}]
        # 標籤順序無語意（前端另按出現次數排序），只驗內容齊全
        self.assertEqual(sorted(cat_tags(units)), sorted(["大比薩", "副食", "飲料"]))
        self.assertEqual(cat_tags([{"group": "main", "groupIdx": 1, "cats": ["比薩"]}]), ["比薩"])


if __name__ == "__main__":
    unittest.main()
