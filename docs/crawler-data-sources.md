# 必勝客選單頁資料來源（crawler data sources）

> 權威文件：每個結構化欄位的「確切 DOM class / JS 結構」由來。
> 原則（2026-09-07 使用者確認）：**不 parse 純文本**，只從 class/結構拿切實數據。
> desc（套餐說明文字）保留一份當備選/人工核對，但**主要資料來自結構化來源**。
> 更新：2026-09-07。

## 兩大券型（依候選 `.pdpop-price` 有無 `+` 判斷）

| 型 | 判定 | 候選 `.pdpop-price` 呈現 | 例子 |
|---|---|---|---|
| **加價型** | 候選有 `+$NN` | 升級口味 `+$NN`、基本款**空** | 26868、16015、16088、16271、16295、26898 |
| **基準型** | 候選純 `$NN`（無 +） | 每候選標**絕對單價** | 16013、16109、16313、16317、26757、26800、26966 |

> 另有一類「全空」（如 26979 素幸福點）：候選 `.pdpop-price` 全空 → 全 priceAdd=0。

## 欄位由來表

### 券級

| 欄位 | 確切來源 | 備註 |
|---|---|---|
| title | `<h1 id="cb_name">` | DOM id |
| 券價 price | ① `descPrice` div（`<div class="descPrice">$ 666</div>`）<br>② `套餐價格：$N` li<br>③ `price_selling` / `caculate_price()` 的 price | 加價型通常有 descPrice（26898→144、16088→666）；基準型 package 走 price_selling（16013→399）。**結構化缺時 → desc「$N 元起」兜底（見「價格來源層級」章節）** |
| msrp（原價） | desc 文案（原價/最高價值/現省） | **純顯示備用註記**；desc 推測、非結構化，前端刪除線用。無 → None |
| priceNote | 僅「起」 | 結構化價缺、以 desc 兜底時標記；顯示「$N 起」。**desc 推測** |
| desc（備選） | `<div class="descTop">` | 保留一份供人工核對/前端 fallback；**非結構化主來源** |

## 價格來源層級（2026-09-07 定稿：desc 退出結構化欄位、僅兜底）

> 原則：**結構化欄位一律只從結構化 HTML 拿；desc 只當備用/人核對，不當結構化主來源**。
> 過往 price 誤抓（26898「=NT$95起」被文本當固定價 → 95，頁面 descPrice=$144 反被忽略）
> 都是 desc-text parse 引起，故移除文本固定價路徑。

券級 `price` 層級（先到先得）：
1. `descPrice` div（`<div class="descPrice">$ 144</div>`）→ **固定價**
2. `套餐價格：$N` li → **固定價**
3. `price_selling`（>0）／`caculate_price()` → **固定價**（基準型 package）
4. 皆無 → desc「`$N 元起`」**兜底**：`price=數字`、`priceNote="起"`（93023→639起、93015→888起）
   ⚠ **此為 desc 推測**，非結構化固定價；僅當「該券本質是起價浮動、無套餐總價」時使用
5. 仍無 → `price=None`（前端顯示「價格未知」）

`msrp`（原價）：**純顯示註記**，來自 desc 文案（直接型 原價/最高價值；差額型 現省僅固定價成立）。
前端畫刪除線「原價$XXX」。⚠ 同為 **desc 推測**，不進任何結構化判定。

> 維護註記：官方線（build_coupons）與外部線（ingest_external）的起價兜底皆為 **desc/文字推測**，
> 非結構化固定價；任何「看起來像固定價」的顯示都不得把 desc 兜底的 priceNote="起" 拿掉。



### 候選級（每張候選卡 = `<div class="pdpop-li" id="mainpop_{組}_{pid}">`）

| 欄位 | 確切來源 | 規則 |
|---|---|---|
| 候選名 | 卡內 `.pdpop-name` | name 錨點：卡片 id 後第一個 `.pdpop-name` |
| **priceAdd** | 卡內 `.pdpop-price` 內容 | **加價型**：`+$NN` → NN；空 → 0<br>**基準型**：`$NN` 單價 → NN − 該組最低單價 |
| 組別 group/groupIdx | `mainpop_{組}_{pid}` | main=main、sndpop=second、addpop=add |
| 組標題 groupTitle | `<input id="main_food_subject_N" value>` / `.product_list_title` | 官方組名原文（溯源） |
| cat | 組標題(main_food_subject_N) | main→大/小/個人比薩、特殊比薩(手工義式薄/Flatzz)、義大利麵/飯(麵/飯/筆管麵/千層麵)、副食(副食/煎餅/點心)；second→飲料(全飲料含湯)/副食。只改顯示、不動 group |
| 口味 flavors | `ctidss.v/t/p["g{組}_{pid}"]` | 該候選可選口味清單（id/名/加價） |
| 加購物 add | addpop 卡 `.show_price` | 人氣加購（薯金幣 +79 等） |

> **coupons.js 的 description（2026-09-07 P2）**：items 結構化成功 → description 不帶 desc；
> 僅 items 拆不出（固定盒型）才以 desc 當內容。desc 全文存 scan_state 備用。

## 關鍵規則（實測驗證 2026-09-07）

1. **`.pdpop-price` 有 `+` = 加價型**，純 `$` 無 `+` = 基準型。判斷只需看有無 `+`。
2. **加價型補差 = DOM `+$NN` 直接用**；空 = 0。26868 千島 +40、四小福空。
3. **基準型候選標絕對單價**（16013 極炙 $638）；priceAdd = 單價 − 該組最低單價。
4. **「限價」語意**（16013「限$410以下」、16109「限$690以上」）：基準型候選單價高於/低於該組基準要補差，本質 = 單價 − 組最低。
5. **加購/送組（26868 組2、16088 組2/3）候選 `.pdpop-price` 空** → priceAdd 全 0。官網 pprcss 對這些組的 add 是殘留錯誤，**不可信**（26868 組2 彩蔬 pprcss.add=14 但實際不加，購物車實測 144=95+49）。
6. **pprcss.add 僅在「候選 DOM 有 +$」時可信**（= 補差）；基準型要用 DOM 單價自己算。

## 前端顯示規則（承 items-schema.md）

- 卡片(compact)：每類只顯示 priceAdd==0 候選前 4 + 「…」。
- 詳細頁：每類內 **+0 預設區在上、加價區在下**（細分隔線）；+0 標記灰字、加價琥珀。
- 口味（flavorSets[flavorIdx]）詳細頁才顯示。

## 除錯速查

- 某候選 priceAdd 異常 → 看它卡片 `.pdpop-price` 原文（+$ / $ / 空）確認型別。
- 券價抓不到 → 找 `descPrice` div，沒有找 `caculate_price()` 的 price / `price_selling`。
