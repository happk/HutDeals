import type { Flavor, MealItem } from "../types";

/** 舊三欄格式（parse_meal 產出，遷移前向後相容用） */
interface LegacyItem {
  text: string;
  choices: string[];
  add?: string | null;
}

/** 尾巴 (N選M) 或 (擇一) 註記（舊格式分類用） */
function tailPick(s: string): { note: string; rest: string } | null {
  let m = s.match(/[（(]\s*(\d{1,2})\s*選\s*(\d{1,2})\s*[)）]\s*$/);
  if (m) return { note: `（${m[1]}選${m[2]}）`, rest: s.slice(0, m.index).trim() };
  m = s.match(/[（(]擇一[)）]\s*$/);
  if (m) return { note: "（擇一）", rest: s.slice(0, m.index).trim() };
  return null;
}

function isDrink(s: string): boolean {
  return /可樂|七喜|飲料|紅茶|綠茶|咖啡|玉米濃湯|檸檬/.test(s);
}
function isPizza(s: string): boolean {
  return /比薩|披薩|鬆厚/.test(s);
}
function isPizzaFlavorGroup(anchor: string, choices: string[]): boolean {
  return isPizza(anchor) && choices.length > 0 && choices.every((c) => !isPizza(c) && !isDrink(c));
}
function candidates(it: LegacyItem): string[] {
  const pick = tailPick(it.text);
  const head = pick ? pick.rest : it.text;
  return [head, ...it.choices];
}
function categoryOf(cands: string[]): string {
  if (cands.length && cands.every(isDrink)) return "飲料";
  return "副餐";
}

/** 舊三欄格式渲染（遷移前 coupons.js 仍是舊 items 時的 fallback） */
function LegacyMealItems({
  items,
  compact,
}: {
  items: LegacyItem[];
  compact: boolean;
}) {
  const main = compact ? "text-[14px]" : "text-[15px]";
  const sub = compact ? "text-[12px]" : "text-[13px]";
  const picks = items.map((it) => tailPick(it.text));
  const groupInfo = items.map((it, i) => {
    const hasPick = picks[i] !== null;
    if (!hasPick || it.choices.length === 0) return { type: "plain" as const };
    const cands = candidates(it);
    if (isPizzaFlavorGroup(picks[i]!.rest, it.choices)) return { type: "pizza" as const };
    return { type: "group" as const, cat: categoryOf(cands) };
  });
  const catCount = new Map<string, number>();
  for (const g of groupInfo) if (g.type === "group") catCount.set(g.cat, (catCount.get(g.cat) ?? 0) + 1);
  const catIdx = new Map<string, number>();
  return (
    <ul className={compact ? "space-y-0.5" : "space-y-1"}>
      {items.map((it, i) => {
        const gi = groupInfo[i];
        const pick = picks[i];
        if (gi.type === "plain") {
          return (
            <li key={i} className={`flex gap-1.5 ${main} leading-snug`}>
              <span className="shrink-0 text-red-500 dark:text-red-400">•</span>
              <span>
                {it.text}
                {it.add && (
                  <span className={`${sub} font-semibold text-amber-600 dark:text-amber-400`}> {it.add}</span>
                )}
              </span>
            </li>
          );
        }
        if (gi.type === "pizza") {
          return (
            <li key={i}>
              <div className={`flex gap-1.5 ${main} leading-snug`}>
                <span className="shrink-0 text-red-500 dark:text-red-400">•</span>
                <span>
                  {pick!.rest}
                  <span className="text-slate-500 dark:text-slate-400">{pick!.note}</span>
                </span>
              </div>
              <ul className="ml-2 mt-0.5 space-y-0.5 border-l border-slate-300 pl-3 dark:border-slate-600">
                {it.choices.map((c, j) => (
                  <li key={j} className={`${sub} leading-snug text-slate-600 dark:text-slate-300`}>{c}</li>
                ))}
              </ul>
            </li>
          );
        }
        const idx = catIdx.get(gi.cat) ?? 0;
        catIdx.set(gi.cat, idx + 1);
        const suffix = catCount.get(gi.cat)! > 1 ? String.fromCharCode(65 + idx) : "";
        const cands = candidates(it);
        return (
          <li key={i}>
            <div className={`flex gap-1.5 ${main} leading-snug`}>
              <span className="shrink-0 text-red-500 dark:text-red-400">•</span>
              <span className="font-medium">
                {gi.cat}
                {suffix}
                <span className="font-normal text-slate-500 dark:text-slate-400">{pick!.note}</span>
              </span>
            </div>
            <ul className="ml-2 mt-0.5 space-y-0.5 border-l border-slate-300 pl-3 dark:border-slate-600">
              {cands.map((cd, j) => (
                <li key={j} className={`${sub} leading-snug text-slate-600 dark:text-slate-300`}>{cd}</li>
              ))}
            </ul>
          </li>
        );
      })}
    </ul>
  );
}

