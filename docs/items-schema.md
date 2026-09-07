# items 結構化 schema（取代 parse_meal 三欄契約，hutdeals orderflow）

> 更新：2026-09-07。背景：官網訂餐後端結構化爬取（orderflow）取代文字 parse_meal
> 後，items 直接存「候選選項」結構化資料，前端不需拆文字即可做卡片/詳細頁顯示。
> 舊三欄 `{text, choices[], add}` 契約退役（見 archive/parse/）。

## 兩層分工（2026-09-07 使用者確認）

- **scan_state.json = 資料庫 = 存完整**：每筆候選帶自己的完整 `flavors` 陣列
  （同券重複沒關係）。scan_state 是權威來源、給人看/未來程式讀，**不做壓縮**。
- **coupons.js = 網站輸出 = 才去重**：產出時（`lib/coupons.py` 的
  `compact_coupon_items`，掛 `write_coupons_js/full` 單一輸出入口）把每券完整
  items 轉成「flavorSets + flavorIdx」節省體積。scan_state 完全不動。

去重只在**券內**做（2a）：同券候選口味清單相同 → 抽成券級 `flavorSets` 一份。
**不跨券共用口味表**——同是「芝心」不同券加價 +30/+90/+115 不同（升級差價跟著券走）。

## 完整格式（scan_state 儲存）

每筆候選帶自己的完整口味：

```ts
interface MealItem {
  text: string;                    // 候選名
  group: "main" | "second" | "add";
  groupIdx: number;                // 該類第幾組
  priceAdd: number;                // 升級/換購加價(0=免)
  flavors: { name: string; priceAdd: number }[];  // 口味候選(主餐才有)
  add?: number | null;             // 加購物價差(僅 add)
  cat?: string | null;             // 組分類(2026-09-08 擴充)：大/小/個人比薩、特殊比薩、義大利麵/飯、副食、飲料
  groupTitle?: string | null;      // 官方組標題原文(如「請選擇1個個人比薩」)；溯源用，不進輸出
}
```

> `cat` 來源（2026-09-08 完整規則，以官網組標題 main_food_subject value 為準）：
> - 大比薩/13吋 → 大比薩；小比薩/9吋 → 小比薩；個人比薩 → 個人比薩
> - 手工義式薄比薩/Flatzz 等特殊餅體 → 特殊比薩
> - 義大利麵/飯/筆管麵/千層麵/飯麵 → 義大利麵/飯
> - 副食/韓式海鮮煎餅/點心 → 副食（官網把部分副食組放 psidss.main，cat 正確標示）
> - second 組整組候選全飲料(湯算飲料)→飲料，任一非飲料→副食
> 原則：只改顯示分類(cat)、不動原始 group(保留爬取原始資訊)。尺寸對照大=13/小=9/個人=6。



## 輸出格式（coupons.js，compact_coupon_items 轉換後）

候選 `flavors` 換成 `flavorIdx`（指向券級 `flavorSets`），券加 `flavorSets`：

```ts
interface MealItem {
  text: string; group: "main" | "second" | "add"; groupIdx: number;
  priceAdd: number;
  flavorIdx: number | null;        // flavorSets 索引（無口味 = null）
  add?: number | null;
  cat?: string | null;             // 組分類（帶出；groupTitle 只留 scan_state）
}
// 券級：coupon.flavorSets[item.flavorIdx] = 該候選可選口味清單
```

實測：coupons.js 5.9MB → 2.91MB（25828 items 全 flavorIdx 化、553 券帶
flavorSets；26868 20 候選 → 2 組口味）。

## 前端顯示規則（2026-09-07 使用者確認 v3）

- **卡片（compact）**：每類(`group`+`groupIdx`)只顯示 `priceAdd==0` 的候選，
  最多 4 個，超過顯示「...」；候選區**雙欄 grid**（1 2/3 4 橫向優先，2026-09-07）。
  `priceAdd>0` 的候選卡片不顯示。
- **詳細頁**：每類內 **+0 預設區在上、加價區在下**（細分隔線分開不拆散）；維持**單欄**。
  候選名一律正常色，+0 標記灰字「+$0」、加價標記琥珀「+$NN」。
- **口味**（`flavorSets[flavorIdx]`）：詳細頁才顯示（餅皮名+價差）。
- **組標題**（2026-09-07）：顯示 `cat`（個人比薩/大比薩/副食…）＋「N 選1」，不再用「主餐」。
  無 `cat`（舊格式/加購）退回 group 名。

## 各券型 items 長相（scan_state 完整格式）

| 券型 | 例 | items 形狀 |
|---|---|---|
| 全展開 | 16010 | main×4(+0) + second×2(+0) + add×11(+79~229) |
| 闖關式 | 26868 | main group1×15(部分+40/+34…/+0) + main group2×5(+0，$49加購) + add×11 |
| 單點定價 | 94199 | main×10(皆+0，口味價差在 flavors) + add×20 |
| 大組合 | 26880 | main×30(含+268高價) + second×4 + add×13 |

## 空 items / fallback

- 固定盒型券（無候選選單）→ items 為單筆 main（priceAdd=0、flavors=[]）視為單一內容。
- 結構化完全失敗 → items 空/缺，前端 fallback 顯示 description 原文（93015 既有行為）。

## 資料源對應

| 欄位 | 來源 |
|---|---|
| text | DOM .pdpop-name（候選產品名） |
| group/groupIdx | psidss main/second/add 的組 |
| priceAdd | pprcss.add（升級差價）或 DOM .pdpop-price/.show_price |
| flavors | ctidss.v/t/p（該候選的口味清單+加價） |
| add | DOM .show_price（加購物價） |
| cat | main=組標題(main_food_subject_N)尺寸詞；second=整組候選名判飲料/副食 |
| groupTitle | 組標題原文（`<input id="main_food_subject_N" value>`） |
