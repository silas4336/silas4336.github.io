"""用法：py -3 -m unittest discover -s scripts -p "test_*.py"（唯讀，只用標準函式庫）

1. scripts/check_i18n.py 各條規則的單元測試（用暫存資料夾的假頁面）
2. 主站 12 頁（中英 index.html、work-*.html）的本機連結與圖片都找得到檔案
3. sitemap.xml 列的網址都對得到檔案，主站每一頁也都在 sitemap 裡
4. math-logic/、neko/、gta6/、preview-*/ 每頁都有 noindex
5. gta6/ 攻略 PWA：data.js 結構、離線檔案清單、不在 sitemap；scripts/build_gta6.py 的解析與合併規則
"""
import contextlib
import glob
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import build_gta6  # noqa: E402
import check_i18n  # noqa: E402

PAGE = """<!doctype html><html><head><title>2024 標題 99</title><style>.a{{width:42px}}</style></head>
<body>{body}<script>var x = 77;</script></body></html>"""


def write(root, rel, body):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(PAGE.format(body=body))
    return path


def run_main(root):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = check_i18n.main(root)
    return code, out.getvalue()


class ParseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_ignores_head_script_style_and_years(self):
        p = write(self.root, "a.html", "<p>2025.10 上線，3 個專案，1,200 位使用者</p>")
        digits, words, imgs, links, to_parent = check_i18n.parse(p)
        self.assertEqual(dict(digits), {"3": 1, "1,200": 1})

    def test_english_number_words(self):
        p = write(self.root, "a.html", "<p>Eight agents and three reviewers</p>")
        _, words, _, _, _ = check_i18n.parse(p)
        self.assertEqual(dict(words), {"8": 1, "3": 1})

    def test_images_drop_lang_suffix_and_links_to_work_pages(self):
        p = write(self.root, "a.html", '<img src="assets/x-en.webp"><img src="../assets/y.jpg">'
                                       '<a href="work-crm.html#top">crm</a><a href="https://e.com">e</a>')
        _, _, imgs, links, _ = check_i18n.parse(p)
        self.assertEqual(dict(imgs), {"x.webp": 1, "y.jpg": 1})
        self.assertEqual(dict(links), {"work-crm.html": 1})

    def test_parent_links_except_language_switch(self):
        p = write(self.root, "a.html", '<a href="../work-crm.html">中文</a><a href="../" hreflang="zh-Hant">中</a>')
        *_, to_parent = check_i18n.parse(p)
        self.assertEqual(to_parent, ["../work-crm.html"])

    def test_root_absolute_links_to_chinese_pages(self):
        """之前只抓 ../ 開頭，/work-crm.html 或完整網址連回中文頁會漏掉。"""
        p = write(self.root, "a.html",
                  '<a href="/work-crm.html">x</a><a href="/">x</a><a href="https://silas4336.github.io/work-side.html#a">x</a>'
                  '<a href="/en/work-crm.html">ok</a><a href="https://silas4336.github.io/en/">ok</a>'
                  '<a href="/assets/cv.pdf">ok</a><a href="//cdn.example.com/x.html">ok</a>'
                  '<a href="/work-crm.html" hreflang="zh-Hant">中文</a>')
        *_, to_parent = check_i18n.parse(p)
        self.assertEqual(to_parent, ["/work-crm.html", "/", "https://silas4336.github.io/work-side.html#a"])

    def test_num_diff_rules(self):
        C = check_i18n.Counter
        self.assertEqual(check_i18n.num_diff(C({"8": 1}), C(), C({"8": 1})), [])  # eight 對上 8
        self.assertEqual(check_i18n.num_diff(C(), C(), C({"1": 2})), [])  # 英文 one 而中文寫「一」
        self.assertEqual(len(check_i18n.num_diff(C({"5": 1}), C({"6": 1}), C())), 2)
        self.assertEqual(len(check_i18n.num_diff(C(), C({"5": 1}), C())), 1)  # 英文多出數字

    def test_version_numbers_do_not_crash(self):
        """之前排序用 float()，頁面出現 1.2.3 會整支當掉。"""
        C = check_i18n.Counter
        out = check_i18n.num_diff(C({"1.2.3": 1, "10": 1}), C({"1.2.3": 1, "2": 1}), C())
        self.assertEqual(out, ["2（中 0／英 1）", "10（中 1／英 0）"])

    def test_main_reports_mismatch_and_missing_english(self):
        write(self.root, "index.html", "<p>3 個專案</p>")
        write(self.root, "en/index.html", "<p>three projects</p>")
        write(self.root, "work-a.html", '<p>5 頁</p><img src="assets/a.webp">')
        write(self.root, "en/work-a.html", '<p>6 pages</p><a href="../index.html">zh</a>')
        write(self.root, "work-b.html", "<p>沒有英文版</p>")
        code, out = run_main(self.root)
        self.assertEqual(code, 1)
        self.assertIn("✓ index.html", out)
        self.assertIn("✗ work-a.html", out)
        self.assertIn("圖片", out)
        self.assertIn("英文頁連到中文頁", out)
        self.assertIn("✗ work-b.html: 沒有英文版", out)
        self.assertIn("2 頁不一致", out)

    def test_main_passes_when_consistent(self):
        write(self.root, "index.html", '<p>3 個</p><img src="assets/a-zh.webp">')
        write(self.root, "en/index.html", '<p>3 items</p><img src="assets/a-en.webp">')
        code, out = run_main(self.root)
        self.assertEqual(code, 0, out)


