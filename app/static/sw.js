var CACHE = 'photoblog-v1';
var SHELL = ['/', '/gallery', '/static/manifest.json'];

self.addEventListener('install', function(e) {
  e.waitUntil(
    caches.open(CACHE).then(function(c) { return c.addAll(SHELL); })
  );
  self.skipWaiting();
});

self.addEventListener('activate', function(e) {
  e.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(keys.filter(function(k) { return k !== CACHE; }).map(function(k) { return caches.delete(k); }));
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', function(e) {
  var url = new URL(e.request.url);

  // Network-first for photos and thumbnails (always fresh)
  if (url.pathname.startsWith('/photos/') || url.pathname.startsWith('/thumbnails/') || url.pathname.startsWith('/display/') || url.pathname === '/hero-image') {
    e.respondWith(
      fetch(e.request).catch(function() { return caches.match(e.request); })
    );
    return;
  }

  // Cache-first for everything else
  e.respondWith(
    caches.match(e.request).then(function(cached) {
      return cached || fetch(e.request).then(function(response) {
        var clone = response.clone();
        caches.open(CACHE).then(function(c) { c.put(e.request, clone); });
        return response;
      });
    })
  );
});
