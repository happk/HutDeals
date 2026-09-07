"""HutDeals — 套餐散文 → 結構化 items[]（規則表驅動 v2，hutdeals#08）。

設計原則（2026-09-04 與使用者確認；2026-09-06 重構為規則表驅動）：
- **規則表驅動，不貼個案**：每條規則對應一個「句式類」（corpus 聚類），
  新樣式 → 加/擴規則表條目 + 測試鎖定，禁止 if code == "16020" 式補丁。
- **多級、逐級降級**：L0 清洗 → L1 主項切分 → L2 段內解析 → L3 驗收。
  任一級對某段處理失敗就停在上級狀態，不 throw、不硬拆。
- **UI fallback**：parse_meal 回 None 時前端顯示原文（誠實），不空不壞。
- **輸出分類語意**：所有「或-chain」統一輸出 anchor+choices 形（首項為 anchor），
  讓前端 MealItems 能歸類 披薩口味組／副餐／飲料；不再併單列拍平。
- 規則路線圖（句式類盤點/已覆蓋/待攻克）：docs/parse-rules.md（改規則先讀它）。

層級職責：
    L0 strip_meta    規則表：前綴(碼/通路/套餐內容)／價格後綴(P1-P5,只刪短語不斷尾)
                     ／尾註(*注意/因餅皮/實際供應/若…加價)
    L1 split_main    ＋、空格 買/再加/升級、「送<量詞數字>」無空格形；買一送一/買大送小不切
    L2 parse_segment 規則表 R0-R6：加價購→口味前綴(冒號可省/任選N/N選M)→
                     括號N選M+冒號清單→內聯(A或B-以上口味N選M)→dash等任選→
                     或-chain(括號深度感知 或/／//,統一 anchor 形)→純項
    L3 verify        ≥1 段且無多句散文殘渣（；/補差價）→ items[]；否則 None

MealItem: {text, choices[], add}（schema 不變；分類由前端 MealItems 推導）
"""

from __future__ import annotations

import re

# ============ L0 清洗（規則表） ============

# 前綴：碼前綴／通路前綴／「套餐內容：」
_CODE_LEAD = re.compile(r"^\s*\d{5}\s*[-－]\s*")
_PREFIX = re.compile(r"^\s*(?:外帶|外送)(?:\s*[/／]\s*(?:外帶|外送)|\s*(?:外帶|外送))?\s*")
_SETUP_LEAD = re.compile(r"^\s*套餐內容\s*[:：]\s*")

# 尾註：* 注意事項（*數字=乘號,保留）；樣板句；（若…需另外加價）條件註記
_TRAIL = re.compile(r"\s+\*(?!\d).*$")
_TRAIL_NOTE = re.compile(
    r"\s*[（(]?(?:實際供應以門市為準|因比[薩蕯]餅皮|一筆訂購一份|外送服務為限區服務).*$")
_TRAIL_COND = re.compile(r"\s*[（(]若.*$")

# 價格後綴（L0 只刪「價格短語」，不再切斷後文——16011/16020 教訓：
# 價格可能出現在句中，後面還有下一個主項）
#   P1 括號價值註記：(最高價值$N)/(原價NT$N元)/{最高價值$N}/(最多現省$N)/(現省$N)
#   P5 此套餐合計$N
#   P2 =／- 帶價：=特價NT$489元 / -特價$369 / =NT$132（可帶「起」）
#   P3 起價短語：(NT)$N元起 / $N起（含括號包裹形）
_VALUE_META = re.compile(
    r"\s*[（({]\s*(?:最多)?\s*(?:最高價值|原價|現省)\s*[:：]?\s*"
    r"(?:NT\\?\$|\$)\s*[\d,]+\s*元?\s*[）)}]")
_SETUP_TOTAL = re.compile(r"此套餐合計\s*(?:NT\\?\$|\$)?\s*[\d,]+\s*元?")
_PRICED_TAIL = re.compile(
    r"\s*[=－-]\s*(?:特價\s*)?(?:NT\\?\$|\$)\s*[\d,]+\s*元?\s*起?(?![\d])")
