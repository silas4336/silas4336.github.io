"""解析 scripts/fetch_oplay.py 抓下來的 oplay.cc GTA 6 攻略頁（繁體中文）。只用標準函式庫，由 build_gta6.py 使用。

輸出刻意只有「純文字＋很小的標記」，不含任何來源頁面的 HTML／樣式／腳本：
  行內標記：**粗體**、⟦按鍵⟧（例如 ⟦L2⟧／LT），頁面用 DOM 方法渲染，不經過 innerHTML。
  內容區塊（blocks）：字串＝段落；{"h": 標題, "l": 層級}；{"ul": [項目…]}；{"ol": [項目…]}；{"tb": [[格…]…], "hd": 1}。
"""
import html as htmllib
import json
import re
from html.parser import HTMLParser

BASE = "https://oplay.cc/gta6/"


def clean(html):
    """去掉 script／style 與 Astro 的 data-astro-cid 屬性。"""
    html = re.sub(r"<(script|style)[\s\S]*?</\1>", "", html)
    return re.sub(r' data-astro-cid-[a-z0-9]+(="[^"]*")?', "", html)


def norm(text):
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("**  **", " ").replace("****", "")
    return re.sub(r" ?\*\* ?\*\*", " ", text).strip()


def inline(fragment):
    """一小段 HTML → 帶 **粗體**、⟦按鍵⟧ 標記的純文字。"""
    fragment = re.sub(r"<kbd[^>]*>([\s\S]*?)</kbd>", lambda m: "⟦" + re.sub(r"<[^>]+>", "", m.group(1)).strip() + "⟧", fragment)
    fragment = re.sub(r"<(strong|b)(?:\s[^>]*)?>([\s\S]*?)</\1>", r"**\2**", fragment)
    fragment = re.sub(r"<br\s*/?>", " ", fragment)
    return norm(htmllib.unescape(re.sub(r"<[^>]+>", "", fragment)))


def text_of(fragment):
    return norm(htmllib.unescape(re.sub(r"<[^>]+>", " ", fragment)))


def extract_div(html, start):
    """html[start] 是 `<div …>` 的開頭，回傳到對應 `</div>` 的整段（含外層）。"""
    depth, i = 0, start
    for m in re.finditer(r"<(/?)div\b[^>]*>", html[start:]):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return html[start:start + m.end()]
    return html[start:]


