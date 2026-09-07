"""HutDeals lib — 文字工具（全 repo 唯一一份 clean_text）。

原散落：fetch_official._clean、parse_step2.clean（byte-identical）→ 合一。
"""
import re

__all__ = ["clean_text"]


def clean_text(text: str) -> str:
    """把任意連續空白（含換行）收成單一空格並去首尾。"""
    return re.sub(r"\s+", " ", text).strip()
