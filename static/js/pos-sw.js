const CACHE_NAME = "laundrex-pos-v2";
const CORE_ASSETS = [
  "/pos/",
  "/static/css/app.css",
  "/static/css/pos.css",
  "/static/manifest.json",
  "/static/assets/laundrex-icon-64x64.png"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(CORE_ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.map((k) => (k === CACHE_NAME ? null : caches.delete(k)))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.pathname.includes("/catalog/api/pos-data/")) {
    event.respondWith(
      fetch(request).then((res) => {
        const resClone = res.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, resClone)).catch(() => {});
        return res;
      }).catch(() => caches.match(request))
    );
    return;
  }

  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) return cached;
      return fetch(request).then((res) => {
        const resClone = res.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, resClone)).catch(() => {});
        return res;
      }).catch(() => cached || Promise.reject("offline"));
    })
  );
});
