"""用法：py -3 scripts/build_gta6.py [遊民星空來源] [oplay 快取資料夾，預設 .oplay-cache] [輸出檔，預設 gta6/data.js]

整合兩份 GTA 6 攻略成 gta6/data.js，給 gta6/ 的攻略 PWA 用。只用標準函式庫。

  1. oplay.cc（繁體中文，台灣官方譯名）：第 1～5 章全部 130 個主線任務，每個都有「重點」「逐步文字攻略（含按鍵）」
     「常見卡關」，另有每章的「會錯過的事／賺錢／開放的功能／支線／人物…」重點頁，以及 28 篇攻略筆記。
     先用 scripts/fetch_oplay.py 抓到本機快取（約 34 頁，每頁間隔 1 秒），這裡只讀快取、不連網。
  2. 遊民星空原站（gamersky.com 路書，簡體）：逐步圖文（有截圖），含支線、搶劫、陌生人，目前只寫到第 2 章第 1 個任務。
     用 OpenCC s2twp 轉成台灣繁體（需要：py -3 -m pip install opencc-python-reimplemented）。最後一則作者預告存成 notices。

合併規則：
  - 骨架是 oplay 的任務順序（官方順序、含章節）。兩邊對得上的任務（YOUMIN_TO_SLUG）合成一筆：
    名稱、摘要、重點與步驟取 oplay，圖文取遊民；遊民的叫法留在 aka 讓搜尋找得到。
  - 遊民獨有的任務（支線、搶劫、陌生人、可選、額外…）依遊民的順序，插在它前面那個已對上的任務後面。
  - 原作者補寫了某個任務，就在 YOUMIN_TO_SLUG 加一行對應，重跑即可（對不上會印警告）。
  - 任務 ID：oplay 的任務用 p-<oplay 代號>（例 p-gone-fishing），只有遊民有的用 y-<遊民節點編號>。
    來源改標題或補內容時 ID 不變，已勾選的進度不會跑掉；舊 ID 對照存在輸出的 aliases，頁面啟動時會轉換。

重跑後把 gta6/sw.js 的 CACHE 版本號加 1，已安裝的 PWA 才會收到新內容。

安全：只保留文字（含 **粗體**、⟦按鍵⟧ 兩種小標記）、來自 img1.gamersky.com 的圖片網址與寬高、https://oplay.cc/ 的連結；
其他標籤（廣告、樣式、腳本）全部丟掉。img1.gamersky.com 有防盜連結：請求帶 Referer 會 403，所以頁面的圖片一律要 no-referrer。
"""
import json
import os
import re
import sys
import urllib.request
from datetime import date
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oplay_parse  # noqa: E402

YOUMIN_URL = "https://www.gamersky.com/tools/guide-map/roadbooks/55"
OPLAY_URL = "https://oplay.cc/gta6/"
IMG_BASE = "https://img1.gamersky.com/"
OPLAY_BASE = "https://oplay.cc/"

TYPE_PREFIX = {"支線": "支線", "搶劫": "搶劫", "可選": "可選", "陌生人": "陌生人"}
# 沒有前綴的標題預設是主線；但內文完全沒出現「任務【…】」的（例如「偷犀牛坦克、戰鬥機」）只是順手的技巧，歸為「額外」
MISSION_MARK = re.compile(r"任務\s*【")

# 遊民星空的（繁體）任務名 → oplay 的任務代號（story.<代號>）。其餘遊民任務（支線、搶劫、陌生人、額外…）沒有對應。
YOUMIN_TO_SLUG = {
    "序幕": "prologue",
    "垂釣": "gone-fishing",
    "整裝待發": "gear-up",
    "作坊費用": "lab-fees",
    "小剮蹭而已": "just-a-scratch",
    "避人耳目": "unwanted-attention",
    "管道活": "pipework",
    "嘿阿諾德": "hey-arnold",
    "島嶼之夢": "island-dreams",
    "風水": "feng-shui",
    "回家": "coming-home",
    "給唐尼擦屁股": "clean-up-after-donnie",
    "元交": "buck-me",
    "如夢方醒": "down-to-earth",
    "找到丟失貨物": "find-the-lost-drugs",
    "郎朗晴空": "clear-skies",
    "自在一日": "day-release",
    "沼澤困境": "swamped",
    "消失的老唐": "don-gone",
    "唐尼的丟失貨物": "donnies-lost-drugs",
    "漁過天晴": "recalibration",
    "遊客陷阱": "tourist-trap",
    "甜蜜的家": "home-sweet-home",
    "出院時間": "discharge-time",
    "包中何物": "whats-in-the-bag",
}

# 遊民的主線任務裡，oplay 沒有對應的（只是家裡操作教學之類）：不用警告
YOUMIN_ONLY_MAIN = {"傑森的家"}

