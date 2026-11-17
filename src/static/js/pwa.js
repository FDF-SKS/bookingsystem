/*
 * PWA bootstrap: registers the service worker, tells it which user is signed
 * in (so offline page snapshots stay per-user), and drives the offline banner.
 *
 * The worker is served from the site root so its scope covers `/`.
 */
(function () {
    'use strict';

    var currentScript = document.currentScript;
    var banner = document.getElementById('offline-banner');
    var bannerText = banner && banner.querySelector('[data-offline-text]');
    var bannerAction = banner && banner.querySelector('[data-offline-action]');
    var onlineTimer = null;

    function userId() {
        var meta = document.querySelector('meta[name="user-id"]');
        // `null` means this page has no session context at all (such as the
        // standalone offline fallback); do not clear another session's cache.
        return meta ? meta.getAttribute('content') || '' : null;
    }

    function identify(worker) {
        var id = userId();
        if (id === null) {
            return;
        }
        var target = worker || navigator.serviceWorker.controller;
        if (!target) {
            return;
        }
        target.postMessage({ type: 'SKS_IDENTIFY', userId: id });
    }

    if ('serviceWorker' in navigator) {
        var workerUrl =
            (currentScript && currentScript.dataset.swUrl) || '/sw.js';

        navigator.serviceWorker.addEventListener('controllerchange', function () {
            identify(navigator.serviceWorker.controller);
        });

        window.addEventListener('load', function () {
            navigator.serviceWorker
                .register(workerUrl, { scope: '/' })
                .then(function (registration) {
                    identify(registration.active);
                })
                .catch(function (error) {
                    if (window.console) {
                        window.console.warn(
                            'Service worker blev ikke registreret:',
                            error
                        );
                    }
                });
        });

        navigator.serviceWorker.ready.then(function (registration) {
            identify(registration.active);
        });
    }

    function formatStamp(value) {
        if (!value) {
            return '';
        }
        var date = new Date(value);
        if (isNaN(date.getTime())) {
            return '';
        }
        try {
            return date.toLocaleString('da-DK', {
                day: 'numeric',
                month: 'short',
                hour: '2-digit',
                minute: '2-digit',
            });
        } catch (error) {
            return date.toLocaleString();
        }
    }

    async function cachedStampFor(url) {
        if (!('caches' in window)) {
            return null;
        }
        try {
            var names = await caches.keys();
            for (var i = 0; i < names.length; i += 1) {
                if (names[i].indexOf('sks-pages-') !== 0) {
                    continue;
                }
                var cache = await caches.open(names[i]);
                var response = await cache.match(url);
                if (response) {
                    var stamp = response.headers.get('X-Cached-At');
                    if (stamp) {
                        return stamp;
                    }
                }
            }
        } catch (error) {
            // Cache Storage can be unavailable in private browsing modes.
        }
        return null;
    }

    async function newestCachedStamp() {
        if (!('caches' in window)) {
            return null;
        }
        var newest = null;
        try {
            var names = await caches.keys();
            for (var i = 0; i < names.length; i += 1) {
                if (names[i].indexOf('sks-pages-') !== 0) {
                    continue;
                }
                var cache = await caches.open(names[i]);
                var requests = await cache.keys();
                // The newest entries are at the end of the insertion order.
                var sample = requests.slice(-10);
                for (var j = 0; j < sample.length; j += 1) {
                    var response = await cache.match(sample[j]);
                    var stamp = response && response.headers.get('X-Cached-At');
                    if (stamp && (!newest || stamp > newest)) {
                        newest = stamp;
                    }
                }
            }
        } catch (error) {
            // Ignore; the banner falls back to a generic message.
        }
        return newest;
    }

    async function updateOfflinePageStamp() {
        var element = document.querySelector('[data-offline-last-updated]');
        if (!element) {
            return;
        }
        var stamp = await newestCachedStamp();
        element.textContent = stamp
            ? 'Senest gemte data: ' + formatStamp(stamp)
            : 'Der er endnu ikke gemt data til offline brug.';
    }

    function setBanner(text, action, tone) {
        if (!banner) {
            return;
        }
        if (bannerText) {
            bannerText.textContent = text;
        }
        if (bannerAction) {
            bannerAction.hidden = !action;
            if (action) {
                bannerAction.textContent = action;
            }
        }
        banner.classList.toggle('is-online', tone === 'online');
        banner.hidden = false;
        document.body.classList.add('has-offline-banner');
    }

    async function showOffline() {
        if (!banner) {
            return;
        }
        var stamp = await cachedStampFor(window.location.href.split('#')[0]);
        if (!stamp) {
            stamp = await newestCachedStamp();
        }
        if (stamp) {
            setBanner('Offline – viser data fra ' + formatStamp(stamp), 'Prøv igen', 'offline');
        } else {
            setBanner('Offline – ingen gemte data til denne side', 'Prøv igen', 'offline');
        }
    }

    function showOnline() {
        if (!banner || banner.hidden) {
            return;
        }
        setBanner('Du er online igen', 'Opdater', 'online');
        if (onlineTimer) {
            window.clearTimeout(onlineTimer);
        }
        onlineTimer = window.setTimeout(function () {
            banner.hidden = true;
            document.body.classList.remove('has-offline-banner');
        }, 8000);
    }

    function refreshConnectivity() {
        if (navigator.onLine === false) {
            showOffline();
        }
    }

    if (bannerAction) {
        bannerAction.addEventListener('click', function () {
            window.location.reload();
        });
    }

    window.addEventListener('offline', showOffline);
    window.addEventListener('online', showOnline);
    window.addEventListener('pageshow', refreshConnectivity);

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', refreshConnectivity);
    } else {
        refreshConnectivity();
    }
    updateOfflinePageStamp();
})();
