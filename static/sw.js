const CACHE_NAME = "progretech-mesh-shell-v27-fleet-discovery";
// Retain the prior cache marker for release-contract and rollback checks.
const LEGACY_CACHE_NAME = "progretech-mesh-shell-v13-all-avatars";
const SHELL_ASSETS = [
  "/static/css/app.css?v=mesh-fleet-v27",
  "/static/analytics/analytics-consent.js",
  "/static/analytics/analytics-consent.css",
  "/static/js/app.js?v=mesh-fleet-v27",
  "/static/js/avatars.js?v=moxy-teal-20261007",
  "/static/js/agent-management.js",
  "/static/js/onboarding.js",
  "/static/css/onboarding.css",
  "/manifest.webmanifest"
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS.map((url) => new Request(url, {cache: "reload"})))));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((key) => key.startsWith("progretech-mesh-shell-") && key !== CACHE_NAME).map((key) => caches.delete(key))))
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);

  // Operational data is never stored in the service-worker cache.
  if (url.origin !== self.location.origin || request.method !== "GET" ||
      url.pathname.startsWith("/api/") ||
      url.pathname.startsWith("/ws/") ||
      url.pathname.startsWith("/agents/") ||
      url.pathname.startsWith("/plugins/") ||
      url.pathname.startsWith("/distribution/")) {
    return;
  }

  // Navigations and all other non-public requests stay on the network.
  if (request.mode === "navigate" || !SHELL_ASSETS.includes(url.pathname + url.search)) return;

  event.respondWith(caches.open(CACHE_NAME).then((cache) => cache.match(request)).then((cached) => cached || fetch(request)));
});
