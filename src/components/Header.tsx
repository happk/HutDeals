import { useEffect, useRef, useState } from "react";

/**
 * 圓形披薩 logo（design-samples/sample-a.html hero 同款）:
 * 餅皮金圈+起司底+八等分切線+臘腸+羅勒葉,header 與 hero 共用。
 */
export function PizzaMark({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" aria-hidden="true" className="shrink-0 drop-shadow-[0_2px_8px_rgba(215,24,42,0.45)]">
      <circle cx="50" cy="50" r="48" fill="#e8a33d" />
      <circle cx="50" cy="50" r="40" fill="#f6b73c" />
      <circle cx="50" cy="50" r="40" fill="none" stroke="rgba(142,15,28,.18)" strokeWidth="1.5" />
      <line x1="50" y1="10" x2="50" y2="90" stroke="rgba(142,15,28,.10)" strokeWidth="1.5" />
      <line x1="10" y1="50" x2="90" y2="50" stroke="rgba(142,15,28,.10)" strokeWidth="1.5" />
      <line x1="21.7" y1="21.7" x2="78.3" y2="78.3" stroke="rgba(142,15,28,.10)" strokeWidth="1.5" />
      <line x1="78.3" y1="21.7" x2="21.7" y2="78.3" stroke="rgba(142,15,28,.10)" strokeWidth="1.5" />
      <circle cx="50" cy="30" r="6" fill="#d7182a" />
      <circle cx="67" cy="43" r="6" fill="#d7182a" />
      <circle cx="60" cy="66" r="6" fill="#d7182a" />
      <circle cx="36" cy="60" r="5.4" fill="#d7182a" />
      <circle cx="30" cy="36" r="5" fill="#d7182a" />
      <circle cx="43" cy="47" r="4.2" fill="#b3121f" />
      <ellipse cx="57" cy="55" rx="3.4" ry="2.2" fill="#4f9153" transform="rotate(30 57 55)" />
      <ellipse cx="38" cy="75" rx="3.4" ry="2.2" fill="#4f9153" transform="rotate(-20 38 75)" />
      <ellipse cx="73" cy="27" rx="3.2" ry="2" fill="#4f9153" transform="rotate(60 73 27)" />
    </svg>
  );
}

function hiconCls(active: boolean) {
  return `inline-flex h-8 w-8 items-center justify-center rounded-[10px] border transition-colors ${
    active
      ? "border-amber-400/60 bg-amber-500/10 text-amber-500 dark:text-amber-400"
      : "border-red-900/10 bg-red-900/[0.04] text-slate-500 hover:text-slate-900 dark:border-white/10 dark:bg-white/5 dark:text-slate-400 dark:hover:text-slate-100"
  }`;
}

/**
 * 常駐毛玻璃 header:Pizza logo+副標題、資料更新時間、
 * GitHub 倉庫(佔位)/通知鈴鐺(彈窗佔位)/收藏夾星(=只看收藏) / 主題切換。
 */
export default function Header({
  lastUpdate,
  theme,
  onToggleTheme,
  favOnly,
  onToggleFavOnly,
  onHome,
}: {
  lastUpdate: string;
  theme: "light" | "dark";
  onToggleTheme: () => void;
  favOnly: boolean;
  onToggleFavOnly: () => void;
  onHome: () => void;
}) {
  const [bellOpen, setBellOpen] = useState(false);
  const bellRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!bellOpen) return;
    const close = (e: MouseEvent) => {
      if (bellRef.current && !bellRef.current.contains(e.target as Node)) setBellOpen(false);
    };
    document.addEventListener("click", close);
    return () => document.removeEventListener("click", close);
  }, [bellOpen]);

  return (
    <header className="sticky top-0 z-50 border-b border-red-900/10 bg-[#fff8ef]/75 shadow-[0_6px_24px_rgba(240,169,46,0.35)] backdrop-blur-xl dark:border-white/10 dark:bg-[#16120e]/65 dark:shadow-none">
      <div className="mx-auto flex max-w-7xl items-center gap-3.5 px-3 py-2.5 sm:px-5">
        <button
          onClick={onHome}
          title="回首頁(清除篩選、回到頂端)"
          aria-label="回首頁(清除篩選、回到頂端)"
          className="group flex cursor-pointer items-center gap-3.5 rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-red-400"
        >
          <PizzaMark />
          <div className="leading-tight">
            <div className="text-[23px] font-extrabold tracking-wide text-red-700 transition-colors group-hover:text-red-800 dark:bg-gradient-to-r dark:from-red-500 dark:to-amber-400 dark:bg-clip-text dark:text-transparent dark:group-hover:brightness-125">
              HutDeals
            </div>
            <div className="mt-px text-[13px] text-slate-500 dark:text-slate-400">
              台灣必勝客 (Pizza Hut) 優惠券
            </div>
          </div>
        </button>
        <div className="ml-auto flex items-center gap-2">
          <span className="hidden text-[12px] text-slate-500 dark:text-slate-400 sm:inline">
            資料最後更新:{lastUpdate}
          </span>
          <div className="flex items-center gap-1.5">
            <a
              href="#"
              title="專案倉庫(佔位)"
              aria-label="GitHub 專案倉庫"
              className={hiconCls(false)}
            >
              <svg width="17" height="17" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
              </svg>
            </a>
            <div className="relative" ref={bellRef}>
              <button
                onClick={() => setBellOpen((v) => !v)}
                title="更新通知"
                aria-label="更新通知"
                aria-expanded={bellOpen}
                className={hiconCls(false)}
              >
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
                  <path d="M13.7 21a2 2 0 0 1-3.4 0" />
                </svg>
              </button>
              {bellOpen && (
                <div className="absolute right-0 top-10 z-50 w-64 rounded-2xl border border-red-900/10 bg-white p-4 text-[13px] shadow-xl dark:border-white/10 dark:bg-[#1d1813]">
                  <b className="mb-1.5 block text-red-600 dark:text-red-400">更新通知</b>
                  {/* 永久佔位：無通知/資料時顯示（2026-09-07） */}
                  <p className="m-0 text-slate-400 dark:text-slate-500">Hello Pizza!</p>
                  {/* 互動提示（2026-09-07）：放通知而非彩蛋視窗 */}
                  <ul className="mt-2 space-y-1 border-t border-red-900/10 pt-2 text-slate-500 dark:border-white/10 dark:text-slate-400">
                    <li>• 點左上 HutDeals logo 回首頁（清篩選）</li>
                    <li>• 點首頁大披薩看尺寸對照</li>
                  </ul>
                </div>
              )}
            </div>
            <button
              onClick={onToggleFavOnly}
              title="收藏夾(只看收藏)"
              aria-label="只看收藏"
              aria-pressed={favOnly}
              className={hiconCls(favOnly)}
            >
              <svg width="17" height="17" viewBox="0 0 24 24" fill={favOnly ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
              </svg>
            </button>
            <button
              onClick={onToggleTheme}
              aria-label={theme === "dark" ? "切換為淺色模式" : "切換為深色模式"}
              title={theme === "dark" ? "淺色模式" : "深色模式"}
              className={hiconCls(false)}
            >
              {theme === "dark" ? (
                <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                  <circle cx="12" cy="12" r="4" />
                  <path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4m11.4-11.4 1.4-1.4" />
                </svg>
              ) : (
                <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
                </svg>
              )}
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
