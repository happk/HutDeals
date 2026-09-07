import type { HutdealsData } from "./types";

/** 開發或資料檔載入失敗時的 mock 資料(與真實欄位同構)。 */
const MOCK: HutdealsData = {
  count: 3,
  last_update: "2026-09-03T08:00:00",
  coupon_list: [
    {
      key: "93034",
      code: "93034",
      name: "93034大比薩送副食/飲料$198",
      description: "-13吋大比薩1個,再送副食/飲料三選一!",
      price: 198,
      priceNote: null,
      image: null,
      category: "神級優惠3折起",
      orderType: "外帶",
      tags: ["比薩", "大比薩", "副食"],
      firstSeen: "2026-09-03",
      lastSeen: "2026-09-03",
      status: "active",
    },
    {
      key: "93020",
      code: "93020",
      name: "93020-外帶買一送五",
      description: "外帶買大比薩,送2個小比薩+副食5選2+可樂1.25L。",
      price: null,
      priceNote: null,
      image: null,
      category: "神級優惠3折起",
      orderType: "外帶",
      tags: ["比薩", "買一送一"],
      firstSeen: "2026-09-03",
      lastSeen: "2026-09-03",
      status: "active",
    },
    {
      key: "94601",
      code: "94601",
      name: "94601-開學優惠!超級總匯/炙燒明太子嫩雞/鐵板雙牛$249",
      description: "超級總匯/炙燒明太子嫩雞/鐵板雙牛$249",
      price: 249,
      priceNote: null,
      image: null,
      category: "開學季優惠",
      orderType: "外帶",
      tags: ["比薩", "套餐"],
      firstSeen: "2026-09-03",
      lastSeen: "2026-09-03",
      status: "offline",
      offlineSince: "2026-09-02",
    },
  ],
};

declare global {
  interface Window {
    HUTDEALS_COUPONS?: HutdealsData;
  }
}

export function loadData(): { data: HutdealsData; isMock: boolean } {
  const real = typeof window !== "undefined" ? window.HUTDEALS_COUPONS : undefined;
  if (real && Array.isArray(real.coupon_list) && real.coupon_list.length > 0) {
    return { data: real, isMock: false };
  }
  return { data: MOCK, isMock: true };
}
