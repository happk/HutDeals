# HutDeals Changelog（改動 ↔ commit 對照）

> 記錄功能改動與對應 commit，方便回溯「哪個 commit 做了什麼」。
> 依日期倒序累積；格式：`[日期] 類別 — 項目 → commit`。

## 2026-09-07 ~ 2026-09-08（資料端結構化重構 + 前端 + 分類擴充）

| 類別 | 項目 | commit |
|---|---|---|
| data+frontend | 結構化價格取代 desc 文字、msrp 分欄、組分類 cat/groupTitle、desc 全文備用、前端四項(回首頁/尺寸彩蛋/讀cat/卡片) | `3a762f0` |
| frontend | 彩蛋互動提示移入通知、Hello Pizza 永久空態佔位 | `f8f1a21` |
| orderflow | 修跨卡誤抓(飲料誤標加價 172 筆，漏 pdName 錨點) + 全量重抓 + 歸檔工具 | `b644be8` |
| frontend | 卡片顯示前4候選含加價 + 通用加購 bar 按鈕 + addons.json(gen_addons) | `64b0dec` |
| frontend | 卡片候選 +0 優先顯示(加價殿後補位)，修 16275 加價擠掉 +0 | `16119bd` |
| frontend | 詳情頁加價區依 priceAdd 低→高排序 | `fb2a61b` |
| data | coupons.js 重建後外部碼 flavors 恢復(flavorSets/flavorIdx) | `a3605e1` |
| data | **組分類擴充：新增 義大利麵/飯、副食(煎餅/點心)、特殊比薩** 類別(以官網組標題為準、只改顯示不動 group) | `87270dc` |
| data | **compact_coupon_items 冪等化** — 修 enrich/build 二次 compact 弄丟 flavors(餅皮選項消失) | `afef517` |
| frontend+data | 篩選區對齊 cat：加 特殊比薩/義大利麵/副食(原「副餐」錯字修正)、ingest 非尺寸類 cat 進 tags | `ef8ddec` |
| docs | items-schema/crawler-data-sources 補 cat 完整分類規則 | `030ce7a` |
| chore | 歸檔 cat 探查腳本(probe_main_titles/probe_cat_sample) | `edafdc6` |

### 分類架構速記（2026-09-08 定稿）

組 `cat`（以官網組標題 `main_food_subject_N` value 為準，**只改顯示、不動 group**）：

| cat | 組標題字樣 | 例 |
|---|---|---|
| 大比薩 | 大比薩 / 13吋 | 94199、93022 |
| 小比薩 | 小比薩 / 9吋 | 16013、16275 |
| 個人比薩 | 個人比薩 | 26898、16010 |
| **特殊比薩** | 手工義式薄比薩 / Flatzz | 16167、16173 |
| **義大利麵/飯** | 義大利麵/飯 / 筆管麵 / 千層麵 / 飯麵 | 16188、91112 |
| **副食** | 副食 / 韓式海鮮煎餅 / 點心 | 16202、92114 |
| 飲料 | (second 組整組候選全飲料含湯) | 16010 second |
| 比薩 | 含比薩無尺寸(中性) | — |

尺寸對照：大=13吋 / 小=9吋 / 個人=6吋（使用者 2026-09-07 更正，官方組標題佐證）。

### 資料欄位補充（2026-09-07~08）

- 券級：`msrp`(原價, desc 推測, 顯示刪除線)、`priceNote`(僅「起」desc 兜底標記)
- 候選：`cat`(組分類)、`groupTitle`(官方組標題原文, scan_state 限定不進 coupons.js)
- desc：全文存 scan_state 備用；coupons.js 僅結構化 items 拆不出時才帶 description
- 價格層級：descPrice/套餐價格/price_selling(結構化) → desc「$N 元起」兜底(priceNote=起) → None
- 詳見 `docs/crawler-data-sources.md`、`docs/items-schema.md`
