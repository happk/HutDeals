"""快照檢查（9f44bb9-1/2，2026-10-26）：scan.yml／update.yml 的熔斷日保全要素。

YAML 無單測，此腳本對 workflow 檔案做結構性斷言（regex、無外部依賴、可重跑）：
1. scan.yml 三個「Commit if changed」step 都有 if: !cancelled()
   （字面 always() 會連手動取消都提交——截斷檔風險，見 docs/todo-analysis）。
2. confirm/explore/sample 的 git add 都含 public/scan_alerts.json（熔斷日 admin 警報不停昨日）。
3. update.yml 的 commit step 也有 if: !cancelled()（同款缺口）。
4. 兩處告警 issue 文案不再宣稱與 !cancelled() 行為矛盾的內容。

用法：python exp_prob/2026-10-26_vuln-sweep/probe_wf_yaml.py
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def main() -> int:
    fails = []
    scan = (REPO / ".github/workflows/scan.yml").read_text(encoding="utf-8")
    update = (REPO / ".github/workflows/update.yml").read_text(encoding="utf-8")

    # 1. 三工 commit step＋sample 發布 step 的 !cancelled()
    n = scan.count("if: ${{ !cancelled() }}")
    if n != 4:
        fails.append(f"scan.yml 應有 4 個 step 帶 if: !cancelled()（三工 commit＋sample 發布），實得 {n}")
    if "always()" in scan or "always()" in update:
        fails.append("發現字面 always()——應改用 !cancelled()（手動取消不撿半成品）")
    nu = update.count("if: ${{ !cancelled() }}")
    if nu != 3:
        fails.append(f"update.yml 應有 3 個 step 帶 if: !cancelled()（sitemap＋發布＋commit），實得 {nu}")

    # 2. 三工 git add 都含 public/scan_alerts.json
    for job in ("confirm", "explore", "sample"):
        m = re.search(
            rf"JOB_NAME: {job}\n\s*run: \|\n(.*?)(?=\n  \w|\Z)", scan, re.S)
        if not m or "git add" not in m.group(1):
            fails.append(f"{job} 找不到 commit step run 區塊")
        elif not re.search(r"git add[^\n]*\n(?:[^\n]*\n)*?[^\n]*public/scan_alerts\.json",
                           m.group(1)) and "public/scan_alerts.json" not in m.group(1):
            fails.append(f"{job} 的 git add 未含 public/scan_alerts.json")

    # 3. update.yml commit step
    if "if: ${{ !cancelled() }}" not in update:
        fails.append("update.yml 的 Commit if changed 缺 if: !cancelled()")

    # 4. 告警文案不得再宣稱「已完成部分已由各 job 自行 commit」的絕對語
    for name, text in (("scan.yml", scan), ("update.yml", update)):
        if "已完成部分已由各 job 自行 commit" in text:
            fails.append(f"{name} 告警文案仍含舊的絕對語宣稱")

    if fails:
        print(f"FAIL（{len(fails)}）:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("PASS：scan.yml 三工 commit＋sample 發布＋update.yml 三 step 皆 !cancelled()；"
          "三工 git add 皆含 public/scan_alerts.json；告警文案如實")
    return 0


if __name__ == "__main__":
    sys.exit(main())
