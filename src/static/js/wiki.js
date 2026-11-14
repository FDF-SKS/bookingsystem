(function () {
    'use strict';

    var modal = document.getElementById('wikiReferenceModal');
    var searchInput = document.getElementById('wiki-reference-search');
    var results = document.getElementById('wiki-reference-results');
    if (!modal || !searchInput || !results) {
        return;
    }

    var lookupUrl = modal.dataset.lookupUrl;
    var textarea = document.querySelector('textarea[name="content"]');
    var debounceTimer = null;
    var lastQuery = null;
    var refocusEditor = false;

    function editorInstance() {
        if (!textarea || !window.DjangoTipTap || typeof window.DjangoTipTap.get !== 'function') {
            return null;
        }
        try {
            // The bundle keys editors by the textarea's id, not the element.
            return window.DjangoTipTap.get(textarea.id);
        } catch (error) {
            return null;
        }
    }

    function insertReference(title, url) {
        var anchor = '<a href="' + url + '">' + escapeHtml(title) + '</a> ';
        var editor = editorInstance();
        if (editor) {
            editor.chain().focus().insertContent(anchor).run();
            refocusEditor = true;
        } else if (textarea) {
            textarea.value = (textarea.value || '') + anchor;
            textarea.dispatchEvent(new Event('input', { bubbles: true }));
        }
        bootstrap.Modal.getOrCreateInstance(modal).hide();
    }

    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function renderResults(data) {
        results.textContent = '';

        if (!data.results || data.results.length === 0) {
            var empty = document.createElement('div');
            empty.className = 'text-secondary small py-3';
            empty.textContent = 'Ingen sider matcher søgningen.';
            results.appendChild(empty);
            return;
        }

        data.results.forEach(function (item) {
            var button = document.createElement('button');
            button.type = 'button';
            button.className = 'list-group-item list-group-item-action border-0 px-0 wiki-reference-result';

            var title = document.createElement('div');
            title.className = 'fw-semibold';
            title.textContent = item.title;
            button.appendChild(title);

            if (item.path) {
                var path = document.createElement('div');
                path.className = 'small text-secondary';
                path.textContent = item.path;
                button.appendChild(path);
            }

            if (item.snippet) {
                var snippet = document.createElement('div');
                snippet.className = 'small text-secondary mt-1';
                snippet.textContent = item.snippet;
                button.appendChild(snippet);
            }

            button.addEventListener('click', function () {
                insertReference(item.title, item.url);
            });
            results.appendChild(button);
        });
    }

    function runSearch(query) {
        fetch(lookupUrl + '?q=' + encodeURIComponent(query), {
            headers: { 'Accept': 'application/json' }
        })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error('Lookup failed');
                }
                return response.json();
            })
            .then(renderResults)
            .catch(function () {
                results.textContent = '';
                var error = document.createElement('div');
                error.className = 'text-danger small py-3';
                error.textContent = 'Kunne ikke hente sider. Prøv igen.';
                results.appendChild(error);
            });
    }

    searchInput.addEventListener('input', function () {
        var value = searchInput.value;
        window.clearTimeout(debounceTimer);
        debounceTimer = window.setTimeout(function () {
            if (value === lastQuery) {
                return;
            }
            lastQuery = value;
            runSearch(value);
        }, 200);
    });

    modal.addEventListener('shown.bs.modal', function () {
        searchInput.focus();
        searchInput.select();
        if (lastQuery === null) {
            lastQuery = '';
            runSearch('');
        }
    });

    modal.addEventListener('hidden.bs.modal', function () {
        if (!refocusEditor) {
            return;
        }
        refocusEditor = false;
        var editor = editorInstance();
        if (editor) {
            editor.commands.focus();
        }
    });
})();
