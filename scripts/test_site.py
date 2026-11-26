"""用法：py -3 -m unittest discover -s scripts -p "test_*.py"（唯讀，只用標準函式庫）

1. scripts/check_i18n.py 各條規則的單元測試（用暫存資料夾的假頁面）
2. 主站 12 頁（中英 index.html、work-*.html）的本機連結與圖片都找得到檔案
3. sitemap.xml 列的網址都對得到檔案，主站每一頁也都在 sitemap 裡
4. math-logic/、neko/、gta6/、preview-*/ 每頁都有 noindex
5. gta6/ 攻略 PWA：data.js 結構與內容完整性、離線檔案清單、不在 sitemap；
   scripts/oplay_parse.py（oplay 頁面解析）與 scripts/build_gta6.py（遊民解析、合併）的規則
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
import clean_tw  # noqa: E402
import oplay_parse  # noqa: E402
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


def load_gta6_codex():
    with open(os.path.join(ROOT, "gta6", "codex.js"), encoding="utf-8") as f:
        text = f.read()
    return json.loads(text[text.index("{"):text.rindex("}") + 1])


class Gta6DataTest(unittest.TestCase):
    """gta6/data.js 與 gta6/codex.js 是 scripts/build_gta6.py 產生的，頁面直接用它們，結構壞了整頁就空白。"""

    def test_structure_and_unique_ids(self):
        d = load_gta6_data()
        self.assertEqual([c["no"] for c in d["chapters"]], [1, 2, 3, 4, 5])
        ids = [m["id"] for c in d["chapters"] for m in c["missions"]]
        self.assertEqual(len(ids), len(set(ids)), "任務 ID 重複")
        id_set = set(ids)
        types = {"主線", "支線", "搶劫", "陌生人", "可選", "額外"}
        for c in d["chapters"]:
            for m in c["missions"]:
                self.assertIn(m["type"], types, m["id"])
                self.assertTrue(m["name"], m["id"])
                self.assertTrue(m.get("steps") or m.get("blocks"), "任務沒有任何內容：" + m["id"])
                if "see" in m:
                    self.assertIn(m["see"], id_set, "see 指向不存在的任務：" + m["id"])
                for cid in m.get("covers", []):
                    self.assertIn(cid, id_set, "covers 指向不存在的任務：" + m["id"])

    def test_every_oplay_mission_has_steps_and_link(self):
        """第 2～5 章的最後一個任務曾經因為截斷邏輯漏掉連結，這裡確保 oplay 的任務都有逐步文字與原站連結。"""
        d = load_gta6_data()
        oplay = [m for c in d["chapters"] for m in c["missions"] if m["id"].startswith("p-")]
        self.assertGreaterEqual(len(oplay), 130)
        for m in oplay:
            self.assertTrue(m.get("steps"), m["id"])    # 「重點」有幾個任務原站本來就沒寫，不強求
            self.assertTrue(m["url"].startswith("https://oplay.cc/gta6/chapters/"), m["id"])

    def test_inline_markers_are_balanced(self):
        """**粗體** 與 ⟦按鍵⟧ 沒成對，頁面渲染會整段變粗體或按鍵框。"""
        d = load_gta6_data()

        def texts(blocks):
            for b in blocks or []:
                if isinstance(b, str):
                    yield b
                elif isinstance(b, dict):
                    for key in ("ol", "ul"):
                        yield from b.get(key, [])
                    for row in b.get("tb", []):
                        yield from row
                    if "h" in b:
                        yield b["h"]

        bad = []
        for c in d["chapters"]:
            pool = [t for m in c["missions"] for t in list(m.get("keys", [])) + list(texts(m.get("steps")))]
            pool += [x for sec in c["info"] for r in sec["rows"] for x in (r.get("a", ""), r.get("k", ""))] + [c["lead"]]
            for n in d["notes"] if c["no"] == 1 else []:
                pool += list(texts(n["blocks"]))
            for t in pool:
                if t.count("**") % 2 or t.count("⟦") != t.count("⟧"):
                    bad.append(t[:40])
        self.assertEqual(bad, [])

    def test_notes_structure(self):
        d = load_gta6_data()
        self.assertEqual(len(d["notes"]), 31)
        cats = {c["id"] for c in d["noteCats"]}
        slugs = [n["slug"] for n in d["notes"]]
        self.assertEqual(len(slugs), len(set(slugs)))
        for n in d["notes"]:
            self.assertIn(n["cat"], cats)
            self.assertRegex(n["slug"], r"^[a-z0-9-]+$")
            self.assertTrue(n["title"] and n["blocks"], n["slug"])
            self.assertIsInstance(n.get("minCh"), int, n["slug"])
            self.assertIn(n["minCh"], range(0, 7), n["slug"])

    def test_ending_guide_and_secrets_integrity(self):
        """無劇透結局指南不含劇情爆雷關鍵字，且 10 項特別互動彩蛋結構與步驟鍵完整。"""
        d = load_gta6_data()
        c = load_gta6_codex()
        eg = d.get("endingGuide")
        self.assertIsInstance(eg, dict)
        self.assertEqual(len(eg.get("pillars", [])), 3)
        self.assertEqual(len(eg.get("prep", [])), 7)
        self.assertEqual(len(eg.get("routes", [])), 8)
        r_ids = [r["id"] for r in eg["routes"]]
        self.assertEqual(len(r_ids), len(set(r_ids)))
        # 確保無劇透結局指南不會透漏角色生死、角色名劇透或橋／沼澤／監獄橋段
        eg_text = json.dumps(eg, ensure_ascii=False)
        spoiler_re = re.compile(r"門德茲|Méndez|Tomás|Tomas|兒子|坐牢|出獄|監獄|鱷魚|頭骨|(?<!身陷)沼澤|被殺|死亡|槍殺|開槍打死|殉情")
        self.assertIsNone(spoiler_re.search(eg_text), "無劇透結局指南洩漏了劇情劇透詞！")

        secs = d.get("secrets", [])
        self.assertGreaterEqual(len(secs), 10)
        s_ids = [s["id"] for s in secs]
        self.assertEqual(len(s_ids), len(set(s_ids)))
        for s in secs:
            self.assertTrue(s["id"].startswith("sec."), s["id"])
            self.assertIn(s["ch"], (1, 2, 3), s["id"])
            self.assertTrue(s.get("title") and s.get("steps"), s["id"])
            ks = [st["k"] for st in s["steps"]]
            self.assertEqual(len(ks), len(set(ks)), f"{s['id']} 步驟 key 重複")
        vc = next(s for s in secs if s["id"] == "sec.vc2002")
        self.assertEqual(len(vc["steps"]), 14, "2002 Vice City 應含起點＋12 座變電站＋傳送門共 14 步")

        egg_ids = {it["id"] for g in c.get("eggs", []) for it in g.get("items", [])}
        for req_id in ("egg.vice-city-portal", "egg.satan-hell", "egg.radio-vault", "egg.radio-laperle"):
            self.assertIn(req_id, egg_ids)

    def test_only_safe_urls_and_images(self):
        d = load_gta6_data()
        for c in d["chapters"]:
            for m in c["missions"]:
                if "url" in m:
                    self.assertTrue(m["url"].startswith("https://oplay.cc/"), m["url"])
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

    def test_trophies_point_to_real_places(self):
        d = load_gta6_data()
        by_id = {m["id"]: m for c in d["chapters"] for m in c["missions"]}
        for x in d["trophies"] + d["optionals"]:
            if "ch" in x:       # oplay 章節「獎盃」區塊
                self.assertIn(x["ch"], [c["no"] for c in d["chapters"]])
            else:
                self.assertIsInstance(by_id[x["m"]]["blocks"][x["p"]], str)

    def test_progress_and_codex_integrity(self):
        d = load_gta6_data()
        self.assertIn("progress", d)
        self.assertGreaterEqual(len(d["progress"]["rows"]), 40)

        c = load_gta6_codex()
        self.assertEqual(len(c["cards"]), 23)
        total_cards = sum(len(v) for v in c["cards"].values())
        self.assertGreaterEqual(total_cards, 1200)
        self.assertGreaterEqual(sum(len(g["items"]) for g in c["eggs"]), 60)
        self.assertGreaterEqual(sum(len(g["items"]) for g in c["hud"]), 25)
        self.assertGreaterEqual(sum(len(x["items"]) for x in c["updates"]), 20)
        for slug, items in c["cards"].items():
            for it in items:
                self.assertTrue(it.get("n"), slug)
                self.assertNotIn("img", it, "不應複製原站圖鑑圖片：" + slug)
                for ukey in ("url", "map"):
                    if ukey in it:
                        self.assertTrue(it[ukey].startswith("https://oplay.cc/"), it[ukey])
                for tkey in ("n", "a", "how"):
                    val = it.get(tkey, "")
                    self.assertEqual(val.count("**") % 2, 0, val[:40])
                    self.assertEqual(val.count("⟦"), val.count("⟧"), val[:40])

    def test_pwa_files_exist_and_not_in_sitemap(self):
        base = os.path.join(ROOT, "gta6")
        with open(os.path.join(base, "sw.js"), encoding="utf-8") as f:
            sw = f.read()
        files = re.search(r"const FILES = \[(.*?)\];", sw, re.S).group(1)
        rels = re.findall(r'"\./([^"]*)"', files)
        self.assertIn("codex.js", rels)
        for rel in rels:
            self.assertTrue(os.path.exists(os.path.join(base, rel or "index.html")), rel)
        with open(os.path.join(base, "manifest.webmanifest"), encoding="utf-8") as f:
            manifest = json.load(f)
        for icon in manifest["icons"]:
            self.assertTrue(os.path.exists(os.path.join(base, icon["src"])), icon["src"])
        with open(os.path.join(ROOT, "sitemap.xml"), encoding="utf-8") as f:
            self.assertNotIn("gta6", f.read())

    def test_checklists_and_clean_tw_integrity(self):
        """必做清單與任務提醒參照完整，且產出的 data.js / codex.js 不含第三方站名與常見陸詞。"""
        d = load_gta6_data()
        c = load_gta6_codex()
        mission_ids = {m["id"] for ch in d["chapters"] for m in ch["missions"]}

        groups = d.get("checklists", [])
        self.assertEqual([g["ch"] for g in groups], [1, 2, 3, 4, 5, 0])
        chk_ids = []
        for g in groups:
            self.assertTrue(g.get("title") and g.get("items"))
            for it in g["items"]:
                self.assertTrue(it["id"].startswith("chk."), it["id"])
                self.assertIn(it["cat"], {"miss", "prep", "do", "end"}, it["id"])
                self.assertTrue(it.get("title"), it["id"])
                if "m" in it:
                    self.assertIn(it["m"], mission_ids, "清單項目指向不存在任務：" + it["id"])
                chk_ids.append(it["id"])
        self.assertEqual(len(chk_ids), len(set(chk_ids)), "清單 ID 重複")
        self.assertGreaterEqual(len(chk_ids), 40)
        chk_set = set(chk_ids)
        by_id = {m["id"]: m for ch in d["chapters"] for m in ch["missions"]}
        for ch in d["chapters"]:
            ponr = ch.get("ponr")
            self.assertIsInstance(ponr, dict, f"第 {ch['no']} 章缺少 ponr")
            self.assertIn(ponr["m"], by_id, f"第 {ch['no']} 章 ponr 指向不存在任務")
            self.assertEqual(by_id[ponr["m"]].get("ponr"), 1, f"{ponr['m']} 缺少 ponr=1")
            for m in ch["missions"]:
                for tid in m.get("todo", []):
                    self.assertIn(tid, chk_set, f"{m['id']} 的 todo 指向不存在清單：{tid}")

        codes = d.get("codes", [])
        self.assertGreaterEqual(len(codes), 25)
        code_ids = []
        for it in codes:
            self.assertTrue(it["id"].startswith("code."), it["id"])
            self.assertIn(it["ch"], (1, 2, 3), it["id"])
            self.assertTrue(it.get("code") and it.get("name"), it["id"])
            if "m" in it:
                self.assertIn(it["m"], mission_ids, "密碼指向不存在任務：" + it["id"])
            code_ids.append(it["id"])
        self.assertEqual(len(code_ids), len(set(code_ids)), "密碼 ID 重複")

        skip_keys = {"url", "map", "imgBase", "i", "id", "slug", "tick", "m", "see", "covers", "todo", "aliases", "items", "code"}
        site_re = re.compile(
            r"PowerPyx|Output\s*Lag|GamesRadar|GTABase|MetaForge|4Gamers|Game8|Gameriv|thegameswiki|"
            r"oplay\.cc|遊民星空|本站未實測|還沒核到|一家說|兩說",
            re.I,
        )
        cn_re = re.compile(r"圖標|手柄|鎖屏|視頻|便利店|公交|作弊碼|僵立停|飛車兄弟|(?<!水上)摩托車|通關(?!密語)")

        def walk(obj, path=""):
            if isinstance(obj, str):
                if site_re.search(obj):
                    leaks.append(("site", path, obj[:60]))
                if cn_re.search(obj):
                    leaks.append(("cn", path, obj[:60]))
            elif isinstance(obj, list):
                for idx, val in enumerate(obj):
                    walk(val, f"{path}[{idx}]")
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    if k in skip_keys:
                        continue
                    walk(v, f"{path}.{k}")

        leaks = []
        walk(d, "data")
        walk(c, "codex")
        self.assertEqual(leaks, [], f"發現外站名或陸詞殘留：{leaks[:5]}")


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


def oplay_chapters():
    def m(slug, n, en, k="用傑森", a="獎勵", body=("步驟",)):
        return {"slug": "story." + slug, "n": n, "en": en, "k": k, "a": a, "keys": ["重點"], "body": list(body), "stuck": [],
                "url": f"https://oplay.cc/gta6/chapters/1/{slug}"}
    return [{"no": 1, "sub": "Paradise", "lead": "第一章", "sections": [{"title": "會錯過", "count": "", "rows": []}], "missions": [
                m("prologue", "序章", "Prologue", "用露西亞・常卡"), m("gone-fishing", "出門獵魚", "Gone Fishing"),
                m("extra-one", "額外一", "Extra One (Sub Title)"), m("hit-bank", "搶銀行", "Hit Bank")]},
            {"no": 2, "sub": "", "lead": "", "sections": [], "missions": [m("whats-next", "下一章", "What's Next?")]}]


class OplayParseTest(unittest.TestCase):
    def test_inline_markers(self):
        self.assertEqual(oplay_parse.inline('<strong>粗</strong>字<kbd class="pad">L2</kbd>／LT<br>下一行&amp;'), "**粗**字⟦L2⟧／LT 下一行&")

    def test_prose_blocks(self):
        html = ("<h2>標題</h2><p>段落 <b>粗</b></p><ul><li>甲<ul><li>子項</li></ul></li><li>乙</li></ul>"
                "<ol><li><strong>步驟。</strong> 按 <kbd>L2</kbd></li></ol>"
                '<figure><img src="x"><figcaption>地圖</figcaption></figure><details><summary>來源</summary>不收</details>'
                "<table><thead><tr><th>欄</th></tr></thead><tbody><tr><td>值</td></tr></tbody></table>")
        self.assertEqual(oplay_parse.to_blocks(html), [
            {"h": "標題", "l": 2}, "段落 **粗**", {"ul": ["甲", "↳ 子項", "乙"]}, {"ol": ["**步驟。** 按 ⟦L2⟧"]},
            {"tb": [["欄"], ["值"]], "hd": 1}])

    def test_parse_row(self):
        html = ('<li><button type="button" class="g6-tick" data-g6tick="miss.a" data-g6tick-name="甲">v</button>'
                '<button type="button" class="g6-row g6-row--till" data-g6card="miss.a" data-kind="miss"> '
                '<span class="g6-n"><span>甲名稱</span><span class="g6-en" lang="en">Alpha</span></span>'
                '<span class="g6-k">會錯過</span> <span class="g6-a">第一章結束；<b>要先做</b></span> </button></li>')
        row = oplay_parse.parse_row(next(oplay_parse.ROW.finditer(html)))
        self.assertEqual(row, {"n": "甲名稱", "en": "Alpha", "k": "會錯過", "a": "第一章結束；**要先做**", "id": "miss.a", "tick": "miss.a"})

    def test_parse_chapter_including_last_mission(self):
        def mission(slug, name, en, last=False):
            return (f'<li id="m-story.{slug}" class="g6-tk"><button class="g6-tick" data-g6tick="story.{slug}">v</button>'
                    f'<button type="button" class="g6-row" data-g6walk="w-{slug}" data-kind="story"> '
                    f'<span class="g6-n"><span>{name}</span><span class="g6-en" lang="en">{en}</span></span>'
                    f'<span class="g6-k">用傑森・常卡</span> <span class="g6-a">$100</span> </button>'
                    f'<div class="g6w" id="w-{slug}" hidden><div class="g6w-in"><ul class="g6w-keys"><li>重點<b>一</b></li></ul> '
                    f'<div class="g6w-body"><ol><li><strong>步驟。</strong> 按 <kbd>L2</kbd></li></ol><p>收尾</p></div> '
                    f'<section class="g6w-rel"><h3>卡關</h3><ul class="g6-rows"><li><button type="button" class="g6-row" '
                    f'data-g6card="stuck.x" data-kind="stuck"> <span class="g6-n"><span>被抓</span></span>'
                    f'<span class="g6-a">劇情</span> </button></li></ul></section>'
                    f'<div class="g6w-acts"><a href="/gta6/chapters/1/{slug}">自己一頁</a></div></div></div></li>')
        page = ("<html><h1>第一章攻略</h1><p>導覽 第一章（礁島群）有 2 個主線任務，從〈甲〉到〈乙〉。這章有 1 件事。</p>"
                '<section><div><h2>主線順序</h2><span class="g6-cnt">2 個任務</span></div> <div class="g6-grp-b"><ol class="g6-rows g6c-seq">'
                + mission("a", "甲", "Alpha") + mission("b", "乙", "Beta (Sub)", last=True)
                + "</ol></div> </section>"
                '<section><div><h2>賺錢方法</h2><span class="g6-cnt">這章新開放 1</span></div><div class="g6-grp-b"><ul class="g6-rows"><li>'
                '<button type="button" class="g6-row" data-g6card="money.x" data-kind="money"> <span class="g6-n"><span>搶店</span></span> '
                '<span class="g6-a">少</span> </button></li></ul></div></section>'
                '<section><div><h2>之前就開放、現在還能做</h2></div><div class="g6-grp-b"><ul class="g6-rows"><li>'
                '<button type="button" class="g6-row" data-g6card="old.x" data-kind="x"> <span class="g6-n"><span>重複</span></span> </button>'
                "</li></ul></div></section></html>")
        ch = oplay_parse.parse_chapter(page, 1)
        self.assertEqual((ch["title"], ch["sub"]), ("第一章攻略", "礁島群"))
        self.assertTrue(ch["lead"].startswith("導覽 第一章（礁島群）有 2 個") or ch["lead"].startswith("第一章（礁島群）有 2 個"))
        self.assertEqual([m["slug"] for m in ch["missions"]], ["story.a", "story.b"])
        for m in ch["missions"]:   # 最後一個任務（乙）以前會被截掉卡關與連結
            self.assertEqual(m["keys"], ["重點**一**"])
            self.assertEqual(m["body"], [{"ol": ["**步驟。** 按 ⟦L2⟧"]}, "收尾"])
            self.assertEqual(m["stuck"], [{"n": "被抓", "a": "劇情", "id": "stuck.x"}])
            self.assertEqual(m["url"], "https://oplay.cc/gta6/chapters/1/" + m["slug"].split(".")[1])
        self.assertEqual((ch["missions"][1]["n"], ch["missions"][1]["en"], ch["missions"][1]["k"]), ("乙", "Beta (Sub)", "用傑森・常卡"))
        self.assertEqual([x["title"] for x in ch["sections"]], ["賺錢方法"])   # 「之前就開放」略過
        self.assertEqual(ch["sections"][0]["rows"], [{"n": "搶店", "a": "少", "id": "money.x"}])

    def test_notes(self):
        index = ('<section class="gh-row" id="cat-a"><h2><span class="baloo gh-hb-n">分類甲</span></h2>'
                 '<a class="gh-it tool" href="/gta6/hud"><b>工具</b></a>'
                 '<a class="gh-it gh-it--heavy" href="/gta6/notes/missables" data-card> <b>會錯過什麼</b> <i class="gh-bd gh-bd--big">大改</i>'
                 ' <span class="gh-sb">只有三件事</span> </a></section>')
        cats = oplay_parse.parse_notes_index(index)
        self.assertEqual(cats, [{"id": "a", "title": "分類甲", "notes": [{"slug": "missables", "title": "會錯過什麼", "sub": "只有三件事", "badge": "大改"}]}])
        page = ('<h1>會錯過什麼</h1><p class="gart-stamp tnum"><span>更新於 2026/11/24</span><span aria-hidden="true">・</span><span>首發版</span></p>'
                '<div class="prose"><h2>先存檔</h2><p>內文</p><div class="inner"><p>巢狀 div 也要收</p></div></div><div>之外</div>')
        note = oplay_parse.parse_note(page)
        self.assertEqual(note["title"], "會錯過什麼")
        self.assertEqual(note["blocks"], [{"h": "先存檔", "l": 2}, "內文", "巢狀 div 也要收"])
        with self.assertRaises(SystemExit):
            oplay_parse.parse_note("<h1>x</h1>")

    def test_parse_cards_index_and_card_page_variants(self):
        idx_html = (
            '<section class="dxh-fam"><h2 class="dxb-h">收集<em class="tnum">277</em></h2><ul class="dxh-grid">'
            '<li><a class="ui-card dxh-tile" href="/gta6/cards/vehicle" data-k="vehicle"><strong>載具</strong><em class="tnum">208</em><span class="dxh-s">跑車…</span></a></li>'
            '<li><a class="ui-card dxh-tile" href="/gta6/eggs" data-k="egg"><strong>彩蛋</strong><em class="tnum">62</em><span class="dxh-s">UFO…</span></a></li>'
            '</ul></section>'
        )
        groups = oplay_parse.parse_cards_index(idx_html)
        self.assertEqual(groups, [{"group": "收集", "cats": [
            {"slug": "vehicle", "name": "載具", "count": 208, "preview": "跑車…"},
            {"slug": "egg", "name": "彩蛋", "count": 62, "preview": "UFO…", "egg": 1},
        ]}])

        # 同時包含 <tr data-d>（有評分）與 <li data-d>（未排行）、以及 img 被剔除
        veh_html = (
            '<div data-unit="台" data-common="掃描就算"><ul class="dx-seg"><li><button>速度</button></li><li><button>耐久</button></li></ul>'
            '<table><tbody><tr data-d="{&quot;id&quot;:&quot;vehicle.a&quot;,&quot;zh&quot;:&quot;甲車&quot;,&quot;cat&quot;:&quot;跑車&quot;,'
            '&quot;img&quot;:{&quot;src&quot;:&quot;/img/x.webp&quot;},&quot;map&quot;:&quot;/gta6/map?at=1,2,3&quot;,'
            '&quot;st&quot;:{&quot;v&quot;:{&quot;速度&quot;:8.3}}}"></tr></tbody></table>'
            '<ul><li data-d="{&quot;id&quot;:&quot;vehicle.b&quot;,&quot;zh&quot;:&quot;乙車&quot;,&quot;edition&quot;:&quot;終極版&quot;}"></li></ul></div>'
        )
        veh = oplay_parse.parse_card_page(veh_html, "vehicle")
        self.assertEqual(veh["unit"], "台")
        self.assertEqual(veh["common"], "掃描就算")
        self.assertEqual(veh["stats"], ["速度", "耐久"])
        self.assertEqual(len(veh["items"]), 2)
        self.assertNotIn("img", veh["items"][0])
        self.assertEqual(veh["items"][0]["map"], "https://oplay.cc/gta6/map?at=1,2,3")
        self.assertEqual(veh["items"][0]["st"], {"速度": 8.3})
        self.assertEqual(veh["items"][1], {"id": "vehicle.b", "n": "乙車", "ed": "終極版"})

        # dxc-card（地圖卡）＋ dxa-row（清單，含空欄位與最後一列）
        mix_html = (
            '<div data-unit="則"><ul>'
            '<li data-c="幫派據點"><a class="ui-card dxc-card" href="/gta6/c/gang.a"><span class="dxc-map"><img src="/x.webp"><em class="tg tg--cat">幫派據點</em></span>'
            '<span class="dxc-b"><strong>小屋</strong><span class="dxc-a"></span><span class="dxc-f"><span class="dx-tags"><em class="tg tg--where">礁島</em></span><b class="dxc-val">$5,000</b></span></span></a></li>'
            '<li data-c="飛機"><a class="dxa-row dxa-row--noic" href="#c-place.air1"><span class="dxa-t"><strong>機場</strong><small>Airfield</small></span>'
            '<span class="dx-tags"><em class="tg">第一章起</em></span><span class="dxa-a">按 <b>L2</b> 起飛</span></a></li>'
            '</ul></div>'
        )
        mix = oplay_parse.parse_card_page(mix_html, "place")
        self.assertEqual(len(mix["items"]), 2)
        self.assertEqual(mix["items"][0], {"n": "小屋", "onMap": 1, "id": "gang.a", "cat": "幫派據點", "where": "礁島", "val": "$5,000", "url": "https://oplay.cc/gta6/c/gang.a"})
        self.assertEqual(mix["items"][1], {"n": "機場", "id": "place.air1", "en": "Airfield", "cat": "飛機", "tags": ["第一章起"], "a": "按 **L2** 起飛"})

    def test_parse_eggs_hud_updates_progress(self):
        eggs_html = (
            '<section class="ui-card dxe-reg"><h2 class="g6e-reg-n">礁島群<em>1</em></h2><a href="/gta6/map?at=1,2,3">地圖</a>'
            '<ul class="dxa"><li data-c="傳說"><a class="dxa-row" href="/gta6/c/egg.ufo"><i class="dxa-no">7</i>'
            '<span class="dxa-t"><strong>UFO</strong><small>UFO</small></span><span class="dx-tags"><em class="tg tg--gift">加耐力</em></span>'
            '<span class="dxa-a">晚上出現</span></a></li></ul></section>'
            '<section class="dxb-sec"><h2>不用找，玩著會遇到<em>1</em></h2>'
            '<div class="dxb-sec"><h3>主線裡<em>1</em></h3><ul class="dxa"><li data-c="致敬"><a class="dxa-row dxa-row--noic" href="/gta6/c/egg.sam">'
            '<span class="dxa-t"><strong>小山姆</strong></span><span class="dx-tags"></span><span class="dxa-a">路過</span></a></li></ul></div></section>'
        )
        eggs = oplay_parse.parse_eggs(eggs_html)
        self.assertEqual(len(eggs), 2)
        self.assertEqual(eggs[0]["region"], "礁島群")
        self.assertEqual(eggs[0]["map"], "https://oplay.cc/gta6/map?at=1,2,3")
        self.assertEqual(eggs[0]["items"][0]["gift"], "加耐力")
        self.assertEqual(eggs[1]["region"], "不用找・主線裡")
        self.assertEqual(eggs[1]["items"][0]["n"], "小山姆")

        hud_html = (
            '<section class="g6-grp"><h2>左上角三條</h2><ul class="hud-rows">'
            '<li><button class="hud-row" data-g6card="hud.o2"><span class="hud-n">氧氣條<em class="hud-pend">還沒確認</em></span>'
            '<span class="hud-say">剩多少氣</span><span class="hud-do"><b>按 × 浮上來</b></span></button></li></ul></section>'
        )
        hud = oplay_parse.parse_hud(hud_html)
        self.assertEqual(hud, [{"title": "左上角三條", "items": [{"n": "氧氣條", "id": "hud.o2", "tag": "還沒確認", "say": "剩多少氣", "do": "**按 × 浮上來**"}]}])

        upd_html = (
            '<section class="up-day"><p class="up-d"><b>11/26</b><span>週四</span><span>2026</span></p>'
            '<ul><li data-t="地圖"><a href="/gta6/map"><span class="up-t">新點 5 個</span></a></li></ul></section>'
        )
        upd = oplay_parse.parse_updates(upd_html)
        self.assertEqual(upd, [{"date": "11/26", "dow": "週四", "year": "2026", "items": [{"tag": "地圖", "text": "新點 5 個", "url": "https://oplay.cc/gta6/map"}]}])

        prog_html = '<script type="application/json" id="ppData">{"secs":["劇情"],"rows":[{"id":"main","name":"主線","sec":"劇情","type":"cards","unit":"個","goals":["100"],"need":130,"total":130,"ico":"<svg/>","items":["story.a"]}]}</script>'
        prog = oplay_parse.parse_progress(prog_html)
        self.assertEqual(prog, {"secs": ["劇情"], "rows": [{"id": "main", "name": "主線", "sec": "劇情", "type": "cards", "unit": "個", "goals": ["100"], "need": 130, "total": 130, "items": ["story.a"]}]})


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

    def test_tagless_node_with_image_and_one_to_many_merge(self):
        """漏標標籤但有截圖的節點（如 D7、D9）不能誤判為作者預告；一對多對應要產生 covers 與 see，且不覆蓋主線類型。"""
        html = (
            '<html><body>'
            + node("101", "D6", "買槍、理髮", "可選任務", "<p>先買槍再理髮</p>" + img("https://img1.gamersky.com/a/d6_S.jpg"))
            + node("102", "D7", "付房錢", "", "<p>回旅館付錢</p>" + img("https://img1.gamersky.com/a/d7_S.jpg"))
            + node("103", "D10", "正在推第2章", "", "<p>預告</p>")
            + '</body></html>'
        )
        _, _, notices, ms = build_gta6.parse_youmin(html)
        self.assertEqual([m["name"] for m in ms], ["買槍、理髮", "付房錢"])
        self.assertEqual(notices, [{"title": "正在推第2章", "text": "預告"}])
        old_map = dict(build_gta6.YOUMIN_TO_SLUG)
        build_gta6.YOUMIN_TO_SLUG.clear()
        build_gta6.YOUMIN_TO_SLUG.update({"買槍、理髮": ("prologue", "gone-fishing"), "付房錢": "extra-one"})
        try:
            chapters, aliases = build_gta6.merge(ms, oplay_chapters())
        finally:
            build_gta6.YOUMIN_TO_SLUG.clear()
            build_gta6.YOUMIN_TO_SLUG.update(old_map)
        by_id = {m["id"]: m for m in chapters[0]["missions"]}
        self.assertEqual(by_id["p-prologue"]["type"], "主線")
        self.assertEqual(by_id["p-prologue"]["covers"], ["p-gone-fishing"])
        self.assertEqual(by_id["p-gone-fishing"]["see"], "p-prologue")
        self.assertEqual(by_id["p-gone-fishing"]["seeLabel"], "買槍、理髮")
        self.assertEqual(by_id["p-extra-one"]["type"], "主線")
        self.assertEqual(aliases["y-101"], "p-prologue")
        self.assertEqual(aliases["y-102"], "p-extra-one")

    def _merge(self, youmin_html=YOUMIN):
        _, _, _, ms = build_gta6.parse_youmin(youmin_html, lambda t: t.replace("线", "線"))
        old_map, old_legacy = dict(build_gta6.YOUMIN_TO_SLUG), dict(build_gta6.LEGACY_Y_IDS)
        build_gta6.YOUMIN_TO_SLUG.clear()
        build_gta6.YOUMIN_TO_SLUG.update({"序幕": "prologue", "垂釣": "gone-fishing"})
        build_gta6.LEGACY_Y_IDS.clear()
        build_gta6.LEGACY_Y_IDS.update({"222": "y-女鄰居", "444": "y-偷戰鬥機"})
        try:
            return build_gta6.merge(ms, oplay_chapters())
        finally:
            build_gta6.YOUMIN_TO_SLUG.clear()
            build_gta6.YOUMIN_TO_SLUG.update(old_map)
            build_gta6.LEGACY_Y_IDS.clear()
            build_gta6.LEGACY_Y_IDS.update(old_legacy)

    def test_merge_uses_oplay_order_and_attaches_youmin(self):
        chapters, aliases = self._merge()
        self.assertEqual([c["no"] for c in chapters], [1, 2])
        ch1 = [(m["id"], m["name"]) for m in chapters[0]["missions"]]
        # oplay 的順序為骨架；遊民獨有的任務插在它前一個已對上的任務後面
        self.assertEqual(ch1, [("p-prologue", "序章"), ("y-222", "女鄰居"), ("p-gone-fishing", "出門獵魚"), ("y-444", "偷戰鬥機"),
                               ("p-extra-one", "額外一"), ("p-hit-bank", "搶銀行")])
        first, fishing, extra, bank = (chapters[0]["missions"][i] for i in (0, 2, 4, 5))
        self.assertEqual((first["aka"], first["en"], first["who"], first["hard"]), ("序幕", "Prologue", "露西亞", 1))
        self.assertEqual(first["blocks"], ["開始主線任務【序幕】", {"i": "a/1_S.jpg", "w": 600, "h": 338}])  # 遊民圖文掛上去
        self.assertEqual(fishing["blocks"], ["主線任務【垂釣】", "第二 行"])
        self.assertEqual(first["steps"], ["步驟"])
        self.assertEqual((extra["en"], extra["note"]), ("Extra One", "Sub Title"))
        self.assertNotIn("blocks", extra)             # 遊民沒寫的任務只有 oplay 的文字
        self.assertEqual(bank["type"], "搶劫")          # hit- 開頭的是搶案
        self.assertEqual(chapters[1]["missions"][0]["id"], "p-whats-next")
        self.assertEqual(chapters[0]["info"], [{"title": "會錯過", "count": "", "rows": []}])
        # 舊 ID 對照：遊民獨有任務改用節點編號、已對上的任務舊的 y- ID 轉成 p- ID
        self.assertEqual(aliases, {"y-111": "p-prologue", "y-333": "p-gone-fishing", "y-女鄰居": "y-222", "y-偷戰鬥機": "y-444"})

    def test_name_without_english_title_prefers_youmin(self):
        """oplay 有些任務的名稱不像標題（例如「第一章〈身陷沼澤〉之後的任務」），要改用遊民的名字。"""
        chapters = oplay_chapters()
        chapters[0]["missions"][1]["en"] = ""
        chapters[0]["missions"][1]["n"] = "第一章〈某某〉之後的任務"
        _, _, _, ms = build_gta6.parse_youmin(YOUMIN, lambda t: t.replace("线", "線"))
        old = dict(build_gta6.YOUMIN_TO_SLUG)
        build_gta6.YOUMIN_TO_SLUG.clear()
        build_gta6.YOUMIN_TO_SLUG.update({"序幕": "prologue", "垂釣": "gone-fishing"})
        try:
            out, _ = build_gta6.merge(ms, chapters)
        finally:
            build_gta6.YOUMIN_TO_SLUG.clear()
            build_gta6.YOUMIN_TO_SLUG.update(old)
        fishing = next(m for m in out[0]["missions"] if m["id"] == "p-gone-fishing")
        self.assertEqual((fishing["name"], fishing["aka"]), ("垂釣", "第一章〈某某〉之後的任務"))

    def test_collect_index(self):
        chapters = [{"no": 1, "missions": [{"id": "a", "blocks": ["x 獎盃【甲】", {"i": "1.webp"}, "可選任務【乙】"]}],
                     "info": [{"title": "獎盃", "rows": [{"n": "丙", "a": "做某事"}]}, {"title": "地點", "rows": [{"n": "丁"}]}]}]
        self.assertEqual(build_gta6.collect_index(chapters),
                         ([{"name": "甲", "m": "a", "p": 0}, {"name": "丙", "ch": 1, "a": "做某事"}], [{"name": "乙", "m": "a", "p": 2}]))


class CleanTwTest(unittest.TestCase):
    def test_strips_third_party_sites_and_normalizes_tw_terms(self):
        raw = "PowerPyx 寫這段要騎摩托車配水上摩托車（本站未實測），按手柄圖標輸入通關密語後即可通關並領僵立停與作弊碼〈暫譯〉。"
        out = clean_tw.clean_text(raw)
        for bad in ("PowerPyx", "本站未實測", "手柄", "圖標", "作弊碼", "僵立停", "暫譯"):
            self.assertNotIn(bad, out)
        self.assertIn("騎機車", out)
        self.assertIn("水上摩托車", out)
        self.assertIn("手把圖示", out)
        self.assertIn("通關密語", out)
        self.assertIn("破關", out)
        self.assertIn("喪必斯", out)
        self.assertIn("秘技", out)
        self.assertEqual(out.count("**") % 2, 0)

    def test_unbalanced_bold_recovered_after_cleanup(self):
        out = clean_tw.clean_text("**PowerPyx 說重點**保留這裡")
        self.assertEqual(out.count("**") % 2, 0)
        self.assertNotIn("PowerPyx", out)
        self.assertIn("保留這裡", out)


if __name__ == "__main__":
    unittest.main()
