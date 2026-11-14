r"""probe 2026-11-14：校驗複審速報（reports/審核速報_phase1-5_20261114.md）的宣稱。

複審宣稱：
    實質缺陷：gate 的 case 拼接（scan.yml:40）漏單邊空字串——OPEN="" OPEN2="0" 拼成 "0"
             過了整數檢查，[ "$OPEN" -gt 0 ] 在 if 條件內報 integer expression expected，
             set -e 對 if 條件不生效 → 判定為假 → 放行（fail-open）。同表 8 輸入 6/8。
    修法：改成兩個獨立 case（各一行）；RUNNING（L50）本來就是單變數，無此問題。
    其他：48/48 落點、熔斷入庫 8/8、⑥b 四序列、⑥a′ 白名單、⑧ 的 // empty 比計畫好、
         probe_phase15_verify 的唯一失敗是探針自己 rolls 期望值寫 2（實作=1 正確）。

探針（Git Bash 實跑 shell 語意＋源碼核對；零真實網路、零 gh 呼叫、repo 與 data/ 零寫入）：
    A gate 現行形狀（逐字取自 scan.yml L38-44）× 8 種輸入 → 與複審的 8 表比對
    B 修法形狀（兩個獨立 case）× 同 8 輸入 → 全部 fail-closed
    C RUNNING 單變數 case 的安全性（複審宣稱「無此問題」）
    D set -e 不作用於 if 條件的機制演示
    E 複審行號引用抽核（⑦b 順序／③a／⑧ // empty／④ coverage／白名單／MARK）
    F rolls 期望值爭議：重跑 test_fuse_after_fix 解析 F1-500 實際 rolls
    G 環境核對（review/phase1-5 五支、review/v6 六支、舊位置已清空）
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASH = r"C:\Program Files\Git\bin\bash.exe"

_results: list[tuple[str, bool]] = []


def note(label: str, ok: bool) -> None:
    _results.append((label, ok))
    print(f"  => {'[OK]' if ok else '[NG]'} {label}")


def run_sh(script: str, *args: str) -> tuple[int, str]:
    p = subprocess.run([BASH, "-ec", script, "gate", *args],
                       capture_output=True, text=True, timeout=30)
    return p.returncode, (p.stdout + p.stderr).replace("\n", " | ").strip()


# ============ A：gate 現行形狀 × 8 輸入（缺陷重現） ============
print("A. gate 現行形狀（逐字取自 scan.yml L38-44，gh 兩行以參數代替）× 8 輸入")
PROD = r'''
set -e
OPEN="$1"
OPEN2="$2"
case "$OPEN$OPEN2" in ""|*[!0-9]*) echo "GATE_FAIL"; exit 1;; esac
if [ "$OPEN" -gt 0 ] || [ "$OPEN2" -gt 0 ]; then
  echo "BLOCKED"
  exit 1
fi
echo "GATE_PASSED"
'''
# (OPEN, OPEN2, 期望結果, 期望 exit)：pass=放行 block=擋下 fail_closed=非整數擋下
CASES = [("0", "0", "GATE_PASSED", 0), ("1", "0", "BLOCKED", 1),
         ("0", "1", "BLOCKED", 1), ("", "0", "FAIL_CLOSED", 1),
         ("0", "", "FAIL_CLOSED", 1), ("", "", "FAIL_CLOSED", 1),
         ("abc", "0", "FAIL_CLOSED", 1), ("null", "0", "FAIL_CLOSED", 1)]
rows = []
for o1, o2, expect, code in CASES:
    rc, out = run_sh(PROD, o1, o2)
    actual = "FAIL_CLOSED" if (rc == 1 and "GATE_FAIL" in out) else \
        ("BLOCKED" if (rc == 1 and "BLOCKED" in out) else
         ("GATE_PASSED" if rc == 0 else f"OTHER({rc})"))
    verdict = "OK" if actual == expect else "DEFECT"
    rows.append((o1, o2, expect, actual, verdict, out[:60]))
    print(f"  OPEN={o1!r:6} OPEN2={o2!r:5} 期望={expect:11} 實測={actual:11} "
          f"{'✓' if verdict == 'OK' else '✗'}   [{out[:48]}]")
n_ok = sum(1 for r in rows if r[4] == "OK")
print(f"  現行形狀：{n_ok}/8 符合預期（複審宣稱 6/8）")
note("A 缺陷重現：OPEN=''/OPEN2='0' 與反序兩例放行（應 fail-closed）＝實質缺陷證實，"
     "其餘 6 例與複審 8 表逐格一致", n_ok == 6 and rows[3][4] == "DEFECT"
     and rows[4][4] == "DEFECT")

# ============ B：修法形狀 × 8 輸入 ============
print("\nB. 修法形狀（兩個獨立 case，複審建議）× 同 8 輸入")
FIXED = r'''
set -e
OPEN="$1"
OPEN2="$2"
case "$OPEN"  in ''|*[!0-9]*) echo "OPEN_NOT_INT"; exit 1;; esac
case "$OPEN2" in ''|*[!0-9]*) echo "OPEN2_NOT_INT"; exit 1;; esac
if [ "$OPEN" -gt 0 ] || [ "$OPEN2" -gt 0 ]; then
  echo "BLOCKED"
  exit 1
fi
echo "GATE_PASSED"
'''
fix_ok = 0
for o1, o2, expect, code in CASES:
    rc, out = run_sh(FIXED, o1, o2)
    if rc == 0:
        actual = "GATE_PASSED"
    elif "BLOCKED" in out:
        actual = "BLOCKED"          # 擋下也是正確出口（exit 1）
    elif "NOT_INT" in out:
        actual = "FAIL_CLOSED"
    else:
        actual = f"OTHER({rc})"
    ok = (actual == expect)
    fix_ok += ok
    print(f"  OPEN={o1!r:6} OPEN2={o2!r:5} 實測={actual:11} {'✓' if ok else '✗'}")
print(f"  修法形狀：{fix_ok}/8 全部符合預期")
note("B 修法驗證：兩個獨立 case 讓 8/8 全部落進正確出口（含單邊空字串 fail-closed）",
     fix_ok == 8)

# ============ C：RUNNING 單變數 case 安全性 ============
print("\nC. RUNNING 單變數 case（複審宣稱「無此問題」）")
RUN = r'''
set -e
RUNNING="$1"
case "$RUNNING" in ""|*[!0-9]*) echo "GATE_FAIL"; exit 1;; esac
if [ "$RUNNING" -gt 0 ]; then echo "YIELD"; exit 0; fi
echo "PROCEED"
'''
c_rc, c_out = run_sh(RUN, "")
a_rc, a_out = run_sh(RUN, "2")
note("C RUNNING 是單變數 case：空字串直接匹配 → fail-closed（複審宣稱證實）",
     c_rc == 1 and "GATE_FAIL" in c_out and a_rc == 0 and "YIELD" in a_out)

# ============ D：set -e 不作用於 if 條件（機制） ============
print("\nD. set -e 對 if 條件內的指令錯誤不生效（複審的機制解釋）")
rc, out = run_sh('set -e\nif [ "" -gt 0 ]; then echo THEN; else echo ELSE; fi\necho SURVIVED')
print(f"  rc={rc} out=[{out}]")
note("D 機制證實：[ '' -gt 0 ] 在 if 條件內報 integer expression expected 但不炸 step，"
     "判定為假走 ELSE——拼接漏空字串時確實會放行", rc == 0 and "ELSE" in out and "SURVIVED" in out)

# ============ E：行號引用抽核 ============
print("\nE. 複審行號引用抽核（⑦b 順序／③a／⑧／④／白名單／MARK）")
daily_src = (REPO / "script" / "scan" / "daily.py").read_text(encoding="utf-8")
order_src = (REPO / "script" / "lib" / "orderflow.py").read_text(encoding="utf-8")
scan_src = (REPO / ".github" / "workflows" / "scan.yml").read_text(encoding="utf-8")
# E1 ⑦b 順序：try step2_of → except blown/break → sleep_scan → bump/ABORT → continue → 歸零
alive = daily_src[daily_src.index("for i, code in enumerate(alive)"):
                  daily_src.index("for i, code in enumerate(dead)")]
i_try = alive.index("try:")
i_break = alive.index("blown = True")
i_sleep = alive.index("sleep_scan(i, alive)")
i_bump = alive.index("fail_streak = bump_parse_streak")
i_cont = alive.index("continue", i_bump)  # bump 之後的第一個 continue＝d-None 分支（迴圈開頭還有一個）
i_reset = alive.index("fail_streak = 0  # ⑥b：真成功歸零")
e1 = i_try < i_break < i_sleep < i_bump < i_cont < i_reset
print(f"  E1 alive 迴圈順序 try<break<sleep<bump<continue<歸零：{e1}")
note("E1 ⑦b 位置精確（複審『熔斷 break 在 sleep_scan 前、失敗 continue 在後』）", e1)
# E2 ③a
e2 = ("if isinstance(e, RuntimeError) and is_fuse_message(e):\n                raise"
      in order_src)
print(f"  E2 ③a 關鍵字直拋在重試 print 之前：{e2}")
note("E2 ③a 形狀核對（複審：關鍵字 calls=1、非關鍵字 calls=3——後者由 134 tests 涵蓋）", e2)
# E3 ⑧ // empty
e3 = "'.[0].number // empty'" in scan_src and 'gh issue comment "$ISSUE"' in scan_src
print(f"  E3 ⑧ 用 // empty＋gh issue comment：{e3}")
note("E3 ⑧ 比計畫原案多 // empty（複審讚證實——空清單 jq 印 null 的縫已補）", e3)
# E4 ④ coverage 兩處
e4 = ("git diff --quiet -- data/scan_state.json data/scan_coverage.json" in scan_src
      and "git add data/scan_state.json data/scan_coverage.json" in scan_src)
print(f"  E4 ④ confirm commit 的 diff 檢查與 git add 都含 coverage：{e4}")
note("E4 ④ coverage 進 confirm commit（複審：三工一致）", e4)
# E5 白名單＋MARK＋bump
e5 = ('ITEMS_NONE_WHITELIST = frozenset({"93015", "15596", "16348"})' in order_src
      and 'MARK_GARBAGE_PAGE = "疑似垃圾頁"' in order_src
      and "PARSE_FAIL_MARKS" in order_src
      and "rec.get(\"step2_error\") in PARSE_FAIL_MARKS" in order_src)
print(f"  E5 白名單三碼／MARK 常數／bump 用 frozenset 成員判定：{e5}")
note("E5 ⑥a′ 白名單與 ⑥b 雙標記定義核對（複審 orderflow.py:70-78/81 引用屬實）", e5)

# ============ F：rolls 期望值爭議 ============
print("\nF. probe_phase15_verify 唯一失敗項（4.500）＝探針期望值寫錯（實作 rolls=1 正確）")
p = subprocess.run([sys.executable, "-I", str(BASE / "test_fuse_after_fix.py")],
                   capture_output=True, text=True, timeout=60)
out = p.stdout + p.stderr
f500 = "F1-500 重配不回歸 : PASS" in out and "rolls=1" in out
print(f"  F1-500：{'PASS（rolls=1）' if f500 else '異常'}")
note("F 重跑 test_fuse_after_fix：500 走重配一次（rolls=1）即正確行為——複審對探針"
     "期望值錯誤（寫 2）的歸責成立，實作無缺陷", f500)

# ============ G：環境核對 ============
print("\nG. 環境核對（review 兩層資料夾）")
p15 = sorted(f.name for f in (BASE / "review" / "phase1-5").glob("*.py"))
v6 = sorted(f.name for f in (BASE / "review" / "v6").glob("*.py"))
old_gone = not (BASE / "review" / "probe_v6_verify.py").exists()
print(f"  review/phase1-5：{len(p15)} 支 {p15}")
print(f"  review/v6：{len(v6)} 支；舊 review/ 根的六支已移除：{old_gone}")
note("G 兩層資料夾與複審附錄一致（phase1-5 五支、v6 六支、舊位置清空）",
     len(p15) == 5 and len(v6) == 6 and old_gone)

# ============ 總判定 ============
print("\n=== 總判定 ===")
for label, ok in _results:
    print(f"  {'[OK]' if ok else '[NG]'} {label}")
fails = [l for l, ok in _results if not ok]
print(f"\n  {len(_results) - len(fails)}/{len(_results)} 項通過"
      + ("；全部與校驗預期一致" if not fails else f"；異常項：{fails}"))
