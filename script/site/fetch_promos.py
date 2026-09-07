"""HutDeals site — 抓必勝客官網優惠列表（site 生產線第一步）。

原 fetch_official.py。網路層改吃 lib/net（fetch_html 統一）；REPO 改吃 lib/repo。

用法:
    python -m script.site.fetch_promos            # 抓 type=plu + type=dgt,存 data/raw/
    python -m script.site.fetch_promos --quiet    # 只輸出摘要

官網兩種列表 markup 都支援:
  A. div.pdpop-li[data-plu] + p.pdpop-name + div.pdpop-price(目前使用,代碼在 data-plu)
  B. div.promotion_list_item[data-id-real] + .pro-li-name + .pro-list-descContent(較舊,無代碼)
"""
import argparse
import datetime as dt
import json
import re
import sys

from script.lib.net import fetch_html
from script.lib.repo import REPO
from script.lib.text import clean_text

RAW_DIR = REPO / "data" / "raw"
PROMO_URL = "https://www.pizzahut.com.tw/promotions/?mode=cpSch&type={type}"


def parse_pdpop_html(html: str) -> list[dict]:
    """變體 A:div.pdpop-li[data-plu],分類在 <details><summary><h3>。"""
    items: list[dict] = []
    for chunk in re.split(r"<details\b", html)[1:]:
        cat_m = re.search(r"<summary><h3[^>]*>([^<]+)", chunk)
        category = clean_text(cat_m.group(1)) if cat_m else None
        for block in re.split(r'class="pdpop-li"', chunk)[1:]:
            code_m = re.search(r'data-plu="([^"]+)"', block)
            name_m = re.search(r"pdpop-name\">([^<]+)", block)
            desc_m = re.search(r'pdpop-price">(.*?)</div>', block, re.S)
            img_m = re.search(r'<img[^>]+src="([^"]+)"', block)
            if not (code_m and name_m):
                continue
            items.append(
                {
                    "source": "pdpop",
                    "code": code_m.group(1),
                    "name": clean_text(name_m.group(1)),
                    "description": (
                        clean_text(re.sub(r"<[^>]+>", "", desc_m.group(1)))
                        if desc_m else None
                    ),
                    "image": img_m.group(1) if img_m else None,
                    "category": category,
                }
            )
    return items


def parse_promos_page(html: str) -> list[dict]:
    """變體 B:div.promotion_list_item[data-id-real](無代碼,以 p_id 為 id)。"""
    items: list[dict] = []
    for block in re.split(r'class="promotion_list_item', html)[1:]:
        id_m = re.search(r'data-id-real="([^"]+)"', block)
        name_m = re.search(r"pro-li-name\">([^<]+)", block)
        desc_m = re.search(r"pro-list-descContent[^>]*>(.*?)</div>", block, re.S)
        img_m = re.search(r'data-src="([^"]+)"', block)
        link_m = re.search(r'href="(\?mode=step_2[^"]+)"', block)
        if not (id_m and name_m):
            continue
        items.append(
            {
                "source": "promotion_list",
                "code": None,
                "id": id_m.group(1),
                "name": clean_text(name_m.group(1)),
                "description": (
                    clean_text(re.sub(r"<[^>]+>", "", desc_m.group(1)))
                    if desc_m else None
                ),
                "image": img_m.group(1) if img_m else None,
                "orderUrl": (
                    "https://www.pizzahut.com.tw/promotions/" + link_m.group(1)
                    if link_m else None
                ),
            }
        )
    return items


def parse_page(html: str) -> list[dict]:
    """Try A 變體;空則退 B 變體（自動偵測兩種 markup）。"""
    items = parse_pdpop_html(html)
    if not items:
        items = parse_promos_page(html)
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description="HutDeals official fetcher")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    summary: dict = {"fetched_at": dt.datetime.now().isoformat(timespec="seconds"),
                     "pages": {}}
    total = 0

    for page_type in ("plu", "dgt"):
        html = fetch_html(PROMO_URL.format(type=page_type))
        raw_path = RAW_DIR / f"{stamp}-{page_type}.html"
        raw_path.write_text(html, encoding="utf-8")
        items = parse_page(html)
        summary["pages"][page_type] = {
            "raw": str(raw_path.relative_to(REPO)),
            "bytes": len(html),
            "items": len(items),
        }
        total += len(items)
        if not args.quiet:
            print(f"[{page_type}] {len(items)} items -> {raw_path.name}")
            for it in items[:5]:
                print("   ", json.dumps(it, ensure_ascii=False)[:160])

    summary["total"] = total
    (RAW_DIR / f"{stamp}-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.quiet:
        print(f"total items: {total}")
    # 官網連基本項目都沒有 = 抓法失效或官網改版,讓 CI 告警
    return 0 if total > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
