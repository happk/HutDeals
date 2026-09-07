"""HutDeals scan — 訂餐流程選單版解析（結構化 items，取代文本 parse_meal）。

2026-09 訂餐後端探索實證：step_1 選門市後重抓的 step_2
頁（「選單版」213~391KB）內嵌完整結構化資料——候選口味/升級價差/餅皮選項/加購物，
等同官網點餐後端直接給的選單，不需再從套餐散文猜。

輸入：選單版 HTML + extract_js.cjs 抽出的 JS 變數 dict（psidss/pprcss/ctidss/
pltdss/exTopping）。
輸出：結構化中介 dict（保留候選/加價/口味完整資訊，供未來前端進階用）+
維持 MealItem 契約的 items[]（{text, choices[], add: string|null}，前端現況可吃）。

資料源：
  psidss.{main,second,add}[組]     各組產品 id
  pprcss[組][產品id] 或 flat dict   候選升級價差 add（兩種架構都遇過）
  ctidss.v/t/p["g{組}_{產品id}"]    該產品口味候選(id/名/加價)
  DOM .pdpop-name / .pd_name        產品名稱
  DOM .show_price / .pdpop-price   加購物價
"""
from __future__ import annotations

import json
import re
from html import unescape

# ============ 組分類（cat）============
#
# 2026-09-07 使用者：組標題(main_food_subject)是官方「組名」第一手來源——
#   「請選擇1個大比薩」(26880組1 / 94199「13吋大比薩」)= 大比薩(13吋)
#   「請選擇1個個人比薩」(26868/16010)= 個人比薩(6吋)
#   副食組：整組候選全飲料（湯也算飲料）→「飲料」；只要任一非飲料 →「副食」（用語副食）
# 尺寸對照（使用者 2026-09-07 更正）：大=13吋 / 小=9吋 / 個人=6吋
_FOOD_SUBJECT_RE = re.compile(
    r'id="(main|second)_food_subject_(\d+)" value="([^"]*)"')

# 2026-09-07 使用者審查定稿：湯算飲料；檸檬過寬(恐誤判檸檬雞翅)移除；
# 茶過寬(恐誤判茶碗蒸)改精準「烏龍茶」
_DRINK_KW = ("可樂", "七喜", "雪碧", "汽水", "紅茶", "綠茶", "烏龍茶",
             "咖啡", "玉米濃湯", "濃湯", "果汁")


def _cat_of_subject(subject: str) -> str | None:
    """組標題 → cat（2026-09-07 使用者確認完整分類）。

    以官網組標題(main_food_subject value)為準；只影響顯示分類(cat)、不動 group。
    規則順序(先比尺寸/特殊、後中性)：
      1. 大比薩/13吋 → 大比薩
      2. 小比薩/9吋 → 小比薩
      3. 個人比薩 → 個人比薩
      4. 義大利麵/飯/筆管麵/千層麵/飯麵 → 義大利麵/飯(新類)
      5. 副食/煎餅/點心 → 副食
      6. 含比薩/披薩(無尺寸，如手工義式薄比薩) → 中性 比薩
      7. 其它 → None(呼叫端 fallback)
    """
    if not subject:
        return None
    if "大比薩" in subject or "大披薩" in subject or "13吋" in subject:
        return "大比薩"
    if "小比薩" in subject or "小披薩" in subject or "9吋" in subject:
        return "小比薩"
    if "個人比薩" in subject or "個人披薩" in subject:
        return "個人比薩"
    # 特殊比薩：非典型餅體(手工義式薄比薩/Flatzz 等)，獨立類(2026-09-07 使用者)
    if re.search(r"手工義式|薄比薩|義式薄|Flatzz", subject):
        return "特殊比薩"
    if ("義大利麵" in subject or "筆管麵" in subject
            or "千層麵" in subject or "飯麵" in subject or "飯" in subject):
        return "義大利麵/飯"
    if "副食" in subject or "煎餅" in subject or "點心" in subject:
        return "副食"
    if "比薩" in subject or "披薩" in subject:
        return "比薩"
    return None