/**
 * 結構化餐點候選（orderflow 版）。items 是「候選選項」扁平清單，每筆含
 * group/groupIdx/priceAdd/flavorIdx；口味經 flavorSets[flavorIdx] 解引用。
 *
 * 顯示規則（2026-09-07 使用者確認 v3）：
 * - 卡片(compact)：每類顯示前 4 個候選(含加價，加價標琥珀 +$NN)，超過 4 顯示深色「…」。
 * - 詳細頁：每類內 **+0 預設區在上、加價區在下**（中間細分隔線，不拆散）；
 *   候選名一律正常色，+0 標記灰字「+$0」、加價標記琥珀「+$NN」。
 * - 口味(flavorSets[flavorIdx])只在詳細頁顯示。
 * - 組標題顯示 cat（個人比薩/大比薩/副食/飲料…），無 cat 退回 group 名。
 */
const GROUP_LABEL: Record<MealItem["group"], string> = {
  main: "主餐",
  second: "副食",
  add: "加購",
};

/** 每組一個類別；同 group 不同 groupIdx 是不同組（26868 有 main×2） */
function groupKey(it: MealItem): string {
  return `${it.group}-${it.groupIdx}`;
}

/** 類別標題：依 cat（大/小/個人比薩/副食/飲料）；無 cat 退回 group 名。 */
function groupTitle(group: MealItem["group"], cat: string | undefined, count: number): string {
  let label: string;
  if (cat) {
    label = cat;
  } else {
    label = GROUP_LABEL[group] ?? group;
  }
  // add(加購) 是「選購」，其餘是「N 選1」
  return group === "add" ? `${label}（${count} 種）` : `${label}（${count} 選1）`;
}

/** 取候選的口味清單（flavorIdx → flavorSets 解引用） */
function flavorsOf(it: MealItem, flavorSets: Flavor[][] | undefined): Flavor[] | null {
  if (it.flavorIdx == null || !flavorSets) return null;
  return flavorSets[it.flavorIdx] ?? null;
}

export default function MealItems({
  items,
  flavorSets,
  compact = false,
}: {
  items: MealItem[];
  flavorSets?: Flavor[][];
  compact?: boolean;
}) {
  // 向後相容：舊三欄格式（{text, choices, add}）無 group 欄位 → 走舊渲染
  if (items.length > 0 && items[0] && !("group" in items[0])) {
    return <LegacyMealItems items={items as unknown as LegacyItem[]} compact={compact} />;
  }
  return <StructuredMealItems items={items} flavorSets={flavorSets} compact={compact} />;
}