class Refs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("a", "img", "link", "script", "source"):
            for key in ("href", "src"):
                if a.get(key):
                    self.refs.append(a[key])
        if a.get("srcset"):
            self.refs += [part.strip().split()[0] for part in a["srcset"].split(",") if part.strip()]


def main_pages():
    pages = []
    for base in ("", "en"):
        pages.append(os.path.join(ROOT, base, "index.html"))
        pages += sorted(glob.glob(os.path.join(ROOT, base, "work-*.html")))
    return pages


class SiteTest(unittest.TestCase):
    def test_main_pages_exist(self):
        self.assertEqual(len(main_pages()), 12)
        for p in main_pages():
            self.assertTrue(os.path.exists(p), p)

    def test_local_links_and_images_exist(self):
        missing = []
        for page in main_pages():
            r = Refs()
            with open(page, encoding="utf-8") as f:
                r.feed(f.read())
            for ref in r.refs:
                if re.match(r"^(https?:|mailto:|tel:|data:|#|//)", ref):
                    continue
                rel = ref.split("#")[0].split("?")[0]
                if not rel:
                    continue
                if rel.startswith("/"):
                    target = os.path.join(ROOT, rel.lstrip("/"))
                else:
                    target = os.path.join(os.path.dirname(page), rel)
                target = os.path.normpath(target)
                if os.path.isdir(target):
                    target = os.path.join(target, "index.html")
                if not os.path.exists(target):
                    missing.append(f"{os.path.relpath(page, ROOT)} → {ref}")
        self.assertEqual(missing, [], "找不到的連結／圖片")

    def test_sitemap_matches_main_pages(self):
        with open(os.path.join(ROOT, "sitemap.xml"), encoding="utf-8") as f:
            xml = f.read()
        locs = re.findall(r"<loc>https://silas4336\.github\.io/([^<]*)</loc>", xml)
        files = set()
        for loc in locs:
            rel = loc + "index.html" if loc == "" or loc.endswith("/") else loc
            self.assertTrue(os.path.exists(os.path.join(ROOT, rel)), "sitemap 列了不存在的頁面 " + loc)
            files.add(os.path.normpath(os.path.join(ROOT, rel)))
        self.assertEqual(files, {os.path.normpath(p) for p in main_pages()}, "sitemap 和主站頁面不一致")
        for lastmod in re.findall(r"<lastmod>([^<]*)</lastmod>", xml):
            self.assertRegex(lastmod, r"^\d{4}-\d{2}-\d{2}$")

    def test_no_cache_or_env_files_tracked(self):
        """整個 repo 都會發佈到 GitHub Pages：快取、瀏覽器暫存與 .env 要被 .gitignore 擋掉，也不能已經在版控裡。"""
        with open(os.path.join(ROOT, ".gitignore"), encoding="utf-8") as f:
            rules = f.read().split()
        for rule in ("__pycache__/", "*.pyc", ".playwright-cli/", ".env", ".env.*"):
            self.assertIn(rule, rules)
        r = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        bad = [f for f in r.stdout.splitlines()
               if "__pycache__/" in f or f.endswith(".pyc")
               or f == ".playwright-cli" or f.startswith(".playwright-cli/") or "/.playwright-cli/" in f
               or re.search(r"(^|/)\.env(\.|$)", f)]
        self.assertEqual(bad, [])

    def test_robots_points_to_sitemap(self):
        with open(os.path.join(ROOT, "robots.txt"), encoding="utf-8") as f:
            self.assertIn("Sitemap: https://silas4336.github.io/sitemap.xml", f.read())

    def test_hidden_sections_are_noindex(self):
        """robots.txt 刻意不擋 math-logic/、neko/、gta6/、preview-*/，所以每個 html 都要自己帶 noindex。"""
        pages = [p for pat in ("math-logic/**/*.html", "neko/**/*.html", "gta6/**/*.html", "preview-*/**/*.html")
                 for p in glob.glob(os.path.join(ROOT, pat), recursive=True)]
        self.assertTrue(pages)
        bad = []
        for p in pages:
            with open(p, encoding="utf-8") as f:
                if not re.search(r'<meta name="robots" content="noindex', f.read()):
                    bad.append(os.path.relpath(p, ROOT))
        self.assertEqual(bad, [], "缺少 noindex 的頁面")


