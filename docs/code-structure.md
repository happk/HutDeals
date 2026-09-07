# HutDeals 代碼結構（code structure）

> 本文件是 `script/` 套件化的**唯一權威目錄樹**。
> 新增/搬移腳本前先讀本文件；實際結構若與此不符，以本文件為準並更新實際。
> 原則：site（官網→網站生產線）/ scan（掃號工作流）二區 ＋ support（測試）。
> 共用邏輯一律進 `lib/`，禁止跨檔複製。

## 目標樹（現行）

```
script/
├── __init__.py
├── lib/                      # 共用模組（消重複的核心；各區 import 用）
│   ├── __init__.py
│   ├── net.py                # UA/HEADERS、fetch_html、m1_probe、fetch_step2_html
│   ├── orderflow.py          # 訂餐流程 session（OrderFlowSession/BatchFetcher/fetch_and_parse）
│   ├── pacing.py             # sleep_scan()：jitter/seg-gap/中場休息
│   ├── state.py              # load_state / save_state（data/scan_state.json）
│   ├── coupons.py            # load_coupons_js / write_coupons_js / DATA_MARKER / 排序鍵
│   ├── text.py               # clean_text（空白整理；全 repo 唯一一份）
│   └── chart.py              # setup_cjk_font()（matplotlib 中文字型）
├── site/                     # 網站區：官網 → coupons.js 生產線（CI 每日）
│   ├── __init__.py
│   ├── fetch_promos.py       # 抓官網 promotions 頁（server-rendered 全列表）
│   ├── build_coupons.py      # 解析 → Coupon → 合併歷史 → coupons.js
│   ├── ingest_external.py    # 外部碼（官網驗證）併入 coupons.js
│   └── enrich_official.py    # 官方碼 step_2 補全（orderflow items；每日 CI）
├── scan/                     # 掃號工作流區：掃號 → 歸檔 → coupons
│   ├── __init__.py
│   ├── daily.py              # 每日三工（confirm/explore/sample；scan.yml CI 主排程）
│   ├── scan_run.py           # production runner（手動用；M1→orderflow step_2→合併 scan_state）
│   ├── scan_probe.py         # stateless 批次探測（--m1-only，研究用）
│   ├── scan_archive.py       # 掃號完成後寫 scan-history/coverage-map（hook）
│   ├── coverage_sync.py      # 掃號結果入庫橋（step_2 raw → scan_state；daily 共用）
│   ├── parse_step2.py        # step_2 頁 meta 解析（title/partner/通路/價格）
│   ├── parse_orderflow.py    # 訂餐流程選單版解析（psidss/pprcss/ctidss → 結構化候選 items）
│   └── extract_js.cjs        # node 執行頁面 JS 抽 psidss/pprcss/ctidss（parse_orderflow 依賴）
└── support/                  # 測試區
    ├── __init__.py
    └── tests/                # 單元測試（unittest）
        ├── test_build_coupons.py
        ├── test_parse_step2.py
        ├── test_parse_orderflow.py
        ├── test_scan_archive.py
        └── fixtures/         # plu_pdpop.html + step2/*.html + orderflow/*.html（官網真實抓取）
```

## archive/（退役區）

文字 items 產線退役實體移至 repo 根 `archive/parse/`：`parse_meal.py`（被 orderflow 取代）、
`parse-rules.md`、`refresh_meal_parse.py`、`test_parse_meal_items.py`。
新 items schema 見 `docs/items-schema.md`。

## 執行方式（套件化後統一）

- 所有腳本一律 **`python -m script.<區>.<模組>`**（例：`python -m script.site.build_coupons`）
- 不再 `python script/xxx.py`、不再 `sys.path.insert` 土法 import
- 測試：`python -m unittest discover -s script/support/tests -v`

## CI 對應（誰跑誰，鏈式 2026-09-08）

| Workflow | 觸發 | 執行的模組 |
|---|---|---|
| scan.yml | 每日 cron 台灣 01:11 + gate（無 open 失敗 issue 才跑）；手動 dispatch | `scan.daily confirm` → `explore` → `sample`（串行，各 job 自行 commit） |
| update.yml | scan 成功 repository_dispatch；手動 dispatch（**無固定 cron**） | `site.build_coupons` → `ingest_external` → `enrich_official` → `gen_sitemap` |
| deploy-pages.yml | push main + update 成功 repository_dispatch | npm（無 python） |

> 鏈式：scan 三工全成功 → dispatch `scan-complete` → update；update 成功 → dispatch `update-complete` → deploy。
> 任一步失敗 → 開 `scan-failed`/`scrape-failed` issue → 隔日 scan gate 見 open issue 即禁掃。
> scan.yml/update.yml 有 setup-node——orderflow session 流程用 node 執行選單版頁面 JS（extract_js.cjs）。

## 命名規約

- 檔名 snake_case；`site` / `scan` 二區各一職責。
- 共用函數一律 `lib/`（net/pacing/state/coupons/text/chart），**禁止跨檔複製**。
- coupon 價格 → `extract_coupon_price`、step2 價格 → `extract_step2_price`（同名衝突已消）。

## 產出（非代碼）去處

- 掃號狀態 → `data/scan_state.json`、`data/scan_coverage.json`、`data/scan_alerts.json`
- 網站資料 → `public/coupons.js`（前端直接載入）
