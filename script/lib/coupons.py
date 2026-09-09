"""HutDeals lib — public/coupons.js 讀寫（全 repo 唯一一份）。

原散落兩套：build_coupons.load_existing/write_coupons_js + 內聯 sort 鍵、
ingest_external.load_coupons_js + main 內聯 writer + 內聯 sort 鍵 → 統一收此。
write_coupons_full 產 admin 分頁用的全量資料檔（2-3，2026-09-05）。
"""
import json
from pathlib import Path

__all__ = ["DATA_MARKER", "COUPONS_JS", "load_coupons_js", "write_coupons_js",
           "FULL_DATA_MARKER", "COUPONS_FULL_JS", "write_coupons_full",
           "coupon_sort_key", "official_keys"]

from script.lib.repo import REPO  # noqa: E402

DATA_MARKER = "window.HUTDEALS_COUPONS = "
COUPONS_JS = REPO / "public" / "coupons.js"
FULL_DATA_MARKER = "window.HUTDEALS_FULL = "
COUPONS_FULL_JS = REPO / "public" / "coupons_full.js"
# coupons.js 檔頭註解（build + ingest 都寫同一行，避免每輪 commit 震盪）
_HEADER_COMMENT = (
    "// 由 script/site/build_coupons.py + script/site/ingest_external.py 產生；"
    "HutDeals 每日自動更新。\n"
)


def load_coupons_js(path: Path = COUPONS_JS) -> dict:
    """讀 coupons.js → {key: coupon}；缺檔/損壞回 {}。"""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    idx = text.find(DATA_MARKER)
    if idx < 0:
        return {}
    try:
        payload = json.JSONDecoder().raw_decode(text[idx + len(DATA_MARKER):])[0]
    except json.JSONDecodeError:
        return {}
    return {c["key"]: c for c in payload.get("coupon_list", [])}


def compact_coupon_items(coupon: dict) -> dict:
    """coupons.js 輸出去重：完整 items(每候選帶 flavors) → flavorSets + flavorIdx。

    scan_state(資料庫)存完整 flavors；coupons.js(輸出)才去重以縮體積。
    - 每券 flavors 去重成券級 flavorSets，候選 flavorIdx 引用（2a 券內去重）
    - 加價數字因券而異，故只做券內去重、不跨券共用（加價留在 flavors 內）
    - group=add 通用加購不進 coupons.js（與券無關，之後抽獨立表）
    回傳複製的 coupon（不動原物件）。

    ⚠ 2026-09-08 冪等化：build/enrich 從 coupons.js load 回來的券已是 compact 格式
    (items 帶 flavorIdx、無 flavors)。對這種再跑一次 compact 會因無 flavors 可抽
    → flavorIdx 全清空(flavorSets 丟失 bug)。偵測到已是 compact 格式則原樣保留。
    """
    out = dict(coupon)
    items = coupon.get("items")
    if not items:
        out["flavorSets"] = []
        return out

    # 冪等：已是 compact 格式(有 flavorIdx 且無 flavors 欄) → 直接回傳
    if any("flavorIdx" in it for it in items) and not any("flavors" in it for it in items):
        if "flavorSets" not in out:
            out["flavorSets"] = []
        return out

    flavor_sets: list[list[dict]] = []
    flavor_index: dict[str, int] = {}
    new_items: list[dict] = []

    def _set_idx(flavors) -> int | None:
        if not flavors:
            return None
        key = json.dumps([[f["name"], f.get("priceAdd") or 0] for f in flavors],
                         ensure_ascii=False)
        if key not in flavor_index:
            flavor_index[key] = len(flavor_sets)
            flavor_sets.append([{"name": f["name"], "priceAdd": f.get("priceAdd") or 0}
                                for f in flavors])
        return flavor_index[key]

    for it in items:
        # 通用加購(group=add)不進 coupons.js：各券加購價格不一、非全站通用
        # (2026-09-08 評估後不抽獨立表)
        if it.get("group") == "add":
            continue
        ni = dict(it)
        fls = ni.pop("flavors", None) or None
        ni["flavorIdx"] = _set_idx(fls)
        # groupTitle（官方組名原文）只留 scan_state 溯源用，不進輸出（2026-09-07）
        ni.pop("groupTitle", None)
        new_items.append(ni)

    out["items"] = new_items
    out["flavorSets"] = flavor_sets
    return out