_QI_PRICE = re.compile(
    r"[（({]?\s*(?:特價\s*)?(?:NT\\?\$|\$)\s*[\d,]+\s*元?\s*起\s*[）)}]?")


def strip_meta(text: str) -> str:
    """L0：規則表逐條套用——前綴剝除、價格短語刪除（保留後文）、尾註剝離。"""
    t = text.replace("{", "(").replace("}", ")")
    t = _CODE_LEAD.sub("", t)
    t = _PREFIX.sub("", t)
    t = _SETUP_LEAD.sub("", t)
    t = _VALUE_META.sub("", t)
    t = _SETUP_TOTAL.sub("", t)
    t = _PRICED_TAIL.sub("", t)
    t = _QI_PRICE.sub("", t)
    t = _TRAIL.sub("", t)
    t = _TRAIL_NOTE.sub("", t)
    t = _TRAIL_COND.sub("", t)
    return re.sub(r"\s+", " ", t).strip(" ｜|，,。；;！!？?")


# ============ L1 主項切分 ============

# 空格帶頭的 買/再加/升級（買一送一/買大送小 不切）
_SPLIT_LEAD = re.compile(r"(?<=[^+＋])\s(?=(?:買(?!一|大)|再加|升級))")
# 「送<量詞+數字>」無空格接續形（16020：…薯金幣送1個13吋…）；
# 外送服務（送後非量詞）與 買1送1（送前有數字）不誤切
_SEND_LEAD = re.compile(r"(?<!外)(?<!\d)送(?=\s*\d{1,3}\s*[個份瓶顆條塊杯盒])")
# 「+NN元即享…」= 加購延伸，不獨立成主項（26979: $109 +33元即享 另一比薩）
_ADDON_LEAD = re.compile(r"^\+\s*\d+\s*元?(?:即享|帶回家|升級)")


def split_main(meal: str) -> list[str]:
    """L1：依 +／＋／空格買/再加/升級／送<量詞> 切主項；「NN元即享」加購段併回前項。"""
    raw: list[str] = []
    for part in _SPLIT_LEAD.split(meal):
        for seg in re.split(r"[+＋]|(?<!外)(?<!\d)(?=送\s*\d{1,3}\s*[個份瓶顆條塊杯盒])", part):
            s = seg.strip()
            if s:
                raw.append(s)
    # 併加購段回前一主項（保留 + 記號供 L2 抽 add）
    merged: list[str] = []
    for s in raw:
        if s.startswith(("即享", "帶回家")) and merged:
            merged[-1] = merged[-1] + "+" + s
        elif _ADDON_LEAD.match("+" + s) and merged:
            merged[-1] = merged[-1] + "+" + s
        else:
            merged.append(s)
    return merged


# ============ L2 段內解析（規則表 R0-R6） ============

_ADD_PREFIX = re.compile(r"^\+\s*(?:NT\$?|\$?|[$＄])?\s*(\d+)\s*元?(即享|可樂|帶回家)")
# 內聯 (A或B或C...N選M) 或 (A或B或C-以上口味3選1)
_INLINE_OR_PICK = re.compile(
    r"[（(]([^（）()]{2,60}?或[^（）()]*?)(?:[-－])?(?:以上口味)?\s*(\d)\s*選\s*(\d)\s*[)）]")
# R1 口味前綴：(口味任選N個)/(口味任N個)/(口味N選M個) + 冒號可省 + 清單
_FLAVOR_LEAD = re.compile(
    r"[（(]\s*口味\s*(?:任選?\s*(\d{1,2})\s*個?|(\d{1,2})\s*選\s*(\d{1,2})\s*個?)\s*[)）]\s*[:：]?\s*(.+)$")
# R1b 泛用：(…N選M…): 清單 —— 括號帶 N選M 且後接冒號清單
_COLON_PICK = re.compile(
    r"^(?P<base>.*[（(][^（）()]*?\d{1,2}\s*選\s*\d{1,2}[^（）()]*[)）])\s*[:：]\s*(?P<lst>.+)$")