def load_gta6_data():
    with open(os.path.join(ROOT, "gta6", "data.js"), encoding="utf-8") as f:
        text = f.read()
    return json.loads(text[text.index("{"):text.rindex("}") + 1])


class Gta6DataTest(unittest.TestCase):
    """gta6/data.js 是 scripts/build_gta6.py 產生的，頁面直接用它，結構壞了整頁就空白。"""

    def test_structure_and_unique_ids(self):
        d = load_gta6_data()
        self.assertGreaterEqual(len(d["chapters"]), 2)
        ids = [m["id"] for c in d["chapters"] for m in c["missions"]]
        self.assertEqual(len(ids), len(set(ids)), "任務 ID 重複")
        types = {"主線", "支線", "搶劫", "陌生人", "可選", "額外"}
        for c in d["chapters"]:
            for m in c["missions"]:
                self.assertIn(m["type"], types, m["id"])
                self.assertTrue(m["name"], m["id"])

    def test_only_safe_urls_and_images(self):
        d = load_gta6_data()
        for c in d["chapters"]:
            for m in c["missions"]:
                if "url" in m:
                    self.assertTrue(m["url"].startswith("https://promptowy.com/"), m["url"])
                for b in m.get("blocks", []):
                    if isinstance(b, dict):
                        self.assertRegex(b["i"], r"^[\w./-]+$", "圖片路徑只能是 img 網域下的相對路徑")
                        self.assertNotIn("..", b["i"])
                        self.assertTrue(isinstance(b.get("w"), int) and isinstance(b.get("h"), int), "圖片要帶寬高才能預留版面：" + b["i"])
        self.assertEqual(d["imgBase"], "https://img1.gamersky.com/")

    def test_aliases_point_to_real_missions(self):
        d = load_gta6_data()
        ids = {m["id"] for c in d["chapters"] for m in c["missions"]}
        for old, new in d["aliases"].items():
            self.assertIn(new, ids)
            self.assertNotIn(old, ids, "舊 ID 不該還在")

    def test_trophies_point_to_real_paragraphs(self):
        d = load_gta6_data()
        by_id = {m["id"]: m for c in d["chapters"] for m in c["missions"]}
        for x in d["trophies"] + d["optionals"]:
            self.assertIn(x["m"], by_id)
            self.assertIsInstance(by_id[x["m"]]["blocks"][x["p"]], str)

    def test_pwa_files_exist_and_not_in_sitemap(self):
        base = os.path.join(ROOT, "gta6")
        with open(os.path.join(base, "sw.js"), encoding="utf-8") as f:
            sw = f.read()
        files = re.search(r"const FILES = \[(.*?)\];", sw, re.S).group(1)
        for rel in re.findall(r'"\./([^"]*)"', files):
            self.assertTrue(os.path.exists(os.path.join(base, rel or "index.html")), rel)
        with open(os.path.join(base, "manifest.webmanifest"), encoding="utf-8") as f:
            manifest = json.load(f)
        for icon in manifest["icons"]:
            self.assertTrue(os.path.exists(os.path.join(base, icon["src"])), icon["src"])
        with open(os.path.join(ROOT, "sitemap.xml"), encoding="utf-8") as f:
            self.assertNotIn("gta6", f.read())


