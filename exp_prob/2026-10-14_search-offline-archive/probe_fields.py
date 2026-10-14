"""唯讀 probe：檢查 coupons.js 欄位完整性與離線判定依據（2026-10-09）

問題：使用者總結「某些數據沒有 status 所以無法追蹤」是否屬實。
檢查：每筆券的 status / source / offlineSince / firstSeen / lastSeen 是否有缺漏，
      以及 build_coupons.merge 對「source 缺失」的券會不會標 offline。

用法：python exp_prob/2026-10-14_search-offline-archive/probe_fields.py
"""

import json
import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def load_coupons():
    src = (REPO / "public" / "coupons.js").read_text(encoding="utf-8")
    m = re.search(r"window\.HUTDEALS_COUPONS\s*=\s*(\{.*\})\s*;?\s*$", src, re.S)
    return json.loads(m.group(1))


def main():
    data = load_coupons()
    coupons = data["coupon_list"]

    print(f"總筆數 {len(coupons)}")
    print("\n== 欄位缺漏統計（0 = 每筆都有）==")
    for f in ("key", "code", "name", "description", "status", "source", "partner",
              "firstSeen", "lastSeen", "offlineSince", "items", "tags", "verifiedAt"):
        miss = [c["key"] for c in coupons if f not in c or c.get(f) is None]
        print(f"  {f:<12} 缺 {len(miss):>3} 筆" + (f"  例: {miss[:6]}" if miss else ""))

    print("\n== status 值分佈 ==")
    print(" ", Counter(c.get("status") for c in coupons))

    print("\n== offline 券的 source 分佈（source=None 會讓 build_coupons 照樣標 offline）==")
    off = [c for c in coupons if c.get("status") != "active"]
    print(" ", Counter(str(c.get("source")) for c in off))
    for c in off[:5]:
        print(f"   {c['key']} source={c.get('source')} offlineSince={c.get('offlineSince')}")

    print("\n== 有無 status 欄位完全缺失（非 active/offline）的券 ==")
    bad = [c for c in coupons if c.get("status") not in ("active", "offline")]
    print(f"  {len(bad)} 筆: {[c['key'] for c in bad][:10]}")

    print("\n== source 缺失(active) 的券 ==")
    nosrc = [c for c in coupons if c.get("status") == "active" and not c.get("source")]
    print(f"  {len(nosrc)} 筆（這些會被 build_coupons 當官網碼，下架就標 offline；"
          f"若實際是外部碼則誤標）例: {[c['key'] for c in nosrc][:8]}")

    print("\n== offline 券是否保留在 coupons.js（60 天後才清）==")
    print(" ", Counter(c.get("offlineSince") for c in off))


if __name__ == "__main__":
    main()