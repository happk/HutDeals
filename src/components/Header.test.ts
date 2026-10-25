import { describe, expect, it } from "vitest";
import { parseNotices } from "./Header";

describe("parseNotices 輕量語法（2026-10-26：h3＋無序列表＋段落）", () => {
  it("### 行 → h3 區塊（去除前綴）", () => {
    const [n] = parseNotices("## 2026-10-26\n### 搜尋升級\n內文");
    expect(n.blocks[0]).toEqual({ kind: "h3", text: "搜尋升級" });
  });

  it("- 與 * 開頭的連續行 → 同一個 ul 區塊（兩種符號可混用）", () => {
    const [n] = parseNotices("## 2026-10-26\n- 甲\n* 乙\n- 丙");
    expect(n.blocks).toEqual([{ kind: "ul", items: ["甲", "乙", "丙"] }]);
  });

  it("段落：連續非空行以換行合併（空白行不打斷），換行保留給 pre-line 渲染", () => {
    const [n] = parseNotices("## 2026-10-26\n第一行\n\n第二行");
    expect(n.blocks).toEqual([{ kind: "p", text: "第一行\n第二行" }]);
  });

  it("區塊交錯：段落→列表→h3→段落，flush 順序正確", () => {
    const [n] = parseNotices("## 2026-10-26\n段落A\n- 項1\n- 項2\n### 標題\n段落B");
    expect(n.blocks.map((b) => b.kind)).toEqual(["p", "ul", "h3", "p"]);
    expect(n.blocks[1]).toEqual({ kind: "ul", items: ["項1", "項2"] });
  });

  it("首個 ## 日期之前的行（檔頭說明）忽略；多則公告依序切分", () => {
    const list = parseNotices("# 標題\n> 說明\n## 2026-10-26\nA\n## 2026-09-08\nB");
    expect(list.map((n) => n.date)).toEqual(["2026-10-26", "2026-09-08"]);
    expect(list[0].blocks).toEqual([{ kind: "p", text: "A" }]);
  });

  it("列表項後接普通行：列表先收束，普通行另起段落", () => {
    const [n] = parseNotices("## 2026-10-26\n- 項\n尾段");
    expect(n.blocks.map((b) => b.kind)).toEqual(["ul", "p"]);
  });
});