def node(nid, label, title, tag, body):
    tags = (f'<div class="reader-node-card__tags"><div class="reader-node-card__tag"><span class="reader-node-card__tag-text">'
            f'<img src="https://img1b.gamersky.com/icon.png" class="reader-node-card__tag-icon">'
            f'<span class="reader-node-card__tag-name">{tag}</span></span></div></div>') if tag else ""
    return (f'<article id="reader-node-{nid}" class="reader-node-card is-expanded"><div class="reader-node-card__header">'
            f'<span class="reader-node-card__node-id">{label}</span><h3 class="reader-node-card__title">{title}</h3></div>{tags}'
            f'<div class="reader-node-card__content"><div class="reader-rich-content">{body}</div></div>'
            f'<div class="reader-node-card__actions"><svg><path d="M0"/></svg></div></article>')


def img(src, w=600, h=338):
    return f'<p class="GsImageLabel"><a href="x"><img class="picact reader-content-image" src="{src}" width="{w}" height="{h}"></a></p>'


YOUMIN = ('<html><head><meta name="description" content="我是游民星空攻略组的Agent，本次制作"></head><body>'
          '<nav>2026-11-24 20:18:47 <span>導覽不該被當成任務</span></nav>'
          + node("111", "A1", "序幕", "主線任務",
                 "<p>公告</p><p>大家好，我是作者</p><p>※須知</p><p>開始主線任務【序幕】</p>" + img("https://img1.gamersky.com/a/1_S.jpg")
                 + '<p><img class="reader-content-image" src="https://evil.example/x.png"></p>')
          + node("222", "A2", "支线-女鄰居", "支線任務", "<p>獎盃【甲】在這裡</p>")
          + node("333", "A3", "垂釣（和卡爾）", "主線任務", "<p>主線任務【垂釣】</p><p>第二<br>行</p>")
          + node("444", "A4", "偷戰鬥機", "主線任務", "<p>只是技巧</p>")
          + node("555", "D2", "正在推第2章", "", "<p>25號開更。</p>")
          + '<script>var x = "<article id=\'reader-node-999\'>";</script></body></html>')


def prompt_chapters(n_per=30):
    return {1: {"sub": "Paradise", "missions": [
                {"who": "Lucia", "en": "Prologue", "sum": "序", "url": "https://promptowy.com/a/"},
                {"who": "Jason", "en": "Gone Fishing", "sum": "釣魚", "url": "https://promptowy.com/b/"},
                {"who": "Jason", "en": "Extra One", "sum": "只有摘要", "url": "https://promptowy.com/c/"}]},
            2: {"sub": "", "missions": [{"who": "", "en": "What's Next?", "sum": "下一章", "url": "https://promptowy.com/d/"}]}}


