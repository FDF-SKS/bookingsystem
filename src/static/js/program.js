/*
 * Rammeprogram calendar interaction.
 *
 * Days are columns and hours are rows. The server renders every block with its
 * geometry, so this file only handles:
 *
 *  - click-and-drag on a day column to open the "new block" modal
 *  - clicking a block to edit it (or view it, when the user cannot edit)
 *  - filling the shared modals from the JSON payload rendered by the view
 *
 * All handlers are attached here rather than as inline attributes because the
 * site runs under a nonce-based Content-Security-Policy.
 */
(function () {
    'use strict';

    var page = document.querySelector('[data-program-page]');
    if (!page) {
        return;
    }

    var dataElement = document.getElementById('program-block-data');
    var blocks = [];
    try {
        blocks = JSON.parse((dataElement && dataElement.textContent) || '[]');
    } catch (error) {
        blocks = [];
    }
    var blocksById = {};
    blocks.forEach(function (block) {
        blocksById[String(block.id)] = block;
    });

    var form = document.getElementById('programBlockForm');
    var modalElement = document.getElementById('programBlockModal');
    var modalLabel = document.getElementById('programBlockModalLabel');
    var deleteForm = document.getElementById('programBlockDeleteForm');
    var deleteButton = document.getElementById('programBlockDeleteButton');
    var viewModalElement = document.getElementById('programBlockViewModal');
    var currentViewBlock = null;

    if (!form || !modalElement || !window.bootstrap) {
        return;
    }

    var createUrl = page.getAttribute('data-create-url') || '';
    var pageScope = page.getAttribute('data-scope') || 'base';
    var pageTeamId = page.getAttribute('data-team-id') || '';
    var canCreate = page.getAttribute('data-can-create') === '1';
    var emptyDoc = { type: 'doc', content: [{ type: 'paragraph' }] };

    function getModal(element) {
        return window.bootstrap.Modal.getOrCreateInstance(element);
    }

    function field(name) {
        return form.elements.namedItem(name);
    }

    function setField(name, value) {
        var element = field(name);
        if (element) {
            element.value = value == null ? '' : value;
        }
    }

    function setResponsible(ids) {
        var select = field('responsible');
        if (!select) {
            return;
        }
        var wanted = {};
        (ids || []).forEach(function (id) {
            wanted[String(id)] = true;
        });
        Array.prototype.forEach.call(select.options, function (option) {
            option.selected = Boolean(wanted[option.value]);
        });
    }

    function setEditorContent(doc) {
        var textarea = field('content');
        if (!textarea) {
            return;
        }
        var content = doc && doc.type ? doc : emptyDoc;
        var api = window.DjangoTipTap;
        var editor = api && api.get ? api.get(textarea) : null;
        if (editor && editor.commands && editor.commands.setContent) {
            editor.commands.setContent(content, { emitUpdate: true });
        } else {
            textarea.value = JSON.stringify({ doc: content, html: '' });
        }
    }

    function setDeleteTarget(url) {
        if (deleteForm) {
            deleteForm.setAttribute('action', url || '');
        }
        if (deleteButton) {
            deleteButton.hidden = !url;
        }
    }

    function openCreate(day, startTime, endTime) {
        form.setAttribute('action', createUrl);
        if (modalLabel) {
            modalLabel.textContent = 'Nyt programpunkt';
        }
        setField('title', '');
        setField('category', 'fixed');
        setField('day', day);
        setField('start_time', startTime);
        setField('end_time', endTime);
        setField('team', pageTeamId);
        setField('scope', pageScope);
        setResponsible([]);
        setEditorContent(null);
        setDeleteTarget('');
        getModal(modalElement).show();

        var title = field('title');
        if (title) {
            window.setTimeout(function () {
                title.focus();
            }, 250);
        }
    }

    function openEdit(block) {
        form.setAttribute('action', block.updateUrl);
        if (modalLabel) {
            modalLabel.textContent = 'Ret programpunkt';
        }
        setField('title', block.title);
        setField('category', block.category);
        setField('day', block.day);
        setField('start_time', block.startTime);
        setField('end_time', block.endTime);
        setField('team', block.teamId || '');
        setField('scope', pageScope);
        setResponsible(block.responsibleIds);
        setEditorContent(block.contentDoc);
        setDeleteTarget(block.deleteUrl);
        getModal(modalElement).show();
    }

    function formatDay(value) {
        if (!value) {
            return '';
        }
        var parts = value.split('-').map(Number);
        if (parts.length < 3) {
            return value;
        }
        var date = new Date(parts[0], parts[1] - 1, parts[2]);
        return date.toLocaleDateString('da-DK', {
            weekday: 'long',
            day: 'numeric',
            month: 'long'
        });
    }

    function openView(block) {
        currentViewBlock = block;
        var title = document.getElementById('programBlockViewTitle');
        var meta = viewModalElement.querySelector('[data-program-view-meta]');
        var category = viewModalElement.querySelector('[data-program-view-category]');
        var origin = viewModalElement.querySelector('[data-program-view-origin]');
        var content = viewModalElement.querySelector('[data-program-view-content]');
        var responsible = viewModalElement.querySelector('[data-program-view-responsible]');
        var editButton = viewModalElement.querySelector('[data-program-edit-from-view]');

        if (title) {
            title.textContent = block.title;
        }
        if (meta) {
            meta.textContent = formatDay(block.day) + ' · ' + block.startTime + '–' + block.endTime;
        }
        if (category) {
            category.className = 'badge program-block--' + block.category;
            category.textContent = block.categoryLabel;
        }
        if (origin) {
            origin.textContent = block.teamName ? block.teamName + ' – teamprogram' : 'Fælles rammeprogram';
        }
        if (content) {
            if (block.contentHtml) {
                content.innerHTML = block.contentHtml;
            } else {
                content.innerHTML = '<p class="text-muted fst-italic mb-0">Ingen beskrivelse endnu.</p>';
            }
        }
        if (responsible) {
            responsible.textContent = block.responsibleNames.length
                ? block.responsibleNames.join(', ')
                : 'Ingen ansvarlige valgt';
        }
        if (editButton) {
            editButton.hidden = !block.canEdit;
        }
        getModal(viewModalElement).show();
    }

    // Blocks: delegated clicks so server-rendered buttons need no handlers.
    document.addEventListener('click', function (event) {
        var target = event.target.closest('[data-program-block]');
        if (!target) {
            return;
        }
        var block = blocksById[target.getAttribute('data-program-block')];
        if (!block) {
            return;
        }
        if (block.canEdit) {
            openEdit(block);
        } else {
            openView(block);
        }
    });

    var newButton = document.querySelector('[data-program-new]');
    if (newButton) {
        newButton.addEventListener('click', function () {
            var firstBody = document.querySelector('[data-program-day]');
            var firstDay = firstBody ? firstBody.getAttribute('data-program-day') : '';
            openCreate(firstDay, '09:00', '10:00');
        });
    }

    var editFromView = viewModalElement && viewModalElement.querySelector('[data-program-edit-from-view]');
    if (editFromView) {
        editFromView.addEventListener('click', function () {
            if (!currentViewBlock) {
                return;
            }
            getModal(viewModalElement).hide();
            openEdit(currentViewBlock);
        });
    }

    if (deleteForm) {
        deleteForm.addEventListener('submit', function (event) {
            if (!deleteForm.getAttribute('action')) {
                event.preventDefault();
                return;
            }
            if (!window.confirm('Slet dette programpunkt? Det kan ikke fortrydes.')) {
                event.preventDefault();
            }
        });
    }

    // Calendar drag-to-create.
    document.querySelectorAll('[data-program-calendar]').forEach(function (calendar) {
        if (calendar.getAttribute('data-can-create') !== '1') {
            return;
        }
        var startHour = parseInt(calendar.getAttribute('data-start-hour'), 10);
        var endHour = parseInt(calendar.getAttribute('data-end-hour'), 10);
        if (isNaN(startHour) || isNaN(endHour) || endHour <= startHour) {
            return;
        }
        var totalMinutes = (endHour - startHour) * 60;

        function snap(minutes) {
            var snapped = Math.round(minutes / 15) * 15;
            // A time input cannot represent 24:00, so the last slot ends 23:45.
            var latestEnd = endHour >= 24 ? 23 * 60 + 45 : endHour * 60;
            return Math.max(startHour * 60, Math.min(latestEnd, snapped));
        }

        function minutesFromOffset(offset, height) {
            if (height <= 0) {
                return startHour * 60;
            }
            return snap(startHour * 60 + (offset / height) * totalMinutes);
        }

        function toTime(minutes) {
            var hours = Math.floor(minutes / 60);
            var mins = minutes % 60;
            return String(hours).padStart(2, '0') + ':' + String(mins).padStart(2, '0');
        }

        function drawSelection(drag, first, second) {
            var from = Math.min(first, second);
            var to = Math.max(first, second);
            var bodyHeight = drag.height;
            var top = ((from - startHour * 60) / totalMinutes) * bodyHeight;
            var height = Math.max(3, ((to - from) / totalMinutes) * bodyHeight);
            drag.selection.style.top = top + 'px';
            drag.selection.style.height = height + 'px';
            drag.selection.hidden = false;
        }

        calendar.querySelectorAll('[data-program-day]').forEach(function (body) {
            var day = body.getAttribute('data-program-day');
            var drag = null;
            var touch = null;

            body.addEventListener('pointerdown', function (event) {
                if (
                    event.button !== 0 ||
                    event.isPrimary === false ||
                    event.target.closest('[data-program-block]')
                ) {
                    return;
                }
                var selection = body.querySelector('[data-program-selection]');
                if (!selection) {
                    return;
                }
                var rect = body.getBoundingClientRect();
                var start = minutesFromOffset(event.clientY - rect.top, rect.height);

                if (event.pointerType === 'mouse') {
                    drag = {
                        height: rect.height,
                        rectTop: rect.top,
                        start: start,
                        selection: selection
                    };
                    drawSelection(drag, start, start);
                    if (body.setPointerCapture) {
                        try {
                            body.setPointerCapture(event.pointerId);
                        } catch (error) {
                            // Pointer capture is a nicety; dragging still works.
                        }
                    }
                    event.preventDefault();
                    return;
                }

                // Touch/pen: do not start a selection on pointerdown. Waiting
                // for movement lets the user swipe to scroll the calendar
                // without accidentally opening the create modal.
                touch = {
                    id: event.pointerId,
                    x: event.clientX,
                    y: event.clientY,
                    start: start,
                    rectTop: rect.top,
                    height: rect.height,
                    moved: false,
                    startedAt: Date.now()
                };
            });

            body.addEventListener('pointermove', function (event) {
                if (drag) {
                    var current = minutesFromOffset(event.clientY - drag.rectTop, drag.height);
                    drawSelection(drag, drag.start, current);
                    event.preventDefault();
                    return;
                }
                if (!touch || event.pointerId !== touch.id) {
                    return;
                }
                if (
                    Math.abs(event.clientX - touch.x) > 10 ||
                    Math.abs(event.clientY - touch.y) > 10
                ) {
                    touch.moved = true;
                }
            });

            function finish(event) {
                if (drag) {
                    var current = minutesFromOffset(event.clientY - drag.rectTop, drag.height);
                    var from = Math.min(drag.start, current);
                    var to = Math.max(drag.start, current);
                    if (to - from < 15) {
                        var latestEnd = endHour >= 24 ? 23 * 60 + 45 : endHour * 60;
                        from = Math.min(drag.start, latestEnd - 60);
                        to = from + 60;
                    }
                    drag.selection.hidden = true;
                    drag = null;
                    openCreate(day, toTime(from), toTime(to));
                    event.preventDefault();
                    return;
                }

                if (!touch || event.pointerId !== touch.id) {
                    return;
                }
                var state = touch;
                touch = null;
                // A swipe (or a long press) must not create a block.
                if (state.moved || Date.now() - state.startedAt > 700) {
                    return;
                }

                var latestEnd = endHour >= 24 ? 23 * 60 + 45 : endHour * 60;
                var start = Math.max(startHour * 60, Math.min(state.start, latestEnd - 15));
                var end = Math.min(start + 60, latestEnd);
                openCreate(day, toTime(start), toTime(end));
            }

            body.addEventListener('pointerup', finish);
            body.addEventListener('pointercancel', function (event) {
                if (touch && event.pointerId === touch.id) {
                    touch = null;
                }
                if (drag) {
                    drag.selection.hidden = true;
                    drag = null;
                }
            });
        });
    });

    // Re-open the modal after a failed POST: the server rendered the bound form.
    if (page.getAttribute('data-modal-open') === '1') {
        var editingId = page.getAttribute('data-editing-block');
        if (editingId && blocksById[editingId]) {
            setDeleteTarget(blocksById[editingId].deleteUrl);
        }
        getModal(modalElement).show();
    }
})();
