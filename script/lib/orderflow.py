"""HutDeals lib — 訂餐流程 session（必勝客 order flow 結構化爬取）。

背景（2026-09-06 訂餐後端探索實證）：
    無 session 直接 GET step_2 只拿到 ~134KB「文字版」（無選單結構）。
    必勝客訂餐系統要「先選門市/日期」才在 step_2 頁內嵌結構化選單資料
    （psidss/pprcss/ctidss/exTopping，213~391KB「選單版」）。本模組實作
    這個 4 步 session 流程，供 scan/daily、site/enrich_official 改用。

流程（每次可共用前置）：
    1. GET  /order/?mode=step_2&type_id=1025&cno=<seed>  → 配 users_session_id
    2. POST /image/order_localization.php  {m:ajax,pl:p,path:order,sv:}  → 取 llcs/llcstmsp
    3. POST /order/?m=ajax  mode=step_1_update（選外帶門市 + 隔日日期）
    4. GET  /order/?mode=step_2&type_id=1025&cno=<code>   ← 之後每券只這一步

共用：前置 1-3 對整個 session 做一次即可服務 K 張券（K 張 = 3+K 請求）。
時效：users_session_id/llcs/llcstmsp 每次 session 都變，不可重用舊值；session
過期時 step_1_update 會回錯 → 自動重配（建新 session 重走前置）。

實作：stdlib-only（http.cookiejar + urllib.request），不引 requests。
紅線：同 lib/net 的 UA/headers 慣例、429/403 熔斷（呼叫端處理）。
"""
from __future__ import annotations

import datetime as dt
import http.cookiejar
import re
import urllib.error
import urllib.parse
import urllib.request

from script.lib.net import STEP2_HEADERS, UA, is_rate_limited

ORDER_URL = "https://www.pizzahut.com.tw/order/?mode=step_2&type_id=1025&cno={code}"
LOC_URL = "https://www.pizzahut.com.tw/image/order_localization.php"
AJAX_URL = "https://www.pizzahut.com.tw/order/?m=ajax"
BASE = "https://www.pizzahut.com.tw"
# 任一可取外帶門市（台北中正區汀洲）。共用前置時固定選它。
DEFAULT_STORE = "346"

# 選單版特徵：含內嵌 ctidss 結構資料且長度遠大於文字版(~134KB)。
# 各券型 select 數差異大(11~43)，不能以 select 數判定。
MENU_MIN_LEN = 180_000


