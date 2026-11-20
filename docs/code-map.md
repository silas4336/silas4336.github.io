# 程式碼地圖

2026-11-21 依 `main` 現況整理。

## 整體架構

```
GitHub Pages ◀── main 分支（整個 repo 原樣發佈，.nojekyll）
├── 主站（在這個 repo 直接手寫維護）
│   ├── index.html、work-*.html        中文
│   ├── en/index.html、en/work-*.html  英文（檔名一一對應）
│   ├── style.css                      12 頁共用
│   └── assets/                        截圖；-zh／-en 結尾是分語言的同一張圖
├── math-logic/、neko/                 由 math-logic-games 的 deploy.sh 同步進來（部署工作區 ../_site_deploy）
├── preview-*/                         設計預覽，noindex
└── scripts/                           本機檢查，不影響網站
```

沒有 JavaScript 框架、沒有建置。每頁的 JS 都是內嵌的小段落。

## 主站頁面

| 頁面 | 組成 |
|---|---|
| `index.html` | `.hero` 自我介紹 → `.sec-title` 分段 → 每個專案一列 `.row`（`.thumb` 縮圖、`.rt` 標題、`.rd` 說明、`.rm` 標籤），連到對應的作品頁 |
| `work-*.html` | 單一作品的介紹與截圖；截圖放在 `.frame` 裡，點擊開大圖 |

每頁共同的三段內嵌 JS：

1. `<head>` 裡的一行：在畫面出現前決定主題。順序是 `localStorage.theme` → 系統 `prefers-color-scheme` → 預設深色，結果寫到 `<html data-theme>`，避免閃一下。
2. 主題切換鈕 `#themeToggle`：點擊在 light／dark 間切換並存進 `localStorage.theme`。沒手動選過時會跟著系統深淺色變。
3. 作品頁才有的燈箱 `#lb`：`.frame img` 可以點擊或用 Enter／空白鍵開大圖，Esc 或點背景關閉，關閉後焦點回到原圖。

瀏覽器儲存只有 `localStorage.theme`（`light`／`dark`）。

## 中英版對應與 SEO

- 每頁 `<head>` 有 `<link rel="alternate" hreflang="zh-Hant|en|x-default">` 互相指向。
- 頁內的語言切換按鈕帶 `hreflang`，是英文頁唯一可以連回中文頁的連結。
- `sitemap.xml` 只列主站 12 頁；`robots.txt` 指向 sitemap。`math-logic/`、`neko/`、`preview-*/` 不擋 robots，改成每頁自己帶 `noindex`。

## 檢查腳本（`scripts/`）

| 檔案 | 作用 |
|---|---|
| `check_i18n.py` | 逐對比較中英頁：內文數字（`eight` 也能對上 `8`，年份與日期不比）、圖片檔（忽略 `-zh`／`-en`）、作品頁連結、英文頁不連回中文頁（`../`、`/en/` 以外的站內絕對路徑或完整網址，`hreflang` 除外）。`main(root)` 回傳結束碼，有不一致回 1 |
| `test_site.py` | `check_i18n.py` 各規則的單元測試（暫存資料夾假頁面）；12 頁本機連結與圖片都存在；sitemap 與主站頁面一致；robots.txt；隱藏區每頁有 noindex；`.gitignore` 擋住快取與 `.env`，且版控裡沒有這些檔 |

資料流：

```
index.html、work-*.html ─┐
en/index.html、en/work-*.html ─┴▶ check_i18n.parse()：數字、圖片、作品頁連結、連回中文頁的連結
                                    └▶ num_diff()／diff() 比較 ─▶ main() 印出 ✓／✗ 與結束碼
主站 12 頁、sitemap.xml、robots.txt、隱藏區 HTML ─▶ test_site.SiteTest
```

## 改東西時

- 改了中文頁要同步英文頁，跑 `py -3 scripts/check_i18n.py`。
- 新增作品頁要一起改：兩種語言的頁面、兩個首頁的專案列、`sitemap.xml`、每頁的 `hreflang`。`test_site.py` 會檢查 sitemap 和頁面對不對得上。
- `math-logic/`、`neko/` 在 `math-logic-games` 改，再用它的 `deploy.sh` 同步，不要直接改這裡。
