"""probe 2026-11-14：校驗第二輪複審（驗收_v2_20261113.md）的兩個阻斷級宣稱。

宣稱一（缺口一）：v2 的修改③（cmd 層／enrich 加 except RuntimeError）是死代碼——
    RuntimeError 在上游兩層就被吞掉，cmd 層只會收到 None，收不到例外。
宣稱二（缺口二）：v2 規劃的測試（mock daily.step2_of）會把被測邏輯整個移除，
    在「修改③ 完全無效」的實作上也會綠燈（假陽性）。

探針（全部 mock 注入，零真實網路、零檔案寫入）：
    A. 真實 step2_of + fetch_and_parse 拋 RuntimeError → 回 None、step2_error 落 rec（第二層吞噬）
    B. 模擬 v2 計畫的 cmd 層 try/except RuntimeError 包住真實 step2_of → blown 恆 False（死代碼證實）
    C. 真實 cmd_confirm（infra 全 mock，零污染）→ 回 0、無熔斷（現行代碼＋RuntimeError 的實際行為）
    D. v2 規劃的測試設計（mock step2_of 拋 RuntimeError）→ blown=True（假陽性證實）
"""
import sys

sys.path.insert(0, r"D:\Desktop\work\project\20260908_PizzaHut-Coupon-Scraper_Public")

from script.scan import daily                           # noqa: E402


def boom(code, fetcher=None):
    raise RuntimeError("step_1_update 失敗: busy（200 錯誤頁）")


class _Args:
    limit = 5


rec = {"code": "15809"}

# ---- A：第二層吞噬（真實 step2_of） ----
daily.fetch_and_parse = boom
a_rec = dict(rec)
a_result = daily.step2_of(a_rec, None)
print(f"A. step2_of 回傳: {a_result}")
print(f"A. rec.step2_error: {a_rec.get('step2_error')!r}")
a_ok = (a_result is None and "step_1_update" in (a_rec.get("step2_error") or ""))
print(f"A. 第二層吞噬證實: {a_ok}")

# ---- B：v2 計畫的 cmd 層 handler 對真實 step2_of（死代碼檢驗） ----
blown_b = False
try:
    d = daily.step2_of(dict(rec), None)   # 真實 step2_of → 內部吞掉 → 回 None
except RuntimeError:
    blown_b = True                        # v2 修改③ 規劃的接法
print(f"B. v2 修改③ handler 觸發: {blown_b}（False＝死代碼證實）")

# ---- C：真實 cmd_confirm（infra 全 mock） ----
daily.load_state = lambda: {"codes": {"15809": {"status": "alive"}}}
daily.save_state = lambda *a, **k: None
daily.update_coverage = lambda recs: None
daily.update_alerts = lambda section, entries: None
daily.history_row = lambda *a, **k: None
daily.merge_step2_failures = lambda *a, **k: None
daily.probe_batch = lambda codes: (
    [{"code": "15809", "at": "2026-11-14T00:00:00", "m1_success": True}], False)
alerts_seen: dict = {}
daily.update_alerts = lambda section, entries: alerts_seen.__setitem__(section, entries)
rc_c = daily.cmd_confirm(_Args())
print(f"C. cmd_confirm 回傳: {rc_c}（0＝無熔斷、迴圈掃完）")

# ---- D：v2 規劃的測試設計（mock step2_of） ----
daily.step2_of = lambda rec_, fetcher=None: (_ for _ in ()).throw(
    RuntimeError("step_1_update 失敗: busy"))
blown_d = False
try:
    d = daily.step2_of(dict(rec), None)
except RuntimeError:
    blown_d = True
print(f"D. mock step2_of 時 handler 觸發: {blown_d}（True＝假陽性證實：測試在補丁無效時也會綠）")

# ---- 總判定 ----
print("\n=== 判定 ===")
print(f"缺口一（修改③ 死代碼）: {'證實' if (a_ok and not blown_b) else '與複審不符，需回查'}")
print(f"缺口二（測試假陽性）  : {'證實' if blown_d else '與複審不符，需回查'}")
print(f"現行代碼行為（C）     : {'exit 0、無熔斷——RuntimeError 200錯誤頁形態目前完全不防' if rc_c == 0 else '回傳值與預期不符，需回查'}")
