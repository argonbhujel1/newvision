/* New Vision Academy – Service Worker for background Web Push */
self.addEventListener("install", (e) => {
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(clients.claim());
});

self.addEventListener("push", (event) => {
  let data = {
    title: "New Vision Academy",
    body: "New update from school",
    url: "/",
  };
  try {
    if (event.data) {
      const parsed = event.data.json();
      data = Object.assign({}, data, parsed);
    }
  } catch (err) {
    try {
      const text = event.data && event.data.text();
      if (text) data.body = text;
    } catch (e2) {}
  }

  const options = {
    body: data.body || "New update from school",
    icon: "/static/icons/icon-192.png",
    badge: "/static/icons/icon-192.png",
    data: { url: data.url || "/" },
    vibrate: [120, 60, 120],
    requireInteraction: false,
    tag: data.id ? "nva-" + data.id : "nva-update",
    renotify: true,
  };

  event.waitUntil(self.registration.showNotification(data.title || "New Vision Academy", options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      for (const c of list) {
        if (c.url.includes(self.location.origin) && "focus" in c) {
          c.navigate(url);
          return c.focus();
        }
      }
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});

self.addEventListener("fetch", () => {});