def _all_drink(names: list[str]) -> bool:
    """整組候選是否全為飲料/湯品（湯算飲料；2026-09-07 使用者確認）。"""
    return bool(names) and all(
        any(kw in (n or "") for kw in _DRINK_KW) for n in names)


# ============ DOM 抽取 ============

def _find_name(tail: str) -> str:
    m = (re.search(r'class="pdpop-name"[^>]*>([^<]+)<', tail)
         or re.search(r'class="pd_name"[^>]*data-name="([^"]+)"', tail)
         or re.search(r'class="pdName"[^>]*data-name="([^"]+)"', tail)
         or re.search(r'alt="([^"]+)"', tail))
    return unescape(m.group(1)).strip() if m else ''


# 卡片範圍視窗（找 name/price 用；卡片開頭常接長 <script>，勿用脆弱的字串切割）
_CARD_WINDOW = 12000


def _card_name_price_raw(html: str, div_start: int) -> tuple[str, str]:
    """卡片 div 起點 → (name, 價格原始內容)。

    name 錨點：卡片內第一個名稱（.pdpop-name / .pd_name data-name /
    .pdName data-name / optgroup label）；price 只在「同一張卡內」找。
    卡內 = div_start 起到下一個 pdpop-li / 區塊(主餐/副食/加購)交界前。
    ⚠ 2026-09-07 修：原先固定往後 3000 字元，空價卡會跨卡誤抓下一張/加購區
    （16010 可樂卡 .pdpop-price 為空，卻被標 +79=薯金幣）。改限卡內。
    """
    # 卡結束：下一個候選卡起點（mainpop/sndpop/addpop）或該卡所屬容器結束
    _NEXT_CARD = re.compile(
        r'<div class="(?:pdpop-li|s2slt-block)[^"]*" id="(?:mainpop_|sndpop_|addpop_)')
    card_end = div_start + _CARD_WINDOW
    m_next = _NEXT_CARD.search(html, div_start + 1)
    if m_next:
        card_end = m_next.start()
    card = html[div_start:card_end]

    nm = (re.search(r'class="pdpop-name"[^>]*>([^<]+)<', card)
          or re.search(r'class="pd_name"[^>]*data-name="([^"]+)"', card)
          or re.search(r'class="pdName"[^>]*data-name="([^"]+)"', card)
          or re.search(r'<optgroup label="([^"]+)"', card))
    name = unescape(nm.group(1)).strip() if nm else ''
    if nm:
        after = card[nm.end():nm.end() + 3000]
        pr = re.search(r'class="pdpop-price[^"]*"[^>]*>\s*([^<]*)<', after) \
            or re.search(r'class="show_price"[^>]*>\s*([^<]*)<', after)
        if pr:
            return name, pr.group(1).strip()
    # fallback：整卡找 price（卡內）
    pr = re.search(r'class="pdpop-price[^"]*"[^>]*>\s*([^<]*)<', card) \
        or re.search(r'class="show_price"[^>]*>\s*([^<]*)<', card)
    return name, (pr.group(1).strip() if pr else '')


def _parse_price_raw(raw: str) -> tuple[str, int | None]:
    """.pdpop-price 原始 → (型別, 數值)。'+'加價型 / '$'基準型單價 / ''空。"""
    if not raw:
        return ('', None)
    if raw.startswith('+'):
        m = re.search(r'\+\s*\$?\s*([\d,]+)', raw)
        return ('+', int(m.group(1).replace(',', '')) if m else None)
    if raw.startswith('$'):
        m = re.search(r'\$\s*([\d,]+)', raw)
        return ('$', int(m.group(1).replace(',', '')) if m else None)
    return (None, None)


def _resolve_price(cards: list[dict]) -> list[dict]:
    """依券型算 price_add（docs/crawler-data-sources.md）。

    加價型(有+$)：price_add = +$ 值、空 = 0。
    基準型(純$單價)：price_add = 單價 − 該組最低單價。
    """
    has_plus = any('+' in (c.get('price_raw') or '') for c in cards)
    base = None
    if not has_plus:
        prices = [_parse_price_raw(c['price_raw'])[1] for c in cards
                  if c['price_raw'].startswith('$')]
        prices = [p for p in prices if p is not None]
        if prices:
            base = min(prices)
    for c in cards:
        typ, val = _parse_price_raw(c['price_raw'])
        if typ == '+':
            c['price_add'] = val or 0
        elif typ == '$':
            c['price_add'] = (val - base) if (val is not None and base is not None) else 0
        else:
            c['price_add'] = 0
        c.pop('price_raw', None)
    return cards


