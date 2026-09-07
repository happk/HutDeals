"""HutDeals parse_meal_items 測試：餐點散文 → items[]（真實 corpus fixture）。

執行:python -m unittest discover -s script/support/tests -v
守護的樣式（2026-09-04 多級 parse 里程碑；改動勿破壞）：
- 主項以 +／買送 切分：26975/26880/26701 三段、26976 兩段、16142 買送兩段
- 內聯括號(3選1) → choices：26880 Flatzz、26701 BBQ烤雞選項
- 括號外 or-chain 選項組 → anchor+choices：26975 薯金幣組、26880 麻糬QQ球組
- 加價前綴：26979 素幸福點 +33元即享
- 尾註(價格/注意事項)剝離
- parse 不出 → None（不硬拆）
"""

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from script.scan.parse_meal import parse_meal, split_main, strip_meta  # noqa: E402

# 真實 og:description（fixtures，取自 data/raw/meal_texts.json 2026-09-04）
CASES = {
    "26975": ("外帶/外送 1個9吋松露起司丁鬆厚比薩(奶素)+1個9吋彩蔬鮮菇鬆厚比薩(奶素)+1份薯金幣(全素)(大)或10顆麻糬QQ球(奶蛋素)或1瓶1.25L可樂(3選1)=NT$388元(原價NT$989) *外送服務為限區服務，購買商品實際付款金額滿$399，外送服務一律免費；購買商品實際付款金額未滿$399，酌收官網定價外送服務費用。"),
    "26880": ("外送/外帶  1個鬆厚大比薩(限620元(含)以下口味)+Flatzz手工個人薄披薩(五重起司蒜香雞或韓式醬烤雪花牛或松露海鮮-以上口味3選1)+5顆麻糬QQ球或1份雞軟骨(小)或1瓶百事可樂(1.25L){3選1}=特價$489(現省$858)"),
    "26976": ("外帶外送 1個大13吋鬆厚比薩松露起司丁鬆厚比薩(奶素)+1個大13吋鬆厚比薩彩蔬鮮菇(奶素)=NT$479元{最高價值$1360}"),
    "16142": ("外送/外帶 買1個13吋鬆厚比薩(口味任選1):和風章魚燒或鐵板雙牛或超級總匯或炙燒明太子嫩雞 送1個13吋鬆厚比薩(口味任選1):香濃蒜香海鮮或彩蔬鮮菇或四小福或夏威夷或日式照燒雞或蒜香起司燻雞培根或義式培根薯金幣或炙燒豬肉總匯 =特價$555(最高價值$1470) 實際供應以門市為準，各項優惠恕不得併用，必勝客保有調整活動辦法及優惠內容之權利。"),
    "26979": ("外帶 買1個6吋松露起司丁鬆厚比薩(奶素)$109+33元即享1個6吋彩蔬鮮菇鬆厚比薩(奶素)此套餐合計$142元"),
    "16054": ("外帶 2個6吋個人鬆厚比薩(口味4選2):四小福或彩蔬鮮菇或日式照燒雞或雙層美式臘腸=NT$132(最高價值NT$218)"),
    # 2026-09-05 官方碼新樣式（bootstrap/官方補全實測）
    "94299": ("13吋大比薩1個，經典口味-韓式泡菜豬五花、超級夏威夷等任選"),
    "94199": ("13吋大比薩1個，10種超值口味-新口味-醬燒鮮蛤田園、熱帶鳳梨海鮮總匯、炙燒豬肉總匯等任選。(免費升級薄脆餅皮)"),
    "93020": ("93020-外帶買大比薩，送2個小比薩+副食5選2+可樂1.25L"),
    # 2026-09-06 v2 規則表新增句式類（scan_state 外部碼實測；每一case=一個句式類）
    "16010": ("外帶 1個6吋鬆厚比薩(4選1):四小福或彩蔬鮮菇或日式照燒雞或夏威夷+1罐330ml百事可樂或七喜(2選1)=NT$99元(最高價值NT$134元) (因比蕯餅皮每日新鮮現做，爲滿足更多消費者的需求，一筆訂單限訂購一份，造成不敬請見諒。) *外送服務為限區服務，購買商品實際付款金額滿$399，外送服務一律免費。"),
    "16011": ("外帶 1個13吋大鬆厚比薩(口味任選1個):炙燒豬肉總匯或彩蔬鮮菇=特價$368(最高價值$1210) +1個9吋小鬆厚比薩(口味任選1個):和風章魚燒或韓式泡菜豬五花或蒜香起司燻雞培根"),
    "16020": ("外帶/外送 買1個9吋小鬆厚比薩(口味任選1個)和風章魚燒或韓式泡菜豬五花或彩蔬鮮菇或義式培根薯金幣-特價$369(最高價值$530)送1個13吋大鬆厚比薩(口味任選1個):炙燒豬肉總匯或彩蔬鮮菇(最高價值$680)"),
    "16282": ("2個鬆厚小比薩(限$410元(含)以下口味)+5顆巧克力QQ球+1份薯金幣(小)+1份酥炸嫩雞球或1份黃金雞軟骨(小)(2選1)+1份酥炸杏鮑菇+1.25L可樂乙瓶=特價NT$489元(最高價值$1123) 實際供應以門市為準，各項優惠恕不得併用。"),
    "16013": ("1個9吋個鬆厚小比薩(限$410元(含)以下口味)+厚燒醬烤BBQ(2腿2排)或4塊厚燒醬烤腿排或BBQ烤雞(4翅4腿)(副食3選1)+1罐330CC可樂或1份薯金幣(小)或5顆麻糬QQ球或1份黃金雞軟骨(小){4選1}=NT$399元(最高價值NT$718元)"),
    "93015": ("3個大比薩(20種以上口味任選)$888起！第一個大比薩限定$565～$790 口味；第二、三個大比薩可選 $620 以上口味，超過 $620 部分需補差價。"),
    "94601": ("超級總匯/炙燒明太子嫩雞/鐵板雙牛$249"),
    "91111": ("套餐內容：經典系列個人比薩*1+副食*1+飲料*1"),
    "92117": ("墨西哥辣椒芝心腸3條 買一送一 $109 (原價$218)"),
    "91112": ("任選私廚飯麵/千層麵+$1多QQ球 $190起"),
}


