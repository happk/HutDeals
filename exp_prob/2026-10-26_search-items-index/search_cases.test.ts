import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { DEFAULT_STATE, filterCoupons } from "../../src/lib/filter";
import type { Coupon } from "../../src/types";

// 資料集驅動的搜尋驗收：[search_cases.json](./search_cases.json)（搜索字 → 應該查到的項）
// 對真實 public/coupons.js 跑 src/lib/filter.ts 的 filterCoupons（真實實作，非重演）。
// 放在 src 外：需 node:fs 讀檔，不進 tsc -b（tsconfig.app 只含 src），npm test 照常執行。
//
// 斷言語意（見 search_cases.json meta.semantics）：
// - expect_keys：至少須命中——期望鍵「仍在資料中」者必命中；資料每日由 CI 重寫，
//   日增的新命中屬正常，鍵因 60 天清除消失時跳過該鍵。
// - absent_keys：仍在資料中者必不命中（負例：口味只在 flavorSets）。
// - 每個命中者另以「純欄位掃描」複核——驗證 WeakMap 快取實作與欄位定義一致（無假陽性）。

// vitest 以專案根為 cwd；import.meta.url 在轉換後非 file:// scheme，不可用
const HERE = join(process.cwd(), "exp_prob", "2026-10-26_search-items-index");

function loadJson(path: string): unknown {
  return JSON.parse(readFileSync(path, "utf-8"));
}

function loadRealCoupons(): Coupon[] {
  const src = readFileSync(join(process.cwd(), "public", "coupons.js"), "utf-8");
  const m = src.match(/window\.HUTDEALS_COUPONS\s*=\s*(\{[\s\S]*\})\s*;?\s*$/);
  if (!m) throw new Error("coupons.js 解析失敗（找不到 window.HUTDEALS_COUPONS）");
  return (JSON.parse(m[1]) as { coupon_list: Coupon[] }).coupon_list;
}

interface CaseFile {
  meta: Record<string, string>;
  cases: {
    q: string;
    note: string;
    expect_keys: string[];
    absent_keys?: string[];
    expect_zero?: boolean;
  }[];
}

const suite = loadJson(join(HERE, "search_cases.json")) as CaseFile;
const coupons = loadRealCoupons();
const byKey = new Map(coupons.map((c) => [c.key, c]));

/** 純欄位掃描（name/description/code/items[].text）——不經 haystackOf 快取的對照組。 */
function naiveMatch(c: Coupon, terms: string[]): boolean {
  const fields = [c.name, c.description ?? "", c.code ?? "", ...(c.items ?? []).map((i) => i.text)];
  const hay = fields.join(" ").toLowerCase();
  return terms.every((t) => hay.includes(t));
}

describe("search_cases 資料集驗收（真實 coupons.js × filterCoupons）", () => {
  it("測試集與資料可載入", () => {
    expect(suite.cases.length).toBeGreaterThan(0);
    expect(coupons.length).toBeGreaterThan(0);
    // 測試集記錄的資料基準（僅顯示用；資料日更不影響「至少命中」語意）
    console.log(`  測試集 ${suite.cases.length} 案例｜資料基準 ${suite.meta.data_last_update}｜當前 ${coupons.length} 券`);
  });

  for (const cs of suite.cases) {
    it(`「${cs.q}」——${cs.note}`, () => {
      const terms = cs.q.trim().toLowerCase().split(/\s+/).filter(Boolean);
      const found = new Set(
        filterCoupons(coupons, { ...DEFAULT_STATE, q: cs.q }, new Set()).map((c) => c.key),
      );

      if (cs.expect_zero) {
        expect(found.size, `「${cs.q}」應零命中`).toBe(0);
        return;
      }

      const missing = cs.expect_keys.filter((k) => byKey.has(k) && !found.has(k));
      expect(missing, `「${cs.q}」應命中卻未命中（鍵仍在資料中）`).toEqual([]);

      const leaked = (cs.absent_keys ?? []).filter((k) => byKey.has(k) && found.has(k));
      expect(leaked, `「${cs.q}」必不命中卻命中`).toEqual([]);

      for (const k of found) {
        expect(naiveMatch(byKey.get(k)!, terms), `假陽性：${k} 非欄位掃描可命中`).toBe(true);
      }
    });
  }
});
