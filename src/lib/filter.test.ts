import { describe, expect, it } from "vitest";
import {
  collectTags,
  filterCoupons,
  parseState,
  sortCoupons,
  toSearchParams,
  DEFAULT_STATE,
} from "./filter";
import type { Coupon } from "../types";

function mk(partial: Partial<Coupon>): Coupon {
  return {
    key: "x",
    code: null,
    name: "",
    description: null,
    price: null,
    image: null,
    tags: [],
    firstSeen: "2026-09-01",
    lastSeen: "2026-09-01",
    status: "active",
    ...partial,
  };
}

const coupons: Coupon[] = [
  mk({ key: "a", name: "大比薩$198", description: "外帶買大送小", price: 198, tags: ["比薩", "買一送一"], firstSeen: "2026-09-01", lastSeen: "2026-09-01" }),
  mk({ key: "b", name: "個人比薩$101餐", description: "經典系列", price: 101, tags: ["比薩", "個人比薩"], firstSeen: "2026-09-03", lastSeen: "2026-09-03" }),
  mk({ key: "c", name: "私廚單點6折", description: "無金額", price: null, tags: ["折扣"], firstSeen: "2026-09-02", lastSeen: "2026-09-02" }),
  mk({ key: "d", name: "APP專屬$259", description: "", price: 259, tags: ["比薩"], orderType: "APP專屬", firstSeen: "2026-09-03", lastSeen: "2026-09-03" }),
  mk({ key: "e", name: "過期券", description: "", price: 50, status: "offline", firstSeen: "2026-09-01", lastSeen: "2026-09-01" }),
];

describe("filterCoupons", () => {
  it("always hides offline (no toggle since redesign 2-2)", () => {
    expect(filterCoupons(coupons, DEFAULT_STATE, new Set()).map((c) => c.key)).toEqual(
      ["a", "b", "c", "d"],
    );
  });

  it("search: multiple space-separated terms all match (case-insensitive)", () => {
    const s = { ...DEFAULT_STATE, q: "比薩 $198" };
    expect(filterCoupons(coupons, s, new Set()).map((c) => c.key)).toEqual(["a"]);
  });

  it("search: 優惠代碼命中品名不含碼的券（93014 型）", () => {
    const list = [
      ...coupons,
      mk({
        key: "93014",
        code: "93014",
        name: "大比薩分享餐$399",
        description: "指定大比薩+黃金和風鱈魚塊",
        price: 399,
      }),
    ];
    const s = { ...DEFAULT_STATE, q: "93014" };
    expect(filterCoupons(list, s, new Set()).map((c) => c.key)).toEqual(["93014"]);
    // 代碼可與其他關鍵字並用（空格分隔全部命中）
    const both = { ...DEFAULT_STATE, q: "93014 分享" };
    expect(filterCoupons(list, both, new Set()).map((c) => c.key)).toEqual(["93014"]);
  });

  it("include tags are OR, exclude tags remove", () => {
    const inc = { ...DEFAULT_STATE, includeTags: ["個人比薩", "折扣"] };
    expect(filterCoupons(coupons, inc, new Set()).map((c) => c.key)).toEqual(["b", "c"]);
    const ex = { ...DEFAULT_STATE, excludeTags: ["買一送一"] };
    expect(filterCoupons(coupons, ex, new Set()).map((c) => c.key)).toEqual(["b", "c", "d"]);
  });

  it("orderType filter", () => {
    const s = { ...DEFAULT_STATE, orderType: "APP專屬" };
    expect(filterCoupons(coupons, s, new Set()).map((c) => c.key)).toEqual(["d"]);
  });

  it("price range min/max filter", () => {
    const minOnly = { ...DEFAULT_STATE, priceMin: 200 };
    expect(filterCoupons(coupons, minOnly, new Set()).map((c) => c.key)).toEqual(["d"]);
    const maxOnly = { ...DEFAULT_STATE, priceMax: 150 };
    expect(filterCoupons(coupons, maxOnly, new Set()).map((c) => c.key)).toEqual(["b"]);
    const both = { ...DEFAULT_STATE, priceMin: 100, priceMax: 200 };
    expect(filterCoupons(coupons, both, new Set()).map((c) => c.key)).toEqual(["a", "b"]);
    // null price 不在任何設限範圍
    const nullExcl = { ...DEFAULT_STATE, priceMax: 300 };
    expect(filterCoupons(coupons, nullExcl, new Set()).map((c) => c.key)).toEqual([
      "a", "b", "d",
    ]);
  });

  it("orderType supports slash-inclusive (外帶/外送 hits both)", () => {
    const slash = mk({ key: "f", name: "雙通", orderType: "外帶/外送", tags: [] });
    const list = [...coupons, slash];
    const delivery = { ...DEFAULT_STATE, orderType: "外送" as const };
    expect(filterCoupons(list, delivery, new Set()).map((c) => c.key)).toContain("f");
    const takeout = { ...DEFAULT_STATE, orderType: "外帶" as const };
    expect(filterCoupons(list, takeout, new Set()).map((c) => c.key)).toContain("f");
  });

  it("favOnly keeps only favorites", () => {
    const s = { ...DEFAULT_STATE, favOnly: true };
    expect(filterCoupons(coupons, s, new Set(["b"])).map((c) => c.key)).toEqual(["b"]);
  });
});

describe("sortCoupons", () => {
  it("price asc puts null last", () => {
    const s = sortCoupons(coupons, "price", "asc").map((c) => c.key);
    expect(s[s.length - 1]).toBe("c");
    expect(s[0]).toBe("e");
  });

  it("price desc puts null last too", () => {
    const s = sortCoupons(coupons, "price", "desc").map((c) => c.key);
    expect(s[s.length - 1]).toBe("c");
    expect(s[0]).toBe("d");
  });

  it("seen sorts by firstSeen (加入時間)", () => {
    const s = sortCoupons(coupons, "seen", "asc").map((c) => c.key);
    expect(s.indexOf("a")).toBeLessThan(s.indexOf("c")); // a=09-01 先於 c=09-02
    expect(s.indexOf("c")).toBeLessThan(s.indexOf("b")); // c=09-02 先於 b=09-03
  });
});

describe("collectTags", () => {
  it("counts only active coupons, sorted by count desc", () => {
    const tags = collectTags(coupons);
    expect(tags[0]).toEqual({ tag: "比薩", count: 3 });
    expect(tags.find((t) => t.tag === "折扣")).toEqual({ tag: "折扣", count: 1 });
  });
});

describe("URL state roundtrip", () => {
  it("parse/toSearchParams preserve non-default state", () => {
    const s = {
      ...DEFAULT_STATE,
      q: "比薩",
      includeTags: ["比薩", "套餐"],
      excludeTags: ["甜點"],
      orderType: "外送",
      priceMin: 100,
      priceMax: 500,
      sort: "seen" as const,
      sortDir: "desc" as const,
      favOnly: true,
      code: "93034",
    };
    const parsed = parseState(toSearchParams(s));
    expect(parsed).toEqual(s);
  });

  it("parseState falls back to defaults on garbage", () => {
    const p = parseState(new URLSearchParams("sort=weird&min=abc&in=比薩"));
    expect(p.sort).toBe("price");
    expect(p.priceMin).toBeNull();
    expect(p.includeTags).toEqual(["比薩"]);
  });
});
