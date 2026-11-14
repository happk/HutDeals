r"""probe 2026-11-14：校驗第四輪複審速報（reports/驗收速報_v4_20261114.md）＋事故報告的代碼層宣稱。

複審宣稱：
    阻斷一：⑥a 門檻（len>180_000 且含 ctidss）可被「大且含 ctidss 字串但無資料」的頁繞過——
            繞過後垃圾成功放行、⑥b 計數不動。
    阻斷二：⑥b 歸零條件太鬆（任何 d 非 None 都歸零）——間歇性忙碌頁夾假成功可讓計數永遠到不了 3。
    補法：⑥a 加軟訊號（items is None → 告警不計數）；⑥b 歸零收窄為「真解析出 items 才歸零」。
事故報告宣稱（代碼層）：
    抓詳情迴圈完全沒有 sleep_scan（對照 probe_batch 有）——速率不對稱的機制基礎。
    alert job 對既有 open issue 靜默 skip；gate 仍 fail-open。

探針（真實解析鏈含 node、唯讀 state、記憶體模擬；零真實網路、repo 與 data/ 零寫入）：
    A 阻斷一重現：264KB＋ctidss 字串＋無資料頁 → 閘門放行
    B 真實 fixtures × 閘門：orderflow 五頁（複審宣稱全過）＋step2 兩頁（行為觀察）
    C data/scan_state.json 唯讀掃描：items 為空的活碼（複審宣稱 625 張中 3 張）
    D ⑥b 計數模擬 N=3：v4 現設計 vs 複審補法 vs 統一計數選項（含殘餘缺口檢驗）
    E 靜態核對：README 過期行／PARSE_FAIL_MARK 字面值副本／sleep_scan 分布／scan.yml
"""
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from script.lib import orderflow                       # noqa: E402

ORIG_PARSE_MENU = orderflow.parse_menu_html
_results: list[tuple[str, bool]] = []


def note(label: str, ok: bool) -> None:
    _results.append((label, ok))
    print(f"  => {'[OK]' if ok else '[NG]'} {label}")


class _FakeFetcher:
    def __init__(self, html: str):
        self.html = html
        self.calls = 0

    def fetch(self, code: str) -> str:
        self.calls += 1
        return self.html


# ============ A：阻斷一——繞過頁 ============
print("A. 真實解析鏈 × 繞過頁（264KB、含 ctidss 字串、無資料）")
PAD = "ctidss psidss pprcss "
bypass = ("<html><head><title>系統忙碌</title></head><body><h1>系統忙碌</h1>"
          + "<!-- " + PAD * 12500 + " --></body></html>")
print(f"  頁面長度={len(bypass)} 含 ctidss={'ctidss' in bypass}")
f = _FakeFetcher(bypass)
r = orderflow.fetch_and_parse("15809", f, sleep=lambda _: None)
print(f"  is_menu_page={orderflow.OrderFlowSession().is_menu_page(bypass)} "
      f"calls={f.calls} 回傳型別={type(r).__name__}")
if isinstance(r, dict):
    print(f"  title={r['meta'].get('title')!r} items={r.get('items')!r}")
gate_triggers = r is None or not orderflow.OrderFlowSession().is_menu_page(bypass)
print(f"  v4 ⑥a 閘門是否攔下={gate_triggers}")
note("A 阻斷一重現：繞過頁通過閘門（dict、calls=1、items=None）",
     isinstance(r, dict) and f.calls == 1 and r.get("items") is None and not gate_triggers)

# ============ B：真實 fixtures × 閘門 ============
print("\nB. 真實 fixtures × ⑥a 閘門（複審宣稱 orderflow 五頁全過）")
fx_dir = REPO / "script" / "support" / "tests" / "fixtures"
ok_pass = 0
for sub in ("orderflow", "step2"):
    for p in sorted((fx_dir / sub).glob("*.html")):
        html = p.read_text(encoding="utf-8", errors="replace")
        menu = orderflow.OrderFlowSession().is_menu_page(html)
        parsed = orderflow.parse_menu_html(p.stem, html)
        gate_pass = parsed is not None and menu
        print(f"  {sub}/{p.stem}.html len={len(html)} is_menu_page={menu} "
              f"parsed={'dict' if parsed is not None else 'None'} "
              f"items={'None' if parsed is None else parsed.get('items') is None and 'None' or len(parsed.get('items') or [])} "
              f"→ 閘門{'放行' if gate_pass else '攔下'}")
        if sub == "orderflow" and gate_pass:
            ok_pass += 1
