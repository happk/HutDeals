# HutDeals Changelog

> 版本紀錄，新版本在上。`vX.Y.Z`：
> - X 大版本（上線/重大架構）
> - Y 功能
> - Z 修正

## v1.0.3（2026-09-09）— 掃號穩定性修正

- 修 `cmd_confirm` 崩潰：券選項無群組時 `cat`/`groupTitle` 為 `None`，與字串同列
  `sorted()` 觸發 `TypeError`（每日掃號 confirm 中斷，run 34263828448）。排序加 `key=str`。
- 修失敗告警 issue 從未發成：`gh label create` 建不出「不存在」的 label、錯誤又被
  `|| true` 吞掉，`gh issue create --label scan-failed` 因 label 不存在而失敗。
  改 REST `POST /repos/{repo}/labels`（不存在才建）；`scan.yml`/`update.yml` 同修
  （`scan-failed`/`scrape-failed`）。
- 新增回歸測試 `test_confirm_cats_none`（離線 mock：含 None 的組分類比對不崩潰）。
- 版本：`package.json` 同步至 1.0.3

## v1.0.2（2026-09-08）— step_2 抓取穩定化 + 失敗可視化

- 掃號 step_2 抓取更穩：瞬時錯誤自動重試（至多 3 次、線性退避），429/403 熔斷不重試
- 死碼復活當日即補 step_2 內容，不再落後一天（原為復活後隔天才補）
- 官方券 step_2 失敗不再靜默：寫入 `scan_alerts.json` step2_failures、admin 警告區顯示；補抓成功／該碼退役自動清除；補全端（enrich）熔斷中止，與掃號端一致觸發失敗告警
- 券內容分類修正：飲料關鍵字補「柚茶」（91113 個人比薩五享餐飲料組含茉香柚茶，不再誤判副食）
- 內部維護：Windows 本機跑 step_2 parser 的中文 JSON 解碼修正（cp950 → utf-8）
- 連結預覽圖：新增 `og-image.png`（深色底 + 披薩 + 漸層 HutDeals），`twitter:card` 升為 `summary_large_image`
- 內部維護：測試快照移除官網公開金鑰（無功能影響）
- 版本：`package.json` 同步至 1.0.2

## v1.0.1（2026-09-08）— 公告即時性 + sitemap 自動更新

- 公告：`notices.md` fetch 改用 `no-cache`，每次載入都驗證新版（未改回 304），免等 CDN 10 分鐘快取
- sitemap：`update.yml` 補 `gen_sitemap` 步驟並納入 commit，每日更新自動重產
- 版本：`package.json` 同步至 1.0.1（原 0.1.0 未隨 v1.0.0 更新）

## v1.0.0（2026-09-08）— 正式上線

首發版。台灣必勝客優惠整理站（非官方），每日自動同步官網與官網驗證的聯名優惠碼。

**資料**
- 結構化價格取代 desc 文字：價格取官網結構化欄位（descPrice/套餐價格/price_selling），
  desc 僅兜底（起價標 priceNote「起」）與備用
- 券內容 items：訂餐流程選單版結構化爬取（組分類 cat：大/小/個人比薩、特殊比薩、
  義大利麵/飯、副食/飲料）；只改顯示分類、保留官網原始 group
- 每日掃號維持碼池（confirm/explore/sample）

**網站**
- 搜尋/篩選/排序/收藏、卡片含加價標記、詳情頁加價低→高排序
- Header 回首頁按鈕、hero 尺寸彩蛋（大13/小9/個人6 吋）
- 公告通知系統（作者 notices.md → 鈴鐺，新版自動彈出）
- SEO：OG/canonical/robots/sitemap（含券深連結）；頁尾非官方聲明

**CI（鏈式）**
- scan.yml 每日 01:11 起頭 → 三工成功 dispatch update → update 成功 dispatch deploy
- gate 熔斷：有未關失敗 issue 即禁掃；update/deploy 無固定 cron

## 開發期（2026-09-07 前）

內部開發階段（資料端結構化重構、前端建置、掃號架構），詳細 commit 對照見本地正本
（20260903 私有 repo，不公開）。
