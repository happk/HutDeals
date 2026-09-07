import { useEffect, useMemo, useRef } from "react";
import type { Coupon } from "../types";
import MealItems from "./MealItems";
import { buildIssueUrl, detectRepo } from "../lib/report";
import { displayName } from "../lib/format";

/** 單券詳情 modal;由 /?code=<key> 深連結或點擊卡片開啟。 */
export default function CouponDetail({
  coupon,
  lastUpdate,
  onClose,
}: {
  coupon: Coupon;
  lastUpdate: string;
  onClose: () => void;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const prev = document.activeElement;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      if (prev instanceof HTMLElement) prev.focus();
    };
  }, [onClose]);

  const shareUrl = useMemo(() => {
    const u = new URL(window.location.href);
    u.search = `?code=${encodeURIComponent(coupon.key)}`;
    return u.toString();
  }, [coupon.key]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="優惠詳情"
        className="mt-10 max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-red-900/10 bg-[#fff8ef]/85 p-6 shadow-[0_20px_50px_rgba(240,169,46,0.35)] backdrop-blur-xl dark:border-white/10 dark:bg-[#1d1813]/85 dark:shadow-none"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <h2 className="text-lg font-bold leading-snug">{displayName(coupon.name)}</h2>
          <button
            ref={closeRef}
            onClick={onClose}
            className="shrink-0 rounded px-2 py-1 text-sm text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
            aria-label="關閉"
          >
            ✕
          </button>
        </div>
        {coupon.items && coupon.items.length > 0 ? (
          <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800/50">
            <MealItems items={coupon.items} flavorSets={coupon.flavorSets} />
          </div>
        ) : (
          coupon.description && (
            <p className="mt-3 whitespace-pre-line text-sm text-slate-700 dark:text-slate-300">
              {coupon.description}
            </p>
          )
        )}
        <dl className="mt-4 space-y-1.5 text-[15px]">
          {/* 活動期間槽（IG 融合前為空，佔位顯示 —） */}
          <div className="flex gap-2">
            <dt className="text-slate-500 dark:text-slate-400">活動期間</dt>
            <dd className={coupon.startDate || coupon.endDate ? "" : "text-slate-400 dark:text-slate-600"}>
              {coupon.startDate && coupon.endDate
                ? `${coupon.startDate} ~ ${coupon.endDate}`
                : coupon.startDate || coupon.endDate || "—"}
            </dd>
          </div>
          {coupon.code && (
            <div className="flex gap-2">
              <dt className="text-slate-500">優惠代碼</dt>
              <dd className="font-mono font-bold text-red-600 dark:text-red-400">
                {coupon.code}
              </dd>
            </div>
          )}
          {coupon.source === "verified-external" && (
            <div className="flex gap-2 text-emerald-700 dark:text-emerald-300">
              <dt className="text-slate-500 dark:text-slate-400">來源</dt>
              <dd>
                {coupon.partner ? `${coupon.partner}聯名` : "活動"}優惠
              </dd>
            </div>
          )}
          {coupon.source === "verified-external" && (
            <div className="flex gap-2 rounded bg-amber-50 p-2 text-xs text-amber-700 dark:bg-amber-900/20 dark:text-amber-300">
              <dt aria-hidden="true">⚠</dt>
              <dd className="whitespace-nowrap max-sm:whitespace-normal">
                外部社群收集代碼，可兌換性以官網下單結果為準。
              </dd>
            </div>
          )}
          {coupon.price != null && (
            <div className="flex gap-2">
              <dt className="text-slate-500">價格</dt>
              <dd className="font-bold">
                ${coupon.price}
                {coupon.priceNote && (
                  <span className="text-xs font-normal"> {coupon.priceNote}</span>
                )}
                {coupon.msrp != null && (
                  <s className="text-xs font-normal"> 原價${coupon.msrp}</s>
                )}
              </dd>
            </div>
          )}
          {coupon.orderType && (
            <div className="flex gap-2">
              <dt className="text-slate-500">適用</dt>
              <dd>{coupon.orderType.replace(/外帶/g, "自取")}</dd>
            </div>
          )}
          {coupon.category && (
            <div className="flex gap-2">
              <dt className="text-slate-500">分類</dt>
              <dd>{coupon.category}</dd>
            </div>
          )}
          {coupon.status === "offline" && (
            <div className="flex gap-2 text-amber-600 dark:text-amber-400">
              <dt>狀態</dt>
              <dd>
                已從官網下架(官網已無此優惠,於 {coupon.offlineSince} 標記)
              </dd>
            </div>
          )}
        </dl>
        <div className="mt-5 flex flex-wrap gap-2">
          {coupon.status === "active" && coupon.orderUrl && (
            <a
              href={coupon.orderUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded bg-red-600 px-4 py-2 text-[15px] font-medium text-white hover:bg-red-700"
            >
              前往官網訂購
            </a>
          )}
          <button
            onClick={() => {
              void navigator.clipboard?.writeText(shareUrl);
            }}
            className="rounded border border-slate-300 px-4 py-2 text-[15px] hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
          >
            複製分享連結
          </button>
          <a
            href={buildIssueUrl(coupon, detectRepo(), lastUpdate)}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded border border-slate-300 px-4 py-2 text-[15px] hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
          >
            回報問題/失效
          </a>
        </div>
      </div>
    </div>
  );
}
