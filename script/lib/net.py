"""HutDeals lib — 網路層（UA/headers、官網 fetch、M1 驗證、step_2 抓取）。

原散落：scan_run.m1_probe/step2_html、scan_probe(scan_codes) 同名、ig_ingest.m1_probe、
probe05.probe、fetch_official.fetch 各自實作 → 統一收此，禁止跨檔複製。
"""
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

__all__ = ["UA", "M1_ENDPOINT", "STEP2_URL", "fetch_html", "m1_probe",
           "fetch_step2_html", "is_rate_limited"]

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
# 官網缺這些 headers 會回空殼頁（實測最小集合 + 瀏覽器常見）
HTML_HEADERS = {
    "User-Agent": UA,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
        "image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}
# step_2 詳情頁（一般 GET，不需完整瀏覽器 header 組）
STEP2_HEADERS = {
    "User-Agent": UA,
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Referer": "https://www.pizzahut.com.tw/order/",
    "Accept": "text/html,*/*;q=0.8",
}
# M1 驗證（XHR POST）
M1_HEADERS = {
    "User-Agent": UA,
    "Origin": "https://www.pizzahut.com.tw",
    "Referer": "https://www.pizzahut.com.tw/order/",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}

M1_ENDPOINT = "https://www.pizzahut.com.tw/order/?m=ajax"
STEP2_URL = "https://www.pizzahut.com.tw/order/?mode=step_2&type_id=1025&cno={code}"


def fetch_html(url: str, headers: dict | None = None, timeout: int = 25,
               retries: int = 3) -> str:
    """GET → HTML 字串。重試 3 次（5s×attempt 退避），全敗丟 RuntimeError。"""
    headers = headers or HTML_HEADERS
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as err:  # noqa: BLE001 — 一律重試
            last_err = err
            if attempt < retries:
                time.sleep(5 * attempt)
    raise RuntimeError(f"fetch failed after {retries} tries: {url}: {last_err}")


def _post_form(url: str, fields: dict, headers: dict, timeout: int = 25) -> bytes:
    body = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def m1_probe(code: str, timeout: int = 25) -> dict:
    """M1 驗證端點：POST get_dgtAll → 解析 JSON dict。

    raise urllib.error.HTTPError（429/403 由呼叫端判斷熔斷）；傳輸錯誤同樣向上拋。
    """
    raw = _post_form(
        M1_ENDPOINT,
        {"mode": "get_dgtAll", "type_id": "", "dType": "plu", "txtPLU": code},
        M1_HEADERS, timeout,
    ).decode("utf-8", errors="replace").lstrip("\ufeff")
    return json.loads(raw)


def fetch_step2_html(code: str, timeout: int = 25) -> str:
    """step_2 套餐詳情頁 HTML（聯名方/通路/價格真值來源）。"""
    req = urllib.request.Request(
        STEP2_URL.format(code=code), headers=STEP2_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def is_rate_limited(err: urllib.error.HTTPError) -> bool:
    """429/403 = 官網限流/擋，掃號要熔斷。"""
    return err.code in (429, 403)
