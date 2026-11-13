# 2026-11-13_403-step2-fuse-gate

2026-11-12 兩場 CI 失敗（issue [#9](https://github.com/happk/HutDeals/issues/9) / [#10](https://github.com/happk/HutDeals/issues/10)——官網 403 熔斷，掃號端 step2 403 未捕獲炸 exit 1、gate 查詢失效）的調查與修復計畫專案。

**狀態**：唯讀階段產物——調查與計畫定稿（v2），主代碼零修改，修復待執行。

## 檔案樹

```
2026-11-13_403-step2-fuse-gate/
├── README.md                            本檔：目的與檔案樹
├── reports/                             報告式文檔（閱讀順序見下）
│   ├── probe_20261113_issue9_10_403.md  ① 問題查找報告（定稿）
│   ├── 修復報告_20261113.md             ② 修復計畫 v1（被驗收對象，保留對照）
│   ├── 修復方法_20261113.md             ③ 逐步操作細節（現行＝v2 Phase 表）
│   ├── 驗收_20261113.md                 ④ 第三方驗收（對②的宣稱↔證據逐條檢驗）
│   ├── 校驗_20261113.md                 ⑤ 我方對驗收的逐條重驗（五缺口六偏差全部證實）
│   ├── 修復報告_v2_20261113.md          ⑥ 修復計畫 v2（現行計畫，採納④全部建議）
│   └── probe_20261113_gitignore_eval.md ⑦ gitignore 規則隔離實測（*backup*＋否定語句）
├── probe_20261113_smoke_m1_step2.py     煙霧 probe：查活單發＋詳情頁單發（官網解封實證）
├── probe_20261113_range_15809pm15.py    中斷點 ±15 區段兩輪掃號
├── probe_20261113_verify_gap1.py        缺口一 mock 重現（RuntimeError 重試 3 次）
├── test_fuse_after_fix.py               注入測試（403/429 失敗基線＋500/超時通過）
├── daily_main_20261113.py               origin/main 的 daily.py 快照（行號對照用）
├── smoke_backup_sha256_20261113.txt     煙霧前 data 三檔的 SHA-256 摘要
└── smoke_backup_20261113/               煙霧前 data 三檔備份（untracked，不入庫；還原用）
```

## 報告閱讀順序

①查找 → ②計畫 v1 → ④第三方驗收（檢驗②）→ ⑤校驗（重驗④）→ ⑥計畫 v2（採納④）→ ③操作細節（現行）。
⑦與 ③④⑤ 無關，屬備份移出作業的規則評估。

## 修復執行進度

計畫 v2 的五處修改與 Phase 1-6 均未執行；進度追蹤在 `reports/修復方法_20261113.md` 的 Phase 表。
