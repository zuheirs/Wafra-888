// Service worker بسيط لوفرة 888: يخزّن هيكل الواجهة (shell) للعمل بدون إنترنت جزئياً،
// وما يلمس أبداً أي طلب API (لازم يضل حي دايماً — بيانات حساسة وحقيقية).
const CACHE_NAME = "wafra888-shell-v1";
const SHELL_URLS = [
  "/static/css/style.css",
  "/static/js/app.js",
  "/static/js/leadership.js",
  "/static/manifest.json",
  "/static/offline.html",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_URLS)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // API وتسجيل الدخول: شبكة فقط، أبداً ما نكاش بيانات حساسة أو ديناميكية
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/login") ||
      url.pathname.startsWith("/logout") || url.pathname.startsWith("/change-password") ||
      url.pathname.startsWith("/cron/")) {
    return;
  }

  if (event.request.method !== "GET") return;

  // ملفات ثابتة: cache-first
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(event.request).then((cached) => cached || fetch(event.request))
    );
    return;
  }

  // صفحات: network-first مع fallback لصفحة أوفلاين بسيطة
  event.respondWith(
    fetch(event.request).catch(() => caches.match("/static/offline.html"))
  );
});
