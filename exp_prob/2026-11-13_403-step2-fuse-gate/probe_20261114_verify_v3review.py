r"""probe 2026-11-14：校驗第三輪複審速報（reports/驗收速報_v3_20261114.md）的宣稱。

宣稱一（阻斷一）：200＋忙碌頁形態全程無例外，三層修完後行為與現在一樣——
    速報描述的路徑：parse_menu_html 回 None → 解析失敗分支重試×3 → None → step2_error。
    本探針額外檢驗其「前提」：真實解析鏈（真 parse_step2/parse_orderflow/flatten_items
    ＋ node extract_js.cjs）對「非空 busy 頁」到底走哪條分支。
宣稱二（阻斷二）：mock daily.fetch_and_parse 不會執行 orderflow.fetch_and_parse（③a 所在）。
宣稱三（次要一）：③c 的 break 只跳出 alive 迴圈，dead 迴圈仍會打 step2。
宣稱四（已驗證論證）：BatchFetcher.fetch 的 except 內 raise 直達呼叫端（v3「不需改」的前提）。
靜態核對：次要二／三／四的行號與內容（v3、修復方法、查找報告）。

探針（mock 注入＋本地 node 解析，零真實網路、repo 與 data/ 零寫入；
parse_menu_html 內建行為會在系統暫存目錄寫入並刪除臨時 html）：
    P1 真實 fetch_and_parse（真解析鏈）×三種 busy 頁形態（短忙碌頁/文字版樣式/空回應）
       ＋ mock parse 變體（重現速報的實測條件）
    P2 真實 cmd_confirm＋垃圾成功 dict（=P1 短頁的實際解析產物）→ 靜默污染實證
    P3 綁定層級：daily.fetch_and_parse is orderflow.fetch_and_parse ＋呼叫計數（③a 是否被執行）
    P4 BatchFetcher.fetch 例外直達（_roll 以 stub 取代，不觸網）
    P5 模擬 ③a+③b+③c 落地後的迴圈結構（與速報同法：模擬實作，非現行代碼）
    P6 文檔行號核對（次要二/三/四）
"""
import shutil
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
try:  # python -I 下 stdout 會回到主控台編碼（cp950）：統一轉 utf-8 避免非 Big5 字元中斷
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from script.lib import orderflow                       # noqa: E402
from script.scan import daily                          # noqa: E402

ORIG_FETCH_AND_PARSE = daily.fetch_and_parse
ORIG_OF_FETCH_AND_PARSE = orderflow.fetch_and_parse
ORIG_PARSE_MENU = orderflow.parse_menu_html
ORIG_ROLL = orderflow.BatchFetcher._roll

_results: list[tuple[str, bool, str]] = []


def note(label: str, ok: bool, detail: str = "") -> None:
    _results.append((label, ok, detail))
    print(f"  => {'[OK]' if ok else '[NG]'} {label}" + (f"（{detail}）" if detail else ""))


# ============ P1：真實解析鏈 × 三種 busy 頁形態 ============
print("P1. 真實 fetch_and_parse（真解析鏈，含 node）× busy 頁形態")
node_ok = shutil.which("node") is not None
print(f"  node 可用: {node_ok}")


class _FakeFetcher:
    """回固定 html 的假 fetcher（記錄呼叫次數）。"""

    def __init__(self, html: str):
        self.html = html
        self.calls = 0

    def fetch(self, code: str) -> str:
        self.calls += 1
        return self.html


BUSY_SHORT = ("<html><head><title>系統忙碌中</title></head>"
              "<body><div>系統忙碌中，請稍後再試</div></body></html>")
TEXT_LIKE = ('<html><head>'
             '<meta property="og:title" content="平日外帶-$399 披薩 | Pizza Hut 必勝客">'
             '<meta property="og:description" content="外帶/外送 經典厚片任你搭">'
             '</head><body>' + "<!-- padding -->" * 13000 + "</body></html>")

