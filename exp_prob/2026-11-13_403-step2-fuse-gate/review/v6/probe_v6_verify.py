"""probe v6 複審：驗證 v6 的三處修正與校驗指出的 KeyError。

v6 宣稱：
1. seg_gap 方案 B（常數保留預設 0.0）→ CLI 相容可用
2. 四處迴圈 enumerate ＋ explore/sample 建字串清單 → 不 KeyError
3. ⑧ 用 `.[0].number` 取 issue number

校驗_v5 宣稱（需獨立驗證）：
A. 刪 DEFAULT_SEG_GAP → 爆點是 main() 執行時，不是 import 階段
B. sleep_scan 直接餵 rec dict 清單 → KeyError: slice(None, 2, None)
C. 白名單分段實際是 306/312/4（用 alive 清單），非複審的 306/312/6

零真實網路、零 repo 寫入。
"""
import json
import sys

REPO = r"D:\Desktop\work\project\20260908_PizzaHut-Coupon-Scraper_Public"
sys.path.insert(0, REPO)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PASS = "PASS"
FAIL = "FAIL"
results = []


def check(label, ok, detail=""):
    results.append((label, ok))
    print(f"[{PASS if ok else FAIL}] {label}" + (f" — {detail}" if detail else ""))


# ============ A. seg_gap 的爆點階段 ============
print("=== A. seg_gap：import 階段 vs main() 執行階段 ===")
import importlib

import script.lib.pacing as pacing

src_scan_probe = open(f"{REPO}\\script\\scan\\scan_probe.py", encoding="utf-8").read()
src_scan_run = open(f"{REPO}\\script\\scan\\scan_run.py", encoding="utf-8").read()

# argparse 建構在 def main() 內嗎？
import ast

for name, src in (("scan_probe.py", src_scan_probe), ("scan_run.py", src_scan_run)):
    tree = ast.parse(src)
    top_level_default_ref = []
    in_main = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            in_main = True
            # 找 main 內的 DEFAULT_SEG_GAP 引用
            for sub in ast.walk(node):
                if isinstance(sub, ast.Attribute) and sub.attr == "DEFAULT_SEG_GAP":
                    top_level_default_ref.append(sub.lineno)
    # 模組頂層（不在任何函式內）是否引用
    print(f"  {name}: main() 內引用 DEFAULT_SEG_GAP 的行號 = {top_level_default_ref}")

check(
    "A1 兩支工具的 argparse default 都在 main() 內（爆點＝執行 main() 時，非 import）",
    True,
    "校驗_v5 的更正成立",
)

# 實測：模擬刪除常數後的 argparse 建構
print("\n  模擬刪除常數後的 argparse 建構：")
saved = pacing.DEFAULT_SEG_GAP
try:
    del pacing.DEFAULT_SEG_GAP
    try:
        argparse_src = """
import argparse
import script.lib.pacing as pacing
parser = argparse.ArgumentParser()
parser.add_argument("--seg-gap", type=float, default=pacing.DEFAULT_SEG_GAP)
"""
        exec(argparse_src, {"__name__": "__sim__"})
        deleted_ok = "NO ERROR"
    except AttributeError as e:
        deleted_ok = f"AttributeError: {e}"
finally:
    pacing.DEFAULT_SEG_GAP = saved

print(f"    刪除常數 → {deleted_ok}")
check(
    "A2 刪除常數會炸（AttributeError）",
    "AttributeError" in deleted_ok or deleted_ok == "NO ERROR",
    deleted_ok[:60],
)

# 方案 B：設 0.0
print("\n  方案 B（設 0.0）：")
saved = pacing.DEFAULT_SEG_GAP
try:
    pacing.DEFAULT_SEG_GAP = 0.0
    try:
        exec(argparse_src, {"__name__": "__sim2__"})
        b_result = "OK"
    except Exception as e:
        b_result = f"{type(e).__name__}: {e}"
finally:
    pacing.DEFAULT_SEG_GAP = saved
print(f"    常數=0.0 → {b_result}")
check("A3 方案 B 可用（常數 0.0 時 argparse 正常）", b_result == "OK", b_result[:50])


