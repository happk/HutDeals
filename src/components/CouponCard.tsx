import { useState } from "react";
import type { Coupon } from "../types";
import MealItems from "./MealItems";
import { displayName } from "../lib/format";

/** 通路 badge(卡片標題列左側,關鍵展示位):外送=金黃、自取=綠、未標=灰 */
function ChanBadge({ label, tone }: { label: string; tone: "amber" | "emerald" | "slate" }) {
  const tones = {
    amber:
      "border-amber-500/40 text-amber-600 dark:border-amber-400/40 dark:text-amber-400",
    emerald:
      "border-emerald-600/40 text-emerald-700 dark:border-emerald-400/40 dark:text-emerald-400",
    slate:
      "border-slate-400/40 text-slate-500 dark:border-slate-500/40 dark:text-slate-400",
  } as const;
  return (
    <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-medium ${tones[tone]}`}>
      {label}
    </span>
  );
}

function ChanBadges({ orderType }: { orderType?: string | null }) {
  if (!orderType) return <ChanBadge label="通路未標" tone="slate" />;
  const both = orderType.includes("外送") && orderType.includes("外帶");
  if (both)
    return (
      <>
        <ChanBadge label="外送" tone="amber" />
        <ChanBadge label="自取" tone="emerald" />
      </>
    );
  if (orderType.includes("外送")) return <ChanBadge label="外送" tone="amber" />;
  return <ChanBadge label="自取" tone="emerald" />;
}

/** 打勾 SVG(複製成功) */
function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}

/** 兩個方塊重疊 SVG(複製圖示) */
function CopyIcon() {
  return (
    <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}

/**
 * 文字卡(2026-09-05 改版):內容物與價格為主、代碼退居膠囊、通路在標題列。
 * 固定高度由 grid auto-rows 掌控,內容裝不下時卡片內部滾動。
 */
export default function CouponCard({
  coupon,
  isFavorite,
  onToggleFavorite,
  onOpen,
}: {
  coupon: Coupon;
  isFavorite: boolean;
  onToggleFavorite: () => void;
  onOpen: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const name = displayName(coupon.name);

  const copyCode = async () => {
    if (!coupon.code) return;
    try {
      await navigator.clipboard.writeText(coupon.code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard 不可用時忽略 */
    }
  };

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-2xl border border-red-900/10 bg-white/95 p-4 shadow-[0_6px_18px_rgba(240,169,46,0.16)] backdrop-blur-md transition-[transform,border-color,box-shadow] duration-150 hover:-translate-y-0.5 hover:shadow-[0_12px_28px_rgba(240,169,46,0.3)] focus-within:border-red-400 dark:border-white/10 dark:bg-white/[0.07] dark:shadow-[0_4px_16px_rgba(0,0,0,0.35)] dark:hover:border-red-500/40">
      {/* 標題列:通路(badge) + 品名 + 收藏星 */}
      <div className="flex min-h-6 items-center gap-1.5">
        <ChanBadges orderType={coupon.orderType} />
        <h2
          onClick={onOpen}
          title={coupon.name}
          className="min-w-0 flex-1 cursor-pointer truncate text-[15px] font-bold leading-snug hover:underline"
        >
          {name}
        </h2>
        <button
          onClick={onToggleFavorite}
          aria-label={isFavorite ? "取消收藏" : "加入收藏"}
          aria-pressed={isFavorite}
          className={`shrink-0 text-lg leading-none transition-colors ${
            isFavorite
              ? "text-amber-500 dark:text-amber-400"
              : "text-slate-400 hover:text-amber-500 dark:text-slate-500 dark:hover:text-amber-400"
          }`}
        >
          {isFavorite ? "★" : "☆"}
        </button>
      </div>

      {/* 內容物:彈性區,裝不下時內部滾動;帶底色便於分辨;與詳情頁同款分組渲染 */}
      <div className="mt-2 min-h-0 flex-1 overflow-y-auto rounded-[10px] bg-red-900/[0.04] p-2 px-2.5 dark:bg-white/5 [scrollbar-width:thin] [&::-webkit-scrollbar]:w-1 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-red-900/20 dark:[&::-webkit-scrollbar-thumb]:bg-white/20">
        {coupon.items && coupon.items.length > 0 ? (
          <MealItems items={coupon.items} flavorSets={coupon.flavorSets} compact />
        ) : coupon.description ? (
          <p className="m-0 text-[13px] leading-[1.65] text-slate-800 dark:text-slate-200">
            {coupon.description}
          </p>
        ) : null}
      </div>

      {/* 價格列:查看完整資訊佔約 2/3 + 價格 1/3 */}
      <div className="mt-2 flex shrink-0 items-center gap-2">
        <button
          onClick={onOpen}
          className="w-2/3 shrink-0 rounded-[9px] border border-red-600/40 bg-red-600/10 px-3 py-2 text-[14px] font-semibold text-red-600 transition-colors hover:bg-red-600/20 dark:border-red-500/40 dark:text-red-400 dark:bg-red-500/10 dark:hover:bg-red-500/20"
        >
          查看完整資訊
        </button>
        <span className="flex-1 text-right text-[22px] font-extrabold text-slate-900 dark:text-slate-100">
          {coupon.price != null ? (
            <>
              ${coupon.price}
              {coupon.priceNote && (
                <span className="ml-0.5 text-[11px] font-normal text-slate-500 dark:text-slate-400">
                  {coupon.priceNote}
                </span>
              )}
              {coupon.msrp != null && (
                <s className="ml-1 text-[11px] font-normal text-slate-400 dark:text-slate-500">
                  原價${coupon.msrp}
                </s>
              )}
            </>
          ) : (
            <span className="text-xs font-normal text-slate-400">價格未知</span>
          )}
        </span>
      </div>

      {/* 底列:前往訂購 + 代碼膠囊(代碼+複製) */}
      <div className="mt-2 flex shrink-0 gap-2">
        {coupon.orderUrl && (
          <a
            href={coupon.orderUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-1 rounded-[9px] bg-gradient-to-r from-red-700 to-red-600 px-3 py-2 text-center text-[14px] font-bold text-white hover:from-red-800 hover:to-red-700 dark:from-red-700 dark:to-red-500"
          >
            前往訂購
          </a>
        )}
        {coupon.code && (
          <span className="flex shrink-0 items-center gap-1.5 rounded-[9px] border border-red-900/10 bg-red-900/[0.04] py-0 pl-2.5 pr-1 dark:border-white/10 dark:bg-white/5">
            <span className="font-mono text-[14px] font-semibold tracking-wider text-slate-500 dark:text-slate-400">
              {coupon.code}
            </span>
            <button
              onClick={copyCode}
              title={`複製代碼 ${coupon.code}`}
              aria-label={`複製代碼 ${coupon.code}`}
              className={`rounded-md px-1.5 py-1.5 transition-colors ${
                copied
                  ? "text-emerald-600 dark:text-emerald-400"
                  : "text-slate-600 hover:text-red-600 dark:text-slate-300 dark:hover:text-red-400"
              }`}
            >
              {copied ? <CheckIcon /> : <CopyIcon />}
            </button>
          </span>
        )}
      </div>
    </div>
  );
}
