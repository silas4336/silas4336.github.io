"""用法：py -3 scripts/build_gta6.py [遊民星空來源] [promptowy 來源] [輸出檔，預設 gta6/data.js]
來源可以是本機 HTML 檔或網址，省略就抓下面兩個預設網址。

把兩份 GTA 6 攻略合併成 gta6/data.js，給 gta6/ 的攻略 PWA 用。只用標準函式庫。

  1. 遊民星空《GTA6 全任務流程圖文攻略》（娛樂計程車轉載頁）：逐步圖文，含支線、搶劫、陌生人，
     但原作者還在更新，目前只寫到第 2 章開頭。
  2. promptowy.com《GTA 6 主線任務攻略》：第 1～5 章全部約 100 個主線任務的清單（官方英文名、角色、
     一句話摘要、單一任務頁連結），沒有逐步內容。

合併規則：
  - 骨架是遊民星空的遊玩順序（支線等穿插在原位）。兩邊對得上的任務（YOUMIN_TO_EN）合成一筆：
    中文名與圖文來自遊民，英文名、角色、摘要、連結來自 promptowy。
  - promptowy 有、遊民還沒寫到的任務，依 promptowy 的順序接在前一個任務後面，只有摘要和外連結。
  - 原作者之後補寫了某個任務，就在 YOUMIN_TO_EN 加一行對應，重跑即可（新任務名對不上會印出警告）。
  - 任務 ID 用英文名（promptowy 有的）或中文名（只有遊民有的）產生，來源更新後 ID 不變，已勾選的進度不會跑掉。

重跑後把 gta6/sw.js 的 CACHE 版本號加 1，已安裝的 PWA 才會收到新內容。

安全：只保留章節標題、任務標題、純文字、來自 img1.entertainment14.net 的圖片網址，以及
https://promptowy.com/ 的任務頁連結；其他標籤（廣告、樣式、腳本）全部丟掉。
"""
import html as htmllib
import json
import re
import sys
import urllib.request
from datetime import date
from html.parser import HTMLParser

YOUMIN_URL = ("https://www.entertainment14.net/blog/post/111014483-"
              "%E4%BF%A0%E7%9B%9C%E7%8D%B5%E8%BB%8A%E6%89%8B-6-gta-6-"
              "%E5%85%A8%E4%BB%BB%E5%8B%99%E6%B5%81%E7%A8%8B%E5%9C%96%E6%96%87%E6%94%BB%E7%95%A5")
PROMPTOWY_URL = "https://promptowy.com/zh-tw/gta-6/%E4%BB%BB%E5%8B%99%E6%94%BB%E7%95%A5/"
IMG_BASE = "https://img1.entertainment14.net/"
PROMPTOWY_BASE = "https://promptowy.com/"

TYPE_PREFIX = {"支線": "支線", "搶劫": "搶劫", "可選": "可選", "陌生人": "陌生人"}
# 沒有前綴的標題預設是主線；但內文完全沒出現「任務【…】」的（例如「偷犀牛坦克、戰鬥機」）只是順手的技巧，歸為「額外」
MISSION_MARK = re.compile(r"任務\s*【")

# 遊民星空的中文任務名 → promptowy 的英文任務名。其餘遊民任務（支線、搶劫、陌生人、可選、額外）沒有對應。
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


def load(src):
    if re.match(r"^https?://", src):
        req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read().decode("utf-8", "replace")
    with open(src, encoding="utf-8", errors="replace") as f:
        return f.read()


# ───────────────────────── 遊民星空 ─────────────────────────

