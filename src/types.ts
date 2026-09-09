export interface Flavor {
  /** 口味候選名（餅皮等），如「芝心」 */
  name: string;
  /** 該口味加價（0=免加價） */
  priceAdd: number;
}

export interface MealItem {
  /** 候選名，如「千島海鮮盛宴」 */
  text: string;
  /** 類別：main(主餐候選) / second(副食候選) / add(加購物) */
  group: "main" | "second" | "add";
  /** 該類第幾組(1-based)。26868 有兩個 main 組，前端以 group+groupIdx 區分 */
  groupIdx: number;
  /**
   * 候選自己的分類（衍生層級，2026-09-09）：
   * 飲料／副食／義大利麵/飯／大比薩／小比薩／個人比薩／特殊比薩／比薩。
   * 主分類在券層 units（「項」＝一個選項組），此欄僅為候選細節。
   */
  cat?: string | null;
  /** 升級/換購加價(0=免加價)。卡片只顯示 +0；詳細頁全部 */
  priceAdd: number;
  /** 指向券級 flavorSets 的索引（主餐比薩有口味才有；否則 null） */
  flavorIdx: number | null;
  /** 加購物價差(僅 group=add 有意義) */
  add?: number | null;
}

/** 項分類（2026-09-09）：「項」＝前端一個選項組；分類掛在項上，與官網組型無關 */
export interface UnitCat {
  group: "main" | "second" | "add";
  groupIdx: number;
  /** 該項的分類集合（混類項會有多個，如 ["副食","飲料"]） */
  cats: string[];
}

export interface Coupon {
  key: string;
  code: string | null;
  name: string;
  description: string | null;
  price: number | null;
  /** 原價（僅外部碼；來自 desc 文案，純顯示刪除線用；2026-09-07 分欄位） */
  msrp?: number | null;
  /** 價格註記。目前僅「起」（結構化價缺、desc 兜底的起價券，顯示「$N 起」） */
  priceNote?: string | null;
  image?: string | null;
  category?: string | null;
  orderType?: string | null;
  orderUrl?: string;
  tags: string[];
  /** 結構化餐點候選（空 = parse 失敗，前端顯示 description 原文） */
  items?: MealItem[];
  /** 項層分類（「項」＝一個選項組；2026-09-09）。前端組標題以這裡為準 */
  units?: UnitCat[];
  /** 券級去重後的口味集合（flavorSets[item.flavorIdx] = 該候選可選口味） */
  flavorSets?: Flavor[][];
  /** 活動期間（IG 文案融合後填；目前為 null） */
  startDate?: string | null;
  endDate?: string | null;
  firstSeen: string;
  lastSeen: string;
  status: "active" | "offline";
  offlineSince?: string;
  /** 資料來源：official=官網列表 / verified-external=掃號驗證的外部碼（聯名/季節） */
  source?: "official" | "verified-external";
  /** 外部碼的聯名方（如 素易、兆豐銀行），official 無 */
  partner?: string | null;
  /** 外部碼最後驗證日期 */
  verifiedAt?: string;
  /** M1 驗證的內部流水號 */
  p_id?: number | null;
}

export interface HutdealsData {
  coupon_list: Coupon[];
  count: number;
  last_update: string;
}
