import { useRef, useState } from "react";

/**
 * 價格篩選:數字輸入 + 雙點拖曳滑桿(步進 10),滑桿水平置於輸入框右側。
 * 兩點推到最外側 = 不設限(onChange 收 null);輸入小數無條件退位、非法字元回前值、最小 1。
 */
export default function PriceFilter({
  max,
  step,
  valueMin,
  valueMax,
  onChange,
}: {
  max: number;
  step: number;
  valueMin: number | null;
  valueMax: number | null;
  onChange: (min: number | null, max: number | null) => void;
}) {
  const sliderRef = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState<"min" | "max" | null>(null);

  const lo = valueMin ?? 0;
  const hi = valueMax ?? max;

  const commit = (lo2: number, hi2: number) => {
    onChange(lo2 <= 0 ? null : lo2, hi2 >= max ? null : hi2);
  };

  const posToValue = (clientX: number) => {
    const r = sliderRef.current?.getBoundingClientRect();
    if (!r) return 0;
    const raw = Math.round(((clientX - r.left) / r.width) * max / step) * step;
    return Math.max(0, Math.min(max, raw));
  };

  const onThumbDown = (which: "min" | "max") => (e: React.PointerEvent) => {
    e.preventDefault();
    const thumb = e.currentTarget as HTMLDivElement;
    thumb.setPointerCapture(e.pointerId);
    setDragging(which);
  };

  const onMove = (e: React.PointerEvent) => {
    if (!dragging) return;
    const v = posToValue(e.clientX);
    if (dragging === "min") commit(Math.min(v, hi), hi);
    else commit(lo, Math.max(v, lo));
  };

  const inputHandler = (which: "min" | "max") => (e: React.ChangeEvent<HTMLInputElement>) => {
    const el = e.target;
    const raw = el.value.trim();
    if (raw === "") {
      el.dataset.prev = "";
      onChange(which === "min" ? null : valueMin, which === "max" ? null : valueMax);
      return;
    }
    const n = Math.floor(Number(raw)); // 小數無條件退位
    if (!Number.isFinite(n)) {
      // 非法字符 → 前一次數值
      el.value = el.dataset.prev ?? "";
      return;
    }
    const v = Math.max(1, n);
    el.dataset.prev = String(v);
    el.value = String(v);
    if (which === "min") onChange(v, valueMax);
    else onChange(valueMin, v);
  };

  const thumbCls = (which: "min" | "max") =>
    `absolute top-[2px] h-4 w-4 rounded-full border-[2.5px] border-white dark:border-[#1d1813] bg-red-600 shadow-md cursor-grab select-none ${
      dragging === which ? "scale-110 cursor-grabbing" : ""
    }`;

  return (
    <div className="flex items-center gap-2">
      <div className="flex items-center gap-1.5 rounded-xl border border-red-900/10 bg-white/80 px-3 py-2 text-[14px] text-slate-500 shadow-sm backdrop-blur-sm dark:border-white/10 dark:bg-white/10 dark:text-slate-400">
        $
        <input
          type="number"
          aria-label="最低價格"
          placeholder="最低"
          value={valueMin ?? ""}
          onChange={inputHandler("min")}
          className="w-20 rounded-lg bg-red-900/[0.06] px-2 py-1 text-center text-[14px] text-slate-900 shadow-inner outline-none placeholder:text-slate-400 focus:bg-red-900/10 dark:bg-white/10 dark:text-slate-100 dark:placeholder:text-slate-500 dark:focus:bg-white/15 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
        />
        –
        $
        <input
          type="number"
          aria-label="最高價格"
          placeholder="最高"
          value={valueMax ?? ""}
          onChange={inputHandler("max")}
          className="w-20 rounded-lg bg-red-900/[0.06] px-2 py-1 text-center text-[14px] text-slate-900 shadow-inner outline-none placeholder:text-slate-400 focus:bg-red-900/10 dark:bg-white/10 dark:text-slate-100 dark:placeholder:text-slate-500 dark:focus:bg-white/15 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
        />
      </div>
      <div
        ref={sliderRef}
        aria-label="價格範圍滑桿"
        className="relative h-5 w-36 select-none sm:w-44"
        onPointerMove={onMove}
        onPointerUp={() => setDragging(null)}
      >
        <div className="absolute inset-x-0 top-2 h-1 rounded bg-red-900/10 dark:bg-white/10" />
        <div
          className="absolute top-2 h-1 rounded bg-gradient-to-r from-red-700 to-red-600"
          style={{ left: `${(lo / max) * 100}%`, width: `${((hi - lo) / max) * 100}%` }}
        />
        <div
          role="slider"
          aria-label="最低價格"
          aria-valuemin={0}
          aria-valuemax={max}
          aria-valuenow={lo}
          tabIndex={0}
          className={`${thumbCls("min")} -ml-2`}
          style={{ left: `${(lo / max) * 100}%` }}
          onPointerDown={onThumbDown("min")}
          data-testid="price-thumb-min"
        />
        <div
          role="slider"
          aria-label="最高價格"
          aria-valuemin={0}
          aria-valuemax={max}
          aria-valuenow={hi}
          tabIndex={0}
          className={`${thumbCls("max")} -ml-2`}
          style={{ left: `${(hi / max) * 100}%` }}
          onPointerDown={onThumbDown("max")}
          data-testid="price-thumb-max"
        />
      </div>
    </div>
  );
}
