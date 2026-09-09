"""HutDeals lib — 「項」分類（HutDeals 自己的分類，與官網組型無關）。

模型（2026-09-09 使用者逐點拍板）：
- **「項」= 前端一個選購區塊 = 一個選項組**（`group`+`groupIdx`）。分類掛在項上。
- **飲料／副食／義大利麵飯 ← 看該項裡的每個候選品名**（單一詞彙表）。
- **大／小／個人／特殊比薩 ← 讀該項的官方組標題**（候選品名不含尺寸；131 種品名實測）。
- **完全不看官網組型 `main`/`second`/`add` 來決定分類**：官網不嚴謹——實測
  「請選擇1份飲料」的組內混有黃金雞軟骨/薯金幣（105 組），「請選擇1份副食」的
  組內有 9 組整組是百事可樂/七喜；step_2 頁面也沒有「每個產品自己的分類」欄位。
- **加購（add）項不參與分類**（前端仍顯示「加購（N 種）」）。
- **scan_state 保持官網原貌**（不寫本模組的分類）；分類只在產出 coupons.js 時套用，
  所以改分類規則只要重跑 build、不必重掃。

詞彙只有這一份：新增飲料／麵飯品項只改本檔。
"""
from __future__ import annotations

# 飲料關鍵字（2026-09-07 使用者審查：湯算飲料；「檸檬」過寬移除、「茶」過寬改
# 精準「烏龍茶」；09-08 補「柚茶」；09-09 補 奶茶／果茶／氣泡／飲 涵蓋新品名）
DRINK_KW = ("可樂", "七喜", "雪碧", "汽水", "紅茶", "綠茶", "烏龍茶", "柚茶",
            "咖啡", "玉米濃湯", "濃湯", "果汁", "奶茶", "果茶", "氣泡", "飲")
# 排除詞：名稱含下列字樣即使命中關鍵字也不算飲料（防茶碗蒸/湯餃誤判）
DRINK_EXCLUDE = ("茶碗蒸", "湯餃", "濃湯麵")

# 麵飯關鍵字（實測麵飯項候選全部含「麵」或「飯」；唯二的例外是副食雞柳/腿排）
PASTA_KW = ("麵", "飯")
PASTA_EXCLUDE = ("麵包", "飯店")

# 尺寸／餅體類 cat：只從官方組標題取（品名不含尺寸）
SIZE_CATS = ("大比薩", "小比薩", "個人比薩", "特殊比薩", "比薩")

# cat → 篩選標籤白名單（尺寸類由 SIZE_TAG 處理）
CAT_TO_TAG = {"比薩", "義大利麵/飯", "副食", "飲料"}
# 尺寸類 cat → 標籤（尺寸語意 大=13吋 / 小=9吋 / 個人=6吋）
SIZE_TAG = {"大比薩": ("13吋", "大比薩"), "小比薩": ("9吋", "小比薩"),
            "個人比薩": ("6吋", "個人比薩")}
# 混類項標題顯示順序（前端 MealItems.tsx 的 CAT_ORDER 需一致）
CAT_ORDER = ("大比薩", "小比薩", "個人比薩", "特殊比薩", "義大利麵/飯",
             "比薩", "副食", "飲料")

# 會被分類的組型（add 加購不分類）
UNIT_GROUPS = ("main", "second")


def looks_drink(name: str | None) -> bool:
    """品名是否為飲料（單一候選判斷）。"""
    n = name or ""
    if any(x in n for x in DRINK_EXCLUDE):
        return False
    return any(k in n for k in DRINK_KW)


def looks_pasta(name: str | None) -> bool:
    """品名是否為義大利麵／飯（單一候選判斷）。"""
    n = name or ""
    if any(x in n for x in PASTA_EXCLUDE):
        return False
    return any(k in n for k in PASTA_KW)


def cat_of_candidate(name: str | None) -> str | None:
    """單一候選品名 → 飲料／義大利麵飯；判不出回 None（交由該項的尺寸類接手）。"""
    if looks_drink(name):
        return "飲料"
    if looks_pasta(name):
        return "義大利麵/飯"
    return None


def size_cats_of_subject(subject: str | None) -> list[str]:
    """官方組標題 → 尺寸／餅體類 cat（可多個，依優先序）。

    只回 大/小/個人/特殊/比薩；副食／飲料／義大利麵飯一律由候選品名判定
    （組標題實測不可靠）。判不出回 []。
    """
    s = subject or ""
    if not s:
        return []
    out: list[str] = []
    if "大比薩" in s or "大披薩" in s or "13吋" in s:
        out.append("大比薩")
    elif "小比薩" in s or "小披薩" in s or "9吋" in s:
        out.append("小比薩")
    elif "個人比薩" in s or "個人披薩" in s:
        out.append("個人比薩")
    elif "手工義式" in s or "薄比薩" in s or "義式薄" in s or "Flatzz" in s:
        out.append("特殊比薩")
    elif "比薩" in s or "披薩" in s:
        out.append("比薩")
    return out


def classify_units(items: list[dict] | None) -> list[dict]:
    """就地分類 items（寫回每筆的 cat）並回傳項層分類。

    回傳 `[{group, groupIdx, cats: [...]}]`（只含 main/second，依出現順序）。
    `cats` = 該項所有候選 cat 的聯集（混類項會有多個，如 ["副食","飲料"]）。

    規則：候選品名先判（飲料／義大利麵飯）→ 判不出用該項官方組標題的尺寸類
    → 都沒有則「副食」。add（加購）項 cat 設 None、不進回傳。
    """
    units: list[dict] = []
    seen: dict[tuple, dict] = {}
    for it in items or []:
        key = (it.get("group"), it.get("groupIdx"))
        unit = seen.get(key)
        if unit is None:
            unit = {"group": key[0], "groupIdx": key[1], "cats": [],
                    "_base": size_cats_of_subject(it.get("groupTitle"))}
            seen[key] = unit
            units.append(unit)
        if key[0] not in UNIT_GROUPS:
            it["cat"] = None
            continue
        cat = cat_of_candidate(it.get("text"))
        if cat is None:
            cat = unit["_base"][0] if unit["_base"] else "副食"
        it["cat"] = cat
        if cat not in unit["cats"]:
            unit["cats"].append(cat)
    for u in units:
        u.pop("_base", None)
    return [u for u in units if u["group"] in UNIT_GROUPS]


def cat_tags(units: list[dict] | None) -> list[str]:
    """項層分類 → 可進券級篩選標籤的 cat（尺寸類＋白名單，去重排序）。"""
    cats = {c for u in units or [] for c in u.get("cats") or []}
    return sorted(c for c in cats if c in SIZE_TAG or c in CAT_TO_TAG)
