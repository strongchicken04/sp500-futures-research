// Offline cache for the Trénink app. Bump CACHE when the files change.
var CACHE = 'trenink-v1';
var ASSETS = [
  './',
  './index.html',
  './manifest.webmanifest',
  './icon-192.png',
  './icon-512.png',
  './apple-touch-icon.png'
];

self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(CACHE).then(function (c) { return c.addAll(ASSETS); }).then(function () {
      return self.skipWaiting();
    })
  );
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys()
      .then(function (keys) {
        return Promise.all(keys.map(function (k) { return k === CACHE ? null : caches.delete(k); }));
      })
      .then(function () { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function (event) {
  var req = event.request;
  if (req.method !== 'GET') return;

  // Network-first for the page itself, so a new version shows up on the next
  // online open; the cached copy is the offline fallback.
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch('./index.html')
        .then(function (res) {
          var clone = res.clone();
          caches.open(CACHE).then(function (c) { c.put('./index.html', clone); });
          return res;
        })
        .catch(function () { return caches.match('./index.html'); })
    );
    return;
  }

  event.respondWith(
    caches.match(req).then(function (cached) {
      return cached || fetch(req).then(function (res) {
        if (res.ok && new URL(req.url).origin === self.location.origin) {
          var clone = res.clone();
          caches.open(CACHE).then(function (c) { c.put(req, clone); });
        }
        return res;
      });
    })
  );
});
