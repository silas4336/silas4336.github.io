"""用法：py -3 -m unittest discover -s scripts -p "test_*.py"（唯讀，只用標準函式庫）

1. scripts/check_i18n.py 各條規則的單元測試（用暫存資料夾的假頁面）
2. 主站 12 頁（中英 index.html、work-*.html）的本機連結與圖片都找得到檔案
3. sitemap.xml 列的網址都對得到檔案，主站每一頁也都在 sitemap 裡
4. math-logic/、neko/、preview-*/ 每頁都有 noindex
"""
import contextlib
import glob
import io
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
        """整個 repo 都會發佈到 GitHub Pages：快取與 .env 要被 .gitignore 擋掉，也不能已經在版控裡。"""
        with open(os.path.join(ROOT, ".gitignore"), encoding="utf-8") as f:
            rules = f.read().split()
        for rule in ("__pycache__/", "*.pyc", ".env", ".env.*"):
            self.assertIn(rule, rules)
        r = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        bad = [f for f in r.stdout.splitlines()
               if "__pycache__/" in f or f.endswith(".pyc") or re.search(r"(^|/)\.env(\.|$)", f)]
        self.assertEqual(bad, [])

    def test_robots_points_to_sitemap(self):
        with open(os.path.join(ROOT, "robots.txt"), encoding="utf-8") as f:
            self.assertIn("Sitemap: https://silas4336.github.io/sitemap.xml", f.read())

    def test_hidden_sections_are_noindex(self):
        """robots.txt 刻意不擋 math-logic/、neko/、preview-*/，所以每個 html 都要自己帶 noindex。"""
        pages = [p for pat in ("math-logic/**/*.html", "neko/**/*.html", "preview-*/**/*.html")
                 for p in glob.glob(os.path.join(ROOT, pat), recursive=True)]
        self.assertTrue(pages)
        bad = []
        for p in pages:
            with open(p, encoding="utf-8") as f:
                if not re.search(r'<meta name="robots" content="noindex', f.read()):
                    bad.append(os.path.relpath(p, ROOT))
        self.assertEqual(bad, [], "缺少 noindex 的頁面")


if __name__ == "__main__":
    unittest.main()
