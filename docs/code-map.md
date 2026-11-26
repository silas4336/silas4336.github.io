# 程式碼地圖

2026-11-26 依 `main` 現況整理。

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
| `fetch_oplay.py` | 把 oplay.cc 的 62 頁（5 章、筆記索引＋28 篇筆記、圖鑑索引＋23 分類、彩蛋、圖示全解、更新紀錄、進度清單）抓進 `.oplay-cache/`（已列入 `.gitignore`）。**會連網、會寫檔** |
| `oplay_parse.py` | oplay 頁面解析（任務、本章重點、筆記、圖鑑 `data-d`／`dxc-card`／`dxa-row`、彩蛋、HUD 圖示、更新紀錄、進度總表、內文轉純文字），沒有副作用，由 `build_gta6.py` 使用 |
| `build_gta6.py` | 產生 `gta6/data.js` 與 `gta6/codex.js`，見下一節。**會寫檔**，除了它和 `fetch_oplay.py`，其餘腳本都是唯讀 |
| `test_site.py` | `check_i18n.py` 各規則的單元測試（暫存資料夾假頁面）；`gta6/data.js` 與 `gta6/codex.js` 結構與內容完整性（每個任務有步驟與連結、行內標記成對、`see`/`covers` 指向有效任務、筆記、圖鑑不收原站圖片）、離線檔案清單、不在 sitemap；`oplay_parse.py` 與 `build_gta6.py` 的解析與合併（含一對多與無標籤有圖節點）；12 頁本機連結與圖片都存在；sitemap 與主站頁面一致；robots.txt；隱藏區（含 `gta6/`）每頁有 noindex；`.gitignore` 擋住快取與 `.env`，且版控裡沒有這些檔 |

資料流：

```
index.html、work-*.html ─┐
en/index.html、en/work-*.html ─┴▶ check_i18n.parse()：數字、圖片、作品頁連結、連回中文頁的連結
                                    └▶ num_diff()／diff() 比較 ─▶ main() 印出 ✓／✗ 與結束碼
主站 12 頁、sitemap.xml、robots.txt、隱藏區 HTML ─▶ test_site.SiteTest
```

## gta6/（攻略 PWA）

```
oplay.cc（繁體：5 章 130 個任務、章節重點、28 篇筆記、23 圖鑑分類、彩蛋、HUD、更新、進度表）
  ─▶ scripts/fetch_oplay.py ─▶ .oplay-cache/（本機快取，不進版控）─┐
                                                                    ├▶ scripts/build_gta6.py ─▶ gta6/data.js ＋ gta6/codex.js ─▶ gta6/index.html
遊民星空原站路書（gamersky.com，簡體：截圖圖文，已至第 2 章 D9）─▶ OpenCC s2twp 簡轉繁 ────┘
```

| 檔案 | 作用 |
|---|---|
| `index.html` | 整個 App（CSS、JS 都內嵌），採遊民路書風格（深色垂直時間軸抽屜／桌機側欄、旗標章節 A～E、頂端 sticky 目前節點列與 scroll-spy、節點卡 `content-visibility:auto`）。底部 5 頁：路書／圖鑑／筆記／搜尋／更多。hash 路由：`#/` 總覽與目錄、`#/book/<章>` 章節路書、`#/m/<任務ID>?md=s\|p&p=<序號>` 開啟該章路書並捲至節點、`#/ch/<章>?r=<區塊>-<列>` 本章重點、`#/codex` 與 `#/codex/<分類>?hl=<ID>` 圖鑑、`#/eggs?hl=<ID>` 彩蛋、`#/hud?hl=<ID>` 圖示全解、`#/updates` 更新紀錄、`#/progress` 進度儀表板（含 100%／白金檢核表）、`#/notes` 與 `#/n/<代號>` 筆記、`#/index` 索引、`#/search?q=` 全站搜尋、`#/more` 更多、`#/settings` 設定。資料文字一律用 DOM 方法放進頁面，不用 `innerHTML`；`**粗體**`、`⟦按鍵⟧` 兩種標記由 `rich()` 轉成 `<strong>`、`<kbd>` |
| `data.js` | `window.GUIDE`，**由腳本產生，不要手改**（約 714KB，gzip 後 277KB）。`chapters` → `missions`（`steps`／`keys`／`stuck` 來自 oplay，`blocks`／`ytags` 來自遊民，`see`／`seeLabel`／`covers` 用於一對多對應）、每章 `info`（本章重點）；另有 `notes`、`noteCats`、`progress`（100%／白金總表）、`aliases`、`trophies`、`optionals`、`notices` |
| `codex.js` | `window.CODEX`，**由腳本產生，不要手改**（約 262KB，gzip 後 80KB），首次渲染後於閒置時或進入圖鑑／搜尋／進度頁時動態載入，避免拖慢首屏。含 `groups`、`cards`（23 分類 1,250 則，含載具／武器數值與作弊碼，不複製原站圖鑑圖片）、`eggs`（62 個彩蛋）、`hud`（27 個圖示說明）、`updates`（更新紀錄） |
| `sw.js` | 離線（`gta6-guide-v5`）：預快取 `index.html`、`data.js`、`codex.js` 與圖示，有網路先抓新版（3 秒逾時退回快取）；遊民 CDN 圖片看過即暫存（上限 350 張，no-cors opaque 回應） |
| `manifest.webmanifest`、`icons/` | 安裝到主畫面用 |

