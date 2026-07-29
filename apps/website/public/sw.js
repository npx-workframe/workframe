// ponytail: minimal installable-shell cache; upgrade to Serwist when offline routes matter
const CACHE = "workframe-website-v3";
const SHELL = ["/favicon.svg", "/manifest.webmanifest", "/wordmark.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))),
    ).then(() => self.clients.claim()),
  );
});

function networkFirst(request) {
  return fetch(request)
    .then((response) => {
      if (response.ok && response.type === "basic") {
        const copy = response.clone();
        void caches.open(CACHE).then((cache) => cache.put(request, copy));
      }
      return response;
    })
    .catch(() => caches.match(request));
}

function cacheFirst(request) {
  return caches.match(request).then((cached) => cached ?? fetch(request));
}

function isNetworkFirstPath(pathname) {
  return (
    pathname === "/" ||
    pathname.startsWith("/docs") ||
    pathname.startsWith("/_next/")
  );
}

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;

  event.respondWith(
    isNetworkFirstPath(url.pathname)
      ? networkFirst(event.request)
      : cacheFirst(event.request),
  );
});