class BuildGta6Test(unittest.TestCase):
    def test_parse_youmin(self):
        conv = lambda t: t.replace("线", "線")  # 測試用的簡轉繁
        meta, intro, notices, ms = build_gta6.parse_youmin(YOUMIN, conv)
        self.assertEqual(meta, {"author": "Agent", "updated": "2026-11-24 20:18:47"})
        self.assertEqual(intro, ["大家好，我是作者", "※須知"])
        self.assertEqual([(m["node"], m["type"], m["name"], m["note"]) for m in ms],
                         [("111", "主線", "序幕", ""), ("222", "支線", "女鄰居", ""), ("333", "主線", "垂釣", "和卡爾"),
                          ("444", "額外", "偷戰鬥機", "")])
        # 公告被丟掉、外站圖與標籤圖示不收、圖片帶寬高、<br> 變空白
        self.assertEqual(ms[0]["blocks"], ["開始主線任務【序幕】", {"i": "a/1_S.jpg", "w": 600, "h": 338}])
        self.assertEqual(ms[2]["blocks"], ["主線任務【垂釣】", "第二 行"])
        self.assertEqual(notices, [{"title": "正在推第2章", "text": "25號開更。"}])

    def test_parse_promptowy(self):
        cards = "".join(
            f'<li><div><small>任務 {i} · Jason</small><br><a href="https://promptowy.com/m{i}/">Name {i}</a><br><small>摘要 {i}</small></div>'
            f'<img src="x.webp"></li>' for i in range(1, 60))
        page = (f'<h2>GTA 6 的章節</h2><li>不是任務</li><h2>GTA 6 任務：第 1 章（Just Like Paradise）</h2><ol>{cards}'
                '<li><div><small>x</small><br><a href="https://evil.example/">壞連結</a></div></li></ol>'
                '<h2>接下來</h2><li><small>x</small><br><a href="https://promptowy.com/z/">不該收</a></li>')
        ch = build_gta6.parse_promptowy(page)
        self.assertEqual(list(ch), [1])
        self.assertEqual(ch[1]["sub"], "Just Like Paradise")
        self.assertEqual(len(ch[1]["missions"]), 59)
        self.assertEqual(ch[1]["missions"][0], {"who": "Jason", "en": "Name 1", "sum": "摘要 1", "url": "https://promptowy.com/m1/"})
        with self.assertRaises(SystemExit):
            build_gta6.parse_promptowy("<h2>GTA 6 任務：第 1 章（A）</h2>")

    def test_merge_keeps_youmin_order_and_adds_missing(self):
        _, _, _, ms = build_gta6.parse_youmin(YOUMIN, lambda t: t.replace("线", "線"))
        old_map, old_legacy = dict(build_gta6.YOUMIN_TO_EN), dict(build_gta6.LEGACY_Y_IDS)
        build_gta6.YOUMIN_TO_EN.clear()
        build_gta6.YOUMIN_TO_EN.update({"序幕": "Prologue", "垂釣": "Gone Fishing"})
        build_gta6.LEGACY_Y_IDS.clear()
        build_gta6.LEGACY_Y_IDS.update({"222": "y-女鄰居", "444": "y-偷戰鬥機"})
        try:
            chapters, aliases = build_gta6.merge(ms, prompt_chapters())
        finally:
            build_gta6.YOUMIN_TO_EN.clear()
            build_gta6.YOUMIN_TO_EN.update(old_map)
            build_gta6.LEGACY_Y_IDS.clear()
            build_gta6.LEGACY_Y_IDS.update(old_legacy)
        self.assertEqual([c["no"] for c in chapters], [1, 2])
        ch1 = [(m["id"], m["name"]) for m in chapters[0]["missions"]]
        # 遊民順序為骨架；promptowy 的 Extra One 接在前一個（Gone Fishing）後面，遊民獨有的任務留在原位
        self.assertEqual(ch1, [("p-prologue", "序幕"), ("y-222", "女鄰居"), ("p-gone-fishing", "垂釣"),
                               ("p-extra-one", "Extra One"), ("y-444", "偷戰鬥機")])
        # 遊民獨有任務改用節點編號當 ID，舊的中文名 ID 要能對到新 ID，使用者已勾的進度才不會跑掉
        self.assertEqual(aliases, {"y-女鄰居": "y-222", "y-偷戰鬥機": "y-444"})
        first = chapters[0]["missions"][0]
        self.assertEqual((first["en"], first["who"], first["url"]), ("Prologue", "Lucia", "https://promptowy.com/a/"))
        self.assertNotIn("blocks", chapters[0]["missions"][3])  # 只有摘要的任務沒有 blocks
        self.assertEqual(chapters[1]["missions"][0]["id"], "p-what-s-next")

    def test_collect_index(self):
        chapters = [{"missions": [{"id": "a", "blocks": ["x 獎盃【甲】", {"i": "1.webp"}, "可選任務【乙】"]}]}]
        self.assertEqual(build_gta6.collect_index(chapters),
                         ([{"name": "甲", "m": "a", "p": 0}], [{"name": "乙", "m": "a", "p": 2}]))


if __name__ == "__main__":
    unittest.main()
