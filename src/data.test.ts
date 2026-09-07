import { describe, expect, it, beforeEach } from "vitest";
import { loadData } from "./data";

describe("loadData", () => {
  beforeEach(() => {
    delete (window as { HUTDEALS_COUPONS?: unknown }).HUTDEALS_COUPONS;
  });

  it("falls back to mock when data file missing", () => {
    const { data, isMock } = loadData();
    expect(isMock).toBe(true);
    expect(data.coupon_list.length).toBeGreaterThan(0);
  });

  it("uses real data when window.HUTDEALS_COUPONS present", () => {
    (window as { HUTDEALS_COUPONS?: unknown }).HUTDEALS_COUPONS = {
      coupon_list: [
        {
          key: "93034",
          code: "93034",
          name: "93034大比薩送副食/飲料$198",
          description: null,
          price: 198,
          priceNote: null,
          image: null,
          category: null,
          orderType: null,
          tags: [],
          firstSeen: "2026-09-03",
          lastSeen: "2026-09-03",
          status: "active",
        },
      ],
      count: 1,
      last_update: "2026-09-03T08:00:00",
    };
    const { data, isMock } = loadData();
    expect(isMock).toBe(false);
    expect(data.count).toBe(1);
    expect(data.coupon_list[0].code).toBe("93034");
  });
});
