# silas4336.github.io

個人作品集網站，GitHub Pages 直接發佈這個 repo 的 `main`（有 `.nojekyll`，檔案原樣上線，push 後約 1 分鐘生效）。純 HTML／CSS，沒有建置步驟與依賴。

- 中文版：https://silas4336.github.io/
- 英文版：https://silas4336.github.io/en/

架構、頁面組成與資料流見 [docs/code-map.md](docs/code-map.md)。

## 內容

| 路徑 | 內容 |
|---|---|
| `index.html`、`work-*.html` | 中文首頁與 5 個作品頁（agentic、crm、maigpt、side、website） |
| `en/` | 同樣 6 頁的英文版，檔名一一對應 |
| `style.css`、`assets/` | 共用樣式；截圖（WebP 為主，部分保留 JPG） |
| `robots.txt`、`sitemap.xml` | sitemap 只列主站 12 頁 |
| `math-logic/`、`neko/` | 八大智能活動小遊戲與貓咪數獨 1000 關 App，**不在這裡改**：原始檔在私人 repo `math-logic-games`，用它的 `deploy.sh` 同步過來 |
| `preview-*/` | 給人看的設計預覽頁，每頁 `noindex`，首頁不連 |
| `scripts/` | 唯讀檢查腳本與測試 |

## 檢查

Windows 上 Python 用 `py -3`。

```bash
py -3 scripts/check_i18n.py                              # 中英版數字、圖片、作品頁連結一致，英文頁不連回中文頁
py -3 -m unittest discover -s scripts -p "test_*.py"     # 上面規則的單元測試＋本機連結、sitemap、noindex、.gitignore
```

改版面後要看手機 390px 與 1280×720 兩種寬度。
