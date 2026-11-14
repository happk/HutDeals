"""v6 落點總表 vs 實際 diff 的逐項對照。

v6 修改點總表列了 20 餘個落點，本 probe 逐項確認實作是否一致。
"""
import re
import subprocess
import sys

REPO = r"D:\Desktop\work\project\20260908_PizzaHut-Coupon-Scraper_Public"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

results = []


def check(label, ok, detail=""):
    results.append((label, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))


def read(path):
    return open(f"{REPO}\\{path}", encoding="utf-8").read()


# ---------- orderflow.py ----------
print("=== orderflow.py ===")
of = read("script\\lib\\orderflow.py")

checks_of = [
    ("FUSE_KEYWORDS 定義", "FUSE_KEYWORDS = " in of),
    ("is_fuse_message 函式", "def is_fuse_message(" in of),
    ("PARSE_FAIL_MARKS frozenset", "PARSE_FAIL_MARKS = frozenset(" in of),
    ("FUSE_PARSE_STREAK = 3（獨立常數）", "FUSE_PARSE_STREAK = 3" in of),
    ("bump_parse_streak 函式", "def bump_parse_streak(" in of),
    ("ITEMS_NONE_WHITELIST", "ITEMS_NONE_WHITELIST = frozenset(" in of),
    ("模組函式 is_menu_page", "def is_menu_page(html: str) -> bool:" in of),
    ("原方法版 is_menu_page 已移除", "    def is_menu_page(self" not in of),
    ("③a: RuntimeError 關鍵字 raise", "if isinstance(e, RuntimeError) and is_fuse_message(e):" in of),
    ("⑥a: parsed is None or not is_menu_page", "if parsed is None or not is_menu_page(html):" in of),
    ("①: 403/429 直拋", "if isinstance(e, urllib.error.HTTPError) and is_rate_limited(e):" in of),
    ("⑥a log 分三種原因", "非選單版/忙碌頁" in of and "空回應" in of and "變體" in of),
]
for label, ok in checks_of:
    check(label, ok)

# ---------- daily.py ----------
print()
print("=== daily.py ===")
dy = read("script\\scan\\daily.py")
checks_dy = [
    ("import time", "import time" in dy),
    ("import is_fuse_message", "is_fuse_message" in dy),
    ("import bump_parse_streak", "bump_parse_streak" in dy),
    ("import ITEMS_NONE_WHITELIST", "ITEMS_NONE_WHITELIST" in dy),
    ("③b: step2_of 放行關鍵字", "if isinstance(err, RuntimeError) and is_fuse_message(err):" in dy),
    ("⑥a′: 垃圾頁判定", "ITEMS_NONE_WHITELIST" in dy and "MARK_GARBAGE_PAGE" in dy),
    ("MARK_PARSE_FAIL 取代字面值", "MARK_PARSE_FAIL" in dy and dy.count('"fetch/parse 失敗"') == 0),
    ("⑦c: time.sleep(45)", "time.sleep(45)" in dy),
    ("⑦b alive: enumerate + sleep_scan", "for i, code in enumerate(alive)" in dy),
    ("⑦b dead: enumerate + sleep_scan", "for i, code in enumerate(dead)" in dy),
    ("⑦b explore: enumerate", "for i, r in enumerate(fresh)" in dy),
    ("⑦b sample: enumerate", "for i, r in enumerate(hits)" in dy),
    ("explore 字串清單", 'codes_fresh = [r["code"] for r in fresh]' in dy),
    ("sample 字串清單", 'codes_hits = [r["code"] for r in hits]' in dy),
    ("③c alive try/except", dy.count("except (urllib.error.HTTPError, RuntimeError) as e:") == 4),
    ("dead 迴圈 if not blown 防護", "if not blown:" in dy),
    ("⑥b streak 四處", dy.count("fail_streak = bump_parse_streak") == 4),
    ("⑥b 熔斷訊息", dy.count("ABORT: 連續 {fail_streak} 碼解析失敗") == 4),
]
for label, ok in checks_dy:
    check(label, ok)

# ---------- enrich_official.py ----------
print()
print("=== enrich_official.py ===")
en = read("script\\site\\enrich_official.py")
checks_en = [
    ("import is_fuse_message", "is_fuse_message" in en),
    ("import PARSE_FAIL_MARKS 相關標記", "MARK_GARBAGE_PAGE" in en and "MARK_PARSE_FAIL" in en),
    ("③c: 關鍵字熔斷出口", "if isinstance(err, RuntimeError) and is_fuse_message(err):" in en),
    ("⑥a′: items is None 判定", 'if r is None or r.get("items") is None:' in en),
    ("⑥b: enrich streak", "bump_parse_streak" in en),
    ("⑥b: 熔斷訊息", "ABORT: 連續 {fail_streak} 碼解析失敗" in en),
]
for label, ok in checks_en:
    check(label, ok)

# ---------- scan.yml ----------
print()
print("=== scan.yml ===")
yml = read(".github\\workflows\\scan.yml")
checks_yml = [
    ("⑤ GH_REPO env", "GH_REPO: ${{ github.repository }}" in yml),
    ("⑤ 移除三處吞錯", yml.count("2>/dev/null || echo 0") == 0),
    ("⑤ 整數驗證（OPEN）", 'case "$OPEN$OPEN2" in ""|*[!0-9]*)' in yml),
    ("⑤ 整數驗證（RUNNING）", 'case "$RUNNING" in ""|*[!0-9]*)' in yml),
    ("④ confirm commit 加 coverage", "data/scan_state.json data/scan_coverage.json" in yml),
    ("⑧ ISSUE 取 number", ".[0].number // empty" in yml),
    ("⑧ comment 分支", 'gh issue comment "$ISSUE"' in yml),
]
for label, ok in checks_yml:
    check(label, ok)

# ---------- pacing.py ----------
print()
print("=== pacing.py ===")
pc = read("script\\lib\\pacing.py")
checks_pc = [
    ("DEFAULT_SLEEP = 1.0", "DEFAULT_SLEEP = 1.0" in pc),
    ("DEFAULT_SEG_GAP = 0.0", "DEFAULT_SEG_GAP = 0.0" in pc),
    ("seg_gap 參數保留", "seg_gap: float = DEFAULT_SEG_GAP" in pc),
    ("docstring 記策略變更", "2026-11-14 節流統一" in pc),
]
for label, ok in checks_pc:
    check(label, ok)

# ---------- docs/workflow.md ----------
print()
print("=== docs/workflow.md ===")
wf = read("docs\\workflow.md")
check("⑦ 節流政策行已改寫", "2026-11-14" in wf or "base 1" in wf or "1s" in wf)
print("  現行節流段落：")
for i, l in enumerate(wf.splitlines()):
    if "請求節奏" in l:
        for j in range(i, min(i + 6, len(wf.splitlines()))):
            print(f"    {wf.splitlines()[j][:80]}")
        break

print()
print("=" * 60)
passed = sum(1 for _, ok in results if ok)
print(f"{passed}/{len(results)} 項通過")
fails = [l for l, ok in results if not ok]
if fails:
    print("未通過：")
    for f in fails:
        print(f"  - {f}")