note("B 複審宣稱證實：orderflow 五個正常 fixture 全部通過閘門", ok_pass == 5)

# ============ C：state 唯讀掃描——items 為空的活碼 ============
print("\nC. data/scan_state.json 唯讀掃描（複審宣稱：625 張活碼中 3 張 items 為空）")
state = json.loads((REPO / "data" / "scan_state.json").read_text(encoding="utf-8"))
codes = state.get("codes", {})
alive = sorted(c for c, rr in codes.items() if rr.get("status") == "alive")
empty_items = [c for c in alive if not (codes[c].get("items") or [])]
print(f"  alive 總數={len(alive)} items 為空的活碼={empty_items}")
for c in empty_items:
    rr = codes[c]
    print(f"    {c}: items={rr.get('items')!r} channels={rr.get('channels')!r} "
          f"status={rr.get('status')}")
print("  （D8 用）排序後相鄰性：")
for c in empty_items:
    i = alive.index(c)
    lo, hi = max(0, i - 1), min(len(alive), i + 2)
    print(f"    {c} 的鄰居={alive[lo:hi]}")
note("C 複審宣稱證實：alive 625、items 為空恰 3 碼（93015/15596/16348）",
     len(alive) == 625 and empty_items == ["15596", "16348", "93015"])

# ============ D：⑥b 計數模擬（N=3） ============
print("\nD. ⑥b 計數模擬（N=3）——v4 現設計 vs 複審補法 vs 統一計數選項")
MARK = "fetch/parse 失敗"
FAIL = ({"step2_error": MARK}, None)                     # 解析失敗 → d None
FAKE = ({}, {"meta": {"title": "垃圾"}, "items": None})  # 假成功 → d 非None、items None
REAL = ({}, {"meta": {"title": "正常"}, "items": [{"text": "x"}]})  # 真成功


def run_loop(seq: list, reset_rule: str) -> tuple[bool, int]:
    """reset_rule: 'v4'＝任何 d 非 None 歸零；'review'＝items 非 None 才歸零（假成功 pass）；
    'unified'＝items 非 None 才歸零、假成功也 +1 計數。"""
    streak = 0
    for rec, d in seq:
        if d is None:
            streak = streak + 1 if rec.get("step2_error") == MARK else 0
        elif reset_rule == "v4":
            streak = 0
        elif d.get("items") is not None:
            streak = 0
        elif reset_rule == "unified":
            streak += 1
        if streak >= 3:
            return True, len(seq)
    return False, len(seq)


mixed12 = ([FAIL] + [FAIL] + [FAKE]) * 4    # 失敗、失敗、假成功 ×12 碼
all_fake10 = [FAKE] * 10                    # 全假成功（繞過頁形態）
s1, n1 = run_loop([FAIL] * 3, "v4")
s2, n2 = run_loop(mixed12, "v4")
s3, n3 = run_loop(all_fake10, "v4")
s4, n4 = run_loop(mixed12, "review")
s5, n5 = run_loop(all_fake10, "review")
s6, n6 = run_loop(mixed12, "unified")
s7, n7 = run_loop(all_fake10, "unified")
print(f"  v4 現設計  ：全失敗×3→熔斷={s1}；失敗夾假成功×12→熔斷={s2}；全假成功×10→熔斷={s3}")
print(f"  複審補法  ：失敗夾假成功×12→熔斷={s4}；全假成功×10→熔斷={s5}")
print(f"  統一計數  ：失敗夾假成功×12→熔斷={s6}；全假成功×10→熔斷={s7}")
note("D 阻斷二重現：v4 設計下「失敗夾假成功」12 碼不熔斷", s2 is False)
note("D 複審補法有效：收窄歸零後同一序列熔斷", s4 is True)
note("D 殘餘缺口屬實：全假成功（繞過頁形態）在複審補法下仍不熔斷（僅告警）", s5 is False)
note("D 統一計數選項：混合與全假成功兩形態都熔斷（假成功 +1、真成功歸零）", s6 is True and s7 is True)

