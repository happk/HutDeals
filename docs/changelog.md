# HutDeals Changelog

> 版本紀錄，新版本在上。`vX.Y.Z`：
> - X 大版本（上線/重大架構）
> - Y 功能
> - Z 修正

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