# 舊版曾用 promptowy 的英文名產生 ID（p-…），其中這幾個和 oplay 的代號只差標點；舊 → 新
LEGACY_P_IDS = {
    "p-what-s-in-the-bag": "p-whats-in-the-bag",
    "p-dealer-s-choice": "p-dealers-choice",
    "p-clonin-keys-makin-gs": "p-clonin-keys",
    "p-child-s-play": "p-childs-play",
}

# 更早的版本（轉載頁）用「y-中文名」當遊民獨有任務的 ID；現在改用遊民節點編號。節點編號 → 舊 ID，產生 aliases 用。
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


# ───────────────────────── oplay ─────────────────────────

def read_oplay(cache_dir):
    """從 fetch_oplay.py 的快取讀 (章節 list, 筆記分類, 筆記 list)。"""
    def read(name):
        path = os.path.join(cache_dir, name)
        if not os.path.exists(path):
            raise SystemExit(f"找不到 {path}，請先執行：py -3 scripts/fetch_oplay.py {cache_dir}")
        with open(path, encoding="utf-8") as f:
            return f.read()

    chapters = [oplay_parse.parse_chapter(read(f"chapters-{n}.html"), n) for n in (1, 2, 3, 4, 5)]
    cats = oplay_parse.parse_notes_index(read("notes.html"))
    notes = []
    for cat in cats:
        for n in cat["notes"]:
            doc = oplay_parse.parse_note(read(f"notes-{n['slug']}.html"))
            notes.append({"slug": n["slug"], "cat": cat["id"], "title": n["title"] or doc["title"], "sub": n["sub"],
                          "badge": n["badge"], "stamp": doc["stamp"], "blocks": doc["blocks"]})
    return chapters, [{"id": c["id"], "title": c["title"]} for c in cats], notes


def core_en(en):
    """「Gear Up (Pick Up Another Gun)」→ ("Gear Up", "Pick Up Another Gun")"""
    m = re.match(r"^(.*?)\s*\((.+)\)\s*$", en)
    return (m.group(1).strip(), m.group(2).strip()) if m else (en.strip(), "")


def who_of(k):
    m = re.search(r"用(傑森|露西亞)", k or "")
    return m.group(1) if m else ""


# ───────────────────────── 合併 ─────────────────────────

def slug_of(m):
    return m["slug"].split(".", 1)[1]


def oplay_mission(m):
    en, sub = core_en(m.get("en", ""))
    slug = slug_of(m)
    out = {"id": "p-" + slug, "slug": slug, "type": "搶劫" if slug.startswith("hit-") else "主線", "name": m["n"],
           "en": en, "who": who_of(m.get("k")), "hard": 1 if "常卡" in (m.get("k") or "") else 0,
           "sum": m.get("a", ""), "note": sub, "url": m.get("url", ""),
           "keys": m.get("keys") or [], "steps": m.get("body") or [], "stuck": m.get("stuck") or []}
    return out


def merge(youmin_missions, oplay_chapters):
    """回傳 (chapters, aliases)。oplay 的順序為骨架，遊民獨有的任務插在它在遊民順序裡前一個已對上的任務後面。"""
    by_slug = {}
    seq = []   # [(章號, 任務 dict)]，oplay 順序
    for ch in oplay_chapters:
        for m in ch["missions"]:
            e = oplay_mission(m)
            e["ch"] = ch["no"]
            by_slug[e["slug"]] = e
            seq.append(e)

    extras = []   # (遊民任務, 它前面已對上的 oplay 任務或 None)
    prev = None
    for ym in youmin_missions:
        slug = YOUMIN_TO_SLUG.get(ym["name"])
        target = by_slug.get(slug) if slug else None
        if slug and target is None:
            print(f"⚠ 遊民的「{ym['name']}」對應的 oplay 代號「{slug}」找不到，當成遊民獨有任務", file=sys.stderr)
        if target is not None:
            if not target.get("en"):          # oplay 的名稱不像標題（例如「第一章〈身陷沼澤〉之後的任務」）：用遊民的名字
                target["aka"], target["name"] = target["name"], ym["name"]
            elif ym["name"] != target["name"]:
                target["aka"] = ym["name"]
            if ym["type"] != "主線":          # 例如遊民歸為「可選」的丟失貨物
                target["type"] = ym["type"]
            if ym.get("note") and not target.get("note"):
                target["note"] = ym["note"]
            target["blocks"] = ym["blocks"]
            target["node"] = ym["node"]
            prev = target
        else:
            if ym["type"] == "主線" and ym["name"] not in YOUMIN_ONLY_MAIN:
                print(f"⚠ 遊民的主線任務「{ym['name']}」沒有在 YOUMIN_TO_SLUG 登記，當成遊民獨有任務", file=sys.stderr)
            extras.append((ym, prev))

    merged = list(seq)
    for ym, anchor in extras:
        entry = {"id": "y-" + ym["node"], "node": ym["node"], "type": ym["type"], "name": ym["name"], "note": ym["note"],
                 "blocks": ym["blocks"]}
        if anchor is None:
            entry["ch"] = merged[0]["ch"]
            merged.insert(0, entry)
        else:
            at = next(i for i, e in enumerate(merged) if e is anchor) + 1
            while at < len(merged) and merged[at].get("node") and merged[at].get("id", "").startswith("y-"):
                at += 1               # 同一個前一任務後面的多個遊民任務，保持遊民順序
            entry["ch"] = anchor["ch"]
            merged.insert(at, entry)

    ids = [e["id"] for e in merged]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        raise SystemExit(f"任務 ID 重複：{sorted(dup)}")

    chapters = []
    by_no = {c["no"]: c for c in oplay_chapters}
    for no in sorted(by_no):
        ch = by_no[no]
        missions = []
        for e in merged:
            if e["ch"] != no:
                continue
            m = {k: e[k] for k in ("id", "type", "name", "aka", "en", "who", "sum", "note", "url") if e.get(k)}
            if e.get("hard"):
                m["hard"] = 1
            for k in ("keys", "steps", "stuck"):
                if e.get(k):
                    m[k] = e[k]
            if e.get("blocks"):
                m["blocks"] = e["blocks"]
            missions.append(m)
        chapters.append({"id": f"c{no}", "no": no, "title": f"第 {no} 章", "sub": ch["sub"], "lead": ch["lead"],
                         "missions": missions, "info": ch["sections"]})

    aliases = {}
    for e in merged:
        node = e.get("node")
        if node and e["id"] != "y-" + node:
            aliases["y-" + node] = e["id"]
        if node and node in LEGACY_Y_IDS and LEGACY_Y_IDS[node] != e["id"]:
            aliases[LEGACY_Y_IDS[node]] = e["id"]
    for old, new in LEGACY_P_IDS.items():
        if new in ids:
            aliases[old] = new
    return chapters, aliases


