"""HutDeals lib — data/scan_state.json 讀寫 + scan_alerts.json 失敗合併。

原散落：scan_run.load_state/save_state、ig_ingest.load_state → 統一收此。
2026-09-08 加 alerts 合併：step2 靜默失敗改寫入可見（admin 頁 step2_failures 區）。
"""
import datetime as dt
import json
from pathlib import Path

__all__ = ["load_state", "save_state", "STATE_PATH",
           "ALERTS_PATH", "STEP2F_SECTION", "merge_step2_failures"]

from script.lib.repo import REPO  # noqa: E402

STATE_PATH = REPO / "data" / "scan_state.json"
ALERTS_PATH = REPO / "data" / "scan_alerts.json"
STEP2F_SECTION = "step2_failures"


def load_state(path: Path = STATE_PATH) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {"updatedAt": None, "codes": {}}


def save_state(path: Path, state: dict) -> None:
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def merge_step2_failures(new_failures: list[dict], clear_codes=(),
                         path: Path = ALERTS_PATH) -> list[dict]:
    """step2 失敗合併進 alerts（admin 可見；取代靜默 SKIP）。

    新失敗 upsert（同 code 覆寫）、clear_codes 的移除（補抓成功，或該碼已非 alive
    不會再自動重試——死碼殘留不該誤導）；回傳全區列表（依 code 排序）。
    entry 形：{code, title?, error, at}。損壞/缺檔從 {} 起算，不 throw。
    """
    try:
        alerts = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except json.JSONDecodeError:
        alerts = {}
    if not isinstance(alerts, dict):
        alerts = {}
    cur = {e.get("code"): e for e in alerts.get(STEP2F_SECTION, [])
           if isinstance(e, dict) and e.get("code")}
    for e in new_failures:
        if isinstance(e, dict) and e.get("code"):
            cur[e["code"]] = e
    for c in clear_codes:
        cur.pop(c, None)
    merged = [cur[k] for k in sorted(cur)]
    alerts[STEP2F_SECTION] = merged
    alerts["updatedAt"] = dt.datetime.now().isoformat(timespec="seconds")
    path.write_text(json.dumps(alerts, ensure_ascii=False, indent=1), encoding="utf-8")
    return merged