# 段尾 N選M 註記（可帶「副食/口味/以上」等前綴字）
_TAIL_PICK = re.compile(r"[（(][^（）(){}]{0,8}?(\d{1,2})\s*選\s*(\d{1,2})\s*個?\s*[）)}]$")
# R3 dash 形：『經典口味-A、B、C等任選』
_DASH_PICK = re.compile(
    r"^(?P<base>.+?)[\-－](?P<rest>[^，。]*、[^，。]+?等任選)"
    r"(?P<note>[。]?[（(][^（）()]*[)）])?$")


def _strip_brackets_main(s: str) -> str:
    """把括號內與 N選M 註記抽空，拿來判斷「括號外的或」。"""
    s = re.sub(r"[（(][^（）()]*[)）]", "", s)
    s = re.sub(r"[（(]\s*\d{1,2}\s*選\s*\d{1,2}\s*[)）]", "", s)
    return s


def _split_or(seg: str) -> list[str]:
    """括號深度感知的 或-chain 切分（分隔符：或／／//）。"""
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    for ch in seg:
        if ch in "（(":
            depth += 1
        elif ch in "）)":
            depth = max(0, depth - 1)
        if depth == 0 and (ch == "或" or ch in "／/"):
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


def _strip_tail_pick(s: str) -> str:
    """剝掉段尾的 (N選M)/（N選M）註記（避免 anchor 註記重複）。"""
    return re.sub(r"[（(][^（）(){}]{0,8}?\d{1,2}\s*選\s*\d{1,2}\s*個?\s*[）)}]\s*$", "", s).strip()


