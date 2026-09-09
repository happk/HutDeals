import { useEffect, useMemo, useRef, useState } from "react";
import Header from "./components/Header";
import CouponCard from "./components/CouponCard";
import CouponDetail from "./components/CouponDetail";
import PriceFilter from "./components/PriceFilter";
import { PizzaMark } from "./components/Header";
import { useFavorites } from "./hooks/useFavorites";
import { useTheme } from "./hooks/useTheme";
import { loadData } from "./data";
import {
  collectTags,
  filterCoupons,
  parseState,
  sortCoupons,
  toSearchParams,
  DEFAULT_STATE,
} from "./lib/filter";
import type { FilterState, SortDir, SortKey } from "./lib/filter";

/**
 * 標籤列白名單：只顯示這份 dict 內的標籤（順序＝顯示順序）。
 * 要增減篩選標籤直接改這裡，資料端其他 tag 不會出現在篩選列。
 */
const TAG_WHITELIST = ["大比薩", "小比薩", "個人比薩", "特殊比薩", "義大利麵/飯", "比薩", "副食", "飲料"];

const SORT_KEYS: { value: SortKey; label: string }[] = [
  { value: "price", label: "價格" },
  { value: "seen", label: "加入時間" },
  { value: "code", label: "優惠代碼順序" },
];

// 價格滑桿邊界（active 券全距外留 headroom,step 10）
const PRICE_MAX = 1000;
const PRICE_STEP = 10;

// 無限滾動：每次載入筆數
const PAGE_SIZE = 30;

