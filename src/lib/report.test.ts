import { describe, expect, it } from "vitest";
import { buildIssueUrl } from "./report";
import type { Coupon } from "../types";

const coupon: Coupon = {
  key: "93034",
  code: "93034",
  name: "93034大比薩送副食/飲料$198",
  description: "-13吋大比薩1個",
  price: 198,
  priceNote: null,
  image: null,
  category: null,
  orderType: null,
  tags: [],
  firstSeen: "2026-09-03",
  lastSeen: "2026-09-03",
  status: "active",
};

describe("buildIssueUrl", () => {
  it("builds prefilled github issue url", () => {
    const url = buildIssueUrl(coupon, "someone/HutDeals", "2026-09-03T08:00:00");
    expect(url.startsWith("https://github.com/someone/HutDeals/issues/new?")).toBe(true);
    const p = new URLSearchParams(url.split("?")[1]);
    expect(p.get("title")).toBe("[回報] 93034大比薩送副食/飲料$198");
    expect(p.get("labels")).toBe("coupon-report");
    const body = p.get("body") ?? "";
    expect(body).toContain("`93034`");
    expect(body).toContain("2026-09-03T08:00:00");
    expect(body).toContain("問題類型");
  });

  it("handles coupons without code", () => {
    const url = buildIssueUrl({ ...coupon, code: null, key: "pid:17904" }, "o/r", "t");
    const body = new URLSearchParams(url.split("?")[1]).get("body") ?? "";
    expect(body).toContain("`pid:17904`");
    expect(body).toContain("代碼: 無");
  });
});
