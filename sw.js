const CACHE = 'tuore-v2';
const ASSETS = ['./', './index.html', './manifest.json', './icons/icon-192.png', './icons/icon-512.png'];

self.addEventListener('install', function (e) {
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(ASSETS); }));
});

self.addEventListener('activate', function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
    }).then(function () { return self.clients.claim(); })
  );
});

// Network-first: always serve the freshest version when online, keeping the
// cache as an offline fallback only -- never let a stale cached copy win.
self.addEventListener('fetch', function (e) {
  e.respondWith(
    fetch(e.request).then(function (response) {
      var copy = response.clone();
      caches.open(CACHE).then(function (c) { c.put(e.request, copy); });
      return response;
    }).catch(function () {
      return caches.match(e.request);
    })
  );
});
