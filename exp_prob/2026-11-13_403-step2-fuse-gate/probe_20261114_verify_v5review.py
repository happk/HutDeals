r"""probe 2026-11-14：校驗第五輪複審速報（reports/驗收速報_v5_20261114.md）的宣稱。

複審宣稱：
    阻斷一：移除 DEFAULT_SEG_GAP 會炸兩支手動工具（argparse default 引用）；「import 階段就 AttributeError」。
    阻斷二：四處迴圈都要 enumerate 但 1.2 只標 alive；sleep_scan 第二參數 explore 傳 fresh、sample 傳 hits。
    次要一：白名單碼會把 streak 歸零；白名單增長切割名單可讓 ⑥b 失效（實測三段 306/312/6）。
    次要二：⑧ 需要 issue number 而非 COUNT。次要三：⑦c 未寫 enrich 適用性。次要四：test_pacing 用 patch。
    節流驗算：現行 39.7 分/0.263、v5 27.8 分/0.376、倍率 1.42；seg 邊界 6 個。

探針（記憶體模擬＋state 唯讀＋源碼核對；零真實網路、repo 與 data/ 零寫入）：
    A 阻斷一：argparse 引用 DEFAULT_SEG_GAP 的炸點機制（刪屬性→AttributeError；設 0.0→正常）＋「import vs main()」核對
    B 阻斷二：四處迴圈無 enumerate（源碼核對）＋fresh/hits 是 rec dict 清單——sleep_scan 直接傳會 TypeError（複審補法的漏洞）
    C 次要一：白名單三碼在 alive 清單的位置與分段（⑥b 基準＝alive-only；M1 627 序列對照）
    D 節流驗算：627 碼真實順序 × 200 seed 模擬（現行 vs v5 參數）＋seg 邊界清單
    E 靜態核對：1.2 只標 alive／1.4 措辭／scan.yml 313-321 只有 COUNT／測試不 import 兩支手動工具
"""
import argparse
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import script.lib.pacing as pacing                     # noqa: E402
from script.scan import daily                          # noqa: E402

ORIG_SEG_GAP = pacing.DEFAULT_SEG_GAP
_results: list[tuple[str, bool]] = []


def note(label: str, ok: bool) -> None:
    _results.append((label, ok))
    print(f"  => {'[OK]' if ok else '[NG]'} {label}")


# ============ A：阻斷一——DEFAULT_SEG_GAP 的炸點 ============
print("A. 阻斷一：移除 DEFAULT_SEG_GAP 的實際爆點")
probe_src = (REPO / "script" / "scan" / "scan_probe.py").read_text(encoding="utf-8").splitlines()
run_src = (REPO / "script" / "scan" / "scan_run.py").read_text(encoding="utf-8").splitlines()
ref_probe = [i + 1 for i, l in enumerate(probe_src) if "pacing.DEFAULT_SEG_GAP" in l]
ref_run = [i + 1 for i, l in enumerate(run_src) if "pacing.DEFAULT_SEG_GAP" in l]
main_probe = next(i + 1 for i, l in enumerate(probe_src) if l.startswith("def main()"))
main_run = next(i + 1 for i, l in enumerate(run_src) if l.startswith("def main()"))
print(f"  引用位置：scan_probe {ref_probe}（def main() 在 L{main_probe}）、"
      f"scan_run {ref_run}（def main() 在 L{main_run}）")
inside_main = all(r > m for r, m in
                  [(ref_probe[0], main_probe), (ref_run[0], main_run)])
print(f"  兩處都在 main() 內（非模組層）: {inside_main}")

del pacing.DEFAULT_SEG_GAP
crash = "無"
try:  # 模擬 argparse 建構（兩支工具 main() 內的同一行）
    p = argparse.ArgumentParser()
    p.add_argument("--seg-gap", type=float, default=pacing.DEFAULT_SEG_GAP)
except AttributeError as e:
    crash = f"AttributeError: {e}"
finally:
    pacing.DEFAULT_SEG_GAP = 0.0
ok_zero = "無"
try:
    p2 = argparse.ArgumentParser()
    p2.add_argument("--seg-gap", type=float, default=pacing.DEFAULT_SEG_GAP)
except Exception as e:
    ok_zero = f"{type(e).__name__}: {e}"
