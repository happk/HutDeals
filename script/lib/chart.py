"""HutDeals lib — matplotlib 中文字型（全 repo 唯一一份）。

原散落：export_aggregator_codes/analyze_y2025/analyze_code_patterns 各一份 setup_font → 合一。
"""
__all__ = ["setup_cjk_font"]


def setup_cjk_font() -> None:
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    for f in ("C:/Windows/Fonts/msjh.ttc", "C:/Windows/Fonts/simhei.ttf"):
        try:
            font_manager.fontManager.addfont(f)
        except Exception:
            continue
    plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