export default function App() {
  const { data, isMock } = useMemo(() => loadData(), []);
  const [state, setState] = useState<FilterState>(() =>
    parseState(new URLSearchParams(window.location.search)),
  );
  const [favorites, toggleFavorite] = useFavorites();
  const { theme, toggle: toggleTheme } = useTheme();
  const [limit, setLimit] = useState(PAGE_SIZE);
  const [sizeOpen, setSizeOpen] = useState(false);
  const sentinelRef = useRef<HTMLDivElement>(null);

  // 狀態寫回 URL(可分享重現)
  useEffect(() => {
    const params = toSearchParams(state);
    const qs = params.toString();
    window.history.replaceState(
      null,
      "",
      `${window.location.pathname}${qs ? `?${qs}` : ""}`,
    );
  }, [state]);

  const patch = (partial: Partial<FilterState>) =>
    setState((s) => ({ ...s, ...partial }));

  // 標籤列只出白名單內的 tag（有券挂該標籤才顯示）
  const tags = useMemo(() => {
    const all = collectTags(data.coupon_list);
    const byName = new Map(all.map((t) => [t.tag, t]));
    return TAG_WHITELIST.flatMap((t) => {
      const hit = byName.get(t);
      return hit ? [hit] : [];
    });
  }, [data]);

  // 通路固定兩鍵；orderType=null 即「不限」。值沿用資料端「外帶」(URL 相容),顯示名「自取」
  const ORDER_TYPES: { value: "外送" | "外帶"; label: string }[] = [
    { value: "外送", label: "外送" },
    { value: "外帶", label: "自取" },
  ];

  const visible = useMemo(
    () =>
      sortCoupons(
        filterCoupons(data.coupon_list, state, favorites),
        state.sort,
        state.sortDir,
      ),
    [data, state, favorites],
  );

  // 篩選條件變動時重置已載入筆數（code 只控詳情窗,不影響列表,排除在 key 外）
  const filterKey = JSON.stringify({ ...state, code: null });
  useEffect(() => {
    setLimit(PAGE_SIZE);
  }, [filterKey, favorites]);

  // 滾動接近底部時再載入一頁
  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setLimit((l) =>
            l < visible.length ? Math.min(l + PAGE_SIZE, visible.length) : l,
          );
        }
      },
      { rootMargin: "600px 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [visible.length]);

  const activeCount = useMemo(
    () => data.coupon_list.filter((c) => c.status === "active").length,
    [data],
  );

  const detail =
    (state.code && data.coupon_list.find((c) => c.key === state.code)) || null;

  // 標籤 chip 三態循環:中性 → 包含 → 排除 → 中性
  const cycleTag = (tag: string) => {
    setState((s) => {
      if (s.includeTags.includes(tag))
        return {
          ...s,
          includeTags: s.includeTags.filter((t) => t !== tag),
          excludeTags: [...s.excludeTags, tag],
        };
      if (s.excludeTags.includes(tag))
        return { ...s, excludeTags: s.excludeTags.filter((t) => t !== tag) };
      return { ...s, includeTags: [...s.includeTags, tag] };
    });
  };

  const chipLook = (tag: string) => {
    if (state.includeTags.includes(tag))
      return "border-transparent bg-red-600 text-white shadow-sm dark:bg-red-600 dark:text-white";
    if (state.excludeTags.includes(tag))
      return "border-transparent bg-stone-500/80 text-stone-50 line-through shadow-sm dark:bg-stone-400/90 dark:text-stone-900";
    return "border-red-900/10 bg-white/80 text-slate-600 shadow-sm backdrop-blur-sm hover:border-red-400/50 dark:border-white/15 dark:bg-white/10 dark:text-slate-200";
  };

  const shown = visible.slice(0, limit);

  // 回首頁：清除篩選 + 關詳情 + 回頂端（Header logo 按鈕）
  const goHome = () => {
    setState({ ...DEFAULT_STATE });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <div className="min-h-screen text-slate-900 dark:text-slate-100">
      <Header
        lastUpdate={data.last_update}
        theme={theme}
        onToggleTheme={toggleTheme}
        favOnly={state.favOnly}
        onToggleFavOnly={() => patch({ favOnly: !state.favOnly })}
        onHome={goHome}
      />
      <main className="mx-auto max-w-7xl px-3 pb-16 sm:px-5">
        {isMock && (
          <p className="mt-4 rounded bg-amber-100 px-3 py-2 text-sm text-amber-900 dark:bg-amber-900/40 dark:text-amber-200">
            目前顯示 mock 資料(public/coupons.js 未載入或為空)。
          </p>
        )}

        {/* hero:發光披薩 + 標語 */}
        <div className="mt-6 mb-2 flex items-center gap-6">
          <div className="relative shrink-0">
            <div
              aria-hidden="true"
              className="absolute -inset-7 rounded-full bg-[radial-gradient(circle,rgba(246,196,83,0.55),rgba(215,24,42,0.16)_55%,transparent_72%)] blur-md dark:bg-[radial-gradient(circle,rgba(246,183,60,0.45),rgba(215,24,42,0.2)_55%,transparent_72%)]"
            />
            <div className="relative">
              <button
                onClick={() => setSizeOpen(true)}
                title="必勝客比薩尺寸對照"
                aria-label="查看必勝客比薩尺寸對照"
                className="cursor-pointer rounded-full outline-none transition-transform hover:scale-[1.03] focus-visible:ring-2 focus-visible:ring-red-400 active:scale-95"
              >
                <PizzaMark size={84} />
              </button>
            </div>
          </div>
          <div>
            <h1 className="text-[30px] font-extrabold tracking-tight">
              今天的<em className="not-italic text-red-600 dark:text-red-400">必勝客</em>
              優惠，一頁看完
            </h1>
            <p className="mt-1 text-[15px] text-slate-500 dark:text-slate-400">
              每天蒐羅必勝客優惠資訊；代碼點一下即複製。
            </p>
          </div>
        </div>

        {/* 搜尋 + 排序(欄位+方向) */}
        <div className="mt-3 flex flex-wrap items-start gap-2">
          <div className="relative min-w-52 flex-1">
            <input
              type="search"
              value={state.q}
              onChange={(e) => patch({ q: e.target.value })}
              placeholder="搜尋餐點、優惠代碼或關鍵字(空格分隔多重條件)"
              className="w-full rounded-xl border border-red-900/10 bg-white/80 py-2.5 pl-3.5 pr-3.5 text-[15px] shadow-sm outline-none backdrop-blur placeholder:text-slate-400 focus:border-red-400/60 dark:border-white/10 dark:bg-white/5 dark:placeholder:text-slate-500"
            />
          </div>
          <div className="flex overflow-hidden rounded-xl border border-red-900/10 shadow-sm backdrop-blur-sm dark:border-white/10">
            <select
              value={state.sort}
              onChange={(e) => patch({ sort: e.target.value as SortKey })}
              aria-label="排序欄位"
              className="border-0 bg-white/80 px-3 py-2.5 text-[14px] text-slate-700 outline-none [&>option]:text-slate-900 dark:bg-white/5 dark:text-slate-200 dark:[&>option]:bg-[#241d16] dark:[&>option]:text-slate-100"
            >
              {SORT_KEYS.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
            <button
              onClick={() =>
                patch({ sortDir: (state.sortDir === "asc" ? "desc" : "asc") as SortDir })
              }
              title={state.sortDir === "asc" ? "升冪" : "降冪"}
              aria-label={state.sortDir === "asc" ? "切換為降冪" : "切換為升冪"}
              className="border-l border-red-900/10 bg-red-900/[0.04] px-3 text-red-600 hover:bg-red-900/10 dark:border-white/10 dark:bg-white/5 dark:text-red-400"
            >
              {state.sortDir === "asc" ? "↑" : "↓"}
            </button>
          </div>
        </div>

        {/* 通路/收藏/價格篩選同列靠左,區組之間用分隔線 */}
        <div className="mt-2.5 flex flex-wrap items-center gap-2">
          {ORDER_TYPES.map((t) => (
            <button
              key={t.value}
              onClick={() => patch({ orderType: state.orderType === t.value ? null : t.value })}
              aria-pressed={state.orderType === t.value}
              className={`rounded-full px-4 py-2 text-[14px] shadow-sm backdrop-blur-sm transition-colors ${
                state.orderType === t.value
                  ? "border border-transparent bg-gradient-to-r from-red-700 to-red-600 text-white"
                  : "border border-red-900/10 bg-white/80 text-slate-500 hover:border-red-400/50 dark:border-white/10 dark:bg-white/10 dark:text-slate-400"
              }`}
            >
              {t.label}
            </button>
          ))}
          <Divider />
          <button
            onClick={() => patch({ favOnly: !state.favOnly })}
            aria-pressed={state.favOnly}
            className={`rounded-full px-4 py-2 text-[14px] shadow-sm backdrop-blur-sm transition-colors ${
              state.favOnly
                ? "border border-transparent bg-gradient-to-r from-red-700 to-red-600 text-white"
                : "border border-red-900/10 bg-white/80 text-slate-500 hover:border-red-400/50 dark:border-white/10 dark:bg-white/10 dark:text-slate-400"
            }`}
          >
            只看收藏
          </button>
          <Divider />
          <PriceFilter
            max={PRICE_MAX}
            step={PRICE_STEP}
            valueMin={state.priceMin}
            valueMax={state.priceMax}
            onChange={(mn, mx) => patch({ priceMin: mn, priceMax: mx })}
          />
          <button
            onClick={() => setState({ ...DEFAULT_STATE, code: state.code })}
            title="清除所有篩選條件"
            className="inline-flex items-center gap-1.5 rounded-xl border border-red-600/40 bg-red-600/10 px-3.5 py-2 text-[14px] font-semibold text-red-600 shadow-sm backdrop-blur-sm transition-colors hover:bg-red-600/20 dark:border-red-500/40 dark:bg-red-500/10 dark:text-red-400 dark:hover:bg-red-500/20"
          >
            <svg
              viewBox="0 0 24 24"
              width="14"
              height="14"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
              <path d="M3 3v5h5" />
            </svg>
            重置
          </button>
        </div>

        {/* 標籤列(三態:點擊循環 包含→排除→取消,+/− 標示;僅白名單 tag) */}
        {tags.length > 0 && (
          <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
            {tags.map(({ tag, count }) => {
              const inc = state.includeTags.includes(tag);
              const ex = state.excludeTags.includes(tag);
              return (
                <button
                  key={tag}
                  onClick={() => cycleTag(tag)}
                  aria-pressed={inc ? "true" : ex ? "mixed" : "false"}
                  title="點一下=包含、再點=排除、再點=取消"
                  className={`rounded-full border px-3 py-1.5 text-[13px] transition-colors ${chipLook(tag)}`}
                >
                  {inc ? "+ " : ex ? "− " : ""}
                  {tag} <span className="opacity-60">{count}</span>
                </button>
              );
            })}
          </div>
        )}

        <p className="mt-4 text-[15px] text-slate-500 dark:text-slate-400">
          共 {visible.length} 筆優惠(全站 {activeCount} 筆,收藏 {favorites.size} 筆)
          {shown.length < visible.length && (
            <span className="ml-2 text-[13px] text-slate-400 dark:text-slate-500">
              已顯示 {shown.length} 筆,往下滑載入更多
            </span>
          )}
        </p>

        <div className="mt-4 grid auto-rows-[300px] grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {shown.map((c) => (
            <CouponCard
              key={c.key}
              coupon={c}
              isFavorite={favorites.has(c.key)}
              onToggleFavorite={() => toggleFavorite(c.key)}
              onOpen={() => patch({ code: c.key })}
            />
          ))}
        </div>
        {visible.length === 0 && (
          <p className="py-10 text-center text-[15px] text-slate-500 dark:text-slate-400">
            沒有符合的優惠——試著放寬條件，或按「重置」。
          </p>
        )}
        {/* 無限滾動哨兵 */}
        <div ref={sentinelRef} aria-hidden="true" className="h-1" />
      </main>

      {/* 頁尾：非官方聲明(資料來源官網/商標歸屬) + 更新時間 + repo 連結 */}
      <footer className="border-t border-red-900/10 bg-[#fff8ef]/40 py-5 text-center text-[12px] leading-relaxed text-slate-400 dark:border-white/10 dark:bg-white/[0.02] dark:text-slate-500">
        <p className="mx-auto max-w-3xl px-4">
          HutDeals 非必勝客官方網站。優惠資料來自必勝客官網公開頁面與官網訂餐驗證端點，
          <br />
          價格與供應以官網為準；Pizza Hut、必勝客等商標屬各權利人。
        </p>
        <p className="mt-1.5">
          資料最後更新：{data.last_update.slice(0, 10)}
          <span aria-hidden="true">　·　</span>
          <a
            href="https://github.com/happk/HutDeals"
            target="_blank"
            rel="noopener noreferrer"
            className="text-slate-500 hover:text-red-600 dark:text-slate-400 dark:hover:text-red-400"
          >
            GitHub 原始碼
          </a>
        </p>
      </footer>

      {detail && (
        <CouponDetail
          coupon={detail}
          lastUpdate={data.last_update}
          onClose={() => patch({ code: null })}
        />
      )}

      {sizeOpen && <SizeChartModal onClose={() => setSizeOpen(false)} />}

      <BackToTop />
    </div>
  );
}

