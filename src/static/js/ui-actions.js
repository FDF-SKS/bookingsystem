/*
 * Small delegated UI behaviours.
 *
 * The site runs under a nonce-based Content-Security-Policy without
 * 'unsafe-inline', so inline event-handler attributes (onclick="...") are
 * blocked. Templates express the same intent with data-* attributes and this
 * file attaches the behaviour once, using event delegation so dynamically
 * inserted elements work too.
 *
 * Supported attributes:
 *   data-href           navigate to the URL when the element is clicked
 *   data-copy-text      copy the value to the clipboard; briefly swap the label
 *   data-copy-label     label shown after a successful copy (default "Kopieret")
 *   data-print          call window.print()
 *   data-autosubmit     submit the surrounding form when the control changes
 */
(function () {
    'use strict';

    function isInteractive(target) {
        return Boolean(target.closest('a, button, input, select, textarea, label'));
    }

    document.addEventListener('click', function (event) {
        var row = event.target.closest('[data-href]');
        // Ignore clicks on a normal control inside the row so links keep working.
        if (!row || isInteractive(event.target)) {
            return;
        }
        window.location.href = row.getAttribute('data-href');
    });

    document.addEventListener('click', function (event) {
        var button = event.target.closest('[data-print]');
        if (!button) {
            return;
        }
        window.print();
    });

    document.addEventListener('click', function (event) {
        var button = event.target.closest('[data-copy-text]');
        if (!button || !navigator.clipboard) {
            return;
        }
        var original = button.textContent;
        var feedback = button.getAttribute('data-copy-label') || 'Kopieret';
        navigator.clipboard.writeText(button.getAttribute('data-copy-text')).then(function () {
            button.textContent = feedback;
            window.setTimeout(function () {
                button.textContent = original;
            }, 1500);
        });
    });

    document.addEventListener('change', function (event) {
        var control = event.target.closest('[data-autosubmit]');
        if (!control || !control.form) {
            return;
        }
        control.form.submit();
    });
})();
