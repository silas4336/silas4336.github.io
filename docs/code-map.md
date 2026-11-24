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
├── gta6/                              個人用 GTA 6 攻略 PWA，noindex、不進 sitemap
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
| `build_gta6.py` | 產生 `gta6/data.js`，見上一節。**會寫檔**，其餘腳本都是唯讀 |
| `test_site.py` | `check_i18n.py` 各規則的單元測試（暫存資料夾假頁面）；`gta6/data.js` 結構、離線檔案清單、不在 sitemap；`build_gta6.py` 的解析與合併；12 頁本機連結與圖片都存在；sitemap 與主站頁面一致；robots.txt；隱藏區（含 `gta6/`）每頁有 noindex；`.gitignore` 擋住快取與 `.env`，且版控裡沒有這些檔 |

資料流：

```
index.html、work-*.html ─┐
en/index.html、en/work-*.html ─┴▶ check_i18n.parse()：數字、圖片、作品頁連結、連回中文頁的連結
                                    └▶ num_diff()／diff() 比較 ─▶ main() 印出 ✓／✗ 與結束碼
主站 12 頁、sitemap.xml、robots.txt、隱藏區 HTML ─▶ test_site.SiteTest
```

## gta6/（攻略 PWA）

```
遊民星空原站路書（gamersky.com，簡體，逐步圖文，只寫到第 2 章第 1 個任務）─▶ 簡轉繁（OpenCC s2twp）─┐
promptowy 主線任務清單（5 章約 100 個，只有摘要）──────────────────────────────┴▶ scripts/build_gta6.py ─▶ gta6/data.js ─▶ gta6/index.html
```

| 檔案 | 作用 |
|---|---|
| `index.html` | 整個 App（CSS、JS 都內嵌）。hash 路由：`#/` 目錄、`#/index` 索引（類型篩選、獎盃、可選任務）、`#/search?q=` 全文搜尋、`#/settings`、`#/m/<任務ID>?p=<段落>` 閱讀。資料文字一律用 `textContent` 放進頁面，不用 `innerHTML` |
| `data.js` | `window.GUIDE`，**由腳本產生，不要手改**。章節 → 任務 → `blocks`（字串＝段落，`{"i": 路徑}`＝圖片） |
| `sw.js` | 離線：頁面與文字「有網路先抓新版、3 秒沒回應用快取」；圖片在原站 CDN，看過的存起來（上限 120 張，no-cors 的 opaque 回應） |
| `manifest.webmanifest`、`icons/` | 安裝到主畫面用 |

- 瀏覽器儲存（`localStorage`，鍵都以 `gta6.` 開頭）：`done` 已完成任務 ID、`fav` 收藏、`steps`（任務 ID → 已標記的段落序號）、`pos` 上次閱讀位置、`fs` 字級、`theme`、`imgs` 是否載入圖片、`stepsOn`／`swipe`／`awake` 三個開關、`open` 目錄展開的章節。設定頁的「備份進度」把 `done`、`fav`、`steps`、`pos` 包成 `GTA6:` 開頭的一串文字，可貼回還原。
- 其他功能：點段落標記步驟、★ 收藏（索引頁有篩選）、閱讀時螢幕常亮（Wake Lock）、左右滑切換任務（避開螢幕邊緣）、預先下載圖片（單一任務或全部）。
- 圖片離線的限制：原站圖片沒有給我們網站的 CORS，只能存成 opaque 回應，瀏覽器配額裡每張算很大（約 7MB），所以不保證存得滿 213 張。`sw.js` 存不進去時會丟掉最舊的 15 張再試；下載完頁面會比對實際存了幾張並告知。要完全可靠就得把圖片複製進 repo（約 6MB），那是版權與 repo 大小的取捨，目前沒做。
- 任務 ID：promptowy 有的用英文名（`p-gone-fishing`），只有遊民有的用遊民的節點編號（`y-1468083467`）。來源改標題、補內容時 ID 都不變，已勾選進度不會跑掉。**改 `YOUMIN_TO_EN` 對照時小心：加／改對應會讓該任務從 `y-` 變成 `p-`，要在 `aliases` 補舊→新的對照。** 舊版（轉載頁）用 `y-中文名`，`LEGACY_Y_IDS` 記著對照，`data.js` 的 `aliases` 讓頁面啟動時把舊進度轉成新 ID。
- 步驟標記與閱讀位置存的是「段落內容的雜湊」（`data-k`），不是段落序號，原作者改文章、插圖時不會錯位；找不到時閱讀位置退回用序號。
- 遊民原站已經沒有「第 1 章（上／中／下）」這種分段，章節以 promptowy 的官方章節（第 1～5 章）為準。作者最後一則「正在推第 2 章，25 號開更」沒有任務標籤，會被存成 `notices`，顯示在目錄頂端。
- 圖片直接引用 `img1.gamersky.com`，不複製進 repo。`_S.jpg` 是 600 寬縮圖（約 25KB），去掉 `_S` 是原圖（約 100KB，點圖放大時才載）。每張圖帶寬高，頁面先用 `aspect-ratio` 留好位置。
- **圖床有防盜連結：請求帶 Referer（連自己網站的都算）會 403，不帶才正常。** 所以 `<head>` 有 `<meta name="referrer" content="no-referrer">`，每個 `<img>`、`fetch` 也都明確設 no-referrer。新加任何載圖的地方都不能漏。

**原作者補寫了新內容時**：

1. 第一次要裝簡轉繁套件：`py -3 -m pip install opencc-python-reimplemented`（只有重新產生資料時才要）。然後 `py -3 scripts/build_gta6.py`（不帶參數會線上抓兩個來源；也可帶本機 HTML 檔）。新寫的任務若是 promptowy 已有的，把（繁體）中文名對應加進 `build_gta6.py` 的 `YOUMIN_TO_EN`，沒對上會印警告。
2. 把 `gta6/sw.js` 的 `CACHE` 版本號加 1，已安裝的 PWA 才會收到新內容。
3. 跑測試，push。

## 改東西時

- 改了中文頁要同步英文頁，跑 `py -3 scripts/check_i18n.py`。
- 新增作品頁要一起改：兩種語言的頁面、兩個首頁的專案列、`sitemap.xml`、每頁的 `hreflang`。`test_site.py` 會檢查 sitemap 和頁面對不對得上。
- `math-logic/`、`neko/` 在 `math-logic-games` 改，再用它的 `deploy.sh` 同步，不要直接改這裡。