/** hero 披薩 logo 彩蛋：必勝客比薩尺寸對照表（大13/小9/個人6 吋，2026-09-07 使用者確認） */
function SizeChartModal({ onClose }: { onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const rows: [string, string, string][] = [
    ["大比薩", "13 吋", "約 4–6 人份"],
    ["小比薩", "9 吋", "約 2–3 人份"],
    ["個人比薩", "6 吋", "單人份"],
  ];
  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="必勝客比薩尺寸對照"
        ref={ref}
        className="mt-16 w-full max-w-sm rounded-2xl border border-red-900/10 bg-[#fff8ef]/90 p-6 shadow-[0_20px_50px_rgba(240,169,46,0.35)] backdrop-blur-xl dark:border-white/10 dark:bg-[#1d1813]/90"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <h2 className="text-lg font-bold">比薩尺寸對照</h2>
          <button
            onClick={onClose}
            className="shrink-0 rounded px-2 py-1 text-sm text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
            aria-label="關閉"
          >
            ✕
          </button>
        </div>
        <table className="mt-3 w-full text-[14px]">
          <thead>
            <tr className="border-b border-red-900/10 text-left text-slate-500 dark:border-white/10 dark:text-slate-400">
              <th className="py-1.5 font-medium">名稱</th>
              <th className="py-1.5 font-medium">尺寸</th>
              <th className="py-1.5 font-medium">建議份量</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([name, size, serve]) => (
              <tr key={name} className="border-b border-red-900/5 last:border-0 dark:border-white/5">
                <td className="py-2 font-semibold text-red-700 dark:text-red-400">{name}</td>
                <td className="py-2">{size}</td>
                <td className="py-2 text-slate-500 dark:text-slate-400">{serve}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** 直向分隔線(元素實現,非「|」字符),篩選列區組之間用 */
function Divider() {
  return <span aria-hidden="true" className="h-6 w-px shrink-0 self-center bg-red-900/15 dark:bg-white/20" />;
}

/** 常駐回到頂端按鈕:下滑超過一屏後出現,右下角固定 */
function BackToTop() {
  const [show, setShow] = useState(false);
  useEffect(() => {
    const onScroll = () => setShow(window.scrollY > 480);
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  if (!show) return null;
  return (
    <button
      onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
      title="回到頂端"
      aria-label="回到頂端"
      className="fixed bottom-6 right-6 z-50 flex h-11 w-11 items-center justify-center rounded-full border border-red-900/10 bg-white/90 text-red-600 shadow-[0_8px_24px_rgba(215,24,42,0.25)] backdrop-blur transition-colors hover:bg-red-600 hover:text-white dark:border-white/15 dark:bg-[#1d1813]/90 dark:text-red-400 dark:hover:bg-red-600 dark:hover:text-white"
    >
      <svg
        viewBox="0 0 24 24"
        width="20"
        height="20"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M12 19V5" />
        <path d="m5 12 7-7 7 7" />
      </svg>
    </button>
  );
}
