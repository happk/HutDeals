"""HutDeals parse_step2 測試：step_2 套餐頁解析規則（真實 HTML fixture）。

執行:python -m unittest discover -s script/support/tests -v
守護的規則（改 HTML 結構或改詞典不得破壞）：
- 聯名詞典命中（兆豐/全支付/素易）→ partner + ig_hint；純官網 94199 → None
- 通路判定：og:desc「外帶/外送」→ {外帶,外送}；title「平日外帶-」→ {外帶}
- 價格判定：=NT$388(原價NT$989)、特價$489(現省$858)、特價$555(最高價值$1470)
"""

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from script.scan.parse_step2 import (  # noqa: E402
    extract_channels,
    extract_html_price,
    extract_msrp,
    match_partner,
    parse_step2,
)

TEST_DIR = Path(__file__).resolve().parent
FIX = TEST_DIR / "fixtures" / "step2"


def load(code: str) -> str:
    return (FIX / f"{code}.html").read_text(encoding="utf-8")


class TestPartner(unittest.TestCase):
    def test_megabank(self):
        self.assertEqual(match_partner("26880兆豐信用卡端午")["name"], "兆豐銀行")

    def test_allpay(self):
        self.assertEqual(match_partner("16142全支付大送大")["name"], "全支付")

    def test_suiis_plain_title(self):
        # 素易靠「素」字，需確認不會誤判季節活動（16231中秋獻禮無素）
        self.assertIsNone(match_partner("16231中秋獻禮568"))

    def test_plain_official_none(self):
        self.assertIsNone(match_partner("94199超值單點大比薩"))


class TestChannels(unittest.TestCase):
    def test_both_from_slash(self):
        self.assertEqual(extract_channels("26975新素歡聚餐", "外帶/外送 1個9吋..."), ["外帶", "外送"])

    def test_reversed_slash(self):
        self.assertEqual(extract_channels("26880兆豐", "外送/外帶 1個..."), ["外帶", "外送"])

    def test_takeout_from_title_prefix(self):
        self.assertEqual(extract_channels("平日外帶-94199超值單點", "13吋大比薩1個..."), ["外帶"])

    def test_takeout_only_from_desc(self):
        self.assertEqual(extract_channels("foo", "限外帶 買1個..."), ["外帶"])


class TestStructuralPrice(unittest.TestCase):
    """結構化價格（2026-09-07 改版：desc 退出結構化欄位）。

    守護：
    - price 只從結構化 HTML（descPrice/套餐價格/price_selling）；不從 desc 文本。
    - 起價（$N起）不算固定價 → None（不回 desc 撈）。
    - msrp 為純顯示備用註記，仍從 desc 文案（直接型/現省）。
    """

    def test_descprice_over_desc_start(self):
        """26868/26898 型：desc 有「$95元起」但結構化 descPrice=$144 → 144。

        舊 bug：L1 文本優先抓「=NT$95」→ 95；結構化 144 被忽略。
        """
        d = parse_step2(load("26868"), "26868")
        self.assertEqual(d["price"], 144)

    def test_html_price_descprice(self):
        self.assertEqual(
            extract_html_price('<div class="descPrice notranslate">$ 144</div>'), 144)

    def test_html_price_package_selling(self):
        # 基準型 package：price_selling
        self.assertEqual(
            extract_html_price('<script>cb={price_selling:399}</script>'), 399)
        # price_selling 0 = 非固定價，不算
        self.assertIsNone(extract_html_price('<script>price_selling:0</script>'))

    def test_html_price_none_when_only_start_text(self):
        # 只有「$N起」文本、無結構化欄位 → None（起價非固定價，不回 desc 撈）
        self.assertIsNone(extract_html_price('<p>=$95元起 買1個…</p>'))

    def test_msrp_direct(self):
        self.assertEqual(extract_msrp("=NT$388元(原價NT$989)", 388), 989)

    def test_msrp_diff_nowsave(self):
        self.assertEqual(extract_msrp("限$620(含)以下…現省$858", 489), 1347)

    def test_msrp_none_without_structural_price(self):
        # 起價券 price=None → 現省差額型不成立（避免虛增）
        self.assertIsNone(extract_msrp("$888起…現省$100", None))


class TestParseStep2(unittest.TestCase):
    def test_official_takeout(self):
        d = parse_step2(load("94199"), "94199")
        self.assertEqual(d["partner"], None)
        self.assertEqual(d["channels"], ["外帶"])
        self.assertIn("13吋大比薩1個", d["desc_head"])

    def test_suiis_meal(self):
        d = parse_step2(load("26975"), "26975")
        self.assertEqual(d["partner"], "素易")
        self.assertEqual(d["ig_hint"], "suiistw")
        self.assertEqual(d["channels"], ["外帶", "外送"])
        self.assertEqual(d["price"], 388)
        self.assertEqual(d["msrp"], 989)
        self.assertEqual(d["title"], "26975新素歡聚餐")

    def test_megabank_meal(self):
        d = parse_step2(load("26880"), "26880")
        self.assertEqual(d["partner"], "兆豐銀行")
        self.assertEqual(d["price"], 489)
        self.assertEqual(d["msrp"], 1347)  # 489 + 現省858（語意修正 2026-09-05）
        self.assertEqual(d["channels"], ["外帶", "外送"])

    def test_allpay_meal(self):
        d = parse_step2(load("16142"), "16142")
        self.assertEqual(d["partner"], "全支付")
        self.assertEqual(d["price"], 555)
        self.assertEqual(d["msrp"], 1470)


if __name__ == "__main__":
    unittest.main()
