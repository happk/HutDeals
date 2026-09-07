# -*- coding: utf-8 -*-
"""20 號抽樣實抓：驗證每張券選單版的結構化價格來源 + 組標題 cat。

目的（2026-09-07 規格）：在改全量前，實抓跨型號碼，回答
  A) 結構化價格(descPrice/套餐價格/price_selling)抓不抓得到 → 判斷哪些券會需要 Q1b fallback
  B) 組標題 → cat 是否正確（大/小/個人比薩/副食/飲料）
只抓不寫（不寫 scan_state / coupons.js），遵守禮節（BatchFetcher 共用 session + sleep_scan）。

輸出：stdout 逐張對照表；另存 exp_prob/sample20_result.json。
用法：python exp_prob/probe_sample_20.py
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(r"D:\Desktop\work\project\20260903_PizzaHut-Coupon-Scraper")
sys.path.insert(0, str(REPO))

from script.lib.orderflow import BatchFetcher, fetch_and_parse  # noqa: E402
from script.lib.pacing import sleep_scan  # noqa: E402
from script.scan.parse_step2 import extract_html_price  # noqa: E402
from script.scan.parse_orderflow import _FOOD_SUBJECT_RE  # noqa: E402

# 20 號抽樣：跨券型 + 你點出的 93015/93023/93022 + 各尺寸/加購/基準/官方池
SAMPLE = [
    "26898", "26868", "16015",      # +49 加購型（現 price 錯抓 95，應 144）
    "16013", "26975", "26976",      # 基準型/套餐（16013 已知 399）
    "93015", "93023", "93022",      # 你點出「網頁看得到」的起價型（官方池 9 開頭）
    "26880", "16010", "94199",      # 大組合 / 6吋個人 / 13吋大(組標題含尺寸)
    "16050", "16051", "16060",      # 大+小組合 / 尺寸多元
    "16002", "16003", "16004",      # 9吋特價套餐（驗小比薩 / 起價）
    "16142", "26979", "26701", "16088",  # 其他代表
]

_PRICE_EL_RE = (
    (r'class="descPrice[^"]*"[^>]*>\s*(?:NT\\?\$)?\$\s*([\d,]+)', "descPrice"),
    (r'套餐價格[：:]\s*(?:NT\\?\$)?\$\s*([\d,]+)', "套餐價格"),
    (r'price_selling\s*[:=]\s*"?(\d+)"?', "price_selling"),
)


def main() -> int:
    print(f"抽樣 {len(SAMPLE)} 張，開始實抓（共用 session）…", flush=True)
    fetcher = BatchFetcher()
    out: dict = {}
    for i, code in enumerate(SAMPLE):
        try:
            r = fetch_and_parse(code, fetcher)
        except Exception as e:  # noqa: BLE001
            print(f"  {code}: FAIL {e}", flush=True)
            out[code] = {"error": str(e)}
            sleep_scan(i, SAMPLE)
            continue
        if r is None:
            print(f"  {code}: None（抓取/解析失敗）", flush=True)
            out[code] = {"error": "None"}
            sleep_scan(i, SAMPLE)
            continue
        html = r["html"]
        meta = r["meta"]
        hp = extract_html_price(html)
        raw_price_els = []
        for pat, name in _PRICE_EL_RE:
            vals = [int(m.group(1).replace(",", "")) for m in re.finditer(pat, html)
                    if int(m.group(1).replace(",", "")) > 0]
            if vals:
                raw_price_els.append((name, vals[:5]))
        subjects = _FOOD_SUBJECT_RE.findall(html)
        items = r["items"] or []
        cats = []
        seen = set()
        for it in items:
            k = (it.get("group"), it.get("groupIdx"))
            if k not in seen:
                seen.add(k)
                cats.append((k, it.get("cat"), it.get("groupTitle"), it.get("text")))
        out[code] = {
            "title": meta.get("title"),
            "old_price": None,
            "price_meta": meta.get("price"),
            "price_struct": hp,
            "price_elements": raw_price_els,
            "subjects": subjects,
            "cat_preview": cats[:8],
        }
        print(f"  {code}: {meta.get('title')}", flush=True)
        sleep_scan(i, SAMPLE)

    state = json.loads((REPO / "data" / "scan_state.json").read_text(encoding="utf-8"))
    for code in out:
        if code in state.get("codes", {}):
            out[code]["old_price"] = state["codes"][code].get("price")

    print("\n===== 對照表 =====")
    for code, d in out.items():
        print(f"\n== {code} {d.get('title')}")
        print(f"   舊price={d.get('old_price')} | 新meta.price={d.get('price_meta')} | "
              f"struct抽={d.get('price_struct')}")
        if d.get("price_elements"):
            print(f"   頁內結構化價元素: {d['price_elements']}")
        if d.get("subjects"):
            print(f"   組標題: {d['subjects']}")
        for (g, gi), cat, gt, txt in (d.get("cat_preview") or []):
            print(f"     {g}{gi} cat={cat} |「{gt}」| e.g.{txt[:18]}")

    out_path = REPO / "exp_prob" / "sample20_result.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n存檔: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
