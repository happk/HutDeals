"""probe_20261114_step2_first_request.py — 手動重現「第一筆 step2 請求」並全程監測（probe A）。

背景：11-12/11-13 生產場 step2 第一發即 403（prepare 前置 3 步都過、403 打在
fetch_menu 的 GET）；11-14 修復場至少一碼成功後仍被拒。現行代碼只留狀態碼，
403 的回應體與 headers 全部丟掉——本 probe 逐位重現生產路徑並補上完整監測。

重現方式：繼承 production 的 OrderFlowSession，只覆寫 _request 做擷取；
header 組裝逐位複製 production（script/lib/orderflow.py _request），
prepare()/fetch_menu() 直接用生產方法——payload、順序、session 邏輯零改動。
production _request 若改動，本檔複製段要同步（probe 是當下快照）。

記錄每請求：實送 headers、狀態、回應 headers、大小/SHA-256/耗時、cookie 變化、
關鍵字掃描（WAF/挑戰頁/忙碌頁/選單版特徵）、重定向（final_url≠請求 URL）；
403/429 時抓 HTTPError 的完整回應體存檔。回應原文存 captures/。

跑法（repo 根目錄）：
    python exp_prob\\2026-11-14_step2-request-403\\probe_20261114_step2_first_request.py
請求預算：session 前置 3＋menu GET 1＋M1 對照 1＝5 發（上限 12，超過即停）。
"""
import datetime as dt
import hashlib
import json
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROBE_DIR = Path(__file__).resolve().parent
REPO = PROBE_DIR.parent.parent
CAPTURES = PROBE_DIR / "captures"
CAPTURES.mkdir(exist_ok=True)

sys.path.insert(0, str(REPO))

from script.lib.net import M1_ENDPOINT, M1_HEADERS, STEP2_HEADERS, UA  # noqa: E402
from script.lib.orderflow import (AJAX_URL, BASE, DEFAULT_STORE,       # noqa: E402
                                  OrderFlowSession, is_menu_page,
                                  is_rate_limited)

REQUEST_CAP = 12
MARKERS = ["cloudflare", "akamai", "cloudfront", "captcha", "challenge",
           "denied", "blocked", "forbidden", "請稍後", "稍候", "忙碌",
           "維護", "ctidss", "psidss", "pprcss", "success"]


def scan_markers(text: str) -> dict:
    low = text.lower()
    title = re.search(r"<title[^>]*>(.*?)</title>", text, re.S | re.I)
    return {"keyword_hits": [m for m in MARKERS if m in low],
            "title": title.group(1).strip()[:80] if title else None}


class MonitoredSession(OrderFlowSession):
    """production session ＋ 全程擷取（_request 組裝複製 production，見 docstring）。"""

    def __init__(self, store: str):
        super().__init__(store)
        self.records: list[dict] = []
        self._n = 0

    def _capture(self, rec: dict, raw: bytes, status, resp_headers, t0: float) -> str:
        self._n += 1
        rec.update(status=status,
                   response_headers=list(resp_headers.items()),
                   elapsed_s=round(time.monotonic() - t0, 3),
                   body_len=len(raw),
                   sha256_16=hashlib.sha256(raw).hexdigest()[:16])
        text = raw.decode("utf-8", errors="replace")
        rec["markers"] = scan_markers(text)
        fname = f"{self._n:02d}_{rec['tag']}.bin"
        (CAPTURES / fname).write_bytes(raw)
        rec["file"] = fname
        self.records.append(rec)
        return text

    def _request(self, url: str, data: dict | None = None,
                 headers: dict | None = None, timeout: int = 25) -> str:
        if self._n >= REQUEST_CAP:
            raise RuntimeError(f"probe 請求上限 {REQUEST_CAP} 已到，停手")
        # --- header 組裝逐位複製 production script/lib/orderflow.py _request ---
        hdrs = dict(STEP2_HEADERS)
        hdrs["User-Agent"] = UA
        hdrs["Origin"] = BASE
        hdrs["Referer"] = f"{BASE}/order/"
        if headers:
            hdrs.update(headers)
        body = urllib.parse.urlencode(data).encode() if data else None
        # --- 複製結束 ---
        tag = ("step0_session" if data is None and self._n == 0
               else "loc" if "order_localization" in url
               else "step1_update" if data and data.get("mode") == "step_1_update"
               else "menu")
        req = urllib.request.Request(url, data=body, headers=hdrs)
        rec = {"tag": tag, "url": url, "method": "POST" if body else "GET",
               "request_headers": list(req.header_items()),
               "request_body_keys": list(data.keys()) if data else None,
               "cookies_before": [c.name for c in self._cj]}
        t0 = time.monotonic()
        try:
            with self._opener.open(req, timeout=timeout) as resp:
                raw = resp.read()
                rec["final_url"] = resp.geturl()
                text = self._capture(rec, raw,
                                     getattr(resp, "status", resp.getcode()),
                                     resp.headers, t0)
                rec["cookies_after"] = [c.name for c in self._cj]
                return text
        except urllib.error.HTTPError as e:
            raw = e.read()
            rec["final_url"] = url
            self._capture(rec, raw, e.code, e.headers, t0)
            rec["cookies_after"] = [c.name for c in self._cj]
            raise


