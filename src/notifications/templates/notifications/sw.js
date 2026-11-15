/* Service worker for SKS Booking.
 *
 * Served from the site root (/sw.js) so it can control every page. It handles
 * incoming Web Push messages, focuses/opens the right page when a notification
 * is tapped, and keeps a minimal offline fallback.
 */
const CACHE_NAME = 'sks-booking-v1';
const OFFLINE_URL = '/notifications/offline/';

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches
            .open(CACHE_NAME)
            .then((cache) => cache.addAll([OFFLINE_URL]))
            .catch(() => undefined)
            .then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches
            .keys()
            .then((keys) =>
                Promise.all(
                    keys
                        .filter((key) => key !== CACHE_NAME)
                        .map((key) => caches.delete(key))
                )
            )
            .then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    const request = event.request;
    if (request.method !== 'GET') {
        return;
    }
    if (request.mode !== 'navigate') {
        return;
    }
    event.respondWith(
        fetch(request).catch(() =>
            caches.match(OFFLINE_URL).then((response) => response || Response.error())
        )
    );
});

self.addEventListener('push', (event) => {
    let payload = {
        title: 'SKS Booking',
        body: 'Du har en ny besked.',
        url: '/',
        tag: 'sks-booking',
    };
    if (event.data) {
        try {
            payload = Object.assign(payload, event.data.json());
        } catch (err) {
            payload.body = event.data.text();
        }
    }

    const options = {
        body: payload.body || '',
        icon: payload.icon || '/static/icons/icon-192.png',
        badge: payload.badge || '/static/icons/badge-72.png',
        tag: payload.tag || 'sks-booking',
        renotify: Boolean(payload.tag),
        timestamp: Date.now(),
        data: {
            url: payload.url || '/',
        },
    };

    event.waitUntil(self.registration.showNotification(payload.title, options));
});

self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    const target = new URL(
        (event.notification.data && event.notification.data.url) || '/',
        self.location.origin
    ).href;

    event.waitUntil(
        self.clients
            .matchAll({ type: 'window', includeUncontrolled: true })
            .then((clientList) => {
                for (const client of clientList) {
                    if (client.url === target && 'focus' in client) {
                        return client.focus();
                    }
                }
                if (self.clients.openWindow) {
                    return self.clients.openWindow(target);
                }
                return undefined;
            })
    );
});