pacing.DEFAULT_SEG_GAP = ORIG_SEG_GAP
print(f"  刪除常數後 argparse 建構: {crash}")
print(f"  設 0.0（複審方案 B）後 argparse 建構: {ok_zero}")
note("A 阻斷一成立：刪常數→AttributeError、方案 B（0.0）可用——但爆點是 main() 執行時而非 import 階段",
     crash.startswith("AttributeError") and ok_zero == "無" and inside_main)

# ============ B：阻斷二——四處迴圈 enumerate＋fresh/hits 是 dict 清單 ============
print("\nB. 阻斷二：四處迴圈的 enumerate 需求＋sleep_scan 第二參數型別")
daily_src = (REPO / "script" / "scan" / "daily.py").read_text(encoding="utf-8").splitlines()
loops = {}
for i, l in enumerate(daily_src):
    s = l.strip()
    if s.startswith("for code in alive:") or s.startswith("for code in dead:") \
            or s.startswith("for r in fresh:") or s.startswith("for r in hits:"):
        loops[s] = i + 1
for s, ln in sorted(loops.items(), key=lambda kv: kv[1]):
    print(f"  L{ln}: {s}  （無 enumerate: {'enumerate' not in s}）")
note("B1 複審宣稱證實：四處迴圈頭皆無 enumerate（178/229 與 explore/sample 實際在 324/365）",
     len(loops) == 4 and all("enumerate" not in s for s in loops))

fresh_like = [{"code": "16001", "m1_success": True},
              {"code": "16002", "m1_success": True},
              {"code": "16003", "m1_success": True}]  # 3 筆：避開末碼早退，切片才會執行
err_dict = "無"
try:  # 複審補法：explore 傳 fresh（rec dict 清單）；參數歸零避免真睡，切片在 sleep 之前執行
    pacing.sleep_scan(1, fresh_like, sleep=0, jitter=0, seg_gap=0, break_every=0)
except (TypeError, KeyError) as e:  # dict[:2] 是以 slice 物件當 key 查找 → KeyError
    err_dict = f"{type(e).__name__}: {e}"
str_list = [r["code"] for r in fresh_like]
err_str = "無"
try:  # 修正後：字串清單
    pacing.sleep_scan(1, str_list, sleep=0, jitter=0, seg_gap=0, break_every=0)
except Exception as e:
    err_str = f"{type(e).__name__}: {e}"
print(f"  sleep_scan(1, fresh)（dict 清單）: {err_dict}")
print(f"  sleep_scan(1, [code strings])   : {err_str}")
note("B2 我方更正複審補法：fresh/hits 是 rec dict 清單，直接傳會 KeyError（d[:2]＝以 slice 當 key 查找）——須先建字串清單",
     err_dict.startswith("KeyError") and err_str == "無")

# ============ C：次要一——白名單位置與分段 ============
print("\nC. 白名單三碼的位置與分段（state 唯讀）")
state = json.loads((REPO / "data" / "scan_state.json").read_text(encoding="utf-8"))
codes_state = state.get("codes", {})
alive = sorted(c for c, rr in codes_state.items() if rr.get("status") == "alive")
WL = {"93015", "15596", "16348"}
pos = {c: alive.index(c) for c in WL if c in alive}
print(f"  alive={len(alive)} 白名單位置: "
      + "、".join(f"{c}@{pos[c]}" for c in sorted(pos, key=pos.get)))
segs_alive, run_len = [], 0
for i, c in enumerate(alive):
    if c in WL:
        if run_len:
            segs_alive.append(run_len)
        run_len = 0
    else:
        run_len += 1
if run_len:
    segs_alive.append(run_len)
seq627 = alive + sorted(c for c, rr in codes_state.items() if rr.get("status") == "dead")
segs_627, run_len = [], 0
for i, c in enumerate(seq627):
    if c in WL:
        if run_len:
            segs_627.append(run_len)
        run_len = 0
    else:
        run_len += 1
if run_len:
    segs_627.append(run_len)
print(f"  ⑥b 基準（alive-only，dead 碼不打 step2）分段={segs_alive} 最短={min(segs_alive)}")
print(f"  複審的基準（627 M1 序列）分段={segs_627} 最短={min(segs_627)}")
note("C 次要一成立但數字更正：三碼位置吻合；⑥b 基準下第三段=4 碼（複審用 627 序列得 6）——結論不變、餘裕更薄",
     pos.get("15596") == 0 and min(segs_alive) >= 3 and min(segs_alive) < min(segs_627))

