# dead_since 缺值補值 — 修復計畫報告（2026-10-26）

> 目標：修復 [docs/todo.md](../../docs/todo.md) cb13be8 條目 1「confirm 退役判斷卡死：dead 缺 `dead_since` 永不轉 empty」。
> 語意拍板：使用者提出 backfill 案（缺值補今天、觀察窗重起算、活的照樣復活）——代理確認機制正確，並把謂詞由「欄位不存在」校正為「缺有效值（falsy）」。
> 範圍：[`daily.py`](../../script/scan/daily.py) cmd_confirm dead 分支一處＋測試＋docs。直接 main（小修慣例，不開 branch）。
> 產物：[sim_backfill_snapshot.py](sim_backfill_snapshot.py)（真實資料目標精確度驗證，可重跑）。

## 結論

一行補值：confirm 的 dead 分支在 days 計算前，對「`dead_since` 缺有效值」的紀錄落地寫入今天。15 筆 2026-09-04 遺留紀錄（key 不存在形狀，[sim 實測](sim_backfill_snapshot.py) 15/15 精確命中）首次流經即補值，7 天後自然退役轉 empty；「存在但 None」形狀的崩潰炸點（`fromisoformat(None)`）同步自癒；alive 654 碼與 empty 48 碼零影響（補值只在 dead 分支執行，活碼不流經）。

## 變更內容

[`daily.py:258-269`](../../script/scan/daily.py)（修復後行號）：

```python
        elif r.get("m1_success") is False:
            # dead_since 缺值落地補值（cb13be8-1，2026-10-26）：runtime 的 get default
            # 只讀不寫，缺欄位的 dead（2026-09-04 遺留 15 筆）days 恆 0 永不退役——
            # 補值日＝觀察窗起算日，7 天後自然退役；falsy 謂詞兼防「欄位存在但 None」
            # （用「無有效值就補」而非「欄位不存在才補」。
            # 「欄位存在但值是 None」，那會讓下一行的 fromisoformat(None) 直接崩）。
            # 已有有效值不覆蓋；alive 碼不流經此分支，不受影響。
            if not codes[code].get("dead_since"):
                codes[code]["dead_since"] = today
            since = codes[code].get("dead_since", today)
            days = (dt.date.today() - dt.date.fromisoformat(since)).days
```

### 設計決策

| 決策 | 選擇 | 理由 |
|---|---|---|
| 謂詞 | falsy（不存在／None／空字串都補），非「key 不存在才補」 | `dict.get(k, default)` 的 default 不保護「存在但 None」——該形狀會讓 `fromisoformat(None)` TypeError 炸掉 confirm；使用者原案「為空不處理」反轉為「為空也補」（今日資料兩案結果相同，falsy 把未來崩潰形狀也自癒） |
| 補值位置 | 消費點（dead 分支、days 計算前） | 標死路徑（[daily.py:184](../../script/scan/daily.py)）本來就寫 `dead_since=today`（9/30 過期潮 38 筆 empty 帶值為證）——bug 只在消費點的 fallback 只讀不寫；一次性遷移腳本無自癒能力（同 merge-inherit 結論） |
| 語意 | backfill 重起算 7 天觀察窗，非「缺值直接轉 empty」 | 使用者拍板：保留觀察語意；代價僅 7 天×15 發探測。復活偵測兩案皆通（dead 期間 confirm 每日全探；退役後 16xxx 6 筆回 explore 每日普查、段外 9 筆靠 sample 每日 10% 隨機——差異已向使用者披露） |

## 情境×前後對照

