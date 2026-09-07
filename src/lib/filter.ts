import type { Coupon } from "../types";

export type SortKey = "price" | "seen" | "code";
export type SortDir = "asc" | "desc";

export interface FilterState {
  q: string;
  includeTags: string[];
  excludeTags: string[];
  orderType: string | null;
  /** 價格上下限（null=不設限），step 10 */
  priceMin: number | null;
  priceMax: number | null;
  sort: SortKey;
  sortDir: SortDir;
  favOnly: boolean;
  code: string | null; // 深連結 /?code=<key>
}

export const DEFAULT_STATE: FilterState = {
  q: "",
  includeTags: [],
  excludeTags: [],
  orderType: null,
  priceMin: null,
  priceMax: null,
  sort: "price",
  sortDir: "asc",
  favOnly: false,
  code: null,
};
function inPriceRange(price: number | null, min: number | null, max: number | null): boolean {
  if (min == null && max == null) return true;
  if (price == null) return false;
  if (min != null && price < min) return false;
  if (max != null && price > max) return false;
  return true;
}

/**
 * orderType 支援判斷（包含語意）：券的 orderType 是「外帶/外送」時，
 * 選「外送」或「外帶」都應命中（UI 顯示名為「自取」,資料值維持「外帶」）。
 * 無 orderType(null) 只在沒選 type 時顯示。
 */
export function supportsOrderType(
  couponType: string | null | undefined,
  wanted: string,
): boolean {
  if (couponType == null) return false;
  return couponType.includes(wanted);
}

export function filterCoupons(
  coupons: Coupon[],
  state: FilterState,
  favorites: Set<string>,
): Coupon[] {
  const terms = state.q.trim().toLowerCase().split(/\s+/).filter(Boolean);
  return coupons.filter((c) => {
    if (c.status !== "active") return false;
    if (state.favOnly && !favorites.has(c.key)) return false;
    if (terms.length > 0) {
      const haystack = `${c.name} ${c.description ?? ""}`.toLowerCase();
      if (!terms.every((t) => haystack.includes(t))) return false;
    }
    if (state.orderType && !supportsOrderType(c.orderType, state.orderType)) return false;
    if (!inPriceRange(c.price, state.priceMin, state.priceMax)) return false;
    if (
      state.includeTags.length > 0 &&
      !state.includeTags.some((t) => c.tags.includes(t))
    )
      return false;
    if (state.excludeTags.some((t) => c.tags.includes(t))) return false;
    return true;
  });
}

/** 排序:欄位(price/seen/code)×方向;null 價格兩個方向都排最後。 */
export function sortCoupons(
  coupons: Coupon[],
  sort: SortKey,
  dir: SortDir,
): Coupon[] {
  const m = dir === "asc" ? 1 : -1;
  const list = [...coupons];
  const byKey = (a: Coupon, b: Coupon) => {
    if (sort === "price") {
      if (a.price == null && b.price == null) return 0;
      if (a.price == null) return 1; // null 恆在最後
      if (b.price == null) return -1;
      return (a.price - b.price) * m;
    }
    if (sort === "seen") {
      return (a.firstSeen < b.firstSeen ? -1 : a.firstSeen > b.firstSeen ? 1 : 0) * m;
    }
    return a.code && b.code
      ? a.code.localeCompare(b.code, "zh-Hans-CN", { numeric: true }) * m
      : 0;
  };
  list.sort(
    (a, b) => byKey(a, b) || String(a.key).localeCompare(String(b.key)),
  );
  return list;
}

/** 統計active 券的標籤,依出現次數多→少排序。 */
export function collectTags(coupons: Coupon[]): { tag: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const c of coupons) {
    if (c.status !== "active") continue;
    for (const t of c.tags) counts.set(t, (counts.get(t) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([tag, count]) => ({ tag, count }))
    .sort((a, b) => b.count - a.count || a.tag.localeCompare(b.tag, "zh-TW"));
}

const KNOWN_SORTS: SortKey[] = ["price", "seen", "code"];

/** 舊版組合鍵（price-asc/price-desc/new）對映到新 欄位+方向，舊連結不失效 */
const LEGACY_SORT: Record<string, { sort: SortKey; sortDir: SortDir }> = {
  "price-asc": { sort: "price", sortDir: "asc" },
  "price-desc": { sort: "price", sortDir: "desc" },
  new: { sort: "seen", sortDir: "desc" },
};

function parsePrice(v: string | null): number | null {
  if (v == null) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

export function parseState(params: URLSearchParams): FilterState {
  const list = (k: string) =>
    params.get(k)?.split(",").map(s => s.trim()).filter(Boolean) ?? [];
  const sortRaw = params.get("sort");
  const legacy = sortRaw ? LEGACY_SORT[sortRaw] : undefined;
  const sort: SortKey | null =
    legacy?.sort ?? (sortRaw && KNOWN_SORTS.includes(sortRaw as SortKey) ? (sortRaw as SortKey) : null);
  const dirRaw = params.get("dir");
  const sortDir: SortDir = legacy?.sortDir ?? (dirRaw === "desc" ? "desc" : dirRaw === "asc" ? "asc" : "asc");
  return {
    ...DEFAULT_STATE,
    q: params.get("q") ?? "",
    includeTags: list("in"),
    excludeTags: list("ex"),
    orderType: params.get("type") || null,
    priceMin: parsePrice(params.get("min")),
    priceMax: parsePrice(params.get("max")),
    sort: sort ?? "price",
    sortDir,
    favOnly: params.get("fav") === "1",
    code: params.get("code"),
  };
}

export function toSearchParams(state: FilterState): URLSearchParams {
  const p = new URLSearchParams();
  if (state.q) p.set("q", state.q);
  if (state.includeTags.length) p.set("in", state.includeTags.join(","));
  if (state.excludeTags.length) p.set("ex", state.excludeTags.join(","));
  if (state.orderType) p.set("type", state.orderType);
  if (state.priceMin != null) p.set("min", String(state.priceMin));
  if (state.priceMax != null) p.set("max", String(state.priceMax));
  if (state.sort !== "price") p.set("sort", state.sort);
  if (state.sortDir !== "asc") p.set("dir", state.sortDir);
  if (state.favOnly) p.set("fav", "1");
  if (state.code) p.set("code", state.code);
  return p;
}
