/*
 * Registers the service worker that powers push notifications and the offline
 * fallback. The worker is served from the site root so its scope covers `/`.
 */
(function () {
    'use strict';

    if (!('serviceWorker' in navigator)) {
        return;
    }

    var script = document.currentScript;
    var workerUrl = (script && script.dataset.swUrl) || '/sw.js';

    window.addEventListener('load', function () {
        navigator.serviceWorker
            .register(workerUrl, { scope: '/' })
            .catch(function (error) {
                // A failed registration must never break the page.
                if (window.console) {
                    window.console.warn('Service worker blev ikke registreret:', error);
                }
            });
    });
})();
