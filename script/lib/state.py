"""HutDeals lib — data/scan_state.json 讀寫。

原散落：scan_run.load_state/save_state、ig_ingest.load_state → 統一收此。
"""
import json
from pathlib import Path

__all__ = ["load_state", "save_state", "STATE_PATH"]

from script.lib.repo import REPO  # noqa: E402

STATE_PATH = REPO / "data" / "scan_state.json"


def load_state(path: Path = STATE_PATH) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {"updatedAt": None, "codes": {}}


def save_state(path: Path, state: dict) -> None:
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
