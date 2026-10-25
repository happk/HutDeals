# merge 繼承官券補全欄位 — 修復計畫報告（2026-10-26）

> 目標：實作[分析報告](官券補全掉殼分析報告.md)定案的修法——`merge()` 繼承 enrich 補全欄位，消除掉殼一天（todo c5d1634-1）。
> 依據：欄位集合經 [probe_fields.py](probe_fields.py) 對當前資料實測校正——todo 記三欄，實為六欄（見下表）。
> 範圍：[`build_coupons.py:merge()`](../../script/site/build_coupons.py#L118-L130) 一處＋測試＋docs。enrich、資料檔、外部碼路徑零改動。
> 產物：[probe_fields.py](probe_fields.py)（修復前事實核查）、[sim_merge_snapshot.py](sim_merge_snapshot.py)（快照模擬測試）。

## 結論

改動 12 行：merge 的 else 分支（舊券存在時）對「新殼缺、舊券有」的補全欄位抄舊，`orderUrl` 舊者勝出。補全結果自此黏在券身上，enrich 失敗日不再掉殼；enrich 成功時的覆寫/補缺行為不變，繼承值至多落後一個 enrich 週期。單元測試 +9、快照模擬對真實資料 PASS，全套測試綠。

## 變更內容

[`build_coupons.py:125-130`](../../script/site/build_coupons.py#L125-L130)（修復後行號）：

```python
for f in ("items", "flavorSets", "units", "msrp", "orderType"):
    if old.get(f) and not coupon.get(f):
        coupon[f] = old[f]
if old.get("orderUrl"):
    coupon["orderUrl"] = old["orderUrl"]  # cno 直連優於通用訂餐頁——舊者勝出
```

繼承欄位集合與語意規則（每欄的實測依據見[分析報告](官券補全掉殼分析報告.md)資料實測節）：

| 欄位 | 語意 | 依據 |
|---|---|---|
| items | 缺才抄 | 22/22 補全券的主體欄 |
| flavorSets | 缺才抄，與 items 同進同出 | items 的 flavorIdx 指向它；落單＝懸空索引（前端口味壞掉）；空陣列視同無、不無中生有 |
| units | 缺才抄 | items 一致性（20/22） |
| msrp | 缺才抄 | 稀少（2/22）但存在 |
| orderType | 缺才抄 | 實測 0 張觸發；防「名稱改版拿掉通路字樣」邊角 |
| orderUrl | 舊者勝出 | cno 直連由 code 推導、無過期風險；失敗日不降級回通用頁 |

不變量：新殼自身有值時不被覆蓋（繼承只墊底）；外部碼走 kept-not-seen 原樣保留分支，不進繼承邏輯；enrich 成功時仍無條件覆寫 items/orderUrl、只補缺 orderType/msrp。

## 測試

單元測試：[`test_build_coupons.py` 的 `TestMergeInherit`](../../script/support/tests/test_build_coupons.py) +9 案例——六欄繼承主案例、無 flavorSets 合法形狀不造懸空、新值勝出、名稱改版繼承 orderType（防禦）、全新券無繼承、offline 復活保留補全、外部碼分支不受影響、orderUrl 舊者勝出、**繼承→write→load roundtrip**（鎖 2026-09-08 flavorSets 冪等 bug 不復發）。

快照模擬：[sim_merge_snapshot.py](sim_merge_snapshot.py)——用 build 自己的 `enrich()` 把真實 coupons.js 的 41 張官券重建為列表殼（忠實模擬明日 update 的 build 步驟），與真實 existing 跑真 `merge()`，語意化斷言（不鎖鍵名，資料日更不破壞）。**實跑 PASS**：補全官券 22 張四欄全保留、flavorIdx 無懸空、cno 直連保留、外部券 682 張零變動。模擬 stats 的 `revived=29` 是快照把全部官券視為在架的副產物——29 張 offline 殘影因此實測了「復活＋繼承」路徑，屬加測。

## 驗證

| 項目 | 指令 | 實跑結果 |
|---|---|---|
| Python 全套 | `python -m unittest discover -s script/support/tests` | OK（含既有全部＋TestMergeInherit 9） |
| 快照模擬 | `python exp_prob/2026-10-26_merge-inherit-fix/sim_merge_snapshot.py` | PASS（22 張保留／682 零變動） |
| 前端不回歸 | `npm test` | 7 檔 60 測試全綠（merge 不動現有 coupons.js） |
| 實戰驗證 | 手動 dispatch update.yml 或 cron 恢復後 nightly 鏈 | **使用者自行處理**（已拍板） |

## 執行順序與授權邊界

| 步 | 內容 | 狀態 |
|---|---|---|
| 1 | merge() 實作＋單元測試＋快照模擬 | ✅ 完成 |
| 2 | 全套測試綠 | ✅ 完成 |
| 3 | docs 收尾：todo.md 移除 c5d1634 條目 1（條目重編號）、changelog 未分配加條目 | ✅ 完成 |
| 4 | commit（直接 main、無分支，已拍板）——先另 commit 工作樹上既有的「搜尋運算子構想」todo 條目，再 commit 本修復 | **等拍板** |
| 5 | push main（ff）→ deploy-pages 自動（前端無變更，無害） | **等拍板** |

commit 訊息草稿：`fix(site): merge 繼承官券 enrich 補全欄位——items/flavorSets/units/msrp/orderType/orderUrl，消除掉殼一天（c5d1634-1）`

## 不在這次範圍

- **c5d1634-2**（無通路字樣官券 orderType 補不出，20/41 空）——需拍板語意（留空或預設值），另案。
- **c5d1634-3**（「套餐價格：199起」價格 regex 放寬＋priceNote=起）——另案。
- **enrich targets 重試行為**——慢性殼（parse 失敗型）仍會被每日重抓，屬既有行為；本修復只保證曾補到的不再掉。

## 風險與對策

| 風險 | 評估與對策 |
|---|---|
| 繼承值過期（官網改內容後、enrich 未成功前） | enrich 成功時無條件覆寫 items/orderUrl——至多落後一個週期；與「掉殼一天」相比嚴格更好 |
| items/flavorSets 落單 | 同進同出寫在同一迴圈；roundtrip 測試＋快照無懸空斷言雙保險 |
| 外部碼誤傷 | 單元測試鎖外部分支原樣保留；快照對 682 張驗證零變動 |
| 資料日更破壞快照測試 | 語意化斷言（不鎖鍵名張數），對當日資料驗證 100% 保留率 |
