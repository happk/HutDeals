// 效能基準：方案 B（items 併入搜尋＋WeakMap 懶快取）在真實資料上的成本。
// 用法：node exp_prob/2026-10-26_search-items-index/bench_search.mjs
// 資料：public/coupons.js（723 券），量測項：
//   1. 快取建立（一次性）：723 券全量組 haystack（含 items 去重）＋lowercase
//   2. 每鍵過濾：快取版 vs 現行版（每鍵重建字串）——1 詞與 2 詞查詢
//   3. 記憶體：快取字串總量（UTF-16 估算）
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const repo = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const src = readFileSync(join(repo, "public", "coupons.js"), "utf-8");
const m = src.match(/window\.HUTDEALS_COUPONS\s*=\s*(\{[\s\S]*\})\s*;?\s*$/);
const coupons = JSON.parse(m[1]).coupon_list;
console.log(`coupons=${coupons.length}`);

// —— 方案 B：WeakMap 懶快取（與建議實作同形）——
const cache = new WeakMap();
function haystackB(c) {
  let h = cache.get(c);
  if (h === undefined) {
    const parts = [c.name ?? "", c.description ?? "", c.code ?? ""];
    if (c.items) {
      const seen = new Set();
      for (const it of c.items) if (it.text && !seen.has(it.text)) seen.add(it.text);
      for (const t of seen) parts.push(t);
    }
    h = parts.join(" ").toLowerCase();
    cache.set(c, h);
  }
  return h;
}
// —— 現行：filter.ts:64，每鍵重建 ——
function haystackNow(c) {
  return `${c.name} ${c.description ?? ""} ${c.code ?? ""}`.toLowerCase();
}

function filterWith(hay, q) {
  const terms = q.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const out = [];
  for (const c of coupons) if (terms.every((t) => hay(c).includes(t))) out.push(c);
  return out.length;
}

function bench(label, fn, n) {
  fn(); // warmup（JIT）
  const t0 = process.hrtime.bigint();
  for (let i = 0; i < n; i++) fn();
  const ms = Number(process.hrtime.bigint() - t0) / 1e6 / n;
  console.log(`${label}: ${ms.toFixed(3)} ms/次`);
}

// 1. 快取建立（一次性，等同首鍵的懶建成本）
{
  const t0 = process.hrtime.bigint();
  let chars = 0;
  for (const c of coupons) chars += haystackB(c).length;
  const ms = Number(process.hrtime.bigint() - t0) / 1e6;
  console.log(`快取建立(一次性): ${ms.toFixed(1)} ms，快取字串共 ${chars.toLocaleString()} 字元 ≈ ${(chars * 2 / 1024).toFixed(0)} KB(UTF-16)`);
}

// 2. 每鍵成本（200 次平均）
bench("每鍵·現行(重建,1詞'雞軟骨') ", () => filterWith(haystackNow, "雞軟骨"), 200);
bench("每鍵·方案B(快取,1詞'雞軟骨') ", () => filterWith(haystackB, "雞軟骨"), 200);
bench("每鍵·方案B(快取,2詞'大 可樂')", () => filterWith(haystackB, "大 可樂"), 200);

// 3. 命中數對照（正確性無異）
console.log(`命中數 對照: 現行'雞軟骨'=${filterWith(haystackNow, "雞軟骨")} 方案B=${filterWith(haystackB, "雞軟骨")}`);