def parse_segment(seg: str) -> dict | None:
    """L2：單一主項段 → {text, choices, add}。拆不出回 None（由呼叫端決定留不留）。"""
    seg = seg.strip()
    if not seg:
        return None
    add: str | None = None
    m = _ADD_PREFIX.match(seg)
    if m:
        add = "+" + m.group(1) + (m.group(2) or "")
        seg = seg[m.end():].strip()

    # R0 加價購形態：主項[$NN] +NN元即享 另品（26979）。抽出當 add，主項留前段。
    mm = re.search(r"[+＋]\s*(\d+)\s*元?(即享|帶回家|升級)\s*(.+)$", seg)
    if mm:
        add = f"+{mm.group(1)}元{mm.group(2)}{mm.group(3)}"
        seg = seg[: mm.start()].strip()
    # 抽掉主項尾巴的單價 $NN（如 $109）→ add 補上（僅當後面沒有加價購時）
    mtail = re.search(r"(?:NT\$?|[$＄])\s*([\d,]+)\s*$", seg)
    if mtail and add is None:
        add = f"${mtail.group(1)}"
        seg = seg[: mtail.start()].strip()
    elif mtail and add is not None:
        seg = seg[: mtail.start()].strip()

    seg = seg.replace("{", "(").replace("}", ")")
    choices: list[str] = []

    # R1 口味前綴：(口味任選N個)/(口味任N個)/(口味N選M個) + 冒號可省 + 清單
    #   例：『(口味任選1個)和風章魚燒或…』(無冒號,16020)／『(口味任1個):炙燒豬肉總匯或…』(16058)
    fm = _FLAVOR_LEAD.search(seg)
    if fm:
        head = seg[: fm.start()].strip().strip("，,。：:")
        lst = fm.group(4)
        choices = [c.strip().strip("，,。") for c in re.split(r"或|／|/", lst) if c.strip()]
        if fm.group(1):  # 任選M → (口味數選M)
            note = f"({len(choices)}選{fm.group(1)})"
        else:  # N選M
            note = f"({fm.group(2)}選{fm.group(3)})"
        seg = f"{head} {note}".strip()
        return {"text": seg, "choices": choices, "add": add}

    # R1b 泛用括號N選M＋冒號清單：『1個6吋鬆厚比薩(4選1):四小福或…』(16010)
    cm = _COLON_PICK.match(seg)
    if cm:
        base = cm.group("base").strip()
        nm = re.search(r"[（(][^（）()]*?(\d{1,2})\s*選\s*(\d{1,2})[^（）()]*[)）]\s*$", base)
        choices = [c.strip().strip("，,。") for c in re.split(r"或|／|/", cm.group("lst")) if c.strip()]
        note = f"({nm.group(1)}選{nm.group(2)})" if nm else "(擇一)"
        if not nm:
            seg = f"{base} {note}".strip()
        else:
            seg = base
        return {"text": seg, "choices": choices, "add": add}

    # R4 內聯 (A或B或C…N選M) → choices，anchor 保留
    m = _INLINE_OR_PICK.search(seg)
    if m:
        inner, n_sel, n_all = m.group(1), m.group(2), m.group(3)
        inner_clean = re.sub(r"[-－以上口味]*\s*$", "", inner)
        choices = [c.strip().strip("，,。") for c in inner_clean.split("或") if c.strip()]
        seg = seg[: m.start()] + seg[m.end():]
        seg = f"{seg.strip()} ({n_sel}選{n_all})" if seg.strip() else f"({n_sel}選{n_all})"
        seg = re.sub(r"\s+", " ", seg).strip(" ，,。")
        return {"text": seg, "choices": choices, "add": add}

    # R3 dash 形：『13吋大比薩1個，經典口味-A、B、C等任選』
    md = _DASH_PICK.match(seg)
    if md:
        seg = md.group("base").strip() + (md.group("note") or "")
        choices = [c.strip().strip("，,。") for c in md.group("rest")
                   .removesuffix("等任選").split("、") if c.strip()]
        return {"text": seg, "choices": choices, "add": add}

    # R5 或-chain（括號深度感知）：統一 anchor 形（首項為 anchor,其餘為 choices）,
    # 段尾 N選M 註記正規化到 anchor 上（無則 擇一）——讓前端能歸類 副餐/飲料 組
    main = _strip_brackets_main(seg)
    if len([p for p in main.split("或") if p.strip()]) >= 2 or len(_split_or(seg)) >= 2:
        parts = _split_or(seg)
        note_m = _TAIL_PICK.search(seg)
        if note_m:
            note = f"({note_m.group(1)}選{note_m.group(2)})"
        else:
            note = "(擇一)"
        parts = [_strip_tail_pick(p).strip("，,。") for p in parts]
        anchor = parts[0]
        if not anchor:
            return None
        return {"text": f"{anchor} {note}".strip(), "choices": [c for c in parts[1:] if c], "add": add}

    seg = re.sub(r"\s+", " ", seg).strip(" ，,。！!？?")
    if not seg:
        return None
    return {"text": seg, "choices": choices, "add": add}


# ============ L3 驗收 ============

# 多句散文殘渣（條款式說明非套餐內容）→ 整體回 None 交前端 fallback 原文
_JUNK_MARKS = ("；", "補差價")


def parse_meal(text: str) -> list[dict] | None:
    """og:description → items[]；結構不足回 None（UI fallback 原文）。"""
    meal = strip_meta(text or "")
    if len(meal) < 8:
        return None
    segs = split_main(meal)
    if not segs:
        return None
    items: list[dict] = []
    for s in segs:
        it = parse_segment(s)
        if it:
            items.append(it)
    if not items:
        return None
    # L3 殘渣檢查：任一項含條款式多句殘渣 → 放棄結構化（誠實 fallback）
    for it in items:
        if any(mark in it["text"] for mark in _JUNK_MARKS):
            return None
    return items


if __name__ == "__main__":
    import json
    import sys

    from script.lib.repo import REPO

    corpus = json.loads(
        (REPO / "data" / "raw" / "meal_texts.json").read_text(encoding="utf-8"))
    show = sys.argv[1] if len(sys.argv) > 1 else None
    ok = 0
    for code, txt in corpus.items():
        items = parse_meal(txt)
        if items:
            ok += 1
        if show and show == code:
            print(f"=== {code} ({len(txt)} chars) ===")
            print("RAW:", txt)
            print("ITEMS:", json.dumps(items, ensure_ascii=False, indent=1))
            print()
    print(f"parsed {ok}/{len(corpus)}")
