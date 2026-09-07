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
  /** 組分類語意（2026-09-07）：main→大/小/個人比薩(或中性比薩)、second→副食/飲料 */
  cat?: string | null;
  /** 升級/換購加價(0=免加價)。卡片只顯示 +0；詳細頁全部 */
  priceAdd: number;
  /** 指向券級 flavorSets 的索引（主餐比薩有口味才有；否則 null） */
  flavorIdx: number | null;
  /** 加購物價差(僅 group=add 有意義) */
  add?: number | null;
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
