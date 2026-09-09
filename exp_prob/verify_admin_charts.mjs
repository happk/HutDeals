// 唯讀驗證：用 jsdom 實際跑 public/admin.html，檢查圖表是否畫出來。
// 用法：node exp_prob/verify_admin_charts.mjs
import fs from "node:fs";
import { JSDOM } from "jsdom";

const html = fs.readFileSync("public/admin.html", "utf8");
const full = fs.readFileSync("public/coupons_full.js", "utf8");

const dom = new JSDOM(html, {
  runScripts: "dangerously",
  url: "https://example.test/admin.html",
  beforeParse(window) {
    window.eval(full); // 模擬 <script src="coupons_full.js">
    window.fetch = () => Promise.reject(new Error("offline"));
  },
});

const doc = dom.window.document;
const q = (sel) => doc.querySelectorAll(sel);

for (const id of ["chart-scatter", "chart-hist", "chart-donut", "chart-intake"]) {
  const svg = doc.getElementById(id);
  console.log(
    `${id}: 存在=${!!svg} circles=${svg ? svg.querySelectorAll("circle").length : "-"} ` +
      `rects=${svg ? svg.querySelectorAll("rect").length : "-"} texts=${svg ? svg.querySelectorAll("text").length : "-"}`,
  );
}

const intake = doc.getElementById("chart-intake");
const dotLabels = [...intake.querySelectorAll("text.ct-bar-val")].map((t) => t.textContent);
const titles = [...intake.querySelectorAll("circle title")].map((t) => t.textContent);
console.log("\n入庫趨勢點上的數值標籤:", dotLabels);
console.log("入庫趨勢 hover 文案:", titles);
console.log("統計卡:", [...doc.querySelectorAll("#stat-cards .stat")].map((d) => d.textContent).join(" | "));
