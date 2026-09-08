# HutDeals 待辦（todo）

> 暫緩不修的已知問題記錄在此。條目格式：全模組路徑＋檔名＋行號/符號引用，禁止縮寫。
> 二級標題固定為 `潛在漏洞`；三級標題為發現問題當時的 commit hash 前 7 碼；內部用列點寫描述。

## 潛在漏洞

### c5d1634

- `script/site/build_coupons.py:merge()`（`script/site/build_coupons.py:87-145`）不保留前日 `items/orderType/msrp`，`script/site/enrich_official.py:31-70` 需每日全量重補（例：`91113`）；`enrich` 失敗一天就掉殼一天。修法方向：`merge()` 繼承舊 `items/orderType/msrp`（`enrich` 仍只補缺不覆蓋），或 `enrich` 失敗時保留前日補全。
- `script/scan/parse_step2.py:extract_channels()`（`script/scan/parse_step2.py:87-111`）對 `title/desc` 全無通路字樣的官券回 `[]`（例：`91113`、`91112`），`orderType` 永為空、永進 `enrich` 待補全。修法方向：留空（現狀）或給預設值（待使用者定）。
- `script/site/fetch_promos.py:parse_pdpop_html()` 系 `套餐價格：199起` 無 `$` 號形，`script/scan/parse_step2.py:_HTML_PRICE_PATTERNS` 要求 `$` 而命中不了（現靠 `price_selling` 撿回，換個券未必有）。修法方向：放寬 `$` 可選，但須同步標 `priceNote=起`（起價不當固定價）。

### 9f44bb9

- `.github/workflows/scan.yml` 三工（confirm:73-84 / explore:106-118 / sample:144-156）的「Commit if changed」step 無 `if: always()`：step2 層級熔斷或未預期例外使 job 失敗時，`script/scan/daily.py` 已 `save_state()`/寫 alerts 的當日結果不會被 commit → 熔斷日資料只留 runner 工作區、不上 remote；且 alert job（`.github/workflows/scan.yml:160-184`）issue body「已完成部分已由各 job 自行 commit」（:182）與實際不符。修法方向：commit step 加 `if: always()`（熔斷 exit 3 時資料已寫檔，可安全提交），或改 issue body 措辭。
- `public/scan_alerts.json` 僅在 `.github/workflows/scan.yml:141-142`（sample 尾工）與 `.github/workflows/update.yml:44-49` 複製：confirm/explore 熔斷中斷鏈時 public 警報停在昨日、admin 看不出當日熔斷（當日唯一警示是 GitHub issue）。修法方向：各 job commit 時一併複製，或 alert job 補一份。
- `script/lib/orderflow.py:fetch_and_parse()`（`script/lib/orderflow.py:186-221`）`except Exception` 對程式內部錯誤也當瞬時錯誤重試（吞自身 bug、至多 3 次），且失敗期間無任何 log。修法方向：限縮可重試的例外類型，或每輪失敗 print 一筆。
