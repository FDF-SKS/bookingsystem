/*
 * Push notification settings for the PWA.
 *
 * The service worker is registered globally by pwa.js. This file owns the
 * subscribe/unsubscribe flow on the settings page and talks to the JSON
 * endpoints in notifications/views.py.
 */
(function () {
    'use strict';

    var root = document.getElementById('notification-settings');
    if (!root) {
        return;
    }

    var pushConfigured = root.dataset.pushConfigured === '1';
    var vapidPublicKey = root.dataset.vapidPublicKey || '';
    var toggleButton = root.querySelector('[data-push-toggle]');
    var toggleLabel = root.querySelector('[data-push-toggle-label]');
    var testButton = root.querySelector('[data-push-test]');
    var statusEl = root.querySelector('[data-push-status]');
    var hintEl = root.querySelector('[data-push-hint]');
    var iosHint = root.querySelector('[data-ios-hint]');
    var installButton = root.querySelector('[data-install-app]');

    function csrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

    function postJson(url, body) {
        return fetch(url, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken(),
            },
            body: JSON.stringify(body || {}),
        }).then(function (response) {
            return response.json().catch(function () {
                return { ok: response.ok };
            }).then(function (data) {
                if (!response.ok || data.ok === false) {
                    throw new Error(data.error || 'Serveren afviste forespørgslen.');
                }
                return data;
            });
        });
    }

    function setStatus(text, tone) {
        if (!statusEl) {
            return;
        }
        statusEl.textContent = text;
        statusEl.className = 'mt-3 mb-1 small ' + (tone || 'text-muted');
    }

    function showHint(text) {
        if (!hintEl) {
            return;
        }
        hintEl.textContent = text;
        hintEl.classList.remove('d-none');
    }

    function setBusy(busy) {
        if (toggleButton) {
            toggleButton.disabled = busy;
        }
        if (testButton) {
            testButton.disabled = busy;
        }
    }

    function urlBase64ToUint8Array(base64String) {
        var padding = '='.repeat((4 - (base64String.length % 4)) % 4);
        var base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
        var rawData = window.atob(base64);
        var outputArray = new Uint8Array(rawData.length);
        for (var i = 0; i < rawData.length; i += 1) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        return outputArray;
    }

    function isIos() {
        return (
            /iPad|iPhone|iPod/.test(window.navigator.userAgent) ||
            (window.navigator.platform === 'MacIntel' && window.navigator.maxTouchPoints > 1)
        );
    }

    function isStandalone() {
        return (
            window.navigator.standalone === true ||
            (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches)
        );
    }

    function unsupportedReason() {
        if (!('serviceWorker' in navigator)) {
            return 'Denne browser understøtter ikke service workers.';
        }
        if (!('PushManager' in window) || !('Notification' in window)) {
            return 'Denne browser understøtter ikke push-notifikationer. Prøv Safari (iPhone) eller Chrome (Android).';
        }
        if (isIos() && !isStandalone()) {
            return 'Føj appen til hjemmeskærmen for at slå notifikationer til på iPhone/iPad.';
        }
        return '';
    }

    function readyRegistration() {
        return new Promise(function (resolve, reject) {
            var timer = window.setTimeout(function () {
                reject(new Error('Service workeren blev ikke aktiveret.'));
            }, 5000);
            navigator.serviceWorker.ready.then(
                function (registration) {
                    window.clearTimeout(timer);
                    resolve(registration);
                },
                function (error) {
                    window.clearTimeout(timer);
                    reject(error);
                }
            );
        });
    }

    function currentSubscription() {
        return readyRegistration().then(function (registration) {
            return registration.pushManager.getSubscription();
        });
    }

    function updateUi(subscription) {
        var subscribed = Boolean(subscription);
        if (toggleLabel) {
            toggleLabel.textContent = subscribed
                ? 'Slå notifikationer fra'
                : 'Slå notifikationer til';
        }
        if (toggleButton) {
            toggleButton.classList.toggle('btn-primary', !subscribed);
            toggleButton.classList.toggle('btn-outline-danger', subscribed);
        }
        if (testButton) {
            testButton.disabled = !subscribed;
        }
        if (subscribed) {
            setStatus('Notifikationer er slået til på denne enhed.', 'text-success');
        } else if (Notification.permission === 'denied') {
            setStatus(
                'Notifikationer er blokeret. Tillad dem i browserens indstillinger for dette websted.',
                'text-warning'
            );
        } else {
            setStatus('Notifikationer er ikke slået til på denne enhed.', 'text-muted');
        }
    }

    function refresh() {
        if (!pushConfigured) {
            return;
        }
        var reason = unsupportedReason();
        if (reason) {
            if (isIos() && iosHint) {
                iosHint.classList.remove('d-none');
            }
            setStatus(reason, 'text-warning');
            if (toggleButton) {
                toggleButton.disabled = true;
            }
            if (testButton) {
                testButton.disabled = true;
            }
            return;
        }
        currentSubscription()
            .then(updateUi)
            .catch(function (error) {
                setStatus('Kunne ikke læse notifikationsstatus: ' + error.message, 'text-danger');
            });
    }

    function subscribe() {
        return Notification.requestPermission()
            .then(function (permission) {
                if (permission !== 'granted') {
                    throw new Error('Du skal tillade notifikationer i browseren.');
                }
                return readyRegistration();
            })
            .then(function (registration) {
                return registration.pushManager.subscribe({
                    userVisibleOnly: true,
                    applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
                });
            })
            .then(function (subscription) {
                var payload = subscription.toJSON();
                return postJson(root.dataset.subscribeUrl, {
                    endpoint: payload.endpoint,
                    keys: payload.keys,
                }).then(function () {
                    return subscription;
                });
            });
    }

    function unsubscribe(subscription) {
        return postJson(root.dataset.unsubscribeUrl, {
            endpoint: subscription.endpoint,
        }).then(function () {
            return subscription.unsubscribe();
        });
    }

    if (toggleButton && pushConfigured) {
        toggleButton.addEventListener('click', function () {
            setBusy(true);
            setStatus('Arbejder…');
            currentSubscription()
                .then(function (subscription) {
                    if (subscription) {
                        return unsubscribe(subscription).then(function () {
                            setStatus('Notifikationer er slået fra på denne enhed.', 'text-muted');
                        });
                    }
                    return subscribe().then(function () {
                        setStatus('Notifikationer er slået til på denne enhed.', 'text-success');
                    });
                })
                .catch(function (error) {
                    setStatus(error.message, 'text-danger');
                })
                .then(function () {
                    setBusy(false);
                    return currentSubscription().then(updateUi);
                });
        });
    }

    if (testButton && pushConfigured) {
        testButton.addEventListener('click', function () {
            setBusy(true);
            postJson(root.dataset.testUrl, {})
                .then(function () {
                    setStatus('Testnotifikation sendt. Tjek din telefon.', 'text-success');
                })
                .catch(function (error) {
                    setStatus(error.message, 'text-danger');
                })
                .then(function () {
                    setBusy(false);
                });
        });
    }

    if (isIos() && !isStandalone() && iosHint) {
        showHint(
            'Tip: Åbn appen fra hjemmeskærmen, når du har føjet den til, for at slå notifikationer til.'
        );
    }

    // Android/Chrome install prompt, when the browser supports it.
    var installPrompt = null;
    window.addEventListener('beforeinstallprompt', function (event) {
        event.preventDefault();
        installPrompt = event;
        if (installButton) {
            installButton.classList.remove('d-none');
        }
    });
    if (installButton) {
        installButton.addEventListener('click', function () {
            if (!installPrompt) {
                return;
            }
            installPrompt.prompt();
            if (installPrompt.userChoice) {
                installPrompt.userChoice.then(hideInstallButton, hideInstallButton);
            } else {
                hideInstallButton();
            }
        });
    }
    function hideInstallButton() {
        installPrompt = null;
        if (installButton) {
            installButton.classList.add('d-none');
        }
    }

    // Confirmation for destructive forms (e.g. rotating the calendar token).
    document.addEventListener('submit', function (event) {
        var form = event.target.closest('form[data-confirm]');
        if (!form) {
            return;
        }
        if (!window.confirm(form.getAttribute('data-confirm'))) {
            event.preventDefault();
        }
    });

    refresh();
})();
