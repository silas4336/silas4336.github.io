"""中英版一致性檢查（唯讀）：py -3 scripts/check_i18n.py

逐對比較 zh（根目錄）與 en/ 的 index.html、work-*.html：
  1. 內文的阿拉伯數字要一樣多、一樣值（英文寫成 eight 也算對上中文的 8；年份與 2025.10 這類日期
     不比，因為中英日期寫法不同）
  2. <img> 的圖片檔要一樣（順序可不同；檔名結尾 -zh／-en 視為同一張）
  3. 站內連到其他作品頁的連結要一樣
  4. 英文頁不可連回中文頁（href 以 ../ 開頭），語言切換鈕（有 hreflang）除外
有不一致就列出並以結束碼 1 結束。數字若是刻意不同（例如英文寫 six），在 ALLOW 加例外。
"""
import re, sys, glob, os

sys.stdout.reconfigure(encoding="utf-8")
from collections import Counter
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOW = {}  # 例：{"work-crm.html": {"6"}} → 忽略該頁數字 6 的差異
WORDS = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split()


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text, self.imgs, self.links, self.skip = [], [], [], 0
        self.to_parent = []  # 沒有 hreflang、卻連到 ../ 的連結

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style", "head"):
            self.skip += 1
        if tag == "img" and a.get("src"):
            self.imgs.append(re.sub(r"-(zh|en)(\.\w+)$", r"\2", os.path.basename(a["src"])))
        if tag == "a" and a.get("href"):
            h = a["href"]
            if h.startswith("../") and "hreflang" not in a:
                self.to_parent.append(h)
            if re.search(r"work-[a-z]+\.html", h):
                self.links.append(re.search(r"work-[a-z]+\.html", h).group(0))

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head") and self.skip:
            self.skip -= 1

    def handle_data(self, d):
        if not self.skip:
            self.text.append(d)


def parse(path):
    """回傳 (阿拉伯數字, 英文數字詞換成的數字, 圖片, 作品頁連結)。年份與年月日期不算。"""
    p = Page()
    p.feed(open(path, encoding="utf-8").read())
    text = " ".join(p.text)
    text = re.sub(r"(?<![\d.])(?:19|20)\d\d(?:\.\d\d)?(?![\d.])", " ", text)
    digits = Counter(re.findall(r"\d+(?:[.,]\d+)*", text))
    words = Counter(str(WORDS.index(w.lower())) for w in re.findall(r"\b(" + "|".join(WORDS) + r")\b", text, flags=re.I))
    parse.to_parent = p.to_parent
    return digits, words, Counter(p.imgs), Counter(p.links)


def num_diff(zh, en, en_words):
    """英文寫成 eight 也算對上中文的 8；英文的 one、three 等若中文是「一」「三」，不算差異。"""
    out = []
    for k in sorted(set(zh) | set(en), key=lambda x: float(x.replace(",", ""))):
        if zh[k] > en[k] + en_words[k] or en[k] > zh[k]:
            out.append(f"{k}（中 {zh[k]}／英 {en[k]}" + (f"＋文字 {en_words[k]}" if en_words[k] else "") + "）")
    return out


def diff(a, b):
    out = []
    for k in sorted(set(a) | set(b)):
        if a[k] != b[k]:
            out.append(f"{k}（中 {a[k]}／英 {b[k]}）")
    return out


bad = 0
names = ["index.html"] + sorted(os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "work-*.html")))
for name in names:
    zh, en = os.path.join(ROOT, name), os.path.join(ROOT, "en", name)
    if not os.path.exists(en):
        print(f"✗ {name}: 沒有英文版")
        bad += 1
        continue
    (zn, _, zi, zl), (en_n, ew, ei, el) = parse(zh), parse(en)
    wrong_lang = parse.to_parent
    allow = ALLOW.get(name, set())
    for k in allow:
        zn.pop(k, None); en_n.pop(k, None)
    problems = [("數字", num_diff(zn, en_n, ew)), ("圖片", diff(zi, ei)), ("作品頁連結", diff(zl, el)),
                ("英文頁連到中文頁", wrong_lang)]
    problems = [(t, d) for t, d in problems if d]
    if problems:
        bad += 1
        print(f"✗ {name}")
        for t, d in problems:
            print(f"    {t}：" + "、".join(d))
    else:
        print(f"✓ {name}（數字 {sum(zn.values())} 個、圖片 {sum(zi.values())} 張一致）")

print("全部一致。" if not bad else f"{bad} 頁不一致。")
sys.exit(1 if bad else 0)