p1_short = p1_text = None
if node_ok:
    # 1a 短忙碌頁（無 og、無 ctidss）
    f = _FakeFetcher(BUSY_SHORT)
    p1_short = orderflow.fetch_and_parse("15809", f, sleep=lambda _: None)
    print(f"  1a 短忙碌頁: calls={f.calls} 回傳型別={type(p1_short).__name__}")
    if isinstance(p1_short, dict):
        m = p1_short["meta"]
        print(f"     meta.title={m.get('title')!r} items={p1_short.get('items')!r}")
    note("1a 非空 busy 頁不走解析失敗分支（回 dict、僅 1 發）",
         isinstance(p1_short, dict) and f.calls == 1)

    # 1b 文字版樣式（有 og:title、~134KB、無 ctidss）
    f = _FakeFetcher(TEXT_LIKE)
    p1_text = orderflow.fetch_and_parse("15809", f, sleep=lambda _: None)
    print(f"  1b 文字版樣式: calls={f.calls} 回傳型別={type(p1_text).__name__}")
    if isinstance(p1_text, dict):
        m = p1_text["meta"]
        print(f"     meta.title={m.get('title')!r} channels={m.get('channels')} "
              f"items={p1_text.get('items')!r}")
    note("1b 文字版樣式同樣「成功」（meta 看起來正常）",
         isinstance(p1_text, dict) and f.calls == 1)

    # 1c 空回應 → 唯一會進解析失敗分支的形態
    f = _FakeFetcher("")
    r = orderflow.fetch_and_parse("15809", f, sleep=lambda _: None)
    print(f"  1c 空回應: calls={f.calls} 回傳={r!r}")
    note("1c 空回應才走「解析失敗×3→None」（速報描述的路徑）",
         r is None and f.calls == 3)
else:
    print("  （node 不可用，P1 真實鏈段跳過——結論退回靜態閱讀依據）")

# 1d mock parse 變體：重現速報的實測條件（parse_menu_html 被固定回 None）
orderflow.parse_menu_html = lambda code, html: None
try:
    f = _FakeFetcher(BUSY_SHORT)
    r = orderflow.fetch_and_parse("15809", f, sleep=lambda _: None)
    print(f"  1d mock parse→None: calls={f.calls} 回傳={r!r}")
    note("1d 速報的實測數字可重現（calls=3、ret=None）——但其前提是 parse 被 mock",
         r is None and f.calls == 3)
finally:
    orderflow.parse_menu_html = ORIG_PARSE_MENU

# ============ P2：真實 cmd_confirm × 垃圾成功 dict ============
print("\nP2. 真實 cmd_confirm × 垃圾成功（busy 頁解析產物）→ 下游實際行為")
garbage = None
if isinstance(p1_short, dict):
    garbage = p1_short  # 用 P1 的真實解析產物
if garbage is None:  # node 不可用時的等價構造（依 parse 鏈靜態行為）
    garbage = {"meta": {"code": "15809", "title": "", "partner": None,
                        "channels": [], "price": None, "msrp": None,
                        "desc_head": "", "desc": ""},
               "items": None, "struct": {"groups": {"main": {}, "second": {}, "add": {}}},
               "html": BUSY_SHORT}

OLD = {"status": "alive", "title": "老券標題", "channels": ["外帶", "外送"],
       "desc_head": "舊描述", "desc": "舊描述全文",
       "items": [{"text": "舊候選", "group": "main", "groupIdx": 1,
                  "priceAdd": 0, "flavors": []}]}
state_cap: dict = {}
alerts_cap: dict = {}
daily.load_state = lambda: {"codes": {"15809": dict(OLD)}}
daily.save_state = lambda path, s: state_cap.update(s)
daily.update_coverage = lambda recs: None
daily.update_alerts = lambda section, entries: alerts_cap.__setitem__(section, entries)
daily.history_row = lambda *a, **k: None
daily.merge_step2_failures = lambda *a, **k: None
daily.probe_batch = lambda codes: (
    [{"code": "15809", "at": "2026-11-14T00:00:00", "m1_success": True}], False)
