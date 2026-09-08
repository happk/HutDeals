# HutDeals 待辦（todo）

> 暫緩不修的已知問題記錄在此。條目格式：全模組路徑＋檔名＋行號/符號引用，禁止縮寫。
> 二級標題固定為 `潛在漏洞`；三級標題為發現問題當時的 commit hash 前 7 碼；內部用列點寫描述。

## 潛在漏洞

### c5d1634

- `script/site/build_coupons.py:merge()`（`script/site/build_coupons.py:87-145`）不保留前日 `items/orderType/msrp`，`script/site/enrich_official.py:31-70` 需每日全量重補（例：`91113`）；`enrich` 失敗一天就掉殼一天。修法方向：`merge()` 繼承舊 `items/orderType/msrp`（`enrich` 仍只補缺不覆蓋），或 `enrich` 失敗時保留前日補全。
- `script/scan/parse_step2.py:extract_channels()`（`script/scan/parse_step2.py:87-111`）對 `title/desc` 全無通路字樣的官券回 `[]`（例：`91113`、`91112`），`orderType` 永為空、永進 `enrich` 待補全。修法方向：留空（現狀）或給預設值（待使用者定）。
- `script/site/fetch_promos.py:parse_pdpop_html()` 系 `套餐價格：199起` 無 `$` 號形，`script/scan/parse_step2.py:_HTML_PRICE_PATTERNS` 要求 `$` 而命中不了（現靠 `price_selling` 撿回，換個券未必有）。修法方向：放寬 `$` 可選，但須同步標 `priceNote=起`（起價不當固定價）。
- `script/scan/daily.py:cmd_confirm()` 死→活（`script/scan/daily.py:203-207`）只翻狀態不抓 `step_2`，內容要再等一天才補。修法方向：復活當次即補 `step2_of`。
