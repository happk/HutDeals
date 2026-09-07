# HutDeals 工作流總覽（data pipeline）

> 本檔是**流程圖與現狀的權威文件**（與 `code-structure.md` 同級）；動線改動時同步更新。
> 更新：2026-09-08（orderflow items、分類 cat、公開版）。

## 1. 全域資料流

```mermaid
flowchart LR
  subgraph 每日CI["每日 CI（update.yml，台灣 00:30）"]
    OFF["官網 promotions 頁<br/>(plu/dgt 列表)"] --> BUILD["build_coupons.py<br/>解析→合併<br/>(60天 offline 規則)"]
    STATE[("data/scan_state.json<br/>碼池(活/死/空)")] --> INGEST["ingest_external.py<br/>官網驗證外部碼併入<br/>(source=verified-external<br/>官網優先)"]
    BUILD --> INGEST
    INGEST --> ENRICH["enrich_official.py<br/>官方碼 step_2 補全<br/>(通路/原價/cno直連/items)"]
    ENRICH --> OUT[("public/coupons.js")]
    ENRICH --> FULL[("public/coupons_full.js<br/>admin 全量")]
    OUT --> PAGES["GitHub Pages"]
  end

  subgraph 掃號線["掃號線（資料源）"]
    DUAL["每日三工 daily.py<br/>confirm/explore/sample"] --> STATE
    STATE --> ARCH["scan_archive.py<br/>自動歸檔 scan-history/<br/>coverage-map"]
  end

  subgraph 前端
    OUT --> SITE["React 站<br/>搜尋/篩選/收藏/詳情"]
    FULL --> ADMIN["admin.html<br/>全量/統計/爬取進度"]
  end
```

## 2. 碼狀態機（三態）

```mermaid
stateDiagram-v2
    [*] --> 空號 : 從未發行（M1 false 且無歷史）
    [*] --> 活 : M1 alive
    活 --> 死 : M1 轉 false，記 dead_since
    死 --> 活 : 觀察期內 M1 復活
    死 --> 空號 : 連續 1 週未復活（退役歸檔）
    空號 --> 活 : 掃到新發行
```

## 3. 各 CI / 腳本職責

| 觸發 | 腳本 | 職責 |
|---|---|---|
| 每日 00:30（update.yml） | `site.build_coupons` | 官網列表 → coupons.js 本體 |
| 〃 | `site.ingest_external` | scan_state 活碼 → coupons.js（外部碼） |
| 〃 | `site.enrich_official` | 官方碼 step_2 補全（orderflow 選單版 items；只補缺不覆蓋） |
| 每日（scan.yml，三順行 job） | `scan.daily confirm` | 現有碼死活＋內容更動確認；死碼 dead_since 滿 7 天→空號 |
| 〃 | `scan.daily explore` | 16/26 號段 M1 普查，新活碼自動入庫 |
| 〃 | `scan.daily sample` | 潛在未知號段抽樣（含 15/25 防長期券；命中→admin 警告） |

## 4. 禮節節奏

掃號對官網驗證端點請求遵守節奏（`lib/pacing`）：sleep + 隨機浮動、每 N 發中場休息、
換號段休息。熔斷：429/403 立即停、傳輸失敗記 unknown 不算死。

## 5. items 來源（orderflow）

券內容 items 用**訂餐流程選單版結構化爬取**（取代文字 parse_meal，退役至 `archive/parse/`）：
- `lib/orderflow.py`：4 步 session 流程（配 cookie → 取 llcs → step_1 選門市 → 重抓選單版），
  `BatchFetcher` K 張共用 session。
- `scan/parse_orderflow.py` + `extract_js.cjs`：選單版內嵌 JS 變數（psidss/pprcss/ctidss）→
  結構化候選 items（含組分類 cat）。
- 新 items schema：`{text, group, groupIdx, priceAdd, flavors[], cat}`（見 `docs/items-schema.md`）。

## 6. 價格與 desc 原則（2026-09-07）

- 結構化欄位一律從結構化 HTML（descPrice/套餐價格/price_selling/組標題），desc 只當備用。
- 起價券（無結構化固定價）以 desc「$N 起」兜底，`priceNote="起"` 標記（見 `docs/crawler-data-sources.md`）。
