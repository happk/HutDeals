"""HutDeals lib — 掃號節奏（隨機浮動等待，掃號策略 2026-09-04）。

原散落：scan_run.main 內聯 jitter、scan_probe._pace（含中場休息）→ 統一收此。
原則（策略紅線）：間隔一律隨機浮動（不固定）、換號段額外休息、每 N 發中場長休息。
"""
import random
import time

__all__ = ["sleep_scan"]

DEFAULT_SLEEP = 2.0   # 基礎間隔秒（策略定稿為 ~2s 浮動）
DEFAULT_JITTER = 2.0  # 每發浮動上限
DEFAULT_SEG_GAP = 15.0
DEFAULT_BREAK_EVERY = 50  # 中場休息間隔：對齊 BatchFetcher 50 張換 session(2026-09-08)
DEFAULT_BREAK_BASE = 90.0


def sleep_scan(index: int, codes: list[str], *,
               sleep: float = DEFAULT_SLEEP, jitter: float = DEFAULT_JITTER,
               seg_gap: float = DEFAULT_SEG_GAP,
               break_every: int = DEFAULT_BREAK_EVERY,
               break_base: float = DEFAULT_BREAK_BASE) -> None:
    """打完第 index 個碼後休息（若為最後一個則不休息）。

    節奏：base sleep + U(0,jitter)；前 2 碼改變(換號段) 追加 seg_gap×U(0.5,1.5)；
    每 break_every 發中場長休息 break_base×U(0.8,1.5)。
    """
    if index >= len(codes) - 1:
        return
    delay = sleep + random.uniform(0, jitter)
    if index > 0 and codes[index][:2] != codes[index - 1][:2]:
        delay += seg_gap * random.uniform(0.5, 1.5)
    time.sleep(delay)
    if break_every and (index + 1) % break_every == 0:
        rest = break_base * random.uniform(0.8, 1.5)
        print(f"[{index+1}/{len(codes)}] 中場休息 {rest:.0f}s", flush=True)
        time.sleep(rest)
