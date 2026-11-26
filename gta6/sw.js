// GTA6 攻略離線快取。
// 頁面與文字（index.html、data.js、codex.js）：有網路時先抓新版（3 秒內沒回應就用快取），沒網路用快取。
// 圖片在原站 CDN：看過的存起來（上限 IMG_MAX 張，全部約 275 張），下次沒網路也看得到。
// 重跑 scripts/build_gta6.py 更新 data.js／codex.js 或改了 index.html 後，把 CACHE 的版本號加 1，已安裝的 PWA 才會收到新內容。
const CACHE = "gta6-guide-v8";
const IMG_CACHE = "gta6-images-v2";
const IMG_HOST = "img1.gamersky.com";
const IMG_MAX = 350;
const FILES = ["./", "./index.html", "./data.js", "./codex.js", "./manifest.webmanifest",
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
    .then(keys => Promise.all(keys.filter(k => k !== CACHE && k !== IMG_CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

async function trimImages(cache) {
  const keys = await cache.keys();
  for (const key of keys.slice(0, Math.max(0, keys.length - IMG_MAX))) await cache.delete(key);
}

// opaque 回應在瀏覽器的配額裡每張算很大（約 7MB），容量滿了 put 會失敗：丟掉最舊的幾張再試一次，還是不行就算了
async function putImage(cache, req, first, second) {
  try { await cache.put(req, first); }
  catch (e) {
    for (const key of (await cache.keys()).slice(0, 15)) await cache.delete(key);
    try { await cache.put(req, second); } catch (e2) { return; }
  }
  await trimImages(cache);
}

async function cachedImage(event) {
  const req = event.request;
  const cache = await caches.open(IMG_CACHE);
  const hit = await cache.match(req);
  if (hit) return hit;
  const res = await fetch(req);
  // <img> 發出的是 no-cors 請求，原站沒有 CORS 標頭，拿到的是 opaque（status 0）；兩種都存
  if (res.ok || res.type === "opaque") event.waitUntil(putImage(cache, req, res.clone(), res.clone()));
  return res;
}

self.addEventListener("fetch", event => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.hostname === IMG_HOST) {
    event.respondWith(cachedImage(event).catch(() => Response.error()));
    return;
  }
  if (url.origin !== location.origin) return;
  const isIcon = url.pathname.includes("/icons/");
  event.respondWith(caches.open(CACHE).then(async cache => {
    const cached = await cache.match(req, { ignoreSearch: true });
    // 圖示幾乎不會變，直接用快取
    if (isIcon && cached) return cached;

    const fresh = fetch(req, { cache: "no-cache" }).then(res => {
      if (res.ok) cache.put(req, res.clone());
      return res;
    });
    if (!cached) return fresh;

    const timeout = new Promise(resolve => setTimeout(() => resolve(cached), NETWORK_TIMEOUT_MS));
    event.waitUntil(fresh.catch(err => console.warn("背景更新失敗，先用快取", err)));
    return Promise.race([fresh.catch(() => cached), timeout]);
  }));
});
