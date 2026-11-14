"""Phase 5 的 gate fail-closed 實測——case "$OPEN$OPEN2" 拼接的邊界。

關鍵懷疑：OPEN="" 但 OPEN2="0" 時，拼接成 "0" 不匹配 *[!0-9]*，
然後 `[ "$OPEN" -gt 0 ]` 報 integer expression expected（在 if 內不觸發 set -e）
→ 判假 → 落到 else → 放行。
"""
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASH = r"C:\Program Files\Git\bin\bash.exe"
results = []


def check(label, ok, detail=""):
    results.append((label, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))


SCRIPT = r"""
set -e
OPEN="%(open)s"
OPEN2="%(open2)s"
case "$OPEN$OPEN2" in
  ""|*[!0-9]*) echo "GATE_FAIL"; exit 1;;
esac
if [ "$OPEN" -gt 0 ] || [ "$OPEN2" -gt 0 ]; then
  echo "GATE_BLOCKED"
  exit 1
fi
echo "GATE_PASSED"
"""

cases = [
    ("0", "0", "正常無 issue"),
    ("1", "0", "1 個 scan-failed"),
    ("0", "1", "1 個 scrape-failed"),
    ("", "0", "OPEN 空、OPEN2=0（jq 異常）"),
    ("0", "", "OPEN=0、OPEN2 空（jq 異常）"),
    ("", "", "兩者都空"),
    ("abc", "0", "非整數"),
    ("null", "0", "jq 印 null"),
]

print("=== gate fail-closed 的邊界實測 ===")
for o1, o2, desc in cases:
    script = SCRIPT % {"open": o1, "open2": o2}
    proc = subprocess.run([BASH, "-c", script], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    out = (proc.stdout + proc.stderr).strip().replace("\n", " | ")
    print(f"  OPEN={o1!r:8} OPEN2={o2!r:8} → exit={proc.returncode} out={out[:60]}")

print()
# 判定：任何「非 0」或「異常輸入」都應該 GATE_FAIL 或 GATE_BLOCKED
def verdict(o1, o2):
    script = SCRIPT % {"open": o1, "open2": o2}
    proc = subprocess.run([BASH, "-c", script], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return proc.returncode, proc.stdout.strip()


for o1, o2, desc in cases:
    rc, out = verdict(o1, o2)
    if (o1, o2) == ("0", "0"):
        check(f"{desc}: 應放行", out == "GATE_PASSED", out)
    elif (o1, o2) in (("1", "0"), ("0", "1")):
        check(f"{desc}: 應擋下", out == "GATE_BLOCKED", out)
    else:
        # 異常輸入：應 GATE_FAIL（fail-closed）
        ok = out == "GATE_FAIL"
        check(f"{desc}: 應 fail-closed", ok, f"實際={out or '(無輸出)'} exit={rc}")

print()
print("=" * 60)
passed = sum(1 for _, ok in results if ok)
print(f"{passed}/{len(results)} 項通過")
for label, ok in results:
    print(f"  {'[OK]' if ok else '[NG]'} {label}")
