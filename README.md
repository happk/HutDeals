# HutDeals — 台灣必勝客優惠整理

網站: https://happk.github.io/HutDeals/

每天自動蒐集[必勝客官網](https://www.pizzahut.com.tw/promotions/?mode=cpSch&type=plu)優惠與官網驗證的聯名/季節優惠碼，整理成可搜尋、篩選、排序、收藏的靜態網站。

※ 非官方專案；資料皆經官網頁面或其訂餐驗證端點確認。

## 架構

```
script/site/fetch_promos.py     抓官網 promotions 頁(plu/dgt, server-rendered 全列表)
script/site/build_coupons.py    官網列表 → 價格/標籤/通路 → 合併歷史(下架 60 天清除) → public/coupons.js
script/site/ingest_external.py  官網驗證的外部碼(scan_state)併入 coupons.js
script/scan/daily.py            每日掃號三工(confirm/explore/sample)：維護碼池死活 → scan_state
script/site/enrich_official.py  官方碼 step_2 補全(通路/原價/直連兌換/結構化內容)
.github/workflows/scan.yml         每日掃號排程(維持 scan_state)
.github/workflows/update.yml       每日建 coupons.js 排程 + 失敗開 Issue 告警
.github/workflows/deploy-pages.yml build + deploy 到 GitHub Pages
src/                           React + Vite + TS + Tailwind 前端
```

完整代碼結構見 `docs/code-structure.md`；資料流見 `docs/workflow.md`。

資料獲取後輸出靜態 `public/coupons.js`(`window.HUTDEALS_COUPONS`)，前端直接載入，無後端。

## 開發

```bash
# 資料獲取(Python 3.12, stdlib 零依賴, 套件化後用 python -m)
python -m script.site.build_coupons
python -m unittest discover -s script/support/tests

# 前端(Node 22+)
npm install
npm run dev      # http://localhost:5173
npm run build    # tsc -b && vite build → dist/
npm test         # vitest
```

## 聲明

非必勝客官方網站；資料來源為必勝客官網公開頁面與官網訂餐驗證端點回傳。
價格與供應以官網為準，商標歸屬各權利人。
