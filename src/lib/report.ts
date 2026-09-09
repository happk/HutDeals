import type { Coupon } from "../types";
import { formatUserTime } from "./format";

/** GitHub repo(owner/name);github.io 網域自動偵測,否則用 fallback(上線前確認)。 */
export function detectRepo(): string {
  const host = window.location.hostname;
  const m = host.match(/^([a-z0-9-]+)\.github\.io$/i);
  if (m) {
    const repo = window.location.pathname.split("/")[1];
    if (repo) return `${m[1]}/${repo}`;
  }
  return "OWNER/HutDeals";
}

export function buildIssueUrl(
  coupon: Coupon,
  repo: string,
  lastUpdate: string,
): string {
  const title = `[回報] ${coupon.name}`;
  const body = [
    "## 問題類型",
    "/(刪除未使用的選項)",
    "- [ ] 此優惠已在官網下架/失效",
    "- [ ] 名稱或內容描述錯誤",
    "- [ ] 價格錯誤",
    "- [ ] 其他(請說明)",
    "",
    "## 券資訊(系統自動帶入,請勿修改)",
    `- key: \`${coupon.key}\``,
    `- 代碼: ${coupon.code ?? "無"}`,
    `- 名稱: ${coupon.name}`,
    `- 資料更新時間: ${formatUserTime(lastUpdate)}（原始 ${lastUpdate}）`,
    "",
    "## 說明",
    "",
  ].join("\n");
  const params = new URLSearchParams({
    title,
    body,
    labels: "coupon-report",
  });
  return `https://github.com/${repo}/issues/new?${params.toString()}`;
}