class OrderFlowSession:
    """一個可服務 K 張券的訂餐 session（前置做一次，逐券只 fetch step_2）。"""

    def __init__(self, store: str = DEFAULT_STORE):
        self.store = store
        self._cj = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._cj))
        self._prepared = False

    # ---- 低階請求 ----
    def _request(self, url: str, data: dict | None = None,
                 headers: dict | None = None, timeout: int = 25) -> str:
        hdrs = dict(STEP2_HEADERS)
        hdrs["User-Agent"] = UA
        hdrs["Origin"] = BASE
        hdrs["Referer"] = f"{BASE}/order/"
        if headers:
            hdrs.update(headers)
        body = urllib.parse.urlencode(data).encode() if data else None
        req = urllib.request.Request(url, data=body, headers=hdrs)
        with self._opener.open(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _cookie(self, name: str) -> str | None:
        for c in self._cj:
            if c.name == name:
                return c.value
        return None

    # ---- 共用前置 ----
    def prepare(self, seed_code: str) -> None:
        """走完前置 1-3。seed_code 用任一活碼即可（只為配 session + 選門市）。"""
        # 1) 配 cookie
        self._request(ORDER_URL.format(code=seed_code))
        if not self._cookie("users_session_id"):
            raise RuntimeError("step0 未配發 users_session_id")
        # 2) localization 取 llcs / llcstmsp
        loc = self._request(LOC_URL, {"m": "ajax", "pl": "p", "path": "order",
                                      "sv": ""})
        m = re.search(r'name="llcs" value="([^"]+)"', loc)
        m2 = re.search(r'name="llcstmsp" value="([^"]*)"', loc)
        if not m:
            raise RuntimeError("localization 面板未含 llcs")
        llcs, llcstmsp = m.group(1), (m2.group(1) if m2 else "")
        # 3) step_1_update 選外帶門市 + 隔日
        tomorrow = (dt.date.today() + dt.timedelta(days=1)).isoformat()
        payload = {
            "mode": "step_1_update", "store": self.store, "type_id": "1025",
            "p_id": "", "cno": seed_code, "service_type": "takeout",
            "d_type_radio": "", "llcs": llcs, "llcstmsp": llcstmsp,
            "get_products_date": tomorrow, "city": "", "area": "",
            "sRoad": "", "sNeighborhood": "", "sLane": "", "sAlley": "",
            "sNo": "", "sSubNo": "", "sFl": "", "sRoom": "",
        }
        resp = self._request(AJAX_URL, payload,
                             headers={"X-Requested-With": "XMLHttpRequest",
                                      "Accept": "application/json, */*"})
        if '"success":true' not in resp and '"success": true' not in resp:
            raise RuntimeError(f"step_1_update 失敗: {resp[:200]}")
        self._prepared = True

    # ---- 逐券抓取 ----
    def fetch_menu(self, code: str, timeout: int = 25) -> str:
        """抓單券 step_2「選單版」HTML。前置未做或已過期會自動重配一次。"""
        if not self._prepared:
            self.prepare(code)
        try:
            return self._request(ORDER_URL.format(code=code), timeout=timeout)
        except urllib.error.HTTPError as e:
            if is_rate_limited(e):
                raise  # 熔斷給呼叫端
            # 其他錯誤重配一次 session 重試（防 session 過期）
            self._prepared = False
            self.prepare(code)
            return self._request(ORDER_URL.format(code=code), timeout=timeout)

    def is_menu_page(self, html: str) -> bool:
        """選單版判定：含 ctidss 且夠長（文字版 ~134KB）。"""
        return len(html) > MENU_MIN_LEN and "ctidss" in html


def fetch_menu_single(code: str, store: str = DEFAULT_STORE) -> str:
    """單碼完整流程（每碼一個新 session，含前置）。給手動/少量用。"""
    s = OrderFlowSession(store)
    s.prepare(code)
    return s.fetch_menu(code)


def parse_menu_html(code: str, html: str) -> dict | None:
    """選單版 HTML → {meta, items, struct}。供已抓到 html 的呼叫端用（可測）。

    meta   parse_step2 產出（title/partner/channels/price/msrp/desc_head/desc）
    items  parse_orderflow 扁平結構化候選（新 schema）
    struct 結構化中介（含候選 flavors 等完整資訊）
    """
    import json
    import os
    import subprocess
    import tempfile

    from script.scan.parse_orderflow import flatten_items, parse_orderflow
    from script.scan.parse_step2 import parse_step2

    if not html:
        return None
    # node 抽 JS 變數
    repo_scan = os.path.join(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))), "script", "scan")
    node_script = os.path.join(repo_scan, "extract_js.cjs")
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False,
                                     encoding="utf-8") as f:
        f.write(html)
        tmp = f.name
    try:
        proc = subprocess.run(["node", node_script, tmp],
                              capture_output=True, text=True, timeout=60,
                              encoding="utf-8")
        if proc.returncode != 0:
            return None
        extract = json.loads(proc.stdout)
    finally:
        os.unlink(tmp)

    meta = parse_step2(html, code)
    struct = parse_orderflow(html, extract)
    items = flatten_items(struct)
    return {"meta": meta, "items": items, "struct": struct}


def fetch_and_parse(code: str, fetcher=None) -> dict | None:
    """抓一碼選單版並解析。fetcher=BatchFetcher（共用 session）；None=新 session。

    回 {html, meta, items, struct} 或 None（抓取/解析失敗）。
    429/403（熔斷）原樣往上拋，由呼叫端處理。
    """
    try:
        if fetcher is not None:
            html = fetcher.fetch(code)
        else:
            html = fetch_menu_single(code)
    except urllib.error.HTTPError as e:
        if is_rate_limited(e):
            raise  # 熔斷給呼叫端處理
        return None
    except Exception:  # noqa: BLE001
        return None
    parsed = parse_menu_html(code, html)
    if parsed is None:
        return None
    parsed["html"] = html
    return parsed


class BatchFetcher:
    """批次共用 session：K 張券共用一份前置（3+K 請求），每 K 張換新 session。

    daily confirm(~565 碼) 用它可省大量請求：565 碼 = 3+565 而非 4×565。
    """

    def __init__(self, k: int = 50, store: str = DEFAULT_STORE):
        self.k = k
        self.store = store
        self._session: OrderFlowSession | None = None
        self._count = 0

    def fetch(self, code: str) -> str:
        """抓單碼選單版；達 K 張自動換新 session；錯誤重配一次後再拋。"""
        if self._session is None or self._count >= self.k:
            self._roll(code)
        try:
            html = self._session.fetch_menu(code)
        except Exception:
            # session 過期/其他錯誤 → 重配一次；若仍錯往上拋（含 429/403 熔斷）
            self._roll(code)
            html = self._session.fetch_menu(code)
        self._count += 1
        return html

    def _roll(self, seed: str) -> None:
        s = OrderFlowSession(self.store)
        s.prepare(seed)
        self._session = s
        self._count = 0