def _slice(html: str, start: int, maxlen: int = 8000) -> str:
    cuts = []
    for c in ('</div>\n\n\n\n', '<div class="pdpop-li '):
        j = html.find(c, start)
        if j > 0:
            cuts.append(j)
    end = min(cuts) if cuts else min(start + maxlen, len(html))
    return html[start:end]


# ============ 主解析 ============

def parse_orderflow(html: str, extract: dict | None = None) -> dict:
    """選單版 HTML → 結構化中介 dict（候選/加價/口味完整保留）。"""
    # 1) 產品名稱（DOM）
    name_by_key: dict[tuple, str] = {}

    def _grab(block_id: str, pid: str, cls: str) -> None:
        i = html.find('id="' + block_id + '"')
        if i < 0:
            return
        nm = _find_name(html[i:i + 5000])
        if nm:
            name_by_key[(cls, pid)] = nm

    for m in re.finditer(r'id="(mainpop_(\d+)_(\d+))"', html):
        _grab(m.group(1), m.group(3), 'main')
    for m in re.finditer(r'id="(sndpop_(\d+)_(\d+))"', html):
        _grab(m.group(1), m.group(3), 'second')
    for m in re.finditer(r'id="(addpop_(\d+)_(\d+))"', html):
        _grab(m.group(1), m.group(3), 'add')

    groups = {'main': {}, 'second': {}, 'add': {}}

    # 暫存 raw（name + price 原始），再依券型 resolve
    raw_cards: dict[str, dict[str, list[dict]]] = {'main': {}, 'second': {}, 'add': {}}

    # mainpop 候選
    for m in re.finditer(
            r'<div class="pdpop-li[^"]*" id="(mainpop_(\d+)_(\d+))"[^>]*>', html):
        bid, g, pid = m.group(1), m.group(2), m.group(3)
        name, raw = _card_name_price_raw(html, m.start())
        raw_cards['main'].setdefault(g, []).append({
            'product_id': pid,
            'name': name_by_key.get(('main', pid)) or name,
            'group': int(g),
            'price_raw': raw,
        })

    # sndpop（second：radio 候選）
    for m in re.finditer(
            r'<div class="pdpop-li[^"]*" id="(sndpop_(\d+)_(\d+))"[^>]*>', html):
        bid, g, pid = m.group(1), m.group(2), m.group(3)
        name, raw = _card_name_price_raw(html, m.start())
        raw_cards['second'].setdefault(g, []).append({
            'product_id': pid,
            'name': name_by_key.get(('second', pid)) or name,
            'group': int(g),
            'price_raw': raw,
        })

    # addpop（加購物）— 兩種 block class
    for m in re.finditer(
            r'<div class="(?:pdpop-li[^"]*|s2slt-block[^"]*)" '
            r'id="(addpop_(\d+)_(\d+))"[^>]*>', html):
        bid, g, pid = m.group(1), m.group(2), m.group(3)
        tail = html[m.start():m.start() + _CARD_WINDOW]
        name, raw = _card_name_price_raw(html, m.start())
        qty = re.search(
            r'class="addslt[^"]*"[^>]*>\s*<option value="0">0</option>'
            r'(?:<option value="([1-9]\d?)">)', tail)
        raw_cards['add'].setdefault(g, []).append({
            'product_id': pid,
            'name': name_by_key.get(('add', pid)) or name,
            'group': int(g),
            'price_raw': raw,
            'max_qty': int(qty.group(1)) if qty else 1,
        })

    # resolve price（依券型：加價型+/基準型$單價減組最低）
    for gtype in ('main', 'second', 'add'):
        for g, cards in raw_cards[gtype].items():
            groups[gtype][g] = _resolve_price(cards)

    # 2) 口味候選（node extract 的 ctidss；不依賴 pprcss 補價）
    if extract:
        ct = extract.get('ctidss') or {}
        vv, tt, pp = ct.get('v') or {}, ct.get('t') or {}, ct.get('p') or {}
        for g, cards in groups['main'].items():
            for card in cards:
                key = f'g{g}_{card["product_id"]}'
                if key in vv:
                    card['flavors'] = [
                        {'flavor_id': vv[key][i],
                         'name': (tt.get(key) or [])[i] if i < len(tt.get(key) or []) else '',
                         'price_add': int((pp.get(key) or [])[i]) if i < len(pp.get(key) or []) and (pp.get(key) or [])[i] else 0}
                        for i in range(len(vv[key]))]
                    card['flavors'] = [f for f in card['flavors'] if f['name']]


    # 組分類註記（組標題原文 groupTitle + cat）寫到每張候選卡（2026-09-07）。
    # main：cat 依組標題尺寸詞；second：整組全飲料→飲料、否則副食。
    subject_by: dict[str, dict[str, str]] = {}
    for m in _FOOD_SUBJECT_RE.finditer(html):
        gtype, g, subj = m.group(1), m.group(2), m.group(3).strip()
        subject_by.setdefault(gtype, {})[g] = subj
    for gtype in ("main", "second"):
        for g, cards in groups.get(gtype, {}).items():
            subject = (subject_by.get(gtype) or {}).get(g, "")
            if gtype == "main":
                cat = _cat_of_subject(subject)
            else:
                cat = "副食"
                if _all_drink([c.get("name", "") for c in cards]):
                    cat = "飲料"
            for c in cards:
                c["cat"] = cat
                c["groupTitle"] = subject or None

    return {"groups": groups}


