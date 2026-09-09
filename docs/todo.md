# HutDeals 待辦（todo）

> 暫緩不修的已知問題與方向性構想記錄在此。
> 條目格式：全模組路徑＋檔名＋行號/符號引用，**一律用 Markdown 連結（文件內連）**，禁止縮寫。
> 二級標題：`潛在漏洞`（暫緩不修的已知問題）、`架構優化`（方向性構想）。
> 三級標題為記錄當時的 commit hash 前 7 碼；內部用列點寫描述。

## 潛在漏洞

### c5d1634

- [`script/site/build_coupons.py:merge()`](../script/site/build_coupons.py#L87-L145) 不保留前日 `items/orderType/msrp`，[`script/site/enrich_official.py`](../script/site/enrich_official.py#L31-L70) 需每日全量重補（例：`91113`）；`enrich` 失敗一天就掉殼一天。修法方向：`merge()` 繼承舊 `items/orderType/msrp`（`enrich` 仍只補缺不覆蓋），或 `enrich` 失敗時保留前日補全。
- [`script/scan/parse_step2.py:extract_channels()`](../script/scan/parse_step2.py#L87-L111) 對 `title/desc` 全無通路字樣的官券回 `[]`（例：`91113`、`91112`），`orderType` 永為空、永進 `enrich` 待補全。修法方向：留空（現狀）或給預設值（待使用者定）。
- [`script/site/fetch_promos.py:parse_pdpop_html()`](../script/site/fetch_promos.py) 系 `套餐價格：199起` 無 `$` 號形，[`script/scan/parse_step2.py:_HTML_PRICE_PATTERNS`](../script/scan/parse_step2.py) 要求 `$` 而命中不了（現靠 `price_selling` 撿回，換個券未必有）。修法方向：放寬 `$` 可選，但須同步標 `priceNote=起`（起價不當固定價）。

### 9f44bb9

- [`.github/workflows/scan.yml`](../.github/workflows/scan.yml) 三工（[confirm](../.github/workflows/scan.yml#L73-L84) / [explore](../.github/workflows/scan.yml#L106-L118) / [sample](../.github/workflows/scan.yml#L144-L156)）的「Commit if changed」step 無 `if: always()`：step2 層級熔斷或未預期例外使 job 失敗時，[`script/scan/daily.py`](../script/scan/daily.py) 已 `save_state()`/寫 alerts 的當日結果不會被 commit → 熔斷日資料只留 runner 工作區、不上 remote；且 alert job（[`.github/workflows/scan.yml`](../.github/workflows/scan.yml#L160-L184)）issue body「已完成部分已由各 job 自行 commit」（[`scan.yml:182`](../.github/workflows/scan.yml#L182)）與實際不符。修法方向：commit step 加 `if: always()`（熔斷 exit 3 時資料已寫檔，可安全提交），或改 issue body 措辭。
- [`public/scan_alerts.json`](../public/scan_alerts.json) 僅在 [`.github/workflows/scan.yml:141-142`](../.github/workflows/scan.yml#L141-L142)（sample 尾工）與 [`.github/workflows/update.yml:44-49`](../.github/workflows/update.yml#L44-L49) 複製：confirm/explore 熔斷中斷鏈時 public 警報停在昨日、admin 看不出當日熔斷（當日唯一警示是 GitHub issue）。修法方向：各 job commit 時一併複製，或 alert job 補一份。
- [`script/lib/orderflow.py:fetch_and_parse()`](../script/lib/orderflow.py#L186-L221) `except Exception` 對程式內部錯誤也當瞬時錯誤重試（吞自身 bug、至多 3 次），且失敗期間無任何 log。修法方向：限縮可重試的例外類型，或每輪失敗 print 一筆。

## 架構優化

### 02120f6

- **在 `scan_state` 與 `coupons.js` 之間加一層 SQLite 管理主資料**（2026-09-09 使用者提出，未實作）：現況是兩層——[`data/scan_state.json`](../data/scan_state.json)（官網原貌、掃號產出）→ [`public/coupons.js`](../public/coupons.js)（網站輸出、項分類在此套用），主資料由 13MB JSON 承擔，衍生欄位（項分類 `units`、篩選標籤）只能在產出時算，無法查詢、無法增量維護，每次都要全量重寫。構想：中間加一層 SQLite（每日 update 時把 scan_state 匯入、跑 [`script/lib/categories.py`](../script/lib/categories.py) 的分類與標籤、再輸出 coupons.js），好處是查詢／關聯／增量更新、保留歷史快照、避免全量重寫。待評估：Actions 上 SQLite 檔的提交體積與鎖競爭、與現有 scan→update 鏈（[`.github/workflows/scan.yml`](../.github/workflows/scan.yml)、[`.github/workflows/update.yml`](../.github/workflows/update.yml)）的整合成本、以及零維運前提下多一個產物是否值得。

### 636496e

- **資料更新自動生效（前端輪詢版本＋提示／自動重載）**（2026-09-09 使用者提出，未實作）：GitHub Pages 對 [`public/coupons.js`](../public/coupons.js) 固定回 `Cache-Control: max-age=600`（無法自訂），回訪者 10 分鐘內直接吃瀏覽器快取、連重新驗證都不做（實測需 Ctrl+F5 才看到新資料）；分頁長開更是永遠不更新。構想：前端定期（如每 30 分鐘）抓一個約 1KB 的 `version.json`（或比對資料的 `last_update`），版本有變就顯示「有新優惠，點此更新」提示，或在使用者切回前景／分頁隱藏時自動重載。取捨：提示不打斷閱讀但需使用者點一下；自動重載要避免打斷正在瀏覽的人。搭配「頁面載入時以 `fetch(..., {cache:'no-cache'})` 重新驗證」可同時覆蓋快取與長開分頁兩種失效窗口（GitHub Pages 支援 ETag 條件式請求，實測未變更回 304／0 bytes）。