daily.fetch_and_parse = lambda code, fetcher=None: dict(garbage)
try:
    rc2 = daily.cmd_confirm(types.SimpleNamespace(limit=0))
    saved_rec = state_cap.get("codes", {}).get("15809", {})
    print(f"  rc={rc2}")
    print(f"  title={saved_rec.get('title')!r} channels={saved_rec.get('channels')!r}")
    print(f"  desc_head={saved_rec.get('desc_head')!r} contentChangedAt={saved_rec.get('contentChangedAt')!r}")
    print(f"  items 保留={saved_rec.get('items') == OLD['items']}")
    print(f"  step2_error={saved_rec.get('step2_error')!r}")
    print(f"  content_changes alert 筆數={len(alerts_cap.get('content_changes', []))}")
    note("2 現行代碼：垃圾成功＝靜默污染（title/channels/desc 被清空＋假「內容更動」告警＋exit 0）",
         rc2 == 0 and saved_rec.get("title") == "" and saved_rec.get("channels") == []
         and saved_rec.get("contentChangedAt") is not None
         and len(alerts_cap.get("content_changes", [])) == 1
         and "step2_error" not in saved_rec)
finally:
    daily.fetch_and_parse = ORIG_FETCH_AND_PARSE

# ============ P3：綁定層級（阻斷二核心） ============
print("\nP3. mock daily.fetch_and_parse 時，orderflow.fetch_and_parse（③a 所在）是否被執行")
pre_identity = daily.fetch_and_parse is orderflow.fetch_and_parse
print(f"  daily.fetch_and_parse is orderflow.fetch_and_parse -> {pre_identity}")
counter = {"n": 0}


def _counting(code, fetcher=None, retries=3, sleep=None):
    counter["n"] += 1
    return ORIG_OF_FETCH_AND_PARSE(code, fetcher, retries=retries,
                                   sleep=sleep or (lambda _: None))


orderflow.fetch_and_parse = _counting
try:
    daily.fetch_and_parse = lambda code, fetcher=None: (_ for _ in ()).throw(
        RuntimeError("step_1_update 失敗: busy"))
    rec3 = {"code": "15809"}
    res3 = daily.step2_of(rec3, None)  # 真實 step2_of → 只會呼叫 daily 綁定的 mock
    print(f"  step2_of 回傳={res3!r} step2_error={rec3.get('step2_error')!r}")
    print(f"  orderflow.fetch_and_parse 被呼叫次數={counter['n']}（0＝③a 完全沒被測到）")
    note("3 測試 mock daily.fetch_and_parse 繞過 ③a（綁定隔離＋呼叫計數 0）",
         pre_identity and counter["n"] == 0)
finally:
    daily.fetch_and_parse = ORIG_FETCH_AND_PARSE
    orderflow.fetch_and_parse = ORIG_OF_FETCH_AND_PARSE

# ============ P4：BatchFetcher.fetch 例外直達（v3「不需改」的前提） ============
print("\nP4. BatchFetcher.fetch 的 RuntimeError 是否直達呼叫端（v3 L70-71 論證重驗）")
rolls = {"n": 0}


class _AlwaysRaiseSession:
    def fetch_menu(self, code: str) -> str:
        raise RuntimeError("step_1_update 失敗: busy")


def _fake_roll(self, seed: str) -> None:
    rolls["n"] += 1
    self._session = _AlwaysRaiseSession()
    self._count = 0


orderflow.BatchFetcher._roll = _fake_roll
try:
    bf = orderflow.BatchFetcher(k=50)
    propagated: str | None = None
    try:
        bf.fetch("15809")
    except RuntimeError as e:
        propagated = str(e)
    print(f"  上拋例外={propagated!r} _roll 呼叫數={rolls['n']}")
    note("4 except 內 retry 的 raise 直接穿出 fetch（初 roll 在 try 外）",
         propagated is not None and "step_1_update" in propagated and rolls["n"] == 2)
finally:
    orderflow.BatchFetcher._roll = ORIG_ROLL

# ============ P5：模擬 ③a+③b+③c 落地後的迴圈結構（次要一） ============
print("\nP5. 模擬計畫落地後：alive 迴圈熔斷 break，dead 迴圈是否仍打 step2")
print("  （模擬實作，與速報同法；非現行代碼——現行代碼無 try，例外會直接炸穿 main）")
call_seq: list[str] = []


