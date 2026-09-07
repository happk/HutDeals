import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import MealItems from "./MealItems";
import type { MealItem } from "../types";

/** 26868 闖關式：主餐兩組(+0/+40 混) + 加購 */
const flavorSets: { name: string; priceAdd: number }[][] = [
  [{ name: "鬆厚", priceAdd: 0 }, { name: "空氣軟歐", priceAdd: 0 }, { name: "芝心", priceAdd: 30 }, { name: "薄脆", priceAdd: 15 }],
  [{ name: "空氣軟歐", priceAdd: 0 }],
];

const mainRaw: { t: string; p: number; fi: number }[] = [
  { t: "四小福", p: 0, fi: 0 },
  { t: "日式照燒雞", p: 0, fi: 0 },
  { t: "雙層美式臘腸", p: 0, fi: 0 },
  { t: "夏威夷比薩", p: 0, fi: 0 },
  { t: "千島海鮮盛宴", p: 40, fi: 1 },
  { t: "經典海鮮四重奏", p: 34, fi: 0 },
];
const addRaw: { text: string; add: number }[] = [
  { text: "薯金幣(大份)", add: 79 },
  { text: "酥炸三味甜不辣", add: 79 },
];

const items26868: MealItem[] = [
  // 主餐組1：+0 4 個 + 加價幾個
  ...mainRaw.map((x) => ({
    text: x.t,
    group: "main" as const,
    groupIdx: 1,
    priceAdd: x.p,
    flavorIdx: x.fi,
  })),
  // 加購組
  ...addRaw.map((x) => ({
    text: x.text,
    group: "add" as const,
    groupIdx: 1,
    priceAdd: x.add,
    flavorIdx: null,
    add: x.add,
  })),
];

describe("MealItems 結構化", () => {
  it("卡片(compact)：顯示前 4 候選(加價標琥珀價)，超過 4 顯示 …", () => {
    const html = renderToStaticMarkup(
      <MealItems items={items26868} flavorSets={flavorSets} compact />,
    );
    expect(html).toContain("四小福");
    expect(html).toContain("日式照燒雞");
    // 千島(+40)/經典(+34)是第 5/6 個候選 → 被前 4 截斷，不顯示
    expect(html).not.toContain("千島海鮮盛宴");
    expect(html).not.toContain("經典海鮮四重奏");
    // 加購組候選也會顯示（含 +$ 價）
    expect(html).toContain("薯金幣");
    expect(html).toContain("+$79");
  });

  it("卡片：加價候選若在前 4 也顯示並標 +$ 值", () => {
    const mixed: MealItem[] = [
      { text: "極炙厚牛干貝海陸", group: "main", groupIdx: 1, priceAdd: 239, flavorIdx: null },
      { text: "四小福", group: "main", groupIdx: 1, priceAdd: 0, flavorIdx: null },
      { text: "火辣辣墨西哥", group: "main", groupIdx: 1, priceAdd: 55, flavorIdx: null },
    ];
    const html = renderToStaticMarkup(<MealItems items={mixed} compact />);
    expect(html).toContain("極炙厚牛干貝海陸");
    expect(html).toContain("+$239");
    expect(html).toContain("+$55");
  });

  it("卡片超過 4 個 +0 → 顯示 …", () => {
    const many: MealItem[] = [1, 2, 3, 4, 5].map((i) => ({
      text: `候選${i}`,
      group: "main" as const,
      groupIdx: 1,
      priceAdd: 0,
      flavorIdx: null,
    }));
    const html = renderToStaticMarkup(<MealItems items={many} compact />);
    expect(html).toContain("候選1");
    expect(html).toContain("候選4");
    expect(html).not.toContain("候選5");
    expect(html).toContain("…");
  });

  it("詳情頁：+0 與加價分兩區，+0 標灰字、加價標琥珀價", () => {
    const html = renderToStaticMarkup(
      <MealItems items={items26868} flavorSets={flavorSets} />,
    );
    // 加價候選出現 + 帶價
    expect(html).toContain("千島海鮮盛宴");
    expect(html).toContain("+$40");
    expect(html).toContain("經典海鮮四重奏");
    expect(html).toContain("+$34");
    // +0 候選出現 + 灰字 +$0 標記
    expect(html).toContain("四小福");
    expect(html).toContain("+$0");
    // 分隔線存在（+0 區與加價區間）
    expect(html).toContain("border-t");
  });

  it("flavorIdx 解引用只在詳細頁顯示口味", () => {
    const withFlavor: MealItem[] = [
      { text: "四小福", group: "main", groupIdx: 1, priceAdd: 0, flavorIdx: 0 },
    ];
    const fs: { name: string; priceAdd: number }[][] = [
      [{ name: "鬆厚", priceAdd: 0 }, { name: "芝心", priceAdd: 30 }],
    ];
    const compactHtml = renderToStaticMarkup(
      <MealItems items={withFlavor} flavorSets={fs} compact />,
    );
    expect(compactHtml).not.toContain("芝心");
    const fullHtml = renderToStaticMarkup(
      <MealItems items={withFlavor} flavorSets={fs} />,
    );
    expect(fullHtml).toContain("芝心");
    expect(fullHtml).toContain("+$30");
  });

  it("詳情頁加價區依 priceAdd 由低到高排序", () => {
    const mixed: MealItem[] = [
      { text: "高價A", group: "main", groupIdx: 1, priceAdd: 239, flavorIdx: null },
      { text: "低價B", group: "main", groupIdx: 1, priceAdd: 34, flavorIdx: null },
      { text: "中價C", group: "main", groupIdx: 1, priceAdd: 120, flavorIdx: null },
      { text: "免費D", group: "main", groupIdx: 1, priceAdd: 0, flavorIdx: null },
    ];
    const html = renderToStaticMarkup(<MealItems items={mixed} />);
    // 加價區順序應為 +$34 → +$120 → +$239
    const i34 = html.indexOf("+$34");
    const i120 = html.indexOf("+$120");
    const i239 = html.indexOf("+$239");
    expect(i34).toBeGreaterThan(-1);
    expect(i34).toBeLessThan(i120);
    expect(i120).toBeLessThan(i239);
    // +0 區獨立(免費D 在 +$0 標記)
    expect(html).toContain("免費D");
  });

  it("舊三欄格式向後相容", () => {
    const legacy = [
      { text: "1個6吋鬆厚比薩(4選1)", choices: ["四小福", "彩蔬鮮菇"], add: null },
    ];
    const html = renderToStaticMarkup(
      <MealItems items={legacy as unknown as MealItem[]} />,
    );
    expect(html).toContain("6吋");
    expect(html).toContain("四小福");
  });
});
