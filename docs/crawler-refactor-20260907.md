# 訂餐爬取價格規則重構紀實（2026-09-07）

> 記錄本次「必勝客訂餐流程爬取」價格規則從摸索到定案的**完整過程**：
> 對話中所有有價值的調查報告、嘗試（含失敗）、測試碼、錯誤 debug、數據表、
> 最終設計與 commit。供未來維護者理解「為什麼 parse 長這樣」，也記錄
> 官網價格結構的各種語意陷阱。
>
> - 資料欄位來源的**權威速查表**：見 `docs/crawler-data-sources.md`
> - 本文件是「怎麼走到那張表」的完整過程 + 調查數據。

## 0. 名詞

- **組 / groupIdx**：一張券可能要選多個主餐（`main_food_num=N`）。每個是獨立
  「組」。例 26868 有 2 組（都是「請選擇1個個人比薩」）、16109 有 3 組
  （買 1 大送 2 小）、16088 有 3 組。
- **候選 / candidate**：組內可選的某個口味/產品（每張卡 `<div class="pdpop-li"
  id="mainpop_{組}_{pid}">`）。
- **加價型 vs 基準型**：看候選 `.pdpop-price` 有無 `+`（見 §4）。
- **descPrice**：券價顯示 div（`<div class="descPrice">$666</div>`），加價型通常有。
- **pprcss.add**：官網 JS 變數 `pprcss[組][pid].add`（見 §3，不可全信）。

## 1. 背景與動機

訂餐流程爬取（orderflow，session 流程拿「選單版」）取代文字 parse 後，發現
scan_state 價格有誤，使用者回報兩例：

1. **26868 組2 彩蔬鮮菇被標 +$14**——但實際不加價。26868 是「買 1 個 $95 起
   + $49 加購第 2 個」，組2（第 2 個 +49）選彩蔬或四小福都一樣，購物車實測
   「組1 四小福 + 組2 彩蔬 = 144」（= 95+49，彩蔬不加）。
2. **16013 極炙被 parse 誤判為 0**（早期只認 `+$`），實際極炙要付 $638。

目標：找出**可靠、不 parse 純文本、找 class 結構**的候選加價規則。

## 2. 第一輪：誤信 pprcss 補價 → 發現核心 bug

原始 parse 邏輯：候選 `.pdpop-price`（DOM）抓不到價時，用官網 JS 變數
`pprcss[組][產品id].add` 補價。

**debug 證據（26868）**：組1 與組2 彩蔬卡片結構幾乎一樣，唯一差別在
`psidss.main[0].push` / `pprcss[0]` / `ctidss.v["g1_2994"]`（組1）vs
`psidss.main[1]` / `pprcss[1]` / `ctidss.v["g2_2994"]`（組2）。而**兩組的
pprcss.add 都是 14**：

```
組1: pprcss[0]["2994"] = {basic:[0,0], add:14}
組2: pprcss[1]["2994"] = {basic:[0,0], add:14}
```

但 **DOM 顯示不同**：組1 彩蔬卡 `.pdpop-price` = `+$ 14`，組2 彩蔬卡 = **空**。
購物車實測組2 彩蔬不加價（144）。

**結論**：官網 UI（DOM）知道組2 不加價（所以顯示空），但 JS 資料 pprcss 沒區分
（兩組都寫 14）——**pprcss.add 對「加購/送組」是殘留錯誤**。DOM 才是 UI 真相。

## 3. 調查：pprcss 結構與語意

多張券抽樣 pprcss：

| 券 | 候選 | pprcss |
|---|---|---|
| 16013 | 極炙 | `{basic:[0,0], add:239}` |
| 16013 | 四小福($399口味) | `{basic:[0,0], add:0}` |
| 26868 組1 | 千島 | `{basic:[0,0], add:40}` |
| 26868 組2 | 彩蔬 | `{basic:[0,0], add:14}` ← 殘留錯誤 |
| 16010 | 全 | `{basic:[0,0], add:0}` |

- `basic` 永遠 `[0,0]`，無用。
- `add` 對**主餐組** = 補差（16013 極炙 239 = 638−399、26868 千島 40）。
- `add` 對**加購/送組**（26868 組2、26880 組2）是殘留，不可信。
- scan_state 舊資料的 priceAdd 其實大多 = pprcss.add，所以「16013 極炙 +239」
  是對的（使用者指出）；真正錯的只有加購/送組被誤標。

