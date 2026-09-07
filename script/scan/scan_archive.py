"""HutDeals scan — 自動歸檔（scan_run 完成後寫掃號紀錄）。

由 scan_run.main() 成功寫完 scan_state 後呼叫（CI scan.yml 每週），自動：
1. `reports/scan-records/scan-history.md`「執行批次」表加一列（時間/腳本/候選數/alive/dead/範圍/附註）。
2. `reports/scan-records/coverage-map.md`「自動掃描回報」區塊更新為本輪逐段 alive/dead 摘要
   （marker 區塊整段取代，避免無限增長）。

設計紅線：
- 只寫「自動區」；不碰人工維護的登錄表 / 區段地圖 / 結論 → 格式對不上就跳過不 crash。
- 缺檔 / 格式異常 → 印 warning 後 return False，不影響 scan_run 退出碼（掃描資料已寫好）。
- 一律 newline='\\n' 寫回，避免 Windows CRLF 造成整檔 churn。

用法（scan_run 內部）:
    from script.scan.scan_archive import archive_scan_run
    archive_scan_run(scanned, codes)
"""
import datetime as dt
import re
from pathlib import Path

from script.lib.repo import REPO

# 公開版：掃號紀錄寫 data/scan-records/(隨 scan.yml commit+push，供除錯追蹤)
RECORDS_DIR = REPO / "data" / "scan-records"
HISTORY_PATH = RECORDS_DIR / "scan-history.md"
COVERAGE_PATH = RECORDS_DIR / "coverage-map.md"

# coverage-map 自動區 marker（整段取代）
COV_START = "<!-- auto-scan-start -->"
COV_END = "<!-- auto-scan-end -->"


def _read_lines(path: Path) -> list[str] | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").split("\n")


def _write_lines(path: Path, lines: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))


def _cell(text: str) -> str:
    """表格儲存格：None → 空、其餘照 str（含 0）；| 換成全形 ／。"""
    if text is None:
        return ""
    return str(text).replace("|", "／").strip()


def append_history_row(fields: dict, path: Path = HISTORY_PATH) -> bool:
    """在 scan-history.md 的「執行批次」表尾加一列。回是否真的寫入。"""
    lines = _read_lines(path)
    if lines is None:
        print("WARN: 缺 scan-history.md，略過歸檔", file=__import__("sys").stderr)
        return False
    # 找執行批次表：標題列之後，插到表的最後一列後（批次表時間序、新的在尾）
    head = next((i for i, ln in enumerate(lines) if ln.startswith("| 時間 |")), None)
    if head is None:
        print("WARN: scan-history.md 找不到「執行批次」表，略過", file=__import__("sys").stderr)
        return False
    j = head + 1
    while j < len(lines) and re.fullmatch(r"\|[\s:\-|]+\|?", lines[j]):
        j += 1  # 跳過 separator
    # 從 j 往後走過所有「表格列」（以 | 開頭且含 |…| 結尾）到第一個非列
    while j < len(lines) and lines[j].startswith("|") and "|" in lines[j][1:]:
        j += 1
    row = (
        f"| {_cell(fields.get('time'))} | {_cell(fields.get('source'))} "
        f"| {_cell(fields.get('count'))} | {_cell(fields.get('alive'))} "
        f"| {_cell(fields.get('dead'))} | {_cell(fields.get('scope'))} "
        f"| {_cell(fields.get('note'))} |"
    )
    lines.insert(j, row)
    _write_lines(path, lines)
    return True


def _segment_scope(codes: list[str]) -> str:
    """codes → 範圍欄：『16xxx×20、26xxx×10』（依前2碼計數、排序）。"""
    from collections import Counter
    cnt = Counter(c[:2] for c in codes)
    return "、".join(f"{k}xxx×{v}" for k, v in sorted(cnt.items()))


def update_coverage(block_text: str, path: Path = COVERAGE_PATH) -> bool:
    """把 coverage-map 的 marker 區塊換成 block_text（無 marker 則檔尾新增）。"""
    lines = _read_lines(path)
    if lines is None:
        print("WARN: 缺 coverage-map.md，略過歸檔", file=__import__("sys").stderr)
        return False
    block = [COV_START, *block_text.split("\n"), COV_END]
    start = next((i for i, ln in enumerate(lines) if ln.strip() == COV_START), None)
    if start is not None:
        end = next((i for i in range(start, len(lines))
                    if lines[i].strip() == COV_END), None)
        if end is None:
            return False
        if lines[start:end + 1] == block:
            return False  # 內容沒變，不 rewrite（避免每輪 churn）
        lines[start:end + 1] = block
    else:
        # 檔尾追加（前留一空行）
        if lines and lines[-1] != "":
            lines.append("")
        lines.extend(block)
        lines.append("")
    _write_lines(path, lines)
    return True


def archive_scan_run(scanned: list[dict], codes: list[str],
                     source: str = "scan_run.py") -> dict:
    """scan_run 成功後呼叫：回 {history: bool, coverage: bool}。全部容錯。"""
    alive = sum(1 for r in scanned if r.get("status") == "alive")
    dead = sum(1 for r in scanned if r.get("status") == "dead")
    unknown = sum(1 for r in scanned if r.get("status") == "unknown")
    now = dt.datetime.now()
    partners = sorted({r.get("partner") for r in scanned
                       if r.get("status") == "alive" and r.get("partner")})
    note = ("、".join(partners) if partners
            else (f"unknown {unknown}" if unknown else "—"))
    fields = {
        "time": now.strftime("%m-%d %H:%M"),
        "source": source,
        "count": len(scanned),
        "alive": alive,
        "dead": dead if dead else 0,
        "scope": _segment_scope(codes or [r.get("code", "") for r in scanned]),
        "note": note,
    }
    hist = append_history_row(fields)
    cov = update_coverage(
        f"## 自動掃描回報（scan_run hook 更新，勿手改）\n\n"
        f"- {now.strftime('%Y-%m-%d %H:%M')}（{source}）: "
        f"掃 {len(scanned)} 碼 alive {alive} / dead {dead}"
        f"{f' / unknown {unknown}' if unknown else ''}"
        f" ｜ 逐段 {fields['scope']}"
        + (f" ｜ 聯名 {note}" if note != "—" else ""),
    )
    return {"history": hist, "coverage": cov}


if __name__ == "__main__":
    # 手動測試：無引數時對真實檔跑一次（示範用）
    print(archive_scan_run(
        [{"code": "26975", "status": "alive", "partner": "素易"},
         {"code": "26976", "status": "alive", "partner": "素易"},
         {"code": "15140", "status": "dead"}],
        ["26975", "26976", "15140"]))
