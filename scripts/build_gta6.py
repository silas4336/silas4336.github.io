"""用法：py -3 scripts/build_gta6.py [遊民星空來源] [promptowy 來源] [輸出檔，預設 gta6/data.js]
來源可以是本機 HTML 檔或網址，省略就抓下面兩個預設網址。

需要簡轉繁套件（只有重新產生資料時才要，網站本身不需要）：
    py -3 -m pip install opencc-python-reimplemented

把兩份 GTA 6 攻略合併成 gta6/data.js，給 gta6/ 的攻略 PWA 用。

  1. 遊民星空原站《GTA6 全任務流程圖文攻略》（gamersky.com 路書）：逐步圖文，含支線、搶劫、陌生人，
     簡體中文，這裡用 OpenCC s2twp（台灣用字與慣用詞）轉成繁體。作者還在更新（目前寫到第 2 章第 1 個任務，
     最後一則是作者預告），所以會被當成「作者預告」另外存，不算任務。
  2. promptowy.com《GTA 6 主線任務攻略》：第 1～5 章全部約 100 個主線任務的清單（官方英文名、角色、
     一句話摘要、單一任務頁連結），沒有逐步內容。

合併規則：
  - 骨架是遊民星空的遊玩順序（支線等穿插在原位）。兩邊對得上的任務（YOUMIN_TO_EN）合成一筆：
    中文名與圖文來自遊民，英文名、角色、摘要、連結來自 promptowy。
  - promptowy 有、遊民還沒寫到的任務，依 promptowy 的順序接在前一個任務後面，只有摘要和外連結。
  - 原作者之後補寫了某個任務，就在 YOUMIN_TO_EN 加一行對應，重跑即可（對不上會印出警告）。
  - 任務 ID：promptowy 有的用英文名（p-gone-fishing），只有遊民有的用遊民的節點編號（y-1468083467）。
    來源改標題或補寫內容時 ID 都不變，已勾選的進度不會跑掉。舊版曾用中文名當 ID，LEGACY_Y_IDS 記著對照，
    輸出的 aliases 讓頁面把舊進度轉成新 ID。

重跑後把 gta6/sw.js 的 CACHE 版本號加 1，已安裝的 PWA 才會收到新內容。

安全：只保留章節標題、任務標題、純文字、來自 img1.gamersky.com 的圖片網址與寬高，以及
https://promptowy.com/ 的任務頁連結；其他標籤（廣告、樣式、腳本）全部丟掉。
注意：img1.gamersky.com 有防盜連結——請求帶 Referer 會 403，所以頁面的圖片一律要 no-referrer。
"""
import html as htmllib
import json
import re
import sys
import urllib.request
from datetime import date
from html.parser import HTMLParser

YOUMIN_URL = "https://www.gamersky.com/tools/guide-map/roadbooks/55"
PROMPTOWY_URL = "https://promptowy.com/zh-tw/gta-6/%E4%BB%BB%E5%8B%99%E6%94%BB%E7%95%A5/"
IMG_BASE = "https://img1.gamersky.com/"
PROMPTOWY_BASE = "https://promptowy.com/"

TYPE_PREFIX = {"支線": "支線", "搶劫": "搶劫", "可選": "可選", "陌生人": "陌生人"}
# 沒有前綴的標題預設是主線；但內文完全沒出現「任務【…】」的（例如「偷犀牛坦克、戰鬥機」）只是順手的技巧，歸為「額外」
MISSION_MARK = re.compile(r"任務\s*【")