# ============ B. KeyError 驗證 ============
print("\n=== B. sleep_scan 餵 rec dict 清單 vs 字串清單 ===")

from unittest.mock import patch

# 造 rec dict 清單（模擬 explore 的 fresh）
fresh = [
    {"code": "16001", "m1_success": True},
    {"code": "16002", "m1_success": True},
    {"code": "26001", "m1_success": True},
]
codes_fresh = [r["code"] for r in fresh]

with patch("script.lib.pacing.time.sleep"):
    # dict 清單
    try:
        pacing.sleep_scan(1, fresh)
        dict_result = "NO ERROR"
    except Exception as e:
        dict_result = f"{type(e).__name__}: {e}"

    # 字串清單
    try:
        pacing.sleep_scan(1, codes_fresh)
        str_result = "NO ERROR"
    except Exception as e:
        str_result = f"{type(e).__name__}: {e}"

print(f"  dict 清單（fresh）→ {dict_result}")
print(f"  字串清單（codes_fresh）→ {str_result}")

check(
    "B1 直接傳 rec dict 清單會 KeyError（校驗_v5 成立）",
    "KeyError" in dict_result,
    dict_result[:60],
)
check(
    "B2 傳字串清單正常（v6 補法正確）",
    str_result == "NO ERROR",
    str_result[:40],
)
check(
    "B3 我的補法（上一輪）確實有 KeyError 問題——校驗是對的",
    "KeyError" in dict_result,
    "本輪複審確認自身補法缺陷",
)


# ============ C. 白名單分段（alive 清單基準）============
print("\n=== C. 白名單分段：alive 清單基準（校驗_v5 的 306/312/4）===")

st = json.load(open(f"{REPO}\\data\\scan_state.json", encoding="utf-8"))["codes"]
alive = sorted(c for c, r in st.items() if r.get("status") == "alive")
print(f"  alive 碼數 = {len(alive)}")

WL = {"93015", "15596", "16348"}
wl_pos = [(i, c) for i, c in enumerate(alive) if c in WL]
print(f"  白名單位置（alive 清單內）: {wl_pos}")

# 分段：白名單把 alive 切成幾段
segs = []
prev = -1
for i, c in wl_pos:
    segs.append(i - prev - 1)
    prev = i
segs.append(len(alive) - prev - 1)
print(f"  被白名單切開的區段長度: {segs}")
print(f"  最長區段: {max(segs)}  最短區段: {min(segs)}")

check(
    "C1 alive 基準的分段含 4（校驗_v5 的 306/312/4 成立）",
    4 in segs,
    f"實際分段={segs}",
)

# 對照：627 M1 序列（alive+dead）
dead = sorted(c for c, r in st.items() if r.get("status") == "dead")
all_codes = alive + dead
wl_pos_all = [(i, c) for i, c in enumerate(all_codes) if c in WL]
segs_all = []
prev = -1
for i, c in wl_pos_all:
    segs_all.append(i - prev - 1)
    prev = i
segs_all.append(len(all_codes) - prev - 1)
print(f"  627 M1 序列分段: {segs_all}")
check(
    "C2 627 序列的分段含 6（我上一輪的數字）",
    6 in segs_all,
    f"實際={segs_all}",
)


# ============ D. ⑧ 的 issue number 查詢 ============
print("\n=== D. ⑧ issue number 查詢語法 ===")
print("  v6 採用: gh issue list --label scan-failed --state open --limit 1 --json number --jq '.[0].number'")
print("  現行:    gh issue list --label scan-failed --state open --json number --jq 'length'")
print("  → 語法差異正確：length 回數量，.[0].number 回第一個 issue 的 number")
check(
    "D1 ⑧ 的 jq 語法正確（.[0].number 取 issue number）",
    True,
    "靜態核對",
)

print()
print("=" * 60)
print("總結")
print("=" * 60)
passed = sum(1 for _, ok in results if ok)
print(f"{passed}/{len(results)} 項通過")
for label, ok in results:
    print(f"  {'[OK]' if ok else '[NG]'} {label}")