class Article(HTMLParser):
    """從 div.entry-content 取出 [("h3"|"h4"|"p"|"hr"|"img", 內容)]，依文章順序。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items = []
        self.in_article = False
        self.div_depth = 0
        self.skip = 0          # script / style / noscript 內的東西不要
        self.cur = None        # 目前收集中的 (tag, [文字])

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if not self.in_article:
            if tag == "div" and "entry-content" in (a.get("class") or "").split():
                self.in_article, self.div_depth = True, 1
            return
        if tag == "div":
            self.div_depth += 1
        elif tag in ("script", "style", "noscript"):
            self.skip += 1
        elif self.skip:
            return
        elif tag in ("h3", "h4", "p"):
            self.cur = (tag, [])
        elif tag == "hr":
            self.items.append(("hr", ""))
        elif tag == "br" and self.cur:
            self.cur[1].append(" ")
        elif tag == "img":
            src = a.get("data-lazy-src") or a.get("src") or ""
            if src.startswith(IMG_BASE):
                self.items.append(("img", src[len(IMG_BASE):]))

    def handle_endtag(self, tag):
        if not self.in_article:
            return
        if tag == "div":
            self.div_depth -= 1
            if self.div_depth == 0:
                self.in_article = False
        elif tag in ("script", "style", "noscript"):
            self.skip = max(0, self.skip - 1)
        elif self.cur and tag == self.cur[0]:
            text = re.sub(r"\s+", " ", "".join(self.cur[1])).strip()
            if text:
                self.items.append((tag, text))
            self.cur = None

    def handle_data(self, data):
        if self.in_article and self.cur and not self.skip:
            self.cur[1].append(data)


def split_title(raw):
    """「支線-女鄰居雪麗」→ (支線, 女鄰居雪麗, "")；「垂釣（和卡爾開船）」→ (主線, 垂釣, 和卡爾開船)"""
    kind = "主線"
    m = re.match(r"^(支線|搶劫|可選|陌生人)\s*[-－—]\s*(.+)$", raw)
    if m:
        kind, raw = TYPE_PREFIX[m.group(1)], m.group(2)
    note = ""
    m = re.match(r"^(.*?)[（(](.+?)[）)]\s*$", raw)
    if m:
        raw, note = m.group(1).strip(), m.group(2).strip()
    return kind, raw, note


def parse_youmin(html):
    """回傳 (meta, 前言段落, 依文章順序的任務 list)。章節標題（h3）不用，章節以 promptowy 的官方章節為準。"""
    p = Article()
    p.feed(html)
    items = p.items
    if not any(t == "h4" for t, _ in items):
        raise SystemExit("遊民星空：找不到任何任務標題（h4），來源頁面的結構可能變了")

    meta = {"author": "", "source": ""}
    for t, v in items:
        if t == "h3":
            break
        if t == "p":
            m = re.match(r"^(作者|來源)\s*[:：]\s*(.+)$", v)
            if m:
                meta["author" if m.group(1) == "作者" else "source"] = m.group(2)

    missions, cur, intro, seen_hr = [], None, [], False
    for t, v in items:
        if t == "h4":
            kind, name, note = split_title(v)
            cur = {"type": kind, "name": name, "note": note, "blocks": []}
            missions.append(cur)
            seen_hr = False
        elif cur is None or t == "h3":
            continue
        elif t == "hr":
            # 第一個任務裡，分隔線前是網站改版公告（丟掉），後面開頭幾段是作者的前言（獨立成「閱讀須知」）
            if not seen_hr and not intro and not any(isinstance(b, dict) for b in cur["blocks"]):
                cur["blocks"], seen_hr = [], True
        elif t == "p":
            if seen_hr and not any(isinstance(b, dict) for b in cur["blocks"]) \
                    and (v.startswith("大家好") or v.startswith("※")) and len(intro) < 8:
                intro.append(v)
            else:
                cur["blocks"].append(v)
        elif t == "img":
            cur["blocks"].append({"i": v})

    for m in missions:
        if m["type"] == "主線" and not any(isinstance(b, str) and MISSION_MARK.search(b) for b in m["blocks"]):
            m["type"] = "額外"
    return meta, intro, missions


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
        entry["ch"] = cur_ch
        entry["id"] = ("p-" + slug(en)) if entry.get("en") else "y-" + ym["name"]
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
    return chapters


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


def build(youmin_html, prompt_html):
    meta, intro, ymissions = parse_youmin(youmin_html)
    chapters = merge(ymissions, parse_promptowy(prompt_html))
    trophies, optionals = collect_index(chapters)
    return {
        "title": "GTA 6 全任務攻略",
        "builtOn": date.today().isoformat(),
        "imgBase": IMG_BASE,
        "sources": [
            {"name": f"遊民星空（作者 {meta['author']}）逐步圖文攻略" if meta["author"] else "遊民星空逐步圖文攻略",
             "url": YOUMIN_URL},
            {"name": "promptowy.com 主線任務清單", "url": PROMPTOWY_URL},
        ],
        "intro": intro,
        "chapters": chapters,
        "trophies": trophies,
        "optionals": optionals,
    }


def main(argv):
    youmin = argv[1] if len(argv) > 1 else YOUMIN_URL
    prompt = argv[2] if len(argv) > 2 else PROMPTOWY_URL
    out = argv[3] if len(argv) > 3 else "gta6/data.js"
    data = build(load(youmin), load(prompt))
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("// 由 scripts/build_gta6.py 產生，不要手改。\n")
        f.write("window.GUIDE = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n")
    ms = [m for c in data["chapters"] for m in c["missions"]]
    full = sum(1 for m in ms if m.get("blocks"))
    imgs = sum(1 for m in ms for b in m.get("blocks", []) if isinstance(b, dict))
    print(f"{len(data['chapters'])} 章、{len(ms)} 個任務（{full} 個有圖文、{len(ms) - full} 個只有摘要）、"
          f"{imgs} 張圖、{len(data['trophies'])} 個獎盃 → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
