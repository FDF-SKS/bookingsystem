/* Service worker for SKS Booking.
 *
 * Served from the site root (/sw.js) so it controls every page. It:
 *  - caches the app shell (CSS, JS, fonts, icons) and CDN assets,
 *  - keeps a per-user snapshot of pages that were visited, so the app still
 *    renders offline with its styling intact,
 *  - stamps cached pages with X-Cached-At, which the client shows in the
 *    offline banner,
 *  - handles Web Push notifications and focuses the right page on tap.
 *
 * Authenticated HTML is cached per user id. The page sends its id after every
 * load; logging out sends null, which clears all page caches on that device.
 */
const VERSION = 'v4'; // Bump when the app shell changes; old caches are removed on activate.
const SHELL_CACHE = `sks-shell-${VERSION}`;
const PAGE_CACHE_PREFIX = `sks-pages-${VERSION}-`;
const MEDIA_CACHE = `sks-media-${VERSION}`;
const META_CACHE = `sks-meta-${VERSION}`;
const USER_KEY = '/__sks_user';
const OFFLINE_URL = '/notifications/offline/';
const NAV_TIMEOUT_MS = 5000;
const MAX_PAGES = 40;
const MAX_MEDIA = 80;

const PRECACHE_URLS = [
    OFFLINE_URL,
    '/static/css/custom.css',
    '/static/css/tiptap-theme.css',
    '/static/css/program.css',
    '/static/vendor/bootstrap/css/bootstrap.min.css',
    '/static/vendor/bootstrap/js/bootstrap.bundle.min.js',
    '/static/vendor/bootstrap-icons/bootstrap-icons.min.css',
    '/static/vendor/bootstrap-icons/fonts/bootstrap-icons.woff2?dd67030699838ea613ee6dbda90effa6',
    '/static/vendor/leaflet/leaflet.css',
    '/static/vendor/leaflet/leaflet.js',
    '/static/js/pwa.js',
    '/static/js/ui-actions.js',
    '/static/js/theme-toggle.js',
    '/static/js/program.js',
    '/static/js/notification-settings.js',
    '/static/fonts/work-sans-latin.woff2',
    '/static/icons/icon-192.png',
    '/static/icons/badge-72.png',
];

const UNCACHEABLE_PREFIXES = [
    '/admin/',
    '/accounts/',
    '/notifications/calendar/',
    '/ses/',
];

let cachedUserId;

function pageCacheName(userId) {
    return `${PAGE_CACHE_PREFIX}${userId || 'anon'}`;
}

function cacheKey(url) {
    const parsed = new URL(url, self.location.origin);
    parsed.hash = '';
    return parsed.href;
}

async function currentUserId() {
    if (cachedUserId !== undefined) {
        return cachedUserId;
    }
    try {
        const meta = await caches.open(META_CACHE);
        const stored = await meta.match(USER_KEY);
        cachedUserId = stored ? (await stored.text()) || null : null;
    } catch (error) {
        cachedUserId = null;
    }
    return cachedUserId;
}

async function setUserId(value) {
    const userId =
        value === undefined || value === null || value === '' ? null : String(value);
    cachedUserId = userId;

    const meta = await caches.open(META_CACHE);
    if (userId) {
        await meta.put(USER_KEY, new Response(userId));
    } else {
        await meta.delete(USER_KEY);
    }

    const keep = pageCacheName(userId);
    const names = await caches.keys();
    await Promise.all(
        names
            .filter(
                (name) =>
                    name.startsWith(PAGE_CACHE_PREFIX) &&
                    (name !== keep || !userId)
            )
            .map((name) => caches.delete(name))
    );

    if (!userId) {
        // Do not leave photos and other media behind after logout.
        await caches.delete(MEDIA_CACHE);
    }
}

async function precache() {
    const cache = await caches.open(SHELL_CACHE);
    await Promise.all(
        PRECACHE_URLS.map(async (url) => {
            try {
                let response = await fetch(url, { cache: 'reload' });
                if (!response || (!response.ok && response.type !== 'opaque')) {
                    response = await fetch(url, {
                        cache: 'reload',
                        mode: 'no-cors',
                    });
                }
                if (response && (response.ok || response.type === 'opaque')) {
                    await cache.put(url, response);
                }
            } catch (error) {
                // An optional asset (or a blocked CDN request) must not block
                // the worker from installing.
            }
        })
    );
}

self.addEventListener('install', (event) => {
    event.waitUntil(precache().then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        (async () => {
            const names = await caches.keys();
            await Promise.all(
                names.map((name) => {
                    if (name === SHELL_CACHE || name === META_CACHE) {
                        return null;
                    }
                    if (name === MEDIA_CACHE) {
                        return null;
                    }
                    if (name.startsWith(PAGE_CACHE_PREFIX)) {
                        return null;
                    }
                    // Drop caches from older versions (including the old v1
                    // offline cache) so no stale personal data survives.
                    if (name.startsWith('sks-')) {
                        return caches.delete(name);
                    }
                    return null;
                })
            );
            await self.clients.claim();
        })()
    );
});

