"""解析 scripts/fetch_oplay.py 抓下來的 oplay.cc GTA 6 攻略頁（繁體中文）。只用標準函式庫，由 build_gta6.py 使用。

輸出刻意只有「純文字＋很小的標記」，不含任何來源頁面的 HTML／樣式／腳本：
  行內標記：**粗體**、⟦按鍵⟧（例如 ⟦L2⟧／LT），頁面用 DOM 方法渲染，不經過 innerHTML。
  內容區塊（blocks）：字串＝段落；{"h": 標題, "l": 層級}；{"ul": [項目…]}；{"ol": [項目…]}；{"tb": [[格…]…], "hd": 1}。
"""
import html as htmllib
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
