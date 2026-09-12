/** 展示層格式化工具 */

/** 剝掉名稱開頭的優惠代碼前綴:「26976 新素幫你送」→「新素幫你送」。
 *  資料層 name 保留原樣,僅展示時套用;只剝「5位數字+分隔符」開頭,防誤傷。 */
export function displayName(name: string): string {
  return name.replace(/^\d{5}\s*[-－]?\s*/, "");
}

/** 資料時間 → 使用者本地時區顯示:「2026-09-10 04:33（UTC+8）」。
 *
 *  資料層 last_update 是 runner 寫的 UTC naive 字串（無時區後綴）→ 視為 UTC；
 *  若帶 offset（+08:00 / Z）則照 offset 解析。渲染目標是瀏覽器本地時區
 *  （整體平移後讀 UTC getters，不依賴 Intl 零件排序），偏移標籤由
 *  getTimezoneOffset 動態算出（半小時時區如 +5:30 也成立）。tzOffsetMin
 *  只給測試注入：「領先 UTC 的分鐘數」（台北=+480，紐約冬令=-300）。
 *  純日期（YYYY-MM-DD）無時刻可轉，原樣回傳；解析失敗亦回原字串。 */
export function formatUserTime(iso: string, tzOffsetMin?: number): string {
  // 不做「補 Z 當午夜」轉換：那會編造 08:00 這類假時刻，且 V8 與其他引擎行為不一致
  if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) return iso;
  const normalized = /[zZ]|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`;
  const d = new Date(normalized);
  if (Number.isNaN(d.getTime())) return iso;
  const offMin = tzOffsetMin ?? -d.getTimezoneOffset();
  const t = new Date(d.getTime() + offMin * 60_000);
  const p = (n: number) => String(n).padStart(2, "0");
  const sign = offMin < 0 ? "-" : "+";
  const abs = Math.abs(offMin);
  const label =
    `UTC${sign}${Math.floor(abs / 60)}` + (abs % 60 ? `:${p(abs % 60)}` : "");
  return (
    `${t.getUTCFullYear()}-${p(t.getUTCMonth() + 1)}-${p(t.getUTCDate())} ` +
    `${p(t.getUTCHours())}:${p(t.getUTCMinutes())}（${label}）`
  );
}
