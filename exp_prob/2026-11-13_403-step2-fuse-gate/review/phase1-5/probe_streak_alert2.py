"""⑥b streak 與 ⑧ alert 的行為驗證（修正版：mock time.sleep 避開 ⑦c 的 45s）。

同時驗證一個實作問題：⑦c 的 time.sleep(45) 硬編碼在 cmd_confirm 內，
測試無法繞過——現有 test_step2_fuse.py 是否有處理？
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


import script.scan.daily as daily

ORIG = {
    "fetch_and_parse": daily.fetch_and_parse,
    "load_state": daily.load_state,
    "save_state": daily.save_state,
    "update_coverage": daily.update_coverage,
    "update_alerts": daily.update_alerts,
    "history_row": daily.history_row,
    "merge_step2_failures": daily.merge_step2_failures,
    "probe_batch": daily.probe_batch,
    "step2_of": daily.step2_of,
    "sleep_scan": daily.sleep_scan,
}


def run_confirm(codes, outcomes):
    state = {c: {"status": "alive", "title": f"t{c}"} for c in codes}
    daily.load_state = lambda: {"codes": state}
    daily.save_state = lambda *a, **k: None
    daily.update_coverage = lambda r: None
    daily.update_alerts = lambda *a: None
    daily.history_row = lambda *a, **k: None
    daily.merge_step2_failures = lambda *a, **k: None
    daily.sleep_scan = lambda *a, **k: None          # ⑦b 不真睡
    daily.probe_batch = lambda cs: (
        [{"code": c, "at": "t", "m1_success": True} for c in codes], False)

    def fake(rec, fetcher=None):
        kind = outcomes.get(rec["code"], "ok")
        if kind == "ok":
            return {"title": "new", "items": [{"text": "x"}]}
        if kind == "garbage":
            rec["step2_error"] = "疑似垃圾頁"
        else:
            rec["step2_error"] = "fetch/parse 失敗"
        rec["step2At"] = "t"
        return None

    daily.step2_of = fake
    with patch("script.scan.daily.time.sleep"):       # ⑦c 的 45s
        return daily.cmd_confirm(type("A", (), {"limit": 0})())


print("=== 1. ⑥b 連續 3 碼解析失敗 → 熔斷 ===")
rc = run_confirm(["A1", "A2", "A3", "A4"], {"A1": "fail", "A2": "fail", "A3": "fail"})
print(f"  rc={rc}（期望 3）")
check("1a 連續 3 碼失敗 → exit 3", rc == 3, f"rc={rc}")

print()
print("=== 2. 2 失敗 + 1 成功 → 歸零，不熔斷 ===")
rc = run_confirm(["B1", "B2", "B3"], {"B1": "fail", "B2": "fail", "B3": "ok"})
print(f"  rc={rc}（期望 0）")
check("2a 失敗被成功打斷 → 不熔斷", rc == 0, f"rc={rc}")

print()
print("=== 3. 垃圾頁也計數（雙標記）===")
rc = run_confirm(["C1", "C2", "C3"], {"C1": "garbage", "C2": "garbage", "C3": "garbage"})
print(f"  rc={rc}（期望 3）")
check("3a 連續 3 碼垃圾頁 → exit 3", rc == 3, f"rc={rc}")

print()
print("=== 4. 混合形態（失敗+垃圾頁+失敗）===")
rc = run_confirm(["D1", "D2", "D3"], {"D1": "fail", "D2": "garbage", "D3": "fail"})
print(f"  rc={rc}（期望 3）")
check("4a 混合標記也累計 streak", rc == 3, f"rc={rc}")

# 還原
for k, v in ORIG.items():
    setattr(daily, k, v)

print()
print("=== 5. ⑧ ISSUE 取值語法 ===")
src = open(f"{REPO}\\.github\\workflows\\scan.yml", encoding="utf-8").read()
check("5a ⑧ 有空清單保護（// empty）", "// empty" in src)
check("5b ⑧ 有 comment 分支", 'gh issue comment "$ISSUE"' in src)
check("5c ⑧ 有 create 分支（空 ISSUE 時）", 'if [ -z "$ISSUE" ]' in src)

print()
print("=== 6. ⑦c 的 time.sleep(45) 對測試的影響 ===")
test_src = open(f"{REPO}\\script\\support\\tests\\test_step2_fuse.py", encoding="utf-8").read()
has_sleep_mock = "time.sleep" in test_src or "sleep" in test_src
print(f"  test_step2_fuse.py 是否 mock time.sleep: {'time.sleep' in test_src}")
print(f"  是否 mock daily.sleep_scan: {'daily.sleep_scan' in test_src}")
print()
# 找出測試怎麼處理 45s
import re
sleep_lines = [l.strip() for l in test_src.splitlines()
               if "sleep" in l.lower()]
for l in sleep_lines[:12]:
    print(f"    {l[:90]}")

check("6a 測試有處理 ⑦c 的 45s（否則每個 cmd_confirm 測試卡 45 秒）",
      "time.sleep" in test_src,
      "見上方實際 mock 行")

print()
print("=" * 60)
passed = sum(1 for _, ok in results if ok)
print(f"{passed}/{len(results)} 項通過")
for label, ok in results:
    print(f"  {'[OK]' if ok else '[NG]'} {label}")