function isCacheableNavigation(url) {
    if (url.origin !== self.location.origin) {
        return false;
    }
    return !UNCACHEABLE_PREFIXES.some((prefix) =>
        url.pathname.startsWith(prefix)
    );
}

async function fetchWithTimeout(request, timeoutMs) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
        return await fetch(request, { signal: controller.signal });
    } finally {
        clearTimeout(timer);
    }
}

async function trimCache(cache, maxEntries) {
    const keys = await cache.keys();
    if (keys.length > maxEntries) {
        await Promise.all(
            keys
                .slice(0, keys.length - maxEntries)
                .map((key) => cache.delete(key))
        );
    }
}

async function cachePage(request, response) {
    if (
        !response ||
        !response.ok ||
        response.type !== 'basic' ||
        response.redirected
    ) {
        return;
    }
    const contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('text/html')) {
        return;
    }

    const cache = await caches.open(pageCacheName(await currentUserId()));
    const body = await response.clone().text();
    const headers = new Headers(response.headers);
    headers.set('X-Cached-At', new Date().toISOString());
    // The body was decoded and re-wrapped, so these headers would lie.
    headers.delete('content-length');
    headers.delete('content-encoding');
    // A cached Set-Cookie would overwrite the live session when the snapshot is
    // served later; session handling belongs to the network response only.
    headers.delete('set-cookie');
    headers.delete('set-cookie2');

    const stamped = new Response(body, {
        status: response.status,
        statusText: response.statusText,
        headers,
    });

    // Use the URL string as key: Django adds Vary: Cookie, which would
    // otherwise prevent matching a later request that has no Cookie header.
    await cache.put(cacheKey(request.url), stamped);
    await trimCache(cache, MAX_PAGES);
}

async function offlineFallback() {
    try {
        const cache = await caches.open(SHELL_CACHE);
        const cached = await cache.match(OFFLINE_URL);
        if (cached) {
            return cached;
        }
    } catch (error) {
        // Fall through to the minimal inline page.
    }
    return new Response(
        '<!doctype html><meta charset="utf-8"><title>Offline</title>' +
            '<p>Du er offline, og der er endnu ikke gemt data til denne side.</p>',
        {
            status: 503,
            headers: { 'Content-Type': 'text/html; charset=utf-8' },
        }
    );
}

async function navigationResponse(request) {
    const url = new URL(request.url);

    if (!isCacheableNavigation(url)) {
        try {
            return await fetch(request);
        } catch (error) {
            return offlineFallback();
        }
    }

    const cache = await caches.open(pageCacheName(await currentUserId()));
    try {
        const response = await fetchWithTimeout(request, NAV_TIMEOUT_MS);
        if (response && response.ok && !response.redirected) {
            await cachePage(request, response);
        }
        return response;
    } catch (error) {
        const cached = await cache.match(cacheKey(request.url));
        if (cached) {
            return cached;
        }
        return offlineFallback();
    }
}

async function fetchAndCache(cache, request) {
    try {
        const response = await fetch(request);
        if (response && (response.ok || response.type === 'opaque')) {
            await cache.put(request.url, response.clone());
        }
        return response;
    } catch (error) {
        return null;
    }
}

async function staticResponse(request, event) {
    const cache = await caches.open(SHELL_CACHE);
    const cached = await cache.match(request.url);
    if (cached) {
        // Stale-while-revalidate: serve immediately, refresh in the background.
        event.waitUntil(fetchAndCache(cache, request));
        return cached;
    }
    const response = await fetchAndCache(cache, request);
    return response || Response.error();
}

async function mediaResponse(request, event) {
    const cache = await caches.open(MEDIA_CACHE);
    const cached = await cache.match(request.url);
    if (cached) {
        event.waitUntil(fetchAndCache(cache, request));
        return cached;
    }
    const response = await fetchAndCache(cache, request);
    if (response) {
        await trimCache(cache, MAX_MEDIA);
    }
    return response || Response.error();
}

self.addEventListener('fetch', (event) => {
    const request = event.request;
    if (request.method !== 'GET') {
        return;
    }

    const url = new URL(request.url);

    if (request.mode === 'navigate') {
        // Only same-origin pages belong to this app; let the browser handle the rest.
        if (url.origin === self.location.origin) {
            event.respondWith(navigationResponse(request));
        }
        return;
    }

    if (
        url.origin === self.location.origin &&
        url.pathname.startsWith('/static/')
    ) {
        event.respondWith(staticResponse(request, event));
        return;
    }

    if (
        url.origin === self.location.origin &&
        url.pathname.startsWith('/media/') &&
        request.destination === 'image'
    ) {
        event.respondWith(mediaResponse(request, event));
    }
});

self.addEventListener('message', (event) => {
    const data = event.data || {};
    if (data.type === 'SKS_IDENTIFY') {
        event.waitUntil(setUserId(data.userId));
    }
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
