"""用法：py -3 scripts/fetch_oplay.py [快取資料夾，預設 .oplay-cache] [--refresh]

把 oplay.cc 的 GTA 6 攻略（繁體中文）抓到本機快取，給 build_gta6.py 解析。只用標準函式庫。

只抓需要的頁面（章節頁 5 頁＋筆記索引＋28 篇筆記＋圖鑑索引＋23 個圖鑑分類＋彩蛋／圖示全解／更新紀錄／進度清單，共 62 頁），
每頁間隔 1 秒，已在快取裡的不重抓（--refresh 才會重抓）。章節頁一頁就含該章全部任務的完整內容，所以不用逐個任務頁爬。
遵守 oplay.cc 的 robots.txt（只禁 /api/）；快取資料夾已列入 .gitignore，不會進 repo。
"""
import os
import re
import sys
import time
import urllib.request

BASE = "https://oplay.cc/gta6/"
CHAPTERS = [1, 2, 3, 4, 5]
NOTES = ["aircraft", "banks", "cars", "challenges", "cheats", "choices", "collectibles", "completion", "controls",
         "endings", "events", "faq", "leonida", "mechanics", "missables", "money", "money-glitch", "patches",
         "ranges", "rewards", "robberies", "romance", "stats", "strangers", "stuck", "wanted", "weapons", "where"]
CARD_CATS = ["vehicle", "weapon", "animal", "style", "collect", "reward", "place", "org", "char", "term", "merch",
             "story", "mission", "challenge", "trophy", "set", "miss", "howto", "hud", "unlock", "money", "stuck", "cheat"]
EXTRA_PAGES = ["cards", "eggs", "hud", "updates", "progress"]
DELAY = 1.0


def pages():
    """(快取檔名, 網址) 清單。"""
    out = [(f"chapters-{n}.html", f"{BASE}chapters/{n}") for n in CHAPTERS]
    out.append(("notes.html", f"{BASE}notes"))
    out += [(f"notes-{s}.html", f"{BASE}notes/{s}") for s in NOTES]
    out += [(f"{p}.html", f"{BASE}{p}") for p in EXTRA_PAGES]
    out += [(f"cards-{c}.html", f"{BASE}cards/{c}") for c in CARD_CATS]
    return out


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (personal reading app; polite crawler)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def fetch_all(cache_dir, refresh=False, log=print):
    os.makedirs(cache_dir, exist_ok=True)
    got = 0
    for name, url in pages():
        path = os.path.join(cache_dir, name)
        if os.path.exists(path) and not refresh:
            continue
        if got:
            time.sleep(DELAY)
        html = get(url)
        if "GTA 6" not in html or len(html) < 12000:
            raise SystemExit(f"{url} 抓到的內容不像攻略頁，來源結構可能變了")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(html)
        got += 1
        log(f"  {name}  {len(html) // 1024} KB")
    return got


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    cache = args[0] if args else ".oplay-cache"
    got = fetch_all(cache, "--refresh" in argv)
    print(f"完成：新抓 {got} 頁，共 {len(pages())} 頁在 {cache}/")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
