// 貓咪數獨離線快取：有網路時先抓新版（3 秒內沒回應就用快取），沒網路時用快取。
// 改了 index.html／levels.js 後也要改 CACHE 版本，玩家開著的頁面才會收到「有新版本」。
const CACHE = "neko-app-v5";
const FILES = ["./", "./index.html", "./levels.js", "./manifest.webmanifest",
  "./icons/icon-192.png", "./icons/icon-512.png", "./icons/maskable-512.png", "./icons/apple-touch-icon.png"];
const NETWORK_TIMEOUT_MS = 3000;

self.addEventListener("install", event => {
  // cache: "reload" 跳過瀏覽器 HTTP 快取，確保存進去的是剛部署的版本
  event.waitUntil(caches.open(CACHE)
    .then(cache => cache.addAll(FILES.map(url => new Request(url, { cache: "reload" }))))
    .then(() => self.skipWaiting()));
});

self.addEventListener("activate", event => {
  event.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", event => {
  const req = event.request;
  if (req.method !== "GET" || new URL(req.url).origin !== location.origin) return;
  const isIcon = new URL(req.url).pathname.includes("/icons/");
  event.respondWith(caches.open(CACHE).then(async cache => {
    const cached = await cache.match(req, { ignoreSearch: true });
    // 圖示幾乎不會變，直接用快取
    if (isIcon && cached) return cached;

    const fresh = fetch(req, { cache: "no-cache" }).then(res => {
      if (res.ok) cache.put(req, res.clone());
      return res;
    });
    if (!cached) return fresh;
    // 伺服器回 404／500 時不要把錯誤頁給玩家，改用快取的版本
    const freshOrCached = fresh.then(res => (res.ok ? res : cached));

    const timeout = new Promise(resolve => setTimeout(() => resolve(cached), NETWORK_TIMEOUT_MS));
    event.waitUntil(fresh.catch(err => console.warn("背景更新失敗，先用快取", err)));
    return Promise.race([freshOrCached.catch(() => cached), timeout]);
  }));
});