## 4. 核心發現：`.pdpop-price` 三種呈現

用瀏覽器實操官網 + DOM 分析，確認候選 `.pdpop-price` 三種內容：

| 呈現 | 語意 | 例子 |
|---|---|---|
| `+$ 40` | **加價型**：補差直接給 | 26868 千島 +40、經典 +34；16088/16271 升級口味 |
| `$ 638` | **基準型**：絕對單價（選它付單價）| 16013 極炙、16109/26757/26966 大比薩 |
| 空 | **不加價**（套餐內基本款 / 加購·送組）| 26868 四小福、組2 全部 |

**使用者關鍵洞察**：「有 `+` 的就是加價版，沒 `+` 的是基準/單點」「16013 是闖關式
（先選口味才展開餅皮）」「16088 右上角有清楚 `$666` 在網頁架構」。

## 5. 16013 瀏覽器實測全程（基準型鐵證）

官網 16013 選單實際操作（瀏覽器）：

1. 進選單，候選都標**絕對單價**：極炙 $638、和風 $519、火辣 $454、
   松露 $628、法式 $628…直到 $399（四小福/夏威夷等 10 個 = 券價）。
2. 點極炙 → 彈出選擇；**餅皮預設「火山起司芝心 +$155」** → 加入購物車 = **$793**
   （= 638 + 155）。
3. 把餅皮改「鬆厚(+0)」（radio `main_food_ps_id_1[value=3020]`）→
   加入購物車 = **$638**。
4. 改選四小福 + 鬆厚 → 加入購物車 = **$399**。

**結論**：基準型候選標的是**絕對單價**，選哪個付哪個（極炙 638、四小福 399）。
「補差 239 = 638−399」是 scan_state 自己算的相對值。

## 6. 券價（基準）來源調查

| 來源 | 位置 | 例 |
|---|---|---|
| `descPrice` div | `<div class="descPrice notranslate">$ 666</div>`（h1 下方）| 16088、26868($144)、16271 |
| `caculate_price()` | JS：`var price = 666` / `cbData.is_package_price ? cbData.price_selling : 0` | 16088、26868 |
| `getCbData()` 的 `price_selling` | JS：`{is_package_price:1, price_selling:399}` | 16013、16313(168) |

- **有 descPrice 的券**（16088/26868/16015）= 加價型；候選 `+$ 或 空`。
- **無 descPrice、走 price_selling 的**（16013/16313）= 基準型 package。
- **無 descPrice 也無 price_selling**（16109/26757/26966）= 基準型多組
  （每組候選標單價，組最低 = 該組基準）。

## 7. 12 張樣本分類調查（全數據）

抽樣 12 張不同券型（限價/加購/個人/大比薩/買送），逐一抓選單版分析：

| 券 | descPrice | main 組 | 候選呈現 | 型 |
|---|---|---|---|---|
| 16015 | 144 | g1:+$11 空4 / g2:全空5 | 加價型(組2=加購) |
| 16088 | 666 | 3 組 | g1 空2 / g2,g3 +$19 空8 | 加價型(組2/3=送) |
| 16109 | 無 | 3 組 | g1 $單價15 / g2,g3 $單價27 | 基準型(買1大送2小) |
| 16271 | 666 | 2 組 | g1 空6 / g2 +$17 空10 | 加價型 |
| 16295 | 666 | 3 組 | 同 16088 | 加價型 |
| 16313 | 無(168) | 1 組 | $單價5(全$168) | 基準型(固定) |
| 16317 | 無(168) | 1 組 | 同上 | 基準型(固定) |
| 26757 | 無 | 2 組 | g1,g2 $單價26 | 基準型 |
| 26800 | 無 | 2 組 | 同上 | 基準型 |
| 26898 | 144 | 2 組 | 同 16015 | 加價型(組2=加購) |
| 26966 | 無 | 3 組 | 同 16109 | 基準型 |
| 26979 | 142 | 2 組 | g1,g2 全空 | 特殊(全空=固定) |