# ============ 結構化 → MealItem[] ============

def _add_str(price_add: int) -> str | None:
    """升級/換購差價 → add 字串（向後相容舊 MealItem 用）。"""
    if price_add:
        return f"+${price_add}"
    return None


def flatten_items(struct: dict) -> list[dict] | None:
    """結構化中介 → 扁平結構化候選清單（新 items schema）。

    每筆 = 一個「可選候選」，前端不需拆文字即可做分組/過濾：
      {text, group, groupIdx, priceAdd, flavors[]}
        text      候選名（如「千島海鮮盛宴」）
        group     main/second/add（類別）
        groupIdx  該類第幾組（1-based；如 26868 有 main 兩組）
        priceAdd  升級/換購加價（0=免加價）
        flavors   口味候選 [{name, priceAdd}]（主餐比薩才有；否則 []）
        add       加購物價差（僅 group=add 有），數字

    固定盒型券（無候選、只有單一內容）→ items 為單筆 group=main 的固定內容
    （priceAdd=0、flavors=[]），前端視為「單一不可選」。
    結構不足以構成任何內容時回 None（前端 fallback description）。
    """
    groups = struct.get('groups', {})
    items: list[dict] = []
    order = {'main': 0, 'second': 1, 'add': 2}
    for gtype in sorted(groups, key=lambda g: order.get(g, 9)):
        for g in sorted(groups[gtype], key=int):
            cards = groups[gtype][g]
            if not cards:
                continue
            for c in cards:
                name = c.get('name')
                if not name:
                    continue
                item: dict = {
                    'text': name,
                    'group': gtype,
                    'groupIdx': int(g),
                    'priceAdd': c.get('price_add') or 0,
                    'flavors': [],
                    'add': None,
                    # 組分類（2026-09-07）：main 依組標題尺寸；second 全飲料→飲料/否則副食
                    'cat': c.get('cat'),
                    'groupTitle': c.get('groupTitle'),
                }
                if gtype == 'main':
                    item['flavors'] = [
                        {'name': f['name'], 'priceAdd': f.get('price_add') or 0}
                        for f in c.get('flavors', []) if f.get('name')]
                elif gtype == 'add':
                    item['add'] = c.get('price_add') or 0
                # 兜底：main 無標題→中性比薩；second 無標題→副食
                if not item['cat']:
                    item['cat'] = {"main": "比薩", "second": "副食"}.get(gtype)
                items.append(item)

    if not items:
        return None
    return items
