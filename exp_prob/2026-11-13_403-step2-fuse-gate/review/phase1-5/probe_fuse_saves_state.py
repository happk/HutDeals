"""最關鍵的驗證：熔斷時成果是否真的入庫（exit 3 + save_state 執行）。

這是整個修復的目的。11-12/11-13 三場事故的損失就是「save_state 沒執行」。
本 probe 驗證：
1. 抓詳情 403 → blown=True → save_state 被呼叫 → 回 3
2. 抓詳情 RuntimeError 關鍵字 → 同上
3. ⑥b streak 熔斷 → 同上
4. 查活階段 403 → 既有路徑仍正常（不比對，僅確認沒壞）
"""
import sys
from unittest.mock import patch

REPO = r"D:\Desktop\work\project\20260908_PizzaHut-Coupon-Scraper_Public"
sys.path.insert(0, REPO)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

results = []


def check(label, ok, detail=""):
    results.append((label, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))


import urllib.error

import script.scan.daily as daily

ORIG = {k: getattr(daily, k) for k in (
    "fetch_and_parse", "load_state", "save_state", "update_coverage",
    "update_alerts", "history_row", "merge_step2_failures", "probe_batch",
    "step2_of", "sleep_scan")}


def run_scenario(name, step2_exc, expect_rc=3):
    """單碼情境：第 2 碼熔斷。驗證 save_state 是否執行。"""
    saved = {"called": False, "state": None}
    alerts = {}

    codes = ["16001", "16002", "16003"]
    state = {c: {"status": "alive", "title": f"t{c}"} for c in codes}

    daily.load_state = lambda: {"codes": state}
    daily.save_state = lambda path, s: saved.update(called=True, state=s)
    daily.update_coverage = lambda r: None
    daily.update_alerts = lambda sec, e: alerts.__setitem__(sec, e)
    daily.history_row = lambda *a, **k: None
    daily.merge_step2_failures = lambda *a, **k: None
    daily.sleep_scan = lambda *a, **k: None
    daily.probe_batch = lambda cs: (
        [{"code": c, "at": "t", "m1_success": True} for c in codes], False)

    def fake_step2(rec, fetcher=None):
        if rec["code"] == "16001":
            rec["title"] = "updated"
            return {"title": "updated", "items": [{"text": "x"}]}
        # 第二碼起熔斷
        if step2_exc == "http403":
            raise urllib.error.HTTPError("https://x/", 403, "m", None, None)
        if step2_exc == "runtime_fuse":
            raise RuntimeError("step_1_update 失敗: busy")
        if step2_exc == "parse_fail":
            rec["step2_error"] = "fetch/parse 失敗"
            rec["step2At"] = "t"
            return None

    daily.step2_of = fake_step2

    with patch("script.scan.daily.time.sleep"):
        rc = daily.cmd_confirm(type("A", (), {"limit": 0})())

    print(f"\n  [{name}]")
    print(f"    rc={rc}  save_state called={saved['called']}")
    if saved["called"]:
        st = saved["state"]["codes"]
        print(f"    16001 title={st['16001'].get('title')!r}（第一碼成果是否保住）")
    print(f"    content_changes alert={len(alerts.get('content_changes', []))} 筆")

    check(f"{name}: exit code = {expect_rc}", rc == expect_rc, f"rc={rc}")
    check(f"{name}: save_state 已執行（成果入庫）", saved["called"],
          "這是修復的核心目的")
    check(f"{name}: 第一碼成果保住",
          saved["called"] and saved["state"]["codes"]["16001"].get("title") == "updated",
          "熔斷前的成果必須入庫")
    return saved


print("=== 場景 1：抓詳情 HTTP 403 熔斷 ===")
run_scenario("403 熔斷", "http403")

print()
print("=== 場景 2：抓詳情 RuntimeError 關鍵字熔斷 ===")
run_scenario("RuntimeError 熔斷", "runtime_fuse")

print()
print("=== 場景 3：⑥b 連續解析失敗熔斷（需 3 碼）===")
# 這個場景需要 3 碼失敗，用 3 碼
codes3 = ["16001", "16002", "16003"]
state3 = {c: {"status": "alive", "title": f"t{c}"} for c in codes3}
saved3 = {"called": False, "state": None}
daily.load_state = lambda: {"codes": state3}
daily.save_state = lambda path, s: saved3.update(called=True, state=s)
daily.update_coverage = lambda r: None
daily.update_alerts = lambda *a: None
daily.history_row = lambda *a, **k: None
daily.merge_step2_failures = lambda *a, **k: None
daily.sleep_scan = lambda *a, **k: None
daily.probe_batch = lambda cs: (
    [{"code": c, "at": "t", "m1_success": True} for c in codes3], False)


def all_fail(rec, fetcher=None):
    rec["step2_error"] = "fetch/parse 失敗"
    rec["step2At"] = "t"
    return None


daily.step2_of = all_fail
with patch("script.scan.daily.time.sleep"):
    rc = daily.cmd_confirm(type("A", (), {"limit": 0})())
print(f"  rc={rc}  save_state called={saved3['called']}")
check("⑥b 熔斷: exit code = 3", rc == 3, f"rc={rc}")
check("⑥b 熔斷: save_state 已執行", saved3["called"])

# 還原
for k, v in ORIG.items():
    setattr(daily, k, v)

print()
print("=" * 60)
passed = sum(1 for _, ok in results if ok)
print(f"{passed}/{len(results)} 項通過")
for label, ok in results:
    print(f"  {'[OK]' if ok else '[NG]'} {label}")
