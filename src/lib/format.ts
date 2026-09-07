/** 展示層格式化工具 */

/** 剝掉名稱開頭的優惠代碼前綴:「26976 新素幫你送」→「新素幫你送」。
 *  資料層 name 保留原樣,僅展示時套用;只剝「5位數字+分隔符」開頭,防誤傷。 */
export function displayName(name: string): string {
  return name.replace(/^\d{5}\s*[-－]?\s*/, "");
}
