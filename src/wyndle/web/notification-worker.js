// Delivery only: this worker does not cache pages or schedule background alarms.
self.addEventListener('install', event => event.waitUntil(self.skipWaiting()));
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
self.addEventListener('notificationclick', event => {
  event.notification.close();
  const path = event.notification.data?.url === '/daily' ? '/daily' : '/';
  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    const existing = windows.find(client => new URL(client.url).pathname === path);
    if (existing) return existing.focus();
    return self.clients.openWindow(path);
  })());
});