**多組券的組最低單價**（16109 例）：組1 大比薩 $690-899（最低 690）、
組2/3 小比薩 $320-649（最低 320）→ 補差各組自減自己最低。

## 8. 嘗試與失敗（依序）

### 8a. `_slice` 字串切割（原 parse，失敗）

```python
def _slice(html, start, maxlen=8000):
    for c in ('</div>\n\n\n\n', '<div class="pdpop-li '):
        j = html.find(c, start)
        ...
```
**bug**：卡片開頭 `<div class="pdpop-li" id="mainpop_..">` 後常接一長串資料
`<script>`（psidss/pprcss/ctidss）。stop 字串 `'<div class="pdpop-li '` 從
**卡片自己起點**找，offset 0 就命中（自己）→ `_slice` 截成**空字串**。
`'</div>\n\n\n\n'` 又在 script 內 ctidss.info 的 `d:` HTML 中出現 → 也截斷在
name/price 前。

**debug 證據（26880）**：卡片 div 起點 84397，`pdpop-name` at 3816、
`pdpop-price` at 4177，但 `_slice` 截到 offset 0 → 全抓不到 → fallback pprcss。

### 8b. 12000 字元視窗（失敗）

改成「卡片起點往後抓 12000」直接找 name/price。26880 成功了（極炙 +268 抓到），
但 **16010 跨卡誤抓**：日式照燒卡無自己的 price，視窗跨到後面加購區抓到
`show_price +$79` → 誤標 79。

**debug**：16010 日式照燒卡，下張卡在 offset 106，但 `show_price +$79` 在
offset 11100（加購區）→ 視窗太長跨卡。

### 8c. regex 漏多 class（失敗）

`class="pdpop-price"`（要求引號緊跟）對 `class="pdpop-price notranslate"`
匹配失敗（實際 pdpop-price 後是空格非引號）。改 `class="pdpop-price[^"]*"`。

### 8d. 只認 `+$`（失敗）

`_find_price` 只認 `+$NN` → 26868 組2 修好（空→0），但 16013 極炙誤判 0
（它顯示 `$638` 無 +）。**漏了基準型。**

### 8e. name 錨點法 + 券型判定（成功，定案）

1. **name 錨點**：卡片 div 起點 → 卡片內第一個名稱（`.pdpop-name` /
   `.pd_name data-name` / add 卡 `optgroup label`），price 緊鄰其後（限 3000 字元）。
2. **券型判定**（每組內 `_resolve_price`）：
   - 有候選 `+$` → 加價型：`+$NN` 直接、空=0
   - 全 `$單價` → 基準型：`單價 − 該組最低單價`
3. **移除 pprcss 補價**。

### 8f. add 卡結構不一（fallback）

add（人氣加購）卡 name/price 結構不統一：
- 16010：`<optgroup label="薯金幣(大份)">` + `.show_price +$79`
- 26868：`.pd_name data-name` 卡片

修正：name 匹配加 `optgroup label`；找不到 name 時 fallback 整卡找 price。
**已知殘留**：add 價跨卡誤抓（酥炸三味甜不辣 75 vs 應 79）→ 通用加購之後抽獨立
addons 表處理，已從 coupons.js 排除。

## 9. 測試碼

### 9a. 候選價格掃描（驗證券型）

```python
import re
def candidate_prices(fp):
    html = open(fp, encoding='utf-8').read()
    pat = re.compile(r'<div class="pdpop-li[^"]*" id="(mainpop_\d+_\d+)"[^>]*>')
    plus = dollar = empty = 0
    for m in pat.finditer(html):
        seg = html[m.start():m.start()+12000]
        nm = re.search(r'class="pdpop-name"[^>]*>([^<]+)<', seg)
        if not nm: continue
        after = seg[nm.end():nm.end()+3000]
        pr = re.search(r'class="pdpop-price[^"]*"[^>]*>\s*([^<]*)<', after)
        val = pr.group(1).strip() if pr else ''
        if val.startswith('+'): plus+=1
        elif val.startswith('$'): dollar+=1
        else: empty+=1
    return plus, dollar, empty
# 結果:
# 加價型: 26868(+$11 空9) 16088(+$38 空18) 16271(+$32 空1) 26979(空2)
# 基準型: 16013(全$27) 16109(全$69) 16313(全$5) 26757/26800(全$52) 26966(全$69)
```

