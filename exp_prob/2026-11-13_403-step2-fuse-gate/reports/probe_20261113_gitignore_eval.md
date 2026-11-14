# gitignore 規則評估：*backup* 搭配 !*backup*.py

## 背景

使用者提議：

```gitignore
*backup*
!*backup*.py
```

動機：排除資料備份，但保留備份相關腳本（如 `sim_backfill_snapshot.py`）。
**注意：`sim_backfill_snapshot.py` 檔名含 snapshot、不含 backup——`*backup*` 本來就不會擋它，
否定語句保護的是「未來」出現的名為 `xxx_backup.py` 的腳本。**

## 隔離 repo 實測（2026-11-13，臨時 git init 測試）

在 %TEMP% 建獨立 repo，寫入這兩條規則，放六個 fixture 看 git 實際行為：

| fixture | 直覺預期 | **git 實際** |
|---|---|---|
| `sim_backfill_snapshot.py` | 可追蹤 | **TRACKABLE** ✅（字串不含 backup） |
| `sim_merge_snapshot.py` | 可追蹤 | **TRACKABLE** ✅ |
| `smoke_backup_20261113/scan_state.json` | 被擋 | **IGNORED** ✅（第 3 行 `*backup*` 擋） |
| `smoke_backup_20261113/some_script.py`（備份目錄裡的 .py） | 被否定語句救回？ | **IGNORED** ❌（第 3 行擋——目錄被排除後 git 不進去掃，否定語句無效） |
| `backup_notes.py`（根層自帶 backup 的 .py） | 被否定語句救回 | **IGNORED** ❌（**第 4 行 `!*backup*.py` 自己擋的**） |
| `exp_prob/sim_backup_restore.py`（同名腳本） | 被否定語句救回 | **IGNORED** ❌（同上） |

**`check-ignore -v` 逐字輸出**：

```
IGNORED  smoke_backup_20261113\scan_state.json   <- .gitignore:3:*backup*
IGNORED  smoke_backup_20261113\some_script.py    <- .gitignore:3:*backup*
（backup_notes.py 與 sim_backup_restore.py 為 check-ignore 命中否定行＝「被排除規則集遮蔽」）
```

**補測澄清**（避免誤判）：第二次查詢顯示 `backup_notes.py`／`exp_prob/sim_backup_restore.py`
在 `ls-files -o --exclude-standard` 中**可見**（=可被追蹤）、`check-ignore -v` 命中第 4 行否定規則。
`check-ignore` 命中 `!` 規則表示「有規則提及，但結果是**不**忽略」。
所以六個 fixture 的正確判定是：

| fixture | 最終判定 |
|---|---|
| `sim_*_snapshot.py` ×2 | 可追蹤（未被任何規則碰） |
| `smoke_backup_20261113/` 兩檔（.json 與 .py） | **都被忽略**（`*backup*` 擋；否定救不了被擋目錄內的檔案） |
| `backup_notes.py`（根層自帶 backup 的 .py） | **可追蹤**（否定語句生效） |
| `exp_prob/sim_backup_restore.py` | **可追蹤**（同上） |

即使用者提議的兩條規則**行為與直覺一致**：資料備份被擋、備份目錄內的一切被擋（含 .py）、
根層自帶 backup 的 .py 被救回。

## 建議

**可以採用使用者的兩條規則**——隔離實測證實行為與直覺一致：

```gitignore
# probe 備份（data 產物不進歷史；sha256 摘要可進）
*backup*
!*backup*.py
```

- 資料備份（.json/.md/.txt 任何在 backup 路徑下的檔）被擋 ✅
- snapshot 腳本不受影響（字串不含 backup）✅
- 未來「檔名自帶 backup 的 .py 腳本」會被否定行救回 ✅（唯一已知限制：被擋目錄內的 .py 救不回——git 不進入被排除目錄掃描；對本專案而言，備份目錄裡本來就不該有要追蹤的 .py，限制無實害）
- `sha256.txt` 在備份目錄內會被擋——摘要檔改放專案資料夾根部（如 `smoke_backup_sha256_20261113.txt`），或靠報告內文記錄

附帶：`check-ignore -v` 命中 `!` 行＝「提及但**不**忽略」，第一輪測試曾誤讀為「擋掉」；
判定一律以 `git ls-files -o --exclude-standard`（可被追蹤清單）為準。