# ============ D：節流驗算（627 碼 × 200 seed） ============
print("\nD. 節流驗算（複審宣稱：現行 39.7 分/0.263、v5 27.8 分/0.376、倍率 1.42）")
print(f"  掃號序列={len(seq627)} 碼（alive {len(alive)} + dead {len(seq627) - len(alive)}）")
bounds = [i for i in range(1, len(seq627))
          if seq627[i][:2] != seq627[i - 1][:2]]
print(f"  seg 邊界數={len(bounds)} 位置={bounds}（複審宣稱 6 個：2/463/615/617/622/625）")


def simulate(base: float, seg_gap: float, seeds: int = 200) -> float:
    total = 0.0
    n = len(seq627)
    for seed in range(seeds):
        rng = random.Random(seed)
        t = 0.0
        for i in range(n):
            if i >= n - 1:
                break                       # sleep_scan L28：尾碼不睡
            t += base + rng.uniform(0, 2.0)
            if i > 0 and seg_gap and seq627[i][:2] != seq627[i - 1][:2]:
                t += seg_gap * rng.uniform(0.5, 1.5)
            if (i + 1) % 50 == 0:
                t += 30 * rng.uniform(0.8, 1.5)
        total += t
    return total / seeds


cur = simulate(2.0, 15.0)
new = simulate(1.0, 0.0)
print(f"  現行（base2.0＋seg15）: {cur / 60:.1f} 分、{len(seq627) / cur:.3f} 發/秒")
print(f"  v5（base1.0＋無seg）  : {new / 60:.1f} 分、{len(seq627) / new:.3f} 發/秒")
print(f"  倍率={cur / new:.2f}")
note("D 節流驗算重現：39.7/27.8 分、0.263/0.376 發/秒、倍率 ~1.42 逐項吻合",
     abs(cur / 60 - 39.7) < 0.5 and abs(new / 60 - 27.8) < 0.5 and 1.40 < cur / new < 1.45
     and len(bounds) == 6)

# ============ E：靜態核對 ============
print("\nE. 靜態核對")
exp = Path(__file__).resolve().parent
method = (exp / "reports" / "修復方法_20261113.md").read_text(encoding="utf-8")
l12 = [l for l in method.splitlines() if "四個抓詳情迴圈補" in l and "enumerate" in l]
print(f"  修復方法 1.2: {l12[0].strip()[:64] if l12 else 'NOT FOUND'}")
only_alive = bool(l12) and l12[0].count("enumerate") == 1 and "alive" in l12[0]
note("E 阻斷二敘述面證實：1.2 只標了 alive 的 enumerate，其餘三處未標", only_alive)

l14 = [l for l in method.splitlines() if "test_pacing" in l and "time.sleep" in l]
print(f"  修復方法 1.4: {l14[0].strip()[:64] if l14 else 'NOT FOUND'}（未指定 patch 方式——次要四成立）")
note("E 次要四成立：1.4 未寫 patch 自動還原方式", bool(l14) and "patch" not in l14[0])

yml = (REPO / ".github" / "workflows" / "scan.yml").read_text(encoding="utf-8").splitlines()
seg = "\n".join(yml[312:321])
has_count = "jq 'length'" in seg and "already exists" in seg
has_number = ".[0].number" in seg
print(f"  scan.yml 313-321: COUNT（length）={has_count} issue number 查詢={has_number}")
note("E 次要二成立：else 分支只有 COUNT、無 issue number 可供 comment", has_count and not has_number)

tests_dir = REPO / "script" / "support" / "tests"
imports_tools = [p.name for p in tests_dir.glob("test_*.py")
                 if "scan_probe" in p.read_text(encoding="utf-8")
                 or "scan_run" in p.read_text(encoding="utf-8")]
print(f"  測試檔 import scan_probe/scan_run: {imports_tools or '無'}")
note("E 阻斷一前提證實：測試不 import 兩支手動工具——CI 抓不到壞", not imports_tools)

# ============ 總判定 ============
print("\n=== 總判定 ===")
for label, ok in _results:
    print(f"  {'[OK]' if ok else '[NG]'} {label}")
fails = [l for l, ok in _results if not ok]
print(f"\n  {len(_results) - len(fails)}/{len(_results)} 項通過"
      + ("；全部與校驗預期一致" if not fails else f"；異常項：{fails}"))