| 情境 | 修復前 | 修復後 |
|---|---|---|
| dead 缺 `dead_since`（15 筆遺留） | days 恆 0、**永不退役**；每日白探 1 發；永不退役→不被 explore 普查盯復活 | 首次流經補值=今天 → +7 天（≥ 2026-11-02）退役轉 empty；退役後回歸普查／sample 監看 |
| dead `dead_since=None`（今日 0 筆，未來形狀） | `fromisoformat(None)` **TypeError 炸 confirm** | 補值自癒，走正常生命週期 |
| dead 有有效值 | 照常 7 天退役 | 同左（**零改變**——原值不覆蓋） |
| 復活（缺欄位 dead 探測成功） | 照常復活＋清欄位（路徑本來就通） | 同左（**零改變**） |
| alive 654 碼（多數無 `dead_since`＝正常形狀） | 不受影響 | 同左（**零改變**——不流經 dead 分支；670 falsy 疑慮已由測試鎖定） |
| alive→死 | 標死路徑寫 `dead_since=today` | 同左（**零改變**——補值非標死路徑的依賴） |
| empty 48 碼 | 不在 confirm 探測集合 | 同左（**零改變**） |
| 煙霧模式（`--limit`）當日未探到的 dead | 不退役 | 補不到值，下次全量 run 補上（無害） |
| 同日重跑 | — | 冪等：已補值者不重寫、days=0 不誤退役 |

## 測試與驗證

| 項目 | 內容 | 實跑 |
|---|---|---|
| 單元 | [`test_dead_since_backfill.py`](../../script/support/tests/test_dead_since_backfill.py) 9 案例：缺值補值不退役／None 不炸／有效值不覆蓋且滿 7 天照常退役／缺值復活乾淨／alive 不被補值（670 疑慮鎖定）／alive 標死走既有路徑／empty 不探不動／補值→撥快 8 天→退役完整生命週期／同日重跑冪等 | 9/9 ok |
| 快照 | [sim_backfill_snapshot.py](sim_backfill_snapshot.py)：真實 scan_state × 同一謂詞——目標 15/15 精確命中（全 key-不存在形狀、firstSeen=2026-09-04）、有效值 dead 0 筆、非 dead falsy 655 筆僅證「正常形狀」（confirm dead 分支走不到） | PASS |
| 全套 | `unittest discover`＋`npm test` | OK／61 綠 |

### 驗證動作盤點——實際做了什麼、沒做什麼

**實際執行的驗證全部是合成/mock 輸入＋唯讀真實資料**——未打官網、未寫真 scan_state、未跑真 CI：

- 單元測試：mock `daily` 命名空間（load_state/probe_batch/fetch_and_parse 等，同 [`test_confirm_revive`](../../script/support/tests/test_confirm_revive.py) 既有模式）；真實時鐘不可注入，「跨日退役」以資料撥快（把補值後的 `dead_since` 撥到 8 天前）模擬。
- 快照模擬：真實 scan_state **只讀**，同一謂詞在記憶體重放。

**未驗證面與實戰驗證清單**（cron 恢復或 smoke dispatch 後，下一次真實 confirm）：

1. 掃號 log 出現 15 碼無異常（不會有專門 log——補值是安靜的）；`data/scan_state.json` 的 15 筆 `dead_since` 落值＝執行日。
2. 執行日＋7 天起的 confirm log 出現 `15140 死→空號（退役，死亡 7 天）` 式訊息，15 碼逐日退役。
3. 期間若某碼復活：log `死→活（觀察期復活）`＋state 清欄位。

## 執行順序與授權邊界

| 步 | 內容 | 狀態 |
|---|---|---|
| 1 | 實作＋單元測試＋快照模擬 | ✅ |
| 2 | 全套測試綠 | ✅ |
| 3 | docs 收尾：todo.md 移除 cb13be8-1、changelog 未分配加條目 | ✅ |
| 4 | commit（直接 main） | **等拍板** |

commit 訊息草稿：`fix(scan): confirm 對缺 dead_since 的 dead 落地補值——觀察窗自補值日起算，15 筆遺留自然退役（cb13be8-1）`

## 不在這次範圍

cb13be8-2（deploy-pages 告警——todo 現僅存此條，歸屬錯誤分級藍圖擱置）、c5d1634-2/3（orderType 拍板／價格 regex probe）。**本修復後，todo.md 潛在漏洞區僅剩「已拍板擱置」與「待拍板語意」兩類，無一行修等級的存量。**