# ============ E：靜態核對 ============
print("\nE. 靜態核對")
exp = Path(__file__).resolve().parent
readme = (exp / "README.md").read_text(encoding="utf-8").splitlines()
l15 = readme[14] if len(readme) >= 15 else ""
l36 = readme[35] if len(readme) >= 36 else ""
print(f"  README L15: {l15.strip()[:52]}")
print(f"  README L36: {l36.strip()[:52]}")
note("E 次要一成立：README L15 仍寫「現行＝v3 Phase 表」（複審引 L16，行號差一）",
     "現行＝v3" in l15 and any("v4" in x for x in readme))

lit = [l for l in (REPO / "script" / "scan" / "daily.py").read_text(encoding="utf-8").splitlines()
       if MARK in l]
probes_lit = [l for l in (REPO / "script" / "scan" / "scan_probe.py").read_text(encoding="utf-8").splitlines()
              if MARK in l]
runs_lit = [l for l in (REPO / "script" / "scan" / "scan_run.py").read_text(encoding="utf-8").splitlines()
            if MARK in l]
enrich_lit = [l for l in (REPO / "script" / "site" / "enrich_official.py").read_text(encoding="utf-8").splitlines()
              if MARK in l]
print(f"  「{MARK}」字面值副本：daily={len(lit)} scan_probe={len(probes_lit)} "
      f"scan_run={len(runs_lit)} enrich={len(enrich_lit)}（複審只列前兩支手動工具）")
note("E 次要二成立但補充：字面值實為四副本（enrich_official.py:84 複審漏列）",
     len(probes_lit) == 1 and len(runs_lit) == 1 and len(enrich_lit) == 1)

daily_src = (REPO / "script" / "scan" / "daily.py").read_text(encoding="utf-8").splitlines()
sleep_lines = [i + 1 for i, l in enumerate(daily_src) if "sleep_scan(" in l]
print(f"  daily.py 的 sleep_scan 呼叫行={sleep_lines}（僅 probe_batch L76；"
      f"alive/dead/explore/sample 四個抓詳情迴圈皆無）")
note("E 事故報告機制宣稱證實＋範圍補充：抓詳情迴圈無節流是四處而非報告點名的一處",
     sleep_lines == [76])

yml = (REPO / ".github" / "workflows" / "scan.yml").read_text(encoding="utf-8").splitlines()
gate_swallow = [i + 1 for i, l in enumerate(yml) if "2>/dev/null || echo 0" in l]
alert_skip = [i + 1 for i, l in enumerate(yml) if "already exists, skip" in l]
confirm_cov = [i + 1 for i, l in enumerate(yml[83:93], start=84) if "scan_coverage" in l]
print(f"  scan.yml：gate 吞錯行={gate_swallow} alert 靜默 skip 行={alert_skip} "
      f"confirm commit 內 coverage 出現={confirm_cov or '無'}")
note("E 事故報告宣稱證實：gate fail-open（35/36/46）＋alert 靜默 skip＋confirm 無 coverage",
     gate_swallow == [35, 36, 46] and len(alert_skip) == 1 and not confirm_cov)

# ============ 總判定 ============
print("\n=== 總判定 ===")
for label, ok in _results:
    print(f"  {'[OK]' if ok else '[NG]'} {label}")
fails = [l for l, ok in _results if not ok]
print(f"\n  {len(_results) - len(fails)}/{len(_results)} 項通過"
      + ("；全部與校驗預期一致" if not fails else f"；異常項：{fails}"))