def monitored_m1(code: str) -> dict:
    """M1 對照一發（與 production m1_probe 同 headers/payload，加擷取）。"""
    body = urllib.parse.urlencode({"mode": "get_dgtAll", "type_id": "",
                                   "dType": "plu", "txtPLU": code}).encode()
    req = urllib.request.Request(M1_ENDPOINT, data=body, headers=dict(M1_HEADERS))
    rec = {"tag": "m1", "url": M1_ENDPOINT, "method": "POST",
           "request_headers": list(req.header_items()), "cookies_before": []}
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            raw = resp.read()
            rec.update(status=getattr(resp, "status", resp.getcode()),
                       response_headers=list(resp.headers.items()),
                       elapsed_s=round(time.monotonic() - t0, 3),
                       body_len=len(raw),
                       sha256_16=hashlib.sha256(raw).hexdigest()[:16],
                       final_url=resp.geturl())
            text = raw.decode("utf-8", errors="replace")
            rec["markers"] = scan_markers(text)
            try:
                rec["m1_success"] = (json.loads(text.lstrip("\ufeff")).get("success")
                                     is True)
            except Exception:
                rec["m1_success"] = "parse-fail"
    except urllib.error.HTTPError as e:
        raw = e.read()
        rec.update(status=e.code,
                   response_headers=list(e.headers.items()),
                   elapsed_s=round(time.monotonic() - t0, 3), body_len=len(raw),
                   sha256_16=hashlib.sha256(raw).hexdigest()[:16])
        rec["markers"] = scan_markers(raw.decode("utf-8", errors="replace"))
        rec["m1_success"] = None
    (CAPTURES / "05_m1.bin").write_bytes(raw)
    rec["file"] = "05_m1.bin"
    return rec


def main() -> int:
    state = json.loads((REPO / "data" / "scan_state.json").read_text(encoding="utf-8"))
    alive = sorted(c for c, r in state["codes"].items() if r.get("status") == "alive")
    seed = alive[0]
    ip = socket.getaddrinfo("www.pizzahut.com.tw", 443)[0][4][0]
    print("=== probe 2026-11-14：第一筆 step2 請求重現＋全程監測 ===")
    print(f"時間 {dt.datetime.now().isoformat(timespec='seconds')}"
          f"｜seed={seed}（state 第一個 alive，= 生產 confirm 的首碼）"
          f"｜www.pizzahut.com.tw 解析 IP={ip}")
    print(f"路徑＝prepare 前置 3 發 → menu GET 1 發 → M1 對照 1 發；預算上限 {REQUEST_CAP}\n")

    s = MonitoredSession(DEFAULT_STORE)
    outcome = "unknown"
    try:
        s.prepare(seed)
        print("prepare 前置 1-3：OK（users_session_id 已配發、llcs 已取、門市已選）")
        html = s.fetch_menu(seed)
        print(f"menu GET：OK——len={len(html)}、is_menu_page={is_menu_page(html)}")
        outcome = "ok"
    except urllib.error.HTTPError as e:
        print(f"階段中斷：HTTP {e.code}（is_rate_limited={is_rate_limited(e)}）")
        outcome = f"http-{e.code}"
    except RuntimeError as e:
        print(f"prepare 前置失敗（RuntimeError）：{e}")
        outcome = "prepare-fail"
    except Exception as e:  # noqa: BLE001
        print(f"{type(e).__name__}: {e}")
        outcome = "error"

    m1rec = monitored_m1(seed)
    print(f"\nM1 對照：HTTP {m1rec.get('status')}"
          f"｜success={m1rec.get('m1_success')}｜len={m1rec.get('body_len')}")

    print("\n=== 逐步紀錄 ===")
    for r in s.records + [m1rec]:
        mk = r.get("markers") or {}
        print(f"[{r['tag']}] {r['method']} → HTTP {r.get('status')}"
              f"｜len={r.get('body_len')}｜{r.get('elapsed_s')}s"
              f"｜關鍵字={mk.get('keyword_hits')}｜title={mk.get('title')}"
              f"｜cookie 前→後 {r.get('cookies_before')}→{r.get('cookies_after')}"
              f"｜檔={r.get('file')}")

    allrec = s.records + [m1rec]
    (CAPTURES / "summary.json").write_text(
        json.dumps({"run_at": dt.datetime.now().isoformat(timespec="seconds"),
                    "seed": seed, "outcome": outcome, "records": allrec},
                   ensure_ascii=False, indent=1), encoding="utf-8")

    bad = [r for r in allrec if r.get("status") != 200]
    if bad:
        r = bad[0]
        print(f"\n=== 非 200 詳情：[{r['tag']}] HTTP {r['status']} ===")
        for k, v in r.get("response_headers", []):
            print(f"  {k}: {v}")
        body = (CAPTURES / r["file"]).read_bytes().decode("utf-8", errors="replace")
        print(f"--- 回應體前 1200 字 ---\n{body[:1200]}")
    else:
        print("\n=== 全數 200——本地 IP 未被擋（結論推論見報告） ===")
    print(f"\ncaptures 與 summary.json 存於 {CAPTURES}")
    print(f"outcome={outcome}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
