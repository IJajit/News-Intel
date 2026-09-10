// News Intel Service Worker — RFC 8291/8292 Push Notification Receiver
self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(clients.claim());
});

self.addEventListener('push', (event) => {
  let data = {};
  if (event.data) {
    try {
      data = event.data.json();
    } catch (_e) {
      data = { title: 'News Intel · Hourly Update', body: event.data.text() };
    }
  }

  const title = data.title || 'News Intel · Hourly Breaking News';
  const options = {
    body: data.body || 'New breaking stories published in the past hour.',
    icon: '/intel-badge.png',
    badge: 'https://img.icons8.com/material-outlined/72/ff5500/news.png',
    tag: 'hourly-news-intel',
    renotify: true,
    data: {
      url: data.url || '/?tab=latest'
    }
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) || '/?tab=latest';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
      for (let client of windowClients) {
        if ('focus' in client) {
          client.navigate(targetUrl);
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});