`scripts/` 裡跟它有關的三支：`fetch_oplay.py`（客氣地爬 oplay：62 頁，間隔 1 秒，遵守 robots.txt，已抓過的不重抓）、`oplay_parse.py`（純文字＋小標記解析）、`build_gta6.py`（讀快取與遊民頁面，合併產出 `data.js` 與 `codex.js`）。

**資料怎麼合併**：以 oplay 的順序（官方順序、台灣官方譯名、5 章 130 個任務）為骨架；`YOUMIN_TO_SLUG` 把遊民任務對到 oplay 代號，對上的就把遊民截圖掛到同一個任務（遊民叫法留在 `aka`），且不覆蓋原本的主線類型；若遊民一個節點涵蓋多個 oplay 任務（如「買槍、理髮、買衣服」），`YOUMIN_TO_SLUG` 填多個 slug 的 tuple，圖文掛在第一個並記 `covers`，其餘任務記 `see`／`seeLabel` 顯示跳轉橫幅。遊民獨有的支線、搶劫、陌生人插在它前一個已對上的任務後面；遊民漏標標籤但有截圖的節點（如 D7、D9）仍保留為任務，僅無標籤且無截圖的節點（如 D10）歸為 `notices`。

- 瀏覽器儲存（`localStorage`，鍵都以 `gta6.` 開頭）：`done` 已完成任務 ID、`fav` 收藏、`ticks` 本章重點與會錯過勾選、`steps`（任務 ID → 已標記步驟的內容雜湊）、`col` 圖鑑與彩蛋已收集 ID、`pcounts` 100% 檢核表的計數與旗標、`pos` 上次閱讀位置、`fs` 字級、`theme`、`imgs` 是否載入圖片、`stepsOn`／`swipe`／`awake` 三個開關、`open` 目錄展開的章節。設定頁的「備份進度」輸出 `GTA6:` 開頭的 v2 備份碼（包含 `col` 與 `pcounts`），還原時向下相容舊版 v1。
- 任務 ID：oplay 的任務用 `p-<oplay 代號>`（`p-gone-fishing`），只有遊民有的用遊民的節點編號（`y-1468083467`）。來源改標題、補內容時 ID 都不變，已勾選進度不會跑掉。**加／改 `YOUMIN_TO_SLUG` 對照會讓遊民任務從 `y-` 變成 `p-`，舊 ID 要有對照：** `LEGACY_Y_IDS`、`LEGACY_P_IDS`，輸出的 `aliases` 讓頁面啟動時把舊進度轉成新 ID。
- 步驟標記與閱讀位置存的是「段落內容的雜湊」（`data-k`），不是段落序號，原作者改文章、插圖時不會錯位；找不到時退回序號。
- 圖片直接引用 `img1.gamersky.com`，不複製進 repo。`_S.jpg` 是 600 寬縮圖（約 25KB），去掉 `_S` 是原圖（約 100KB，點圖放大時才載）。每張圖帶寬高，頁面先用 `aspect-ratio` 留好位置。
- **圖床有防盜連結：請求帶 Referer（連自己網站的都算）會 403，不帶才正常。** 所以 `<head>` 有 `<meta name="referrer" content="no-referrer">`，每個 `<img>`、`fetch` 也都明確設 no-referrer。新加任何載圖的地方都不能漏。
- 圖片離線的限制：原站圖片沒有 CORS，只能存成 opaque 回應，瀏覽器配額每張估計約 7MB，不保證存得滿全部圖片。`sw.js` 存不進去時會丟掉最舊的 15 張再試；下載完頁面會比對實際存了幾張並告知。文字（路書步驟、章節重點、筆記、圖鑑、彩蛋、HUD、更新紀錄）全在 `data.js` 與 `codex.js`，一定能離線看。
- 互動地圖不複製，僅於「更多」與各項目外連至 `https://oplay.cc/gta6/map`。

**原作者／oplay 更新內容時**：

1. `py -3 scripts/fetch_oplay.py --refresh` 重抓 oplay（約 1 分鐘）。
2. 第一次要裝簡轉繁套件：`py -3 -m pip install opencc-python-reimplemented`（只有重新產生資料時才要）。然後 `py -3 scripts/build_gta6.py`（遊民頁面線上抓；oplay 讀快取）。遊民新寫的任務若 oplay 已有，把（繁體）中文名對應加進 `YOUMIN_TO_SLUG`（一對多用 tuple）；沒對上的主線任務腳本會印警告。
3. 把 `gta6/sw.js` 的 `CACHE` 版本號加 1，已安裝的 PWA 才會收到新內容。
4. 跑測試（`unittest` + `check_i18n.py`），push。

## 改東西時

- 改了中文頁要同步英文頁，跑 `py -3 scripts/check_i18n.py`。
- 新增作品頁要一起改：兩種語言的頁面、兩個首頁的專案列、`sitemap.xml`、每頁的 `hreflang`。`test_site.py` 會檢查 sitemap 和頁面對不對得上。
- `math-logic/`、`neko/` 在 `math-logic-games` 改，再用它的 `deploy.sh` 同步，不要直接改這裡。