class TestStripMeta(unittest.TestCase):
    def test_removes_prefix_and_price_tail(self):
        r = strip_meta(CASES["26976"])
        self.assertNotIn("外帶外送", r)
        self.assertNotIn("=NT$479", r)
        self.assertNotIn("最高價值", r)

    def test_removes_asterisk_trailer(self):
        r = strip_meta(CASES["26975"])
        self.assertNotIn("外送服務為限區", r)


class TestSplitMain(unittest.TestCase):
    def test_plus_splits_26975(self):
        segs = split_main(strip_meta(CASES["26975"]))
        self.assertEqual(len(segs), 3)

    def test_buy_send_splits_16142(self):
        segs = split_main(strip_meta(CASES["16142"]))
        self.assertEqual(len(segs), 2)
        self.assertTrue(segs[0].startswith("買1個"))
        self.assertTrue(segs[1].startswith("送1個"))


class TestParseMeal(unittest.TestCase):
    def test_26975_three_items_third_has_choices(self):
        items = parse_meal(CASES["26975"])
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]["text"], "1個9吋松露起司丁鬆厚比薩(奶素)")
        self.assertEqual(items[1]["text"], "1個9吋彩蔬鮮菇鬆厚比薩(奶素)")
        self.assertGreaterEqual(len(items[2]["choices"]), 2)

    def test_26880_flatzz_inline_choices(self):
        items = parse_meal(CASES["26880"])
        self.assertEqual(len(items), 3)
        # 第二項 Flatzz 內聯 3 口味
        self.assertIn("五重起司蒜香雞", items[1]["choices"])
        self.assertEqual(len(items[1]["choices"]), 3)

    def test_26976_two_items(self):
        items = parse_meal(CASES["26976"])
        self.assertEqual(len(items), 2)

    def test_16142_buy_and_send_with_flavors(self):
        items = parse_meal(CASES["16142"])
        self.assertEqual(len(items), 2)
        self.assertGreaterEqual(len(items[0]["choices"]), 4)
        self.assertGreaterEqual(len(items[1]["choices"]), 8)

    def test_16054_4select2_kept(self):
        items = parse_meal(CASES["16054"])
        self.assertIsNotNone(items)
        self.assertGreaterEqual(len(items[0]["choices"]), 3)

    def test_94299_dash_flavor_choices(self):
        """口味 dash 樣式『經典口味-A、B等任選』→ choices，不拍平純文字。"""
        items = parse_meal(CASES["94299"])
        self.assertIsNotNone(items)
        self.assertEqual(items[0]["choices"], ["韓式泡菜豬五花", "超級夏威夷"])
        self.assertNotIn("等任選", items[0]["text"])

    def test_94199_dash_choices_keeps_note_and_sublabel(self):
        """dash + 尾註(句號+括號) + 子標籤(新口味-)都要保留。"""
        items = parse_meal(CASES["94199"])
        self.assertIsNotNone(items)
        self.assertEqual(len(items[0]["choices"]), 3)
        self.assertEqual(items[0]["choices"][0], "新口味-醬燒鮮蛤田園")
        self.assertIn("免費升級薄脆餅皮", items[0]["text"])

    def test_93020_code_prefix_stripped(self):
        """desc 帶『93020-』碼前綴 → L0 剝除，碼不得漏進 items。"""
        items = parse_meal(CASES["93020"])
        self.assertIsNotNone(items)
        joined = json.dumps(items, ensure_ascii=False)
        self.assertNotIn("93020", joined)
        self.assertIn("副食5選2", joined)