# 遊民星空的（繁體）任務名 → promptowy 的英文任務名。其餘遊民任務（支線、搶劫、陌生人、可選、額外）沒有對應。
YOUMIN_TO_EN = {
    "序幕": "Prologue",
    "垂釣": "Gone Fishing",
    "整裝待發": "Gear Up",
    "作坊費用": "Lab Fees",
    "小剮蹭而已": "Just a Scratch",
    "避人耳目": "Unwanted Attention",
    "管道活": "Pipework",
    "嘿阿諾德": "Hey Arnold!",
    "島嶼之夢": "Island Dreams",
    "風水": "Feng Shui",
    "回家": "Coming Home",
    "給唐尼擦屁股": "Clean Up After Donnie",
    "元交": "Buck Me",
    "如夢方醒": "Down to Earth",
    "郎朗晴空": "Clear Skies",
    "自在一日": "Day Release",
    "沼澤困境": "Swamped",
    "消失的老唐": "Don Gone",
    "漁過天晴": "Recalibration",
    "遊客陷阱": "Tourist Trap",
    "甜蜜的家": "Home Sweet Home",
    "出院時間": "Discharge Time",
    "包中何物": "What's in the Bag?",
}

# 遊民的主線任務裡，promptowy 沒有對應的（只是家裡操作教學之類）：不用警告
YOUMIN_ONLY_MAIN = {"傑森的家"}

# 舊版（轉載頁）用「y-中文名」當遊民獨有任務的 ID；現在改用遊民節點編號。節點編號 → 舊 ID，產生 aliases 用。
LEGACY_Y_IDS = {
    "1468083467": "y-傑森的家", "793266265": "y-女鄰居雪麗", "1317901914": "y-奇珍動物門面",
    "850023057": "y-翠鳥幫漁棚", "1038409068": "y-搜查潛水點", "1564511324": "y-釣一條更大的魚1",
    "1884475042": "y-偷走代步車", "995188833": "y-釣一條更大的魚2", "1612145627": "y-搜查潛水點2",
    "1889613080": "y-找到丟失貨物", "535367646": "y-臭猿學入門", "850564572": "y-搜尋樹雕",
    "1461250244": "y-進階臭猿經濟學", "1271184100": "y-偷犀牛坦克、戰鬥機", "667627542": "y-唐尼的丟失貨物",
}


def load(src):
    if re.match(r"^https?://", src):
        req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read().decode("utf-8", "replace")
    with open(src, encoding="utf-8", errors="replace") as f:
        return f.read()


def make_converter():
    try:
        from opencc import OpenCC
    except ImportError:
        raise SystemExit("需要簡轉繁套件：py -3 -m pip install opencc-python-reimplemented")
    return OpenCC("s2twp").convert


# ───────────────────────── 遊民星空（gamersky 路書） ─────────────────────────