### 9b. 購物車比對（探索區驗證腳本）

```python
from verify_cart_price import new_session, full_flow, add_to_cart
def total(code, main, crust=None, second=None):
    s = new_session(code); html = full_flow(s, code)
    crust = crust or {k:3021 for k in main}
    resp = add_to_cart(s, html, main, crust, second_choices=second)
    m = re.search(r'id="show_total"[^>]*>\s*([\d,]+)', resp)
    return m.group(1) if m else '?'
```
關鍵比對（每次獨立 session，避免購物車累加）：
- 26868 組1四小福+組2四小福 = **144**
- 26868 組1千島+組2四小福 = **184**（千島 +40 正確）
- 26868 組1四小福+組2彩蔬 = **144**（組2 彩蔬不加價 → scan_state 誤標 +14 是錯）
- 26868 組1彩蔬+組2四小福 = **158**（組1 彩蔬 +14 正確）

### 9c. 瀏覽器實操官網（最可靠驗證）

選單頁首次需過門市（cookie 記憶後免重選）。操作：點候選 → 切餅皮
（`input[name=main_food_ps_id_1][value=3020]` = 鬆厚）→ 讀「加入購物車 +$NN」。
16013：極炙+鬆厚=638、四小福+鬆厚=399。

## 10. 最終設計（定案）

**候選 priceAdd**（`script/scan/parse_orderflow.py` `_resolve_price`）：
- 每組內判券型（有候選 `+$` = 加價型）
- 加價型：`+$NN` → NN；空 → 0
- 基準型：`單價 − 該組最低單價`
- add 組：之後抽 addons 表，coupons.js 已排除

**scan_state 存「完整格式」**（每候選帶 flavors），coupons.js 輸出才去重成
flavorSets（兩層分工見 docs/items-schema.md）。

## 11. Commit 記錄

| Commit | 內容 |
|---|---|
| `9cbbfbf` | docs/crawler-data-sources.md（欄位由來權威表）|
| `fc0ac27` | tools/ph_crawler parse 改價格規則 |
| `143633a` | 主線 parse_orderflow 套用同樣規則 + add 卡 fallback |
| `a643bfb` | scan_state 全量重建 561 碼（0 失敗）|
| `c06d666` | coupons.js 重建（排除通用加購組）|
| `8a15a35` | 本文件（重構紀實）|

## 12. 驗證結果（重構後）

| 券 | 結果 |
|---|---|
| 26868/16015 組1 千島 | +40（購物車 184 ✓）|
| 26868/16015 **組2** | **全 0**（原誤標 +14 修好，144 = 95+49 ✓）|
| 16013 基準型 | 極炙 +239、和風 +120（638−399、519−399）|
| 16109 基準型多組 | 各組自減最低（組1 極炙 +198、組2 +329）|
| 16313/16010/94199 | 全 0（固定價）|
| coupons.js | 2.26MB（排除 add 後較前小），18728 items 無 add 殘留 |

scan_state 全量：**561 成功 / 0 失敗 / 4 結構空**（93015 等固定內容）。
測試：44 unittest + vitest 22 + build 全過。瀏覽器目檢 26868 詳情
「主餐(5 選1)」彩蔬鮮菇 +$0（不再 +14）。

## 13. 前端待辦（交接下一對話，詳見 handoff）

資料端重構完成。前端尚未處理：

1. **通用加購抽獨立表** `public/addons.json` + bar 加購按鈕（tabler text-plus
   圖示，回頂端鈕上方）；加購「與券內容無關、全站通用」。注意 add 價逐券 parse
   不可靠（同物 75/79 混），建議取眾數或另抓官網加購表。
2. **卡片雙欄 grid**（1 2 / 3 4 橫向優先）。
3. **詳情/卡片顯示確認**（MealItems 已初步分區：+0 灰字、加價琥珀、分隔線）。
4. 尺寸彩蛋：點 logo 彈尺寸表（大13/小9/個人6吋）。

## 14. 殘留清理

本次臨時檔已清（git 歷史可回滾，不需保留）。
備份（git 歷史可回滾，不需保留）。`exp_prob/` 為使用者既有實驗目錄，非本次產物。