function StructuredMealItems({
  items,
  flavorSets,
  compact = false,
}: {
  items: MealItem[];
  flavorSets?: Flavor[][];
  compact?: boolean;
}) {
  // 字體：詳情頁加大（16/14），卡片維持小（14/12）
  const main = compact ? "text-[14px]" : "text-[16px]";
  const sub = compact ? "text-[12px]" : "text-[14px]";

  // 依 group+groupIdx 分組（保持出現順序）
  const groups: { key: string; group: MealItem["group"]; items: MealItem[] }[] = [];
  const seen = new Map<string, typeof groups[number]>();
  for (const it of items) {
    const k = groupKey(it);
    let g = seen.get(k);
    if (!g) {
      g = { key: k, group: it.group, items: [] };
      seen.set(k, g);
      groups.push(g);
    }
    g.items.push(it);
  }

  return (
    <ul className={compact ? "space-y-1" : "space-y-1.5"}>
      {groups.map((g) => {
        const cat = g.items[0]?.cat ?? undefined;
        const label = groupTitle(g.group, cat, g.items.length);
        const freeItems = g.items.filter((i) => i.priceAdd === 0);
        // 加價候選：詳情頁加價區依 priceAdd 由低到高排序(2026-09-07 使用者)；卡片補位亦同
        const paidItems = g.items
          .filter((i) => i.priceAdd > 0)
          .sort((a, b) => a.priceAdd - b.priceAdd);
        // 卡片：+0 優先顯示，加價補在後；合計取前 4(加價標 +$NN)、超過 4 顯示「…」
        // 詳情：+0 全顯(上) + 加價區(下分隔分開)
        const cardVisible = [...freeItems, ...paidItems].slice(0, 4);
        const cardHidden = g.items.length - cardVisible.length;

        return (
          <li key={g.key}>
            {/* 類別標題 */}
            <div className={`flex gap-1.5 ${main} leading-snug`}>
              <span className="shrink-0 text-red-500 dark:text-red-400">•</span>
              <span className="font-medium">{label}</span>
            </div>
            {/* 卡片：前 4 候選雙欄(1 2/3 4)、含加價標記 */}
            {compact ? (
              <div className="ml-2 mt-1 grid grid-cols-2 gap-x-3 gap-y-0.5 border-l border-slate-300 pl-3 dark:border-slate-600">
                {cardVisible.map((it, j) => (
                  <div key={j} className={`${sub} min-w-0 leading-snug text-slate-700 dark:text-slate-200`}>
                    <span className="break-words">{it.text}</span>
                    {it.priceAdd > 0 && (
                      <span className="ml-1 font-semibold text-amber-600 dark:text-amber-400">
                        +${it.priceAdd}
                      </span>
                    )}
                  </div>
                ))}
                {cardHidden > 0 && (
                  <div className={`${sub} leading-snug text-slate-900 dark:text-slate-100`}>…</div>
                )}
              </div>
            ) : (
              <>
                <ul className="ml-2 mt-1 space-y-1 border-l border-slate-300 pl-3 dark:border-slate-600">
                  {freeItems.map((it, j) => {
                    const fl = flavorsOf(it, flavorSets);
                    return (
                      <li key={j} className={`${sub} leading-snug text-slate-700 dark:text-slate-200`}>
                        <span>{it.text}</span>
                        {/* +0 標記：詳情才顯示灰字 */}
                        <span className="ml-1 font-semibold text-slate-400 dark:text-slate-500">
                          +$0
                        </span>
                        {fl && fl.length > 0 && (
                          <span className="ml-1 text-slate-400 dark:text-slate-500">
                            （{fl.map((f) => f.name + (f.priceAdd > 0 ? `+$${f.priceAdd}` : "")).join("/")}）
                          </span>
                        )}
                      </li>
                    );
                  })}
                </ul>
                {/* 加價區：詳情才顯示，+0 區下方細分隔 */}
                {paidItems.length > 0 && (
                  <>
                    <div className="mx-2 my-1.5 border-t border-slate-200 dark:border-slate-700" />
                    <ul className="ml-2 space-y-1 border-l border-slate-300 pl-3 dark:border-slate-600">
                      {paidItems.map((it, j) => {
                        const fl = flavorsOf(it, flavorSets);
                        return (
                          <li key={j} className={`${sub} leading-snug text-slate-700 dark:text-slate-200`}>
                            <span>{it.text}</span>
                            <span className="ml-1 font-semibold text-amber-600 dark:text-amber-400">
                              +${it.priceAdd}
                            </span>
                            {fl && fl.length > 0 && (
                              <span className="ml-1 text-slate-400 dark:text-slate-500">
                                （{fl.map((f) => f.name + (f.priceAdd > 0 ? `+$${f.priceAdd}` : "")).join("/")}）
                              </span>
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  </>
                )}
              </>
            )}
          </li>
        );
      })}
    </ul>
  );
}
