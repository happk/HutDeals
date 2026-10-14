// 唯讀：用「已部署的 coupons.js」模擬前端 filterCoupons（includeTags=["飲料"]），
// 確認 16166 是否應該出現。
// 用法：node exp_prob/check_deployed_filter.mjs /tmp/hutdeals_deployed_coupons.js
import fs from "node:fs";

const path = process.argv[2] || "/tmp/hutdeals_deployed_coupons.js";
const src = fs.readFileSync(path, "utf8");
const window = {};
// eslint-disable-next-line no-eval
eval(src);
const data = window.HUTDEALS_COUPONS;
const list = data.coupon_list;

console.log("部署資料:", data.count, "券 | last_update:", data.last_update);

// 前端 filterCoupons 的核心條件（src/lib/filter.ts）
const state = {
  q: "",
  includeTags: ["飲料"],
  excludeTags: [],
  orderType: null,
  priceMin: null,
  priceMax: null,
  favOnly: false,
};

const visible = list.filter((c) => {
  if (c.status !== "active") return false;
  if (state.favOnly) return false;
  if (state.orderType && !(c.orderType || "").includes(state.orderType)) return false;
  if (state.includeTags.length > 0 && !state.includeTags.some((t) => c.tags.includes(t)))
    return false;
  if (state.excludeTags.some((t) => c.tags.includes(t))) return false;
  return true;
});

console.log('includeTags=["飲料"] → 命中', visible.length, "筆");
console.log("16166 在其中:", visible.some((c) => c.code === "16166"));

const c = list.find((x) => x.code === "16166");
console.log("16166 status:", c?.status, "| tags:", c?.tags, "| orderType:", c?.orderType);
console.log("16166 在全部 active 中:", list.filter((x) => x.status === "active").some((x) => x.code === "16166"));
console.log("有『飲料』tag 的 active 券:", list.filter((x) => x.status === "active" && x.tags.includes("飲料")).length);
