import { describe, expect, it } from "vitest";
import { displayName, formatUserTime } from "./format";

describe("displayName", () => {
  it("strips leading 5-digit code prefix", () => {
    expect(displayName("26976 新素幫你送")).toBe("新素幫你送");
  });

  it("leaves names without code prefix alone", () => {
    expect(displayName("大比薩送副食")).toBe("大比薩送副食");
  });
});

describe("formatUserTime", () => {
  // runner 寫的 UTC naive 字串 → 台北(+480)跨日
  it("treats naive strings as UTC and shifts to viewer zone", () => {
    expect(formatUserTime("2026-09-09T20:33:27", 480)).toBe(
      "2026-09-10 04:33（UTC+8）",
    );
  });

  // 同一瞬間，紐約冬令(-300)看到當地換算＋當地偏移
  it("labels the viewer zone offset, not a fixed one", () => {
    expect(formatUserTime("2026-09-09T20:33:27", -300)).toBe(
      "2026-09-09 15:33（UTC-5）",
    );
  });

  // 半小時時區
  it("handles half-hour offsets", () => {
    expect(formatUserTime("2026-09-09T20:33:27", 330)).toBe(
      "2026-09-10 02:03（UTC+5:30）",
    );
  });

  // 已帶 offset 的輸入照 offset 解析
  it("respects explicit offsets in input", () => {
    expect(formatUserTime("2026-09-10T04:33:27+08:00", 480)).toBe(
      "2026-09-10 04:33（UTC+8）",
    );
    expect(formatUserTime("2026-09-09T20:33:27Z", 480)).toBe(
      "2026-09-10 04:33（UTC+8）",
    );
  });

  // 非跨日時段
  it("formats non-midnight-crossing times", () => {
    expect(formatUserTime("2026-09-03T08:00:00", 480)).toBe(
      "2026-09-03 16:00（UTC+8）",
    );
  });

  it("returns the original string when unparsable", () => {
    expect(formatUserTime("not-a-time")).toBe("not-a-time");
  });
});