def _planned_step2(rec, fetcher=None):
    """模擬 ③a+③b 落地後：關鍵字 RuntimeError 穿過兩層直達第三層。"""
    call_seq.append(rec["code"])
    raise RuntimeError("step_1_update 失敗: busy")


blown5 = False
alive_codes, dead_codes = ["A1", "A2"], ["D1"]
by_code5 = {c: {"code": c, "m1_success": True}
            for c in ("A1", "A2", "D1")}
for code in alive_codes:            # daily.py:178 alive 迴圈＋修改②/③c 的 try
    r5 = by_code5.get(code)
    if r5 is None:
        continue
    try:
        _planned_step2(r5, None)    # daily.py:194
    except RuntimeError:
        blown5 = True
        break                        # ③c：只跳出 alive 迴圈
for code in dead_codes:              # daily.py:229 dead 迴圈（獨立迴圈）
    r5 = by_code5.get(code)
    if r5 is None:
        continue
    if r5.get("m1_success") is True:  # 復活碼（daily.py:233）
        try:
            _planned_step2(r5, None)  # daily.py:242
        except RuntimeError:
            blown5 = True
print(f"  step2 呼叫序={call_seq} blown={blown5}")
note("5 alive 熔斷後 dead 迴圈仍打 step2（呼叫序 ['A1','D1']，與速報一致）",
     call_seq == ["A1", "D1"] and blown5)

# ============ P6：文檔行號核對（次要二/三/四） ============
print("\nP6. 文檔核對")
exp = Path(__file__).resolve().parent


def _lines(p: Path) -> list[str]:
    return p.read_text(encoding="utf-8").splitlines()


v3 = _lines(exp / "reports" / "修復報告_v3_20261114.md")
method = _lines(exp / "reports" / "修復方法_20261113.md")
finding = _lines(exp / "reports" / "probe_20261113_issue9_10_403.md")

# 次要二：commit 清單過期——v3 實際位置（速報引用 L123；另 L206 附註也有同樣過期資訊）
v3_l123 = v3[122] if len(v3) >= 123 else ""
v3_l206 = v3[205] if len(v3) >= 206 else ""
print(f"  v3 L123: {v3_l123.strip()[:60]}")
print(f"  v3 L206: {v3_l206.strip()[:70]}")
note("6a 次要二成立：v3「三個 commit」過期資訊在 L123（Phase 0，速報所引，引用正確）＋L206（附註）兩處",
     "三個 commit" in v3_l123 and "三個 commit" in v3_l206)
m_l31 = method[30] if len(method) >= 31 else ""
print(f"  修復方法 L31 (0.1): {m_l31.strip()[:70]}")
note("6b 修復方法 0.1 同樣寫「三個 commit」", "三個 commit" in m_l31)

# 次要三：修復方法 1.3 是否寫明 test_step2_visibility 是 ③b 守門員
m_13 = "\n".join(method[40:41])  # L41 = 1.3 列
has_gatekeeper = "守門" in m_13 or "test_step2_visibility" in m_13
print(f"  修復方法 L41 (1.3): {m_13.strip()[:80]}")
note("6c 次要三成立：1.3 未寫明 test_step2_visibility 是 ③b 守門員", not has_gatekeeper)

# 次要四：查找報告三處偏差仍在
l70, l83, l122 = finding[69], finding[82], finding[121]
print(f"  查找報告 L70: {l70.strip()[:60]}")
print(f"  查找報告 L122: {l122.strip()[:60]}")
note("6d 次要四成立：L70/83/122 偏差未回改",
     "2 張死" in l70 and "超時重試成功" in l70 and "煙霧重現確認 dead" in l122)

# ============ 總判定 ============
print("\n=== 總判定 ===")
for label, ok, _ in _results:
    print(f"  {'[OK]' if ok else '[NG]'} {label}")
fails = [l for l, ok, _ in _results if not ok]
print(f"\n  {len(_results) - len(fails)}/{len(_results)} 項通過" +
      ("；全部與校驗預期一致" if not fails else f"；異常項：{fails}"))
