# HutDeals 待辦（todo）

> 暫緩不修的已知問題與方向性構想記錄在此。
>
> 格式：
>
> - 二級標題：`潛在漏洞`（暫緩不修的已知問題）、`架構優化`（方向性構想）。
> - 三級標題：`<commit hash前7碼> (YYYY-MM-DD)`，hash 為記錄當下的 commit。
> - 每項是一則有序列表，項與項之間空一行。
> - 項內用「問題／影響／修法方向」等小標起頭，每句一行，句子保持短。
> - 引用一律用 Markdown 連結（文件內連）指向全模組路徑＋行號或符號，禁止縮寫。

## 潛在漏洞

### cb13be8 (2026-10-25)

1. **`deploy-pages.yml` 失敗不開 issue**

   問題：[`.github/workflows/deploy-pages.yml`](../.github/workflows/deploy-pages.yml) 沒有告警 job。
   scan/update 兩鏈失敗都會開紅 issue，唯獨部署失敗靜默。

   影響：部署掛掉無推送無記錄，網站可能停在舊版數日無人知。

   修法方向：補失敗告警（開 issue）。歸屬錯誤分級藍圖（2026-10-25 拍板擱置）一起做。

### c5d1634 (2026-09-08)

1. **官券沒有通路字樣時，`orderType` 永遠補不出來**

   問題：[`script/scan/parse_step2.py:extract_channels()`](../script/scan/parse_step2.py#L87-L111) 對 `title`／`desc` 全無通路字樣的官券回 `[]`（例：`91113`、`91112`）。

   影響：`orderType` 永為空，每天都進 `enrich` 待補全。

   修法方向：留空，或給預設值。待使用者定。

2. **官網「套餐價格：199起」抓不到價格**

   問題：[`script/site/fetch_promos.py:parse_pdpop_html()`](../script/site/fetch_promos.py) 的價格字串沒有 `$` 號形。
   [`script/scan/parse_step2.py:_HTML_PRICE_PATTERNS`](../script/scan/parse_step2.py) 要求 `$`，命中不了。

   影響：現靠 `price_selling` 撿回。換一張券未必有。

   修法方向：放寬 `$` 可選，但要同步標 `priceNote=起`。起價不當固定價。

## 架構優化

### c233381 (2026-10-26)

1. **搜尋支援邏輯運算子（`-` NOT／`||` OR／`&` AND）**

   構想（2026-10-26 使用者提出，語法未拍板）：搜尋主體（items 品名進索引）
   已隨 PR #7 上線；下一梯增強是邏輯運算子。

   現況：唯一邏輯＝空格隱式 AND
   （[`filter.ts:filterCoupons()` 的 terms 拆分](../src/lib/filter.ts#L80)）。
   `&`／`||` 不是運算子——被當必要字面子串，幾乎必然零結果。
   `-詞` 也非 NOT——字面子串，官網券名含連字號（如 `93020-外帶買一送五`）會意外命中。

   設計方向（已提案）：Gmail 式——`-詞`＝NOT 排除；`||`／`OR`＝分組 OR
   （組內空格仍 AND）；`&` 視同空格。優先級 NOT＞AND＞OR。
   改動點只在 terms 拆分處，haystack（[`haystackOf`](../src/lib/filter.ts#L59)）不動。

   落地：自最新 main 開新分支（如 `feat/search-operators`），不續用已 merge 的分支。

### 02120f6 (2026-09-09)

1. **在 `scan_state` 與 `coupons.js` 之間加一層 SQLite 管理主資料**

   構想（2026-09-09 使用者提出，未實作）：現況是兩層。
   [`data/scan_state.json`](../data/scan_state.json) 存官網原貌，由掃號產出。
   [`public/coupons.js`](../public/coupons.js) 是網站輸出，項分類在此套用。

   主資料由 13MB JSON 承擔。衍生欄位（項分類 `units`、篩選標籤）只能在產出時算。
   無法查詢，無法增量維護，每次都要全量重寫。

   好處：查詢、關聯、增量更新。保留歷史快照，避免全量重寫。

   待評估：Actions 上 SQLite 檔的提交體積與鎖競爭。
   與現有 scan→update 鏈的整合成本（[`.github/workflows/scan.yml`](../.github/workflows/scan.yml)、[`.github/workflows/update.yml`](../.github/workflows/update.yml)）。
   零維運前提下多一個產物是否值得。

### 636496e (2026-09-09)

1. **資料更新自動生效（前端輪詢版本＋提示／自動重載）**

   構想（2026-09-09 使用者提出，未實作）：GitHub Pages 對 [`public/coupons.js`](../public/coupons.js) 固定回 `Cache-Control: max-age=600`，無法自訂。
   回訪者 10 分鐘內直接吃瀏覽器快取，連重新驗證都不做。實測需 Ctrl+F5 才看到新資料。
   分頁長開更是永遠不更新。

   構想：前端定期抓一個約 1KB 的 `version.json`（或比對 `last_update`），例如每 30 分鐘一次。
   版本有變就顯示「有新優惠，點此更新」提示。
   或在使用者切回前景、分頁隱藏時自動重載。

   取捨：提示不打斷閱讀，但需使用者點一下。自動重載要避免打斷正在瀏覽的人。

   搭配「頁面載入時以 `fetch(..., {cache:'no-cache'})` 重新驗證」，可同時覆蓋快取與長開分頁兩種失效窗口。
   GitHub Pages 支援 ETag 條件式請求，實測未變更時回 304、0 bytes。