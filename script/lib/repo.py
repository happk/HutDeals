"""HutDeals lib — repo 根路徑（全 repo 統一來源）。

套件化後各模組深度不一，禁止各檔自己 __file__.parents[N]；一律 from script.lib.repo import REPO。
script/lib/repo.py 固定在第 3 層（repo/script/lib/），故 parents[2]。
"""
from pathlib import Path

__all__ = ["REPO"]

REPO = Path(__file__).resolve().parents[2]