class Prose(HTMLParser):
    """文章 HTML → blocks。處理 p、h2～h4、ul／ol（巢狀的項目攤平成「↳ 」開頭）、table；跳過 details、figure、圖片、按鈕。"""
    SKIP = {"script", "style", "svg", "button", "details", "figure", "nav", "aside"}
    BLOCK = {"p", "h2", "h3", "h4", "ul", "ol", "table", "div", "section", "li"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []
        self.skip = 0
        self.buf = None       # 目前收集中的行內文字
        self.kind = None      # "p" | "h" | "li" | "cell"
        self.level = 2
        self.lists = []       # 巢狀清單堆疊：[{"k": "ul"/"ol", "items": [...]}]
        self.table = None     # {"rows": [], "hd": False}
        self.row = None
        self.sub = 0          # 已進入的巢狀清單層數

    def _flush(self):
        if self.buf is None:
            return
        text = norm("".join(self.buf))
        kind, self.buf, self.kind = self.kind, None, None
        if not text:
            return
        if kind == "h":
            self.blocks.append({"h": text, "l": self.level})
        elif kind == "li":
            self.lists[-1]["items"].append(("↳ " if self.sub else "") + text)
        elif kind == "cell":
            self.row.append(text)
        else:
            self.blocks.append(text)

    def _start(self, kind):
        self._flush()
        self.buf, self.kind = [], kind

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
            return
        if self.skip:
            return
        if tag in ("h2", "h3", "h4"):
            self._start("h"); self.level = int(tag[1])
        elif tag == "p":
            if self.kind == "li" or self.kind == "cell":
                self.buf.append(" ")
            else:
                self._start("p")
        elif tag in ("ul", "ol"):
            self._flush()
            if self.lists:
                self.sub += 1
                self.lists.append(self.lists[-1])   # 巢狀：項目併入外層清單
            else:
                self.lists.append({"k": tag, "items": []})
        elif tag == "li":
            self._start("li")
        elif tag == "table":
            self._flush(); self.table = {"rows": [], "hd": False}
        elif tag == "tr":
            self.row = []
        elif tag in ("td", "th"):
            if tag == "th":
                self.table["hd"] = True
            self._start("cell")
        elif tag in ("strong", "b"):
            self._ensure(); self.buf.append("**")
        elif tag == "kbd":
            self._ensure(); self.buf.append("⟦")
        elif tag == "br" and self.buf is not None:
            self.buf.append(" ")

    def _ensure(self):
        if self.buf is None:
            self._start("p")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag in ("h2", "h3", "h4", "p") and self.kind in ("h", "p"):
            self._flush()
        elif tag == "li":
            self._flush()
        elif tag in ("ul", "ol"):
            self._flush()
            if self.sub:
                self.sub -= 1; self.lists.pop()
            elif self.lists:
                lst = self.lists.pop()
                if lst["items"]:
                    self.blocks.append({lst["k"]: lst["items"]})
        elif tag in ("td", "th"):
            self._flush()
        elif tag == "tr":
            if self.row:
                self.table["rows"].append(self.row)
            self.row = None
        elif tag == "table":
            if self.table and self.table["rows"]:
                blk = {"tb": self.table["rows"]}
                if self.table["hd"]:
                    blk["hd"] = 1
                self.blocks.append(blk)
            self.table = None
        elif tag in ("strong", "b") and self.buf is not None:
            self.buf.append("**")
        elif tag == "kbd" and self.buf is not None:
            self.buf.append("⟧")

    def handle_data(self, data):
        if self.skip:
            return
        if self.buf is None:
            if not data.strip():
                return
            self._start("p")
        self.buf.append(data)

    def close(self):
        super().close()
        self._flush()


def to_blocks(fragment):
    p = Prose()
    p.feed(fragment)
    p.close()
    return p.blocks


# ───────────────────────── 章節頁 ─────────────────────────

ROW = re.compile(
    r'<li[^>]*>\s*(?:<button type="button" class="g6-tick"[^>]*data-g6tick="(?P<tick>[^"]+)"[^>]*>[\s\S]*?</button>)?\s*'
    r'<button type="button" class="g6-row(?P<cls>[^"]*)"(?P<attrs>[^>]*)>(?P<body>[\s\S]*?)</button>')


def parse_row_parts(body, attrs="", tick=None):
    """一列：名稱、英文名、標籤（g6-k）、一句話（g6-a）、卡片 ID 與勾選 ID。"""
    name = re.search(r'<span class="g6-n"><span[^>]*>([\s\S]*?)</span>', body)
    en = re.search(r'<span class="g6-en"[^>]*>([\s\S]*?)</span>', body)
    k = re.search(r'<span class="g6-k">([\s\S]*?)</span>', body)
    a = re.search(r'<span class="g6-a">([\s\S]*?)</span>', body)
    card = re.search(r'data-g6card="([^"]+)"', attrs)
    row = {"n": text_of(name.group(1)) if name else ""}
    if en:
        row["en"] = text_of(en.group(1))
    if k and text_of(k.group(1)):
        row["k"] = inline(k.group(1))
    if a and text_of(a.group(1)):
        row["a"] = inline(a.group(1))
    if card:
        row["id"] = card.group(1)
    if tick:
        row["tick"] = tick
    return row


def parse_row(m):
    return parse_row_parts(m.group("body"), m.group("attrs"), m.group("tick"))


def parse_mission(chunk, slug):
    top = re.search(r'<button type="button" class="g6-row[^"]*"[^>]*data-g6walk[^>]*>([\s\S]*?)</button>', chunk)
    m = {"slug": slug}
    if top:
        row = parse_row_parts(top.group(1))
        m.update({"n": row.get("n", ""), "en": row.get("en", ""), "k": row.get("k", ""), "a": row.get("a", "")})
    keys = re.search(r'<ul class="g6w-keys">([\s\S]*?)</ul>', chunk)
    m["keys"] = [inline(x) for x in re.findall(r"<li>([\s\S]*?)</li>", keys.group(1))] if keys else []
    body = re.search(r'<div class="g6w-body">', chunk)
    m["body"] = to_blocks(extract_div(chunk, body.start())) if body else []
    rel = re.search(r'<section class="g6w-rel">([\s\S]*?)</section>', chunk)
    m["stuck"] = [parse_row(r) for r in ROW.finditer(rel.group(1))] if rel else []
    link = re.search(r'href="(/gta6/chapters/\d+/[^"]+)"', chunk)
    m["url"] = "https://oplay.cc" + link.group(1) if link else ""
    return m


def parse_chapter(html, no):
    """回傳 {no, title, sub, lead, missions: [...], sections: [{title, count, rows}]}。"""
    a = clean(html)
    h1 = re.search(r"<h1[^>]*>([\s\S]*?)</h1>", a)
    hit = re.search(r"第.章（[^）<]+）有 \d+ 個主線任務|第.章有 \d+ 個主線任務", a)
    lead = ""
    if hit:
        start = a.rfind("<p", 0, hit.start())
        end = a.find("</p>", hit.end())
        lead = inline(a[a.find(">", start) + 1:end]) if start >= 0 and end > 0 else ""
    sub = re.search(r"第.章（(.+?)）有", lead)
    out = {"no": no, "title": text_of(h1.group(1)) if h1 else f"第{no}章攻略", "sub": sub.group(1) if sub else "",
           "lead": lead, "missions": [], "sections": []}
    for sec in re.split(r"(?=<h2[ >])", a):
        head = re.match(r"<h2[^>]*>([\s\S]*?)</h2>(?:<span class=\"g6-cnt\">([\s\S]*?)</span>)?", sec)
        if not head:
            continue
        title = text_of(head.group(1))
        if title == "主線順序":
            marks = list(re.finditer(r'<li id="m-(story\.[^"]+)"', sec))
            for i, mk in enumerate(marks):
                end = marks[i + 1].start() if i + 1 < len(marks) else len(sec)
                chunk = sec[mk.start():end]
                if i + 1 == len(marks):   # 最後一個任務：到整份任務清單結尾為止（任務自己裡面也有 <section>，不能用第一個 </section> 截）
                    chunk = re.split(r"</li>\s*</ol>\s*</div>\s*</section>", chunk)[0]
                out["missions"].append(parse_mission(chunk, mk.group(1)))
            continue
        if title.startswith("之前就開放"):   # 把前面章節已開放的東西再列一次，重複又很長
            continue
        rows = [parse_row(r) for r in ROW.finditer(sec)]
        if rows and "g6-grp-b" in sec:
            out["sections"].append({"title": title, "count": text_of(head.group(2) or ""), "rows": rows})
    return out


# ───────────────────────── 筆記 ─────────────────────────

def parse_notes_index(html):
    """回傳 [{id, title, notes: [{slug, title, sub, badge}]}]，依網站的分類與順序。"""
    a = clean(html)
    cats = []
    for sec in re.split(r'(?=<section class="gh-row")', a):
        cid = re.match(r'<section class="gh-row" id="cat-([^"]+)"', sec)
        if not cid:
            continue
        t = re.search(r'class="baloo gh-hb-n">([\s\S]*?)</span>', sec)
        notes = []
        for it in re.finditer(r'<a class="gh-it[^"]*" href="/gta6/notes/([a-z0-9-]+)"([\s\S]*?)</a>', sec):
            title = re.search(r"<b>([\s\S]*?)</b>", it.group(2))
            sub = re.search(r'<span class="gh-sb">([\s\S]*?)</span>', it.group(2))
            badge = re.search(r'<i class="gh-bd gh-bd--(new|big)">([\s\S]*?)</i>', it.group(2))
            notes.append({"slug": it.group(1), "title": text_of(title.group(1)) if title else it.group(1),
                          "sub": inline(sub.group(1)) if sub else "", "badge": text_of(badge.group(2)) if badge else ""})
        cats.append({"id": cid.group(1), "title": text_of(t.group(1)) if t else cid.group(1), "notes": notes})
    return cats


def parse_note(html):
    a = clean(html)
    h1 = re.search(r"<h1[^>]*>([\s\S]*?)</h1>", a)
    stamp = re.search(r'<p class="gart-stamp[^"]*">([\s\S]*?)</p>', a)
    prose = re.search(r'<div class="prose">', a)
    if not prose:
        raise SystemExit("找不到文章內容（div.prose），來源頁面的結構可能變了")
    return {"title": text_of(h1.group(1)) if h1 else "", "stamp": text_of(stamp.group(1)).replace(" ・ ", "・") if stamp else "",
            "blocks": to_blocks(extract_div(a, prose.start()))}


# ───────────────────────── 圖鑑／彩蛋／圖示／更新／進度 ─────────────────────────

def _oplay_url(href):
    """只接受站內 /gta6/… 路徑並補成完整 https://oplay.cc/… 網址。"""
    if not href or not href.startswith("/gta6/"):
        return ""
    return "https://oplay.cc" + href


def _id_from_href(href):
    if not href:
        return ""
    if href.startswith("/gta6/c/"):
        return href[len("/gta6/c/"):]
    if href.startswith("#c-"):
        return href[len("#c-"):]
    return ""


def _parse_tags(frag, skip_cat=True):
    """從 <em class="tg ..."> 擷取 cat、where、gift、其他 tags。"""
    cat, where, gift, tags = "", "", "", []
    for m in re.finditer(r'<em class="([^"]*)"[^>]*>([\s\S]*?)</em>', frag):
        cls = m.group(1).split()
        val = text_of(m.group(2))
        if not val:
            continue
        if "tg--cat" in cls:
            if not cat:
                cat = val
        elif "tg--where" in cls:
            where = val
        elif "tg--gift" in cls:
            gift = val
        elif "tg" in cls:
            tags.append(val)
    return cat, where, gift, tags


def _parse_dxa_li(li_attrs, href, body):
    """解析 <li ...><a class="dxa-row..." href="...">...</a></li>。"""
    cid = _id_from_href(href)
    url = _oplay_url(href) if href.startswith("/gta6/c/") else ""
    t_blk = re.search(r'<span class="dxa-t">([\s\S]*?)</span>', body)
    name = re.search(r"<strong>([\s\S]*?)</strong>", t_blk.group(1)) if t_blk else re.search(r"<strong>([\s\S]*?)</strong>", body)
    en = re.search(r"<small[^>]*>([\s\S]*?)</small>", t_blk.group(1)) if t_blk else None
    a_m = re.search(r'<span class="dxa-a">([\s\S]*?)</span>', body)
    no_m = re.search(r'<i class="dxa-no[^"]*"[^>]*>([\s\S]*?)</i>', body)
    dc = re.search(r'data-c="([^"]+)"', li_attrs)
    tags_blk = re.search(r'<span class="dx-tags">([\s\S]*?)</span>', body)
    cat, where, gift, tags = _parse_tags(tags_blk.group(1)) if tags_blk else ("", "", "", [])
    if dc and not cat:
        cat = htmllib.unescape(dc.group(1)).strip()

    item = {"n": text_of(name.group(1)) if name else ""}
    if cid:
        item["id"] = cid
    if en and text_of(en.group(1)):
        item["en"] = text_of(en.group(1))
    if no_m and text_of(no_m.group(1)):
        item["no"] = text_of(no_m.group(1))
    if cat:
        item["cat"] = cat
    if where:
        item["where"] = where
    if gift:
        item["gift"] = gift
    if tags:
        item["tags"] = tags
    if a_m and inline(a_m.group(1)):
        item["a"] = inline(a_m.group(1))
    if url:
        item["url"] = url
    return item


def _parse_dxc_li(li_attrs, href, body):
    """解析標在地圖上的卡片 <li ...><a class="... dxc-card" href="...">...</a></li>（不收圖鑑／地圖縮圖）。"""
    cid = _id_from_href(href)
    url = _oplay_url(href) if href.startswith("/gta6/c/") else ""
    dc = re.search(r'data-c="([^"]+)"', li_attrs)
    cat, where, gift, tags = _parse_tags(body)
    if dc and not cat:
        cat = htmllib.unescape(dc.group(1)).strip()
    b_m = re.search(r'<span class="dxc-b">([\s\S]*)$', body)
    b_src = b_m.group(1) if b_m else body
    name = re.search(r"<strong>([\s\S]*?)</strong>", b_src)
    en = re.search(r"<small[^>]*>([\s\S]*?)</small>", b_src)
    a_m = re.search(r'<span class="dxc-a">([\s\S]*?)</span>', b_src)
    val_m = re.search(r'<b class="dxc-val[^"]*">([\s\S]*?)</b>', b_src)

    item = {"n": text_of(name.group(1)) if name else "", "onMap": 1}
    if cid:
        item["id"] = cid
    if en and text_of(en.group(1)):
        item["en"] = text_of(en.group(1))
    if cat:
        item["cat"] = cat
    if where:
        item["where"] = where
    if gift:
        item["gift"] = gift
    if tags:
        item["tags"] = tags
    if a_m and inline(a_m.group(1)):
        item["a"] = inline(a_m.group(1))
    if val_m and text_of(val_m.group(1)):
        item["val"] = text_of(val_m.group(1))
    if url:
        item["url"] = url
    return item


def parse_cards_index(html):
    """解析 /gta6/cards，回傳 [{group, cats: [{slug, name, count, preview, egg?}]}]。"""
    a = clean(html)
    groups = []
    for sec in re.split(r'(?=<section class="dxh-fam")', a):
        if not sec.startswith('<section class="dxh-fam"'):
            continue
        h2 = re.search(r"<h2[^>]*>([\s\S]*?)</h2>", sec)
        gname = text_of(re.sub(r"<em[\s\S]*?</em>", "", h2.group(1))) if h2 else ""
        cats = []
        for m in re.finditer(r'<a[^>]*class="[^"]*\bdxh-tile\b[^"]*"[^>]*href="([^"]+)"[^>]*data-k="([^"]+)"[^>]*>([\s\S]*?)</a>', sec):
            href, slug, body = m.group(1), m.group(2), m.group(3)
            st = re.search(r"<strong>([\s\S]*?)</strong>", body)
            em = re.search(r"<em[^>]*>(\d+)</em>", body)
            pv = re.search(r'<span class="dxh-s">([\s\S]*?)</span>', body)
            entry = {
                "slug": slug,
                "name": text_of(st.group(1)) if st else slug,
                "count": int(em.group(1)) if em else 0,
                "preview": text_of(pv.group(1)) if pv else "",
            }
            if href == "/gta6/eggs":
                entry["egg"] = 1
            cats.append(entry)
        if cats:
            groups.append({"group": gname, "cats": cats})
    return groups


def parse_card_page(html, slug):
    """解析 /gta6/cards/<slug>，同時處理 data-d 表格、dxc-card 地圖卡、dxa-row 清單。"""
    a = clean(html)
    unit_m = re.search(r'data-unit="([^"]*)"', a)
    common_m = re.search(r'data-common="([^"]*)"', a)
    seg_m = re.search(r'<ul[^>]*\bdx-seg\b[^>]*>([\s\S]*?)</ul>', a)
    stats = [text_of(x) for x in re.findall(r"<button[^>]*>([\s\S]*?)</button>", seg_m.group(1))] if seg_m else []

    items = []
    # 1. data-d 表格列／清單列（載具、武器、動物、外觀、作弊碼）— 不收 img
    for m in re.finditer(r'<(?:tr|li)\b[^>]*\bdata-d="([^"]+)"', a):
        raw = json.loads(htmllib.unescape(m.group(1)))
        item = {"id": raw.get("id", ""), "n": norm(str(raw.get("zh", "")))}
        if raw.get("en"):
            item["en"] = norm(str(raw["en"]))
        if raw.get("cat"):
            item["cat"] = norm(str(raw["cat"]))
        if raw.get("how"):
            item["how"] = norm(str(raw["how"]))
        if raw.get("code"):
            item["code"] = norm(str(raw["code"]))
        if raw.get("price"):
            item["price"] = norm(str(raw["price"]))
        if raw.get("edition"):
            item["ed"] = norm(str(raw["edition"]))
        if raw.get("tr"):
            item["tr"] = 1
        if isinstance(raw.get("st"), dict) and isinstance(raw["st"].get("v"), dict) and raw["st"]["v"]:
            item["st"] = raw["st"]["v"]
        pg_url = _oplay_url(raw.get("pg", ""))
        if pg_url:
            item["url"] = pg_url
        map_url = _oplay_url(raw.get("map", ""))
        if map_url:
            item["map"] = map_url
        if item["n"]:
            items.append(item)

    # 2. dxc-card（標在地圖上的項目：地點、店家、人物、支線、挑戰、獎勵、賺錢）
    for m in re.finditer(r'<li([^>]*)>\s*<a class="[^"]*\bdxc-card\b[^"]*" href="([^"]+)"[^>]*>([\s\S]*?)</a>\s*</li>', a):
        it = _parse_dxc_li(m.group(1), m.group(2), m.group(3))
        if it["n"]:
            items.append(it)

    # 3. dxa-row（清單項目）
    for m in re.finditer(r'<li([^>]*)>\s*<a class="dxa-row(?:\s[^"]*)?" href="([^"]+)"[^>]*>([\s\S]*?)</a>\s*</li>', a):
        it = _parse_dxa_li(m.group(1), m.group(2), m.group(3))
        if it["n"]:
            items.append(it)

    out = {"slug": slug, "unit": unit_m.group(1) if unit_m else "則", "items": items}
    if common_m and htmllib.unescape(common_m.group(1)).strip():
        out["common"] = norm(htmllib.unescape(common_m.group(1)))
    if stats:
        out["stats"] = stats
    return out


def parse_eggs(html):
    """解析 /gta6/eggs，回傳依地區（與「不用找，玩著會遇到」子分類）分組的彩蛋清單。"""
    a = clean(html)
    groups = []
    # 1. 有地區地圖的各區
    for m in re.finditer(r'<section class="[^"]*\bdxe-reg\b[^"]*"[^>]*>([\s\S]*?)</section>', a):
        sec = m.group(1)
        h2 = re.search(r"<h2[^>]*>([\s\S]*?)</h2>", sec)
        reg = text_of(re.sub(r"<em[\s\S]*?</em>", "", h2.group(1))) if h2 else ""
        map_m = re.search(r'<a[^>]*href="(/gta6/map[^"]*)"', sec)
        items = [_parse_dxa_li(r.group(1), r.group(2), r.group(3))
                 for r in re.finditer(r'<li([^>]*)>\s*<a class="dxa-row(?:\s[^"]*)?" href="([^"]+)"[^>]*>([\s\S]*?)</a>\s*</li>', sec)]
        if items:
            grp = {"region": reg, "items": items}
            if map_m:
                grp["map"] = _oplay_url(map_m.group(1))
            groups.append(grp)

    # 2. 「不用找，玩著會遇到」區塊（底下各個 <div class="dxb-sec"><h3>...</h3><ul class="... dxa">）
    extra_m = re.search(r'<section class="dxb-sec"[^>]*>\s*<h2[^>]*>不用找[\s\S]*?</section>', a)
    if extra_m:
        sec = extra_m.group(0)
        for sub in re.finditer(r'<div class="dxb-sec"[^>]*>\s*<h3[^>]*>([\s\S]*?)</h3>([\s\S]*?)</ul>\s*</div>', sec):
            sub_title = text_of(re.sub(r"<em[\s\S]*?</em>", "", sub.group(1)))
            items = [_parse_dxa_li(r.group(1), r.group(2), r.group(3))
                     for r in re.finditer(r'<li([^>]*)>\s*<a class="dxa-row(?:\s[^"]*)?" href="([^"]+)"[^>]*>([\s\S]*?)</a>\s*</li>', sub.group(2))]
            if items:
                groups.append({"region": "不用找・" + sub_title if sub_title else "不用找，玩著會遇到", "items": items})
    return groups


def parse_hud(html):
    """解析 /gta6/hud，回傳分組後的畫面圖示說明。"""
    a = clean(html)
    groups = []
    for m in re.finditer(r'<section class="[^"]*\bg6-grp\b[^"]*"[^>]*>([\s\S]*?)</section>', a):
        sec = m.group(1)
        h2 = re.search(r"<h2[^>]*>([\s\S]*?)</h2>", sec)
        if not h2:
            continue
        title = text_of(h2.group(1))
        items = []
        for r in re.finditer(r'<li[^>]*>\s*<button[^>]*class="hud-row"([^>]*)>([\s\S]*?)</button>\s*</li>', sec):
            attrs, body = r.group(1), r.group(2)
            cid = re.search(r'data-g6card="([^"]+)"', attrs)
            n_m = re.search(r'<span class="hud-n">([\s\S]*?)</span>', body)
            say_m = re.search(r'<span class="hud-say">([\s\S]*?)</span>', body)
            do_m = re.search(r'<span class="hud-do">([\s\S]*?)</span>', body)
            tag = ""
            n_html = n_m.group(1) if n_m else ""
            em_m = re.search(r"<em[^>]*>([\s\S]*?)</em>", n_html)
            if em_m:
                tag = text_of(em_m.group(1))
                n_html = n_html[:em_m.start()] + n_html[em_m.end():]
            item = {"n": text_of(n_html)}
            if cid:
                item["id"] = cid.group(1)
            if tag:
                item["tag"] = tag
            if say_m and inline(say_m.group(1)):
                item["say"] = inline(say_m.group(1))
            if do_m and inline(do_m.group(1)):
                item["do"] = inline(do_m.group(1))
            if item["n"]:
                items.append(item)
        if items:
            groups.append({"title": title, "items": items})
    return groups


def parse_updates(html):
    """解析 /gta6/updates，回傳依日期分組的更新紀錄。"""
    a = clean(html)
    days = []
    for m in re.finditer(r'<section class="up-day">([\s\S]*?)</section>', a):
        sec = m.group(1)
        dm = re.search(r'<p class="up-d">([\s\S]*?)</p>', sec)
        d_html = dm.group(1) if dm else ""
        b_m = re.search(r"<b[^>]*>([\s\S]*?)</b>", d_html)
        spans = [text_of(x) for x in re.findall(r"<span[^>]*>([\s\S]*?)</span>", d_html)]
        items = []
        for li in re.finditer(r'<li[^>]*data-t="([^"]*)"[^>]*>([\s\S]*?)</li>', sec):
            tag = htmllib.unescape(li.group(1)).strip()
            body = li.group(2)
            ut = re.search(r'<span class="up-t">([\s\S]*?)</span>', body)
            href = re.search(r'href="([^"]+)"', body)
            text = inline(ut.group(1)) if ut else text_of(body)
            if not text:
                continue
            it = {"tag": tag, "text": text}
            url = _oplay_url(href.group(1)) if href else ""
            if url:
                it["url"] = url
            items.append(it)
        if items:
            day = {"date": text_of(b_m.group(1)) if b_m else "", "items": items}
            if spans:
                day["dow"] = spans[0]
            if len(spans) > 1:
                day["year"] = spans[1]
            days.append(day)
    return days


def parse_progress(html):
    """解析 /gta6/progress 內嵌的 ppData JSON，抽出 100%／白金／全收集總表（去掉 SVG 與重複卡片）。"""
    m = re.search(r'<script[^>]*id="ppData"[^>]*>([\s\S]*?)</script>', html)
    if not m:
        return {"secs": [], "rows": []}
    raw = json.loads(m.group(1))
    rows = []
    for r in raw.get("rows", []):
        entry = {
            "id": r["id"],
            "name": norm(str(r.get("name", ""))),
            "sec": norm(str(r.get("sec", ""))),
            "type": r.get("type", "count"),
            "unit": r.get("unit", ""),
            "goals": r.get("goals", []),
            "total": r.get("total", 0),
        }
        if r.get("need") is not None:
            entry["need"] = r["need"]
        if isinstance(r.get("items"), list) and r["items"]:
            entry["items"] = r["items"]
        rows.append(entry)
    return {"secs": raw.get("secs", []), "rows": rows}

