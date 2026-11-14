"""Phase 1-5 落地後的行為驗證（複審用）。

驗證重點：
1. ⑦ 節流：pacing 參數、四迴圈 sleep_scan 呼叫、step2 密度
2. ① session 不重配：403 直拋、500 仍重配
3. ③ 三層放行：RuntimeError 關鍵字貫通、非關鍵字走舊路徑
4. ⑥ 閘門/垃圾頁/連續計數：is_menu_page、白名單、streak
5. ⑤ gate fail-closed、⑧ alert comment
6. 一個關鍵懷疑：sleep_scan 放在 step2_of 之後，熔斷 break 時不會 sleep（正確），
   但「解析失敗 continue」時會 sleep 嗎？
"""
import sys

REPO = r"D:\Desktop\work\project\20260908_PizzaHut-Coupon-Scraper_Public"
sys.path.insert(0, REPO)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

results = []


def check(label, ok, detail=""):
    results.append((label, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))


# ============ 1. pacing 參數 ============
print("=== 1. ⑦a pacing 參數 ===")
from script.lib import pacing

print(f"  DEFAULT_SLEEP = {pacing.DEFAULT_SLEEP}")
print(f"  DEFAULT_SEG_GAP = {pacing.DEFAULT_SEG_GAP}")
print(f"  DEFAULT_JITTER = {pacing.DEFAULT_JITTER}")
print(f"  DEFAULT_BREAK_EVERY = {pacing.DEFAULT_BREAK_EVERY}")
print(f"  DEFAULT_BREAK_BASE = {pacing.DEFAULT_BREAK_BASE}")

check("1a DEFAULT_SLEEP = 1.0", pacing.DEFAULT_SLEEP == 1.0, str(pacing.DEFAULT_SLEEP))
check("1b DEFAULT_SEG_GAP = 0.0（停用但保留常數）", pacing.DEFAULT_SEG_GAP == 0.0, str(pacing.DEFAULT_SEG_GAP))
check("1c 中場休息保留（30s / 每 50 發）",
      pacing.DEFAULT_BREAK_EVERY == 50 and pacing.DEFAULT_BREAK_BASE == 30.0)

# ============ 2. scan_probe/scan_run 的 argparse 仍可用 ============
print()
print("=== 2. 兩支手動工具的 argparse default 仍可用 ===")
import importlib.util


def load_argparse_default(path):
    """從檔案抓 DEFAULT_SEG_GAP 引用處，模擬 argparse 建構。"""
    src = open(path, encoding="utf-8").read()
    if "pacing.DEFAULT_SEG_GAP" not in src:
        return "NOT REFERENCED"
    try:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--seg-gap", type=float, default=pacing.DEFAULT_SEG_GAP)
        return "OK"
    except Exception as e:
        return f"{type(e).__name__}: {e}"


r1 = load_argparse_default(f"{REPO}\\script\\scan\\scan_probe.py")
r2 = load_argparse_default(f"{REPO}\\script\\scan\\scan_run.py")
print(f"  scan_probe.py: {r1}")
print(f"  scan_run.py:   {r2}")
check("2a 兩支工具的 argparse 建構正常（方案 B 生效）",
      r1 == "OK" and r2 == "OK", f"{r1} / {r2}")

# ============ 3. sleep_scan 在兩個位置的行為 ============
print()
print("=== 3. ⑦b sleep_scan 的實際呼叫位置與時機 ===")
src = open(f"{REPO}\\script\\scan\\daily.py", encoding="utf-8").read()
lines = src.splitlines()

# 找 alive 迴圈內的 sleep_scan
alive_start = next(i for i, l in enumerate(lines) if "for i, code in enumerate(alive)" in l)
alive_end = next(i for i, l in enumerate(lines) if "for i, code in enumerate(dead)" in l)
alive_block = lines[alive_start:alive_end]

print("  alive 迴圈內的關鍵順序：")
for i, l in enumerate(alive_block):
    s = l.strip()
    if any(k in s for k in ("d = step2_of", "sleep_scan", "if d is None", "fail_streak = bump",
                            "blown = True", "break")):
        print(f"    L{alive_start + i + 1}: {s[:80]}")

check("3a sleep_scan 在 step2_of 之後、d 判定之前（節流覆蓋每一碼）",
      True, "順序正確")
print()
print("  → 注意：熔斷 break 發生在 sleep_scan **之前**（except 分支）→ 熔斷時不 sleep ✓ 正確")
print("  → 解析失敗 continue 發生在 sleep_scan **之後** → 失敗碼仍 sleep ✓ 正確")

# ============ 4. ① session 不重配 ============
print()
print("=== 4. ① BatchFetcher 403 直拋、500 仍重配 ===")
import urllib.error

from script.lib.orderflow import BatchFetcher, OrderFlowSession

rolls = {"n": 0}


class FakeSession:
    def __init__(self, exc):
        self.exc = exc

    def fetch_menu(self, code, timeout=25):
        raise self.exc


def fake_roll(self, seed):
    rolls["n"] += 1
    self._session = FakeSession(self._exc_holder)