class Roadbook(HTMLParser):
    """每個任務是一個 <article id="reader-node-編號" class="reader-node-card">：
    span.reader-node-card__node-id（A1…）、h3.reader-node-card__title、span.reader-node-card__tag-name（主線任務…）、
    div.reader-rich-content 裡的 <p> 段落與 img.reader-content-image 圖片（_S.jpg 是 600 寬縮圖，並帶寬高）。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.nodes = []
        self.cur = None
        self.cap = None     # (kind, 結束標籤, [文字])
        self.rich = 0       # 在 reader-rich-content 內的 div 深度
        self.skip = 0       # script / style / svg 內的東西不要

    @staticmethod
    def classes(attrs):
        return (dict(attrs).get("class") or "").split()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = self.classes(attrs)
        if tag == "article" and (a.get("id") or "").startswith("reader-node-"):
            self.cur = {"node": a["id"][len("reader-node-"):], "label": "", "title": "", "tags": [], "blocks": []}
            return
        c = self.cur
        if c is None:
            return
        if tag in ("script", "style", "svg"):
            self.skip += 1
            return
        if self.skip:
            return
        if tag == "div":
            if "reader-rich-content" in cls:
                self.rich = 1
            elif self.rich:
                self.rich += 1
        elif tag == "span" and "reader-node-card__node-id" in cls:
            self.cap = ("label", "span", [])
        elif tag == "h3" and "reader-node-card__title" in cls:
            self.cap = ("title", "h3", [])
        elif tag == "span" and "reader-node-card__tag-name" in cls:
            self.cap = ("tag", "span", [])
        elif tag == "p" and self.rich:
            self.cap = ("para", "p", [])
        elif tag == "br" and self.cap:
            self.cap[2].append(" ")
        elif tag == "img" and self.rich and "reader-content-image" in cls:
            src = a.get("src") or ""
            if src.startswith(IMG_BASE):
                blk = {"i": src[len(IMG_BASE):]}
                if (a.get("width") or "").isdigit() and (a.get("height") or "").isdigit():
                    blk["w"], blk["h"] = int(a["width"]), int(a["height"])
                c["blocks"].append(blk)

    def handle_endtag(self, tag):
        c = self.cur
        if c is None:
            return
        if tag in ("script", "style", "svg"):
            self.skip = max(0, self.skip - 1)
            return
        if tag == "article":
            self.nodes.append(c)
            self.cur, self.cap, self.rich = None, None, 0
            return
        if tag == "div" and self.rich:
            self.rich -= 1
        if self.cap and self.cap[1] == tag:
            kind, _, buf = self.cap
            text = re.sub(r"\s+", " ", "".join(buf)).strip()
            self.cap = None
            if not text:
                return
            if kind == "para":
                c["blocks"].append(text)
            elif kind == "tag":
                c["tags"].append(text)
            else:
                c[kind] = text

    def handle_data(self, data):
        if self.cur is not None and self.cap and not self.skip:
            self.cap[2].append(data)


def split_title(raw):
    """「支線-女鄰居雪莉」→ (支線, 女鄰居雪莉, "")；「垂釣（和卡爾開船）」→ (主線, 垂釣, 和卡爾開船)"""
    kind = "主線"
    m = re.match(r"^(支線|搶劫|可選|陌生人)\s*[-－—]\s*(.+)$", raw)
    if m:
        kind, raw = TYPE_PREFIX[m.group(1)], m.group(2)
    note = ""
    m = re.match(r"^(.*?)[（(](.+?)[）)]\s*$", raw)
    if m:
        raw, note = m.group(1).strip(), m.group(2).strip()
    return kind, raw, note


def parse_youmin(html, convert=lambda s: s):
    """回傳 (meta, 前言段落, 作者預告, 依文章順序的任務 list)。convert 是簡轉繁函式（測試時用恆等）。"""
    p = Roadbook()
    p.feed(html)
    nodes = [n for n in p.nodes if n["title"]]
    missions_raw = [n for n in nodes if n["tags"]]
    if not missions_raw:
        raise SystemExit("遊民星空：找不到任何任務（reader-node-card），來源頁面的結構可能變了")

    def conv_blocks(blocks):
        return [convert(b) if isinstance(b, str) else b for b in blocks]

    missions = []
    for n in missions_raw:
        kind, name, note = split_title(convert(n["title"]))
        missions.append({"node": n["node"], "type": kind, "name": name, "note": note, "blocks": conv_blocks(n["blocks"])})

    # 沒有任務標籤的節點（例如「正在推第2章：25號開更」）是作者預告
    notices = [{"title": convert(n["title"]), "text": " ".join(b for b in conv_blocks(n["blocks"]) if isinstance(b, str))}
               for n in nodes if not n["tags"]]

    # 第一個任務開頭：網站改版公告（丟掉）→「大家好，我是…」作者前言與「※」須知（獨立成「閱讀須知」）→ 正文
    intro, first = [], missions[0]["blocks"]
    start = next((i for i, b in enumerate(first) if isinstance(b, str) and b.startswith("大家好，我是")), None)
    if start is not None:
        end = start
        while end < len(first) and isinstance(first[end], str) and (first[end].startswith("大家好") or first[end].startswith("※")) \
                and end - start < 8:
            end += 1
        intro = first[start:end]
        missions[0]["blocks"] = first[end:]

    for m in missions:
        if m["type"] == "主線" and not any(isinstance(b, str) and MISSION_MARK.search(b) for b in m["blocks"]):
            m["type"] = "額外"

    text = re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)[\s\S]*?</\1>", "", html))
    stamp = re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", text)
    author = re.search(r"攻略组的(\w+)", html)
    meta = {"author": author.group(1) if author else "", "updated": stamp.group(0) if stamp else ""}
    return meta, intro, notices, missions


# ───────────────────────── promptowy ─────────────────────────

LI = re.compile(r'<li[^>]*>(?P<li>[\s\S]*?)</li>')
CARD = re.compile(r'<small[^>]*>(?P<label>[\s\S]*?)</small>\s*<br>\s*<a href="(?P<url>[^"]+)"[^>]*>(?P<en>[\s\S]*?)</a>'
                  r'\s*(?:<br>\s*<small[^>]*>(?P<sum>[\s\S]*?)</small>)?')


def text_of(fragment):
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", "", fragment))).strip()


def parse_promptowy(html):
    """回傳 {章節編號: {"sub": 章名, "missions": [{who, en, sum, url}]}}，任務依官方順序。"""
    html = re.sub(r"<(script|style)[\s\S]*?</\1>", "", html)
    chapters = {}
    for sec in re.split(r"(?=<h2[ >])", html):
        head = re.match(r"<h2[^>]*>([\s\S]*?)</h2>", sec)
        title = text_of(head.group(1)) if head else ""
        if title.startswith("接下來") and chapters:
            break
        if not title.startswith("GTA 6 任務"):
            continue
        m = re.search(r"第\s*(\d+)\s*章\s*[（(](.+?)[）)]", title)
        ctx_no, ctx_sub = (int(m.group(1)), m.group(2).strip()) if m else (None, "")
        for li in LI.finditer(sec):
            c = CARD.search(li.group("li"))
            if not c:
                continue
            url = htmllib.unescape(c.group("url"))
            if not url.startswith(PROMPTOWY_BASE):
                continue
            label = text_of(c.group("label"))
            who = ""
            lm = re.match(r"^第\s*(\d+)\s*章\s*·\s*\d+$", label)
            if lm:
                no = int(lm.group(1))
            else:
                no = ctx_no
                wm = re.match(r"^任務\s*\d+\s*·\s*(.+)$", label)
                who = wm.group(1).strip() if wm else ""
            if no is None:
                continue
            ch = chapters.setdefault(no, {"sub": "", "missions": []})
            if ctx_no == no and ctx_sub:
                ch["sub"] = ctx_sub
            ch["missions"].append({"who": who, "en": text_of(c.group("en")),
                                   "sum": text_of(c.group("sum") or ""), "url": url})
    if sum(len(c["missions"]) for c in chapters.values()) < 50:
        raise SystemExit("promptowy：任務數量太少，來源頁面的結構可能變了")
    return chapters


# ───────────────────────── 合併 ─────────────────────────

def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def merge(youmin_missions, prompt_chapters):
    """回傳 (chapters, aliases)。"""
    en_info = {}
    for no, ch in prompt_chapters.items():
        for m in ch["missions"]:
            en_info[m["en"]] = {"ch": no, **m}

    merged, cur_ch = [], min(prompt_chapters)
    for ym in youmin_missions:
        entry = dict(ym)
        en = YOUMIN_TO_EN.get(ym["name"])
        if en:
            info = en_info.get(en)
            if info is None:
                print(f"⚠ 遊民的「{ym['name']}」對應的英文名「{en}」在 promptowy 找不到，當成遊民獨有任務", file=sys.stderr)
            else:
                entry.update(en=en, who=info["who"], sum=info["sum"], url=info["url"])
                cur_ch = info["ch"]
        elif ym["type"] == "主線" and ym["name"] not in YOUMIN_ONLY_MAIN:
            print(f"⚠ 遊民的主線任務「{ym['name']}」沒有在 YOUMIN_TO_EN 登記，當成遊民獨有任務", file=sys.stderr)
        entry["ch"] = cur_ch
        entry["id"] = ("p-" + slug(entry["en"])) if entry.get("en") else "y-" + ym["node"]
        merged.append(entry)

    by_en = {e["en"]: e for e in merged if e.get("en")}
    prev = None
    for no in sorted(prompt_chapters):
        for pm in prompt_chapters[no]["missions"]:
            if pm["en"] in by_en:
                prev = by_en[pm["en"]]
                continue
            entry = {"id": "p-" + slug(pm["en"]), "ch": no, "type": "主線", "name": pm["en"], "en": pm["en"],
                     "who": pm["who"], "sum": pm["sum"], "url": pm["url"], "blocks": []}
            at = 0 if prev is None else next(i for i, e in enumerate(merged) if e is prev) + 1
            merged.insert(at, entry)
            by_en[pm["en"]] = prev = entry

    ids = [e["id"] for e in merged]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        raise SystemExit(f"任務 ID 重複：{sorted(dup)}")

    chapters = []
    for no in sorted({e["ch"] for e in merged}):
        missions = []
        for e in merged:
            if e["ch"] != no:
                continue
            m = {k: e[k] for k in ("id", "type", "name", "en", "who", "sum", "note", "url") if e.get(k)}
            if e.get("blocks"):
                m["blocks"] = e["blocks"]
            missions.append(m)
        sub = prompt_chapters.get(no, {}).get("sub", "")
        chapters.append({"id": f"c{no}", "no": no, "title": f"第 {no} 章", "sub": sub, "missions": missions})

    aliases = {LEGACY_Y_IDS[e["node"]]: e["id"] for e in merged
               if e.get("node") in LEGACY_Y_IDS and LEGACY_Y_IDS[e["node"]] != e["id"]}
    return chapters, aliases


def collect_index(chapters):
    """從段落抓「獎盃【…】」「可選任務【…】」，索引頁用。p 是該段落在任務 blocks 裡的位置。"""
    trophies, optionals = [], []
    for ch in chapters:
        for m in ch["missions"]:
            for i, b in enumerate(m.get("blocks", [])):
                if isinstance(b, str):
                    for name in re.findall(r"獎盃\s*【(.+?)】", b):
                        trophies.append({"name": name, "m": m["id"], "p": i})
                    for name in re.findall(r"可選任務\s*【(.+?)】", b):
                        optionals.append({"name": name, "m": m["id"], "p": i})
    return trophies, optionals


def build(youmin_html, prompt_html, convert=lambda s: s):
    meta, intro, notices, ymissions = parse_youmin(youmin_html, convert)
    chapters, aliases = merge(ymissions, parse_promptowy(prompt_html))
    trophies, optionals = collect_index(chapters)
    return {
        "title": "GTA 6 全任務攻略",
        "builtOn": date.today().isoformat(),
        "sourceUpdated": meta["updated"],
        "imgBase": IMG_BASE,
        "sources": [
            {"name": f"遊民星空（作者 {meta['author']}）逐步圖文攻略" if meta["author"] else "遊民星空逐步圖文攻略",
             "url": YOUMIN_URL},
            {"name": "promptowy.com 主線任務清單", "url": PROMPTOWY_URL},
        ],
        "intro": intro,
        "notices": notices,
        "chapters": chapters,
        "aliases": aliases,
        "trophies": trophies,
        "optionals": optionals,
    }


def main(argv):
    youmin = argv[1] if len(argv) > 1 else YOUMIN_URL
    prompt = argv[2] if len(argv) > 2 else PROMPTOWY_URL
    out = argv[3] if len(argv) > 3 else "gta6/data.js"
    data = build(load(youmin), load(prompt), make_converter())
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("// 由 scripts/build_gta6.py 產生，不要手改。\n")
        f.write("window.GUIDE = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n")
    ms = [m for c in data["chapters"] for m in c["missions"]]
    full = sum(1 for m in ms if m.get("blocks"))
    imgs = sum(1 for m in ms for b in m.get("blocks", []) if isinstance(b, dict))
    print(f"{len(data['chapters'])} 章、{len(ms)} 個任務（{full} 個有圖文、{len(ms) - full} 個只有摘要）、"
          f"{imgs} 張圖、{len(data['trophies'])} 個獎盃、{len(data['aliases'])} 個舊 ID 對照 → {out}")
    for n in data["notices"]:
        print(f"作者預告：{n['title']}　{n['text']}")
    print(f"遊民原文更新時間：{data['sourceUpdated']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