def write_coupons_js(coupons: list[dict], last_update: str,
                     path: Path = COUPONS_JS) -> None:
    """序列化 {coupon_list, count, last_update} → coupons.js（DATA_MARKER + minified）。

    寫入前對每券 items 做去重轉換（compact_coupon_items）：scan_state 完整格式
    → coupons.js flavorSets 格式。build + ingest + enrich 統一由此輸出。
    """
    compacted = [compact_coupon_items(c) for c in coupons]
    payload = {"coupon_list": compacted, "count": len(compacted),
               "last_update": last_update}
    body = DATA_MARKER + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";"
    path.write_text(_HEADER_COMMENT + body, encoding="utf-8")


def scan_summary() -> dict | None:
    """data/scan_state.json → 掃號池摘要（admin 進度分頁用）；缺檔/損壞回 None。

    updatedAt：state 最後寫入（掃描最後執行）；lastChanged：池內實質更動
    （內容變更 contentChangedAt／死亡 dead_since／新入庫 firstSeen）的最晚日期，
    三者皆無回 None。"""
    from script.lib.state import STATE_PATH, load_state
    state = load_state(STATE_PATH)
    codes = state.get("codes") or {}
    if not codes:
        return None
    by_status: dict[str, int] = {}
    changed: list[str] = []
    for rec in codes.values():
        s = rec.get("status") or "unknown"
        by_status[s] = by_status.get(s, 0) + 1
        for d in (rec.get("contentChangedAt"), rec.get("dead_since"), rec.get("firstSeen")):
            if isinstance(d, str) and len(d) >= 10:
                changed.append(d[:10])
    return {
        "updatedAt": state.get("updatedAt"),
        "lastChanged": max(changed) if changed else None,
        "total": len(codes),
        "alive": by_status.get("alive", 0),
        "dead": by_status.get("dead", 0),
        "unknown": by_status.get("unknown", 0) + sum(
            v for k, v in by_status.items() if k not in ("alive", "dead", "unknown")
        ),
    }


def write_coupons_full(coupons: list[dict], last_update: str,
                       path: Path = COUPONS_FULL_JS) -> None:
    """全量資料檔（admin.html 用）：coupons.js 同內容 + active/offline 統計 + 掃號摘要。

    與 write_coupons_js 冪等（同輸入同輸出），build/ingest 誰後跑誰覆蓋。
    同樣先對每券 items 去重（compact_coupon_items）。
    """
    active = sum(1 for c in coupons if c.get("status") == "active")
    compacted = [compact_coupon_items(c) for c in coupons]
    payload = {
        "coupon_list": compacted,
        "count": len(compacted),
        "last_update": last_update,
        "stats": {"active": active, "offline": len(compacted) - active},
        "scan": scan_summary(),
    }
    body = FULL_DATA_MARKER + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";"
    path.write_text(_HEADER_COMMENT + body, encoding="utf-8")


def coupon_sort_key(coupon: dict):
    """coupons.js 排序鍵：active 在前、有價格者優先、價低者前、最後按 key。"""
    return (coupon.get("status") != "active",
            coupon.get("price") is None,
            coupon.get("price") or 0,
            str(coupon.get("key")))


def official_keys(coupons: dict) -> set[str]:
    """非 external 的 key 集合（代理「官網集」：ingest 用來排除衝突）。"""
    return {k for k, c in coupons.items() if c.get("source") != "verified-external"}
