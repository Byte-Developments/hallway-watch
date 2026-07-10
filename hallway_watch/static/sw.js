const NOTIFICATION_ICON =
  "data:image/svg+xml," +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">' +
      '<rect width="64" height="64" rx="12" fill="#4f8cff"/>' +
      '<circle cx="32" cy="24" r="10" fill="white"/>' +
      '<path d="M16 52c0-9 7-16 16-16s16 7 16 16" fill="white"/>' +
      "</svg>"
  );

self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("push", (event) => {
  let data = { title: "Hallway Alert", message: "Someone is in the hallway" };

  if (event.data) {
    try {
      data = event.data.json();
    } catch (err) {
      console.error("Bad push payload", err);
    }
  }

  event.waitUntil(
    self.registration.showNotification(data.title || "Hallway Alert", {
      body: data.message || "Someone is in the hallway",
      icon: NOTIFICATION_ICON,
      tag: "hallway-watch-alert",
      renotify: true,
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((windowClients) => {
      for (const client of windowClients) {
        if ("focus" in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow("/");
      }
    })
  );
});