def collect_index(chapters):
    """從遊民段落抓「獎盃【…】」「可選任務【…】」，再加上 oplay 各章的「獎盃」區塊。p 是段落在任務 blocks 裡的位置。"""
    trophies, optionals = [], []
    for ch in chapters:
        for m in ch["missions"]:
            for i, b in enumerate(m.get("blocks", [])):
                if isinstance(b, str):
                    for name in re.findall(r"獎盃\s*【(.+?)】", b):
                        trophies.append({"name": name, "m": m["id"], "p": i})
                    for name in re.findall(r"可選任務\s*【(.+?)】", b):
                        optionals.append({"name": name, "m": m["id"], "p": i})
        for sec in ch.get("info", []):
            if sec["title"] == "獎盃":
                for r in sec["rows"]:
                    trophies.append({"name": r["n"], "ch": ch["no"], "a": r.get("a", "")})
    return trophies, optionals


def build(youmin_html, oplay, convert=lambda s: s):
    """oplay 是 read_oplay() 的結果 (章節, 筆記分類, 筆記)。"""
    meta, intro, notices, ymissions = parse_youmin(youmin_html, convert)
    oplay_chapters, note_cats, notes = oplay
    chapters, aliases = merge(ymissions, oplay_chapters)
    trophies, optionals = collect_index(chapters)
    return {
        "title": "GTA 6 全任務攻略",
        "builtOn": date.today().isoformat(),
        "sourceUpdated": meta["updated"],
        "imgBase": IMG_BASE,
        "sources": [
            {"name": "oplay.cc 攻略（任務步驟、章節重點、筆記）", "url": OPLAY_URL},
            {"name": f"遊民星空（作者 {meta['author']}）逐步圖文攻略" if meta["author"] else "遊民星空逐步圖文攻略",
             "url": YOUMIN_URL},
        ],
        "intro": intro,
        "notices": notices,
        "chapters": chapters,
        "noteCats": note_cats,
        "notes": notes,
        "aliases": aliases,
        "trophies": trophies,
        "optionals": optionals,
    }


def main(argv):
    youmin = argv[1] if len(argv) > 1 else YOUMIN_URL
    cache = argv[2] if len(argv) > 2 else ".oplay-cache"
    out = argv[3] if len(argv) > 3 else "gta6/data.js"
    data = build(load(youmin), read_oplay(cache), make_converter())
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("// 由 scripts/build_gta6.py 產生，不要手改。\n")
        f.write("window.GUIDE = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n")
    ms = [m for c in data["chapters"] for m in c["missions"]]
    imgs = sum(1 for m in ms for b in m.get("blocks", []) if isinstance(b, dict))
    print(f"{len(data['chapters'])} 章、{len(ms)} 個任務（{sum(1 for m in ms if m.get('steps'))} 個有逐步文字、"
          f"{sum(1 for m in ms if m.get('blocks'))} 個有遊民圖文）、{imgs} 張圖、{len(data['notes'])} 篇筆記、"
          f"{len(data['trophies'])} 個獎盃、{len(data['aliases'])} 個舊 ID 對照 → {out}（{os.path.getsize(out) // 1024} KB）")
    for n in data["notices"]:
        print(f"遊民作者預告：{n['title']}　{n['text']}")
    print(f"遊民原文更新時間：{data['sourceUpdated']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
