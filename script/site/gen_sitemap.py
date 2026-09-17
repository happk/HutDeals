"""HutDeals site — 產生 public/sitemap.xml（主站 + 各券深連結）。

在 update.yml 每日 build_coupons 後跑：讀 public/coupons.js 的活躍券，
產 sitemap.xml（含 `/HutDeals/?code=XXX` 深連結，讓 Google 個別索引每張券）。

注意：全站 canonical 指向主站（index.html），搜尋引擎會把 ?code= 視為
主站的重複頁——此處深連結僅當「爬蟲發現路徑＋使用者分享 modal 落地」，
不期待單券獨立排名（SPA 單頁架構的先天限制）。真要單券排名需每券靜態頁，
超出目前範圍。

用法：python -m script.site.gen_sitemap
"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape as xml_escape

REPO = Path(__file__).resolve().parents[2]
COUPONS_JS = REPO / "public" / "coupons.js"
SITEMAP = REPO / "public" / "sitemap.xml"

# GitHub Pages 部署網址（public repo 上線後）
BASE = "https://happk.github.io/HutDeals/"


def load_coupons() -> list[dict]:
    txt = COUPONS_JS.read_text(encoding="utf-8")
    m = re.search(r"window\.HUTDEALS_COUPONS\s*=\s*(\{.*?\});?\s*$", txt, re.S)
    if not m:
        raise SystemExit("coupons.js 解析失敗")
    obj = json.loads(m.group(1))
    return obj.get("coupon_list") or []


def main() -> int:
    coupons = load_coupons()
    active = [c for c in coupons if c.get("status") == "active"]
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        "  <url>",
        f"    <loc>{BASE}</loc>",
        "    <changefreq>daily</changefreq>",
        "  </url>",
    ]
    for c in active:
        # 與 gen_seo.coupon_url 同政策：缺 code 回退 key，並做 URL/XML 跳脫。
        # （今日資料 code==key 全數字，輸出與舊版位元一致；防未來特殊字元。）
        target = c.get("code") or c.get("key")
        if not target:
            continue
        url = f"{BASE}?code={quote(str(target), safe='')}"
        lines += [
            "  <url>",
            f"    <loc>{xml_escape(url)}</loc>",
            "    <changefreq>weekly</changefreq>",
            "  </url>",
        ]
    lines.append("</urlset>")
    SITEMAP.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"sitemap.xml: 主站 + {len(active)} 張活躍券深連結 -> {SITEMAP}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
