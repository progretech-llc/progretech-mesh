const CACHE_NAME = "progretech-mesh-shell-v14-moxy-avatar";
// Retain the prior cache marker for release-contract and rollback checks.
const LEGACY_CACHE_NAME = "progretech-mesh-shell-v13-all-avatars";
const SHELL_ASSETS = [
  "/",
  "/how-it-works",
  "/static/css/app.css",
  "/static/js/app.js",
  "/static/js/avatars.js?v=seven-roles-moxy",
  "/static/js/agent-management.js",
  "/static/js/onboarding.js",
  "/static/css/onboarding.css",
  "/manifest.webmanifest"
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);

  // Operational data is never stored in the service-worker cache.
  if (request.method !== "GET" ||
      url.pathname.startsWith("/api/") ||
      url.pathname.startsWith("/ws/") ||
      url.pathname.startsWith("/agents/") ||
      url.pathname.startsWith("/plugins/") ||
      url.pathname.startsWith("/distribution/")) {
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(fetch(request).catch(() => caches.match(request).then((r) => r || caches.match("/"))));
    return;
  }

  event.respondWith(caches.match(request).then((cached) => cached || fetch(request)));
});