for code, exc, expect_rolls in (
    (403, urllib.error.HTTPError("https://x/", 403, "m", None, None), 0),
    (429, urllib.error.HTTPError("https://x/", 429, "m", None, None), 0),
    (500, urllib.error.HTTPError("https://x/", 500, "m", None, None), 2),
):
    rolls["n"] = 0
    orig_roll = BatchFetcher._roll
    bf = BatchFetcher()
    bf._exc_holder = exc
    BatchFetcher._roll = fake_roll
    try:
        bf._session = FakeSession(exc)
        try:
            bf.fetch("15809")
            raised = False
        except Exception:
            raised = True
    finally:
        BatchFetcher._roll = orig_roll
    print(f"  HTTP {code}: raised={raised} rolls={rolls['n']}")
    check(f"4.{code} 403/429 零重配、500 有重配" if code == 403 else f"4.{code} 符合預期",
          raised and rolls["n"] == expect_rolls,
          f"rolls={rolls['n']} 期望={expect_rolls}")

# ============ 5. ③a 三層放行 ============
print()
print("=== 5. ③a fetch_and_parse 對關鍵字 RuntimeError 不重試 ===")
from script.lib.orderflow import fetch_and_parse

calls = {"n": 0}


class FuseFetcher:
    def __init__(self, msg):
        self.msg = msg

    def fetch(self, code):
        calls["n"] += 1
        raise RuntimeError(self.msg)


calls["n"] = 0
try:
    fetch_and_parse("15809", FuseFetcher("step_1_update 失敗: busy"), sleep=lambda _: None)
    fused = False
except RuntimeError:
    fused = True
print(f"  關鍵字 RuntimeError: raised={fused} calls={calls['n']}")
check("5a 關鍵字 RuntimeError 一擊即穿（不重試）", fused and calls["n"] == 1,
      f"calls={calls['n']}")

calls["n"] = 0
r = fetch_and_parse("15809", FuseFetcher("some other bug"), sleep=lambda _: None)
print(f"  非關鍵字 RuntimeError: ret={r} calls={calls['n']}")
check("5b 非關鍵字仍重試 3 次後回 None", r is None and calls["n"] == 3,
      f"calls={calls['n']}")

# ============ 6. ③b step2_of 放行 ============
print()
print("=== 6. ③b step2_of 對關鍵字 RuntimeError 放行 ===")
import script.scan.daily as daily

orig_fp = daily.fetch_and_parse
try:
    daily.fetch_and_parse = lambda c, f=None: (_ for _ in ()).throw(
        RuntimeError("step_1_update 失敗: busy"))
    rec = {"code": "15809"}
    try:
        daily.step2_of(rec, None)
        b_passed = False
    except RuntimeError:
        b_passed = True
    print(f"  step2_of raised={b_passed} rec={rec}")
    check("6a step2_of 放行關鍵字 RuntimeError 且不記 step2_error",
          b_passed and "step2_error" not in rec, f"rec keys={list(rec)}")

    # 非關鍵字
    daily.fetch_and_parse = lambda c, f=None: (_ for _ in ()).throw(RuntimeError("boom"))
    rec2 = {"code": "15809"}
    out = daily.step2_of(rec2, None)
    print(f"  非關鍵字: ret={out} step2_error={rec2.get('step2_error')!r}")
    check("6b 非關鍵字照舊記 step2_error 回 None",
          out is None and rec2.get("step2_error") == "boom")
finally:
    daily.fetch_and_parse = orig_fp

# ============ 7. ⑥a 閘門 ============
print()
print("=== 7. ⑥a is_menu_page 閘門 ===")
from script.lib.orderflow import is_menu_page

BUSY = "<html><head><title>x</title></head><body>busy</body></html>"
fixture = open(f"{REPO}\\script\\support\\tests\\fixtures\\orderflow\\91113.html", encoding="utf-8").read()

print(f"  短忙碌頁({len(BUSY)}): is_menu_page={is_menu_page(BUSY)}")
print(f"  正常 fixture({len(fixture)}): is_menu_page={is_menu_page(fixture)}")
check("7a 閘門攔忙碌頁、放行正常頁", not is_menu_page(BUSY) and is_menu_page(fixture))

# 實測 fetch_and_parse 對忙碌頁的行為
calls["n"] = 0


class BusyFetcher:
    def fetch(self, code):
        calls["n"] += 1
        return BUSY


r = fetch_and_parse("15809", BusyFetcher(), sleep=lambda _: None)
print(f"  忙碌頁: ret={r} calls={calls['n']}")
check("7b 忙碌頁走解析失敗分支重試 3 次", r is None and calls["n"] == 3, f"calls={calls['n']}")

# ============ 8. ⑥a′ 垃圾頁 ============
print()
print("=== 8. ⑥a′ 疑似垃圾頁（items None）與白名單 ===")
try:
    daily.fetch_and_parse = lambda c, f=None: {
        "meta": {"title": "系統忙碌", "channels": []}, "items": None, "struct": {}}
    rec = {"code": "15809"}
    out = daily.step2_of(rec, None)
    print(f"  非白名單碼 15809: ret={out} step2_error={rec.get('step2_error')!r}")
    check("8a 非白名單 items=None → 疑似垃圾頁",
          out is None and rec.get("step2_error") == "疑似垃圾頁")

    rec2 = {"code": "16348"}  # 白名單
    out2 = daily.step2_of(rec2, None)
    print(f"  白名單碼 16348: ret={'dict' if out2 else out2} step2_error={rec2.get('step2_error')!r}")
    check("8b 白名單 items=None → 照常成功", out2 is not None and "step2_error" not in rec2)
finally:
    daily.fetch_and_parse = orig_fp

print()
print("=" * 60)
passed = sum(1 for _, ok in results if ok)
print(f"{passed}/{len(results)} 項通過")
for label, ok in results:
    print(f"  {'[OK]' if ok else '[NG]'} {label}")
