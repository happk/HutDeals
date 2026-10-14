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

### 6a7ec13 (2026-10-14)

1. **搜尋查不到卡片上的餐點內容物**

   問題：[`src/lib/filter.ts:filterCoupons()`](../src/lib/filter.ts#L53-L77) 的搜尋字串只組 `name`、`description`、`code`。
   卡片上實際顯示的餐點候選沒有進去（[`src/types.ts:MealItem`](../src/types.ts#L8-L27) 的 `items[].text`）。

   放大問題的是 [`script/site/ingest_external.py:external_to_coupon()`](../script/site/ingest_external.py#L59-L119)。
   它在能拆出結構化餐點時，把 `description` 設為 `None`（L70-L74）。
   兩個行為疊在一起，內容物就對搜尋完全隱形。

   影響：`26821` 的 `description` 是空的，內容物「黃金雞軟骨(小份)」寫在 `items`。
   搜「黃金雞軟骨」查不到它。
   全站有 356 筆券的內容物含這個品名。
   能被搜到的只有 1 筆，因為那一筆的 `description` 剛好也含該詞。

   修法方向：產出端加一個 `searchText` 欄位。餐點品名只有 106 個不重複值，去重後很小。
   或讓前端把 `items` 併入搜尋字串。這個做法每次輸入要掃 13 萬字元，宜先去重。

   驗證：`exp_prob/2026-10-14_search-offline-archive/probe.py`

2. **外部碼沒有離線歸檔機制**

   問題：掃號已判死的外部碼，仍以 `active` 留在 [`public/coupons.js`](../public/coupons.js)。
   三段機制一起作用才會漏。

   - [`script/site/ingest_external.py:main()`](../script/site/ingest_external.py#L122-L170)
     只入庫 `status=="alive"` 的 [`data/scan_state.json`](../data/scan_state.json) 紀錄（L132-L135）。
     `dead` 與 `empty` 連迴圈都進不去。
     coupons.js 的舊條目就原封不動。
     `status` 留 `active`，`lastSeen` 與 `verifiedAt` 凍結在最後一次存活的日子。

   - [`script/site/build_coupons.py:merge()`](../script/site/build_coupons.py#L87-L145)
     刻意保留 `source=="verified-external"` 的條目，不標 offline（L132-L136）。
     它信任 ingest 的結果。ingest 不處理離線，這個缺口就沒有人補。

   - [`src/lib/filter.ts:filterCoupons()`](../src/lib/filter.ts#L53-L77) 一律排除非 active 的規則（L60）
     對外部碼形同無效。它們永遠是 `active`。

   影響：`26821` 在 scan_state 是 `empty`，`dead_since=2026-09-30`。
   coupons.js 裡仍是 `active`。
   全站 35 筆這樣。31 筆 `empty` 已死 14 天，4 筆 `dead` 死 3 到 4 天。
   coupons.js 現有 20 筆 offline 全是官網下架，外部碼 0 筆。

   前端沒有失效標示。列表排除 offline，使用者看不到。
   [`src/components/CouponDetail.tsx`](../src/components/CouponDetail.tsx#L131-L138) 有橫幅，但只在深連結看得到。
   深連結走 [`src/App.tsx`](../src/App.tsx#L120-L121) 的 `?code=`，那一行不過濾 status。
   橫幅文案寫死「已從官網下架」，對外部碼的語意不符。
   [`script/site/gen_sitemap.py`](../script/site/gen_sitemap.py#L32) 也把死碼收進 sitemap。

   修法方向：讓 ingest 依 scan_state 標 offline。
   `empty` 立即離線，`dead` 走 7 天寬限期。
   `offlineSince` 取 `dead_since`，保留真實死亡日，每日重跑也無 diff。
   復活路徑已有（[`ingest_external.py:L154-L158`](../script/site/ingest_external.py#L154-L158)）。
   滿 60 天由 `merge()` 自然清除。
   另有兩個決定要一起做：離線後是否仍顯示。橫幅文案怎麼按來源分支。

   驗證：`exp_prob/2026-10-14_search-offline-archive/probe_archive.py`（`probe.py` 為現象快照）

### c5d1634 (2026-09-08)

1. **`merge()` 不保留前日的 `items`／`orderType`／`msrp`**

   問題：[`script/site/build_coupons.py:merge()`](../script/site/build_coupons.py#L87-L145) 只保留 `firstSeen`／`lastSeen`／`status`／`offlineSince`。

   影響：[`script/site/enrich_official.py`](../script/site/enrich_official.py#L31-L70) 需每日全量重補（例：`91113`）。
   `enrich` 失敗一天，那張券就掉殼一天。

   修法方向：`merge()` 繼承舊的 `items`／`orderType`／`msrp`，`enrich` 仍只補缺不覆蓋。
   或 `enrich` 失敗時保留前日補全的結果。

2. **官券沒有通路字樣時，`orderType` 永遠補不出來**

   問題：[`script/scan/parse_step2.py:extract_channels()`](../script/scan/parse_step2.py#L87-L111) 對 `title`／`desc` 全無通路字樣的官券回 `[]`（例：`91113`、`91112`）。

   影響：`orderType` 永為空，每天都進 `enrich` 待補全。

   修法方向：留空，或給預設值。待使用者定。

3. **官網「套餐價格：199起」抓不到價格**

   問題：[`script/site/fetch_promos.py:parse_pdpop_html()`](../script/site/fetch_promos.py) 的價格字串沒有 `$` 號形。
   [`script/scan/parse_step2.py:_HTML_PRICE_PATTERNS`](../script/scan/parse_step2.py) 要求 `$`，命中不了。

   影響：現靠 `price_selling` 撿回。換一張券未必有。

   修法方向：放寬 `$` 可選，但要同步標 `priceNote=起`。起價不當固定價。

### 9f44bb9 (2026-09-08)

1. **三工的「Commit if changed」缺 `if: always()`**

   問題：[`.github/workflows/scan.yml`](../.github/workflows/scan.yml) 的 [confirm](../.github/workflows/scan.yml#L73-L84)／[explore](../.github/workflows/scan.yml#L106-L118)／[sample](../.github/workflows/scan.yml#L144-L156) 三個 job，commit step 沒有 `if: always()`。

   影響：step2 層級熔斷或未預期例外使 job 失敗時，[`script/scan/daily.py`](../script/scan/daily.py) 已 `save_state()`、已寫 alerts 的當日結果不會被 commit。
   熔斷日的資料只留 runner 工作區，不上 remote。
   [告警 job 的文案](../.github/workflows/scan.yml#L160-L184)寫「已完成部分已由各 job 自行 commit」，與實際不符。

   修法方向：commit step 加 `if: always()`。熔斷 exit 3 時資料已寫檔，可安全提交。
   或改 issue body 的措辭。

2. **熔斷日 `public/scan_alerts.json` 停在昨日**

   問題：[`public/scan_alerts.json`](../public/scan_alerts.json) 只在 [sample 尾工](../.github/workflows/scan.yml#L141-L142) 與 [`update.yml`](../.github/workflows/update.yml#L44-L49) 複製。

   影響：confirm 或 explore 熔斷中斷鏈時，public 警報停在昨日。admin 看不出當日熔斷，當日唯一警示是 GitHub issue。

   修法方向：各 job commit 時一併複製，或由 alert job 補一份。

3. **`orderflow` 把程式內部錯誤也當瞬時錯誤重試**

   問題：[`script/lib/orderflow.py:fetch_and_parse()`](../script/lib/orderflow.py#L186-L221) 的 `except Exception` 範圍太寬。

   影響：自身的 bug 也被吞掉，最多重試 3 次。失敗期間沒有任何 log，難以回溯。

   修法方向：限縮可重試的例外類型，或每輪失敗 print 一筆。

## 架構優化

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