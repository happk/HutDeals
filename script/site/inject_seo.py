"""HutDeals site — 把 SEO 片段灌入 dist/index.html（deploy 專用）。

讀 public/seo-noscript.html + public/seo-ld.json，注入到 dist/index.html：
  - <noscript data-seo>…</noscript> 緊接 <div id="root"></div> 之後
    （JS 生效時 React 接管，noscript 自動隱藏；爬蟲則看到明文清單）
  - <script type="application/ld+json" data-seo>…</script> 置於 </head> 之前

冪等：以 data-seo 標記定位，已存在即取代、不重複插入。
片段缺檔時警告後 exit 0（不擋 deploy；首頁退回純 SPA，不壞版）。

用法（deploy-pages.yml，npm run build 之後）：
    python -m script.site.inject_seo
"""
import json
import re
import sys

from script.lib.repo import REPO

PUBLIC = REPO / "public"
DIST_INDEX = REPO / "dist" / "index.html"
NOSCRIPT_PATH = PUBLIC / "seo-noscript.html"
LD_PATH = PUBLIC / "seo-ld.json"

ROOT_RE = re.compile(r'<div\s+id=["\']root["\'][^>]*>\s*</div>')
NOSCRIPT_RE = re.compile(r'<noscript data-seo="1">.*?</noscript>', re.S)
LD_RE = re.compile(r'<script type="application/ld\+json" data-seo="1">.*?</script>', re.S)


def main() -> int:
    if not DIST_INDEX.exists():
        print("ERROR: dist/index.html 不存在（先跑 npm run build）", file=sys.stderr)
        return 1
    if not (NOSCRIPT_PATH.exists() and LD_PATH.exists()):
        print("WARN: SEO 片段缺檔，跳過注入（首頁維持純 SPA）")
        return 0

    noscript_inner = NOSCRIPT_PATH.read_text(encoding="utf-8")
    ld_json = LD_PATH.read_text(encoding="utf-8").strip()
    try:
        json.loads(ld_json)  # 壞檔不上線：fail-closed，直接擋 deploy
    except json.JSONDecodeError as e:
        print(f"ERROR: seo-ld.json 非法 JSON（{e}），拒絕注入", file=sys.stderr)
        return 1
    noscript_tag = f"<noscript data-seo=\"1\">\n{noscript_inner}</noscript>"
    ld_tag = (
        "<script type=\"application/ld+json\" data-seo=\"1\">"
        f"{ld_json}</script>"
    )

    doc = DIST_INDEX.read_text(encoding="utf-8")

    # noscript：已存在即取代，否則接在 #root 之後
    if NOSCRIPT_RE.search(doc):
        doc = NOSCRIPT_RE.sub(lambda _: noscript_tag, doc, count=1)
    else:
        m = ROOT_RE.search(doc)
        if not m:
            print("ERROR: dist/index.html 找不到 #root 掛載點", file=sys.stderr)
            return 1
        doc = doc[: m.end()] + f"\n    {noscript_tag}" + doc[m.end():]

    # JSON-LD：已存在即取代，否則插在 </head> 之前
    if LD_RE.search(doc):
        doc = LD_RE.sub(lambda _: ld_tag, doc, count=1)
    elif "</head>" in doc:
        doc = doc.replace("</head>", f"    {ld_tag}\n  </head>", 1)
    else:
        print("ERROR: dist/index.html 找不到 </head>", file=sys.stderr)
        return 1

    DIST_INDEX.write_text(doc, encoding="utf-8")
    print(f"inject_seo: noscript + JSON-LD 已注入 -> {DIST_INDEX}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
