"""HutDeals lib — 掃號節奏（隨機浮動等待，掃號策略 2026-09-04）。

原散落：scan_run.main 內聯 jitter、scan_probe._pace（含中場休息）→ 統一收此。
原則（策略紅線）：間隔一律隨機浮動（不固定）、每 N 發中場長休息。

2026-11-14 節流統一（issue #9/#10 修復⑦，計畫 v6）：base 2.0→1.0 整體減半，
M1/step2/enrich 同套參數（step2 四迴圈補 sleep_scan——事故量測 step2 密度為
M1 的 8.6 倍）；號段等待停用（DEFAULT_SEG_GAP=0.0）；每 50 發中場長休息保留。
seg_gap 常數與參數保留供 CLI 相容——scan_probe/scan_run 的 argparse default
引用它，勿直接刪除（停用後預設加成為零，顯式傳值仍有效）。
"""
import random
import time

__all__ = ["sleep_scan"]

DEFAULT_SLEEP = 1.0   # 基礎間隔秒（2026-11-14 ⑦節流統一：2.0→1.0 整體減半，M1/step2/enrich 同套）
DEFAULT_JITTER = 2.0  # 每發浮動上限
DEFAULT_SEG_GAP = 0.0  # 號段等待 2026-11-14 ⑦停用；常數與 seg_gap 參數保留（scan_probe/scan_run 的 argparse default 引用，勿刪）
DEFAULT_BREAK_EVERY = 50  # 中場休息間隔：對齊 BatchFetcher 50 張換 session(2026-09-08)
DEFAULT_BREAK_BASE = 30.0  # 中場休息基數(2026-09-09 90→30：省每日約 1h，官網密度已由每發 2s 主導)


def sleep_scan(index: int, codes: list[str], *,
               sleep: float = DEFAULT_SLEEP, jitter: float = DEFAULT_JITTER,
               seg_gap: float = DEFAULT_SEG_GAP,
               break_every: int = DEFAULT_BREAK_EVERY,
               break_base: float = DEFAULT_BREAK_BASE) -> None:
    """打完第 index 個碼後休息（若為最後一個則不休息）。

    節奏：base sleep + U(0,jitter)；換號段追加 seg_gap×U(0.5,1.5)（⑦ 停用：
    DEFAULT_SEG_GAP=0.0，顯式傳值仍有效）；每 break_every 發中場長休息
    break_base×U(0.8,1.5)。
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
