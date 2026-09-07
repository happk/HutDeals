# archive/tool — 一次性分析/驗證工具暫存

> 放「未來可能重跑」的調查/驗證腳本（有保留價值但不屬主線 script/）。
> 主線正式工具在 `script/`（見 docs/code-structure.md）；這裡是探索期的暫時工具。
> 歸檔原則：可重跑驗證、具參考價值 → 進這裡；一次性 → 不留。

## 目錄

| 檔案 | 用途 | 何時重跑 |
|---|---|---|
| `probe_sample_20.py` | 20 號抽樣實抓官網：結構化價格來源 + 組標題 cat 對照 | 改 parser/價格規則後，抽樣驗證跨型券 |
| `probe_crosscard_bug.py` | 估算 parse_orderflow 跨卡誤抓(飲料誤標加價)影響範圍 | 修價格解析後，確認誤標清乾淨 |
| `probe_second_card.py` | 看 second 組候選 priceAdd 分佈(哪些卡片預覽會空白) | 改卡片顯示規則時 |
| `trace_price_26868.py` | 實證 26898/26868 價格誤抓根因(desc 文本 vs descPrice) | 價格規則再改動時回顧 |
| `verify_fix_scan_state.py` | 驗證 scan_state 中「疑似飲料卻加價」的跨卡誤抓殘留 | 改價格解析/全量重抓後確認誤標清乾淨 |
| `probe_main_titles.py` | 盤點全站 main 組標題詞彙(19種)供 cat 分類表設計 | 未來要加/改 cat 類別時 |
| `probe_cat_sample.py` | 抽樣跨類別號碼重抓→驗證 cat 分類(比薩/義大利麵/副食/特殊比薩) | 改 cat 分類規則後抽樣確認 |

## 背景

- 2026-09-07 資料端重構：desc 退出結構化欄位、價格改結構化來源時產出這些驗證腳本。
- 修正跨卡誤抓：`parse_orderflow._card_name_price_raw` 原本固定往後 3000 字元找價，
  空價卡會跨卡誤抓下一張/加購區價（16010 可樂被標 +79=薯金幣）。已修（限卡內）+ 全量重抓。
- 使用者工作流：`exp_prob/` 是個人實驗目錄（untracked），一次性腳本多放那；可重用才歸到這。