class TestParseMealV2Rules(unittest.TestCase):
    """2026-09-06 v2 規則表：每個測試對應一個句式類（非個案補丁）。"""

    def test_16011_midtext_price_keeps_second_item(self):
        """句中價格段（=特價$…(最高價值$…)）只刪短語不斷尾——第二主項必須存活。"""
        items = parse_meal(CASES["16011"])
        self.assertIsNotNone(items)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["text"], "1個13吋大鬆厚比薩 (2選1)")
        self.assertEqual(len(items[0]["choices"]), 2)
        self.assertEqual(items[1]["text"], "1個9吋小鬆厚比薩 (3選1)")
        self.assertEqual(len(items[1]["choices"]), 3)

    def test_16020_send_split_without_space(self):
        """『)送1個…』無空格送切分＋口味前綴無冒號形——兩個比薩分兩項。"""
        items = parse_meal(CASES["16020"])
        self.assertIsNotNone(items)
        self.assertEqual(len(items), 2)
        self.assertTrue(items[0]["text"].startswith("買1個9吋小鬆厚比薩"))
        self.assertTrue(items[0]["text"].endswith("(4選1)"))
        self.assertEqual(len(items[0]["choices"]), 4)
        self.assertTrue(items[1]["text"].startswith("送1個13吋大鬆厚比薩"))
        self.assertEqual(len(items[1]["choices"]), 2)

    def test_16010_drink_orchain_grouped(self):
        """飲料 or-chain → anchor+choices（量詞『罐』）,註記不重複。"""
        items = parse_meal(CASES["16010"])
        self.assertIsNotNone(items)
        drink = items[1]
        self.assertEqual(drink["text"], "1罐330ml百事可樂 (2選1)")
        self.assertEqual(drink["choices"], ["七喜"])
        self.assertNotIn("(2選1) (2選1)", json.dumps(items, ensure_ascii=False))
        # 泛用括號N選M＋冒號清單：披薩口味
        self.assertEqual(items[0]["text"], "1個6吋鬆厚比薩(4選1)")
        self.assertEqual(len(items[0]["choices"]), 4)

    def test_16282_price_suffix_not_glued(self):
        """=特價NT$N元(最高價值$M) 後綴不得黏進品項文字。"""
        items = parse_meal(CASES["16282"])
        self.assertIsNotNone(items)
        self.assertEqual(items[-1]["text"], "1.25L可樂乙瓶")
        joined = json.dumps(items, ensure_ascii=False)
        self.assertNotIn("特價", joined)
        self.assertNotIn("最高價值", joined)

    def test_16013_tailnote_prefix_normalized(self):
        """段尾註記帶類別前綴（副食3選1）→ 正規化 (N選M) 到 anchor。"""
        items = parse_meal(CASES["16013"])
        self.assertIsNotNone(items)
        self.assertEqual(items[1]["text"], "厚燒醬烤BBQ(2腿2排) (3選1)")
        self.assertEqual(len(items[1]["choices"]), 2)
        self.assertEqual(items[2]["text"], "1罐330CC可樂 (4選1)")
        self.assertEqual(len(items[2]["choices"]), 3)

    def test_93015_multisentence_falls_back(self):
        """多句條款散文（；/補差價）→ 整體回 None,前端誠實顯示原文。"""
        self.assertIsNone(parse_meal(CASES["93015"]))

    def test_94601_slash_orchain(self):
        """／ 分隔 or-chain（無或字）→ anchor 形。"""
        items = parse_meal(CASES["94601"])
        self.assertIsNotNone(items)
        self.assertEqual(items[0]["text"], "超級總匯 (擇一)")
        self.assertEqual(items[0]["choices"], ["炙燒明太子嫩雞", "鐵板雙牛"])

    def test_91111_asterisk_count_kept(self):
        """『*1』是數量記號非尾註——不得被 *注意事項規則砍掉。"""
        items = parse_meal(CASES["91111"])
        self.assertIsNotNone(items)
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]["text"], "經典系列個人比薩*1")

    def test_92117_buyone_getone_not_split(self):
        """『買一送一』不是 買/送 主項切分點。"""
        items = parse_meal(CASES["92117"])
        self.assertIsNotNone(items)
        self.assertEqual(len(items), 1)
        self.assertIn("買一送一", items[0]["text"])

    def test_91112_qi_price_removed(self):
        """$N起 起價短語刪除（含括號包裹形）——不得留在品項。"""
        items = parse_meal(CASES["91112"])
        self.assertIsNotNone(items)
        joined = json.dumps(items, ensure_ascii=False)
        self.assertNotIn("190", joined)


if __name__ == "__main__":
    unittest.main()
