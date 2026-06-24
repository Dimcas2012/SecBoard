/**
 * Initialize vendor add/edit form behavior (owners pool, TPRM field descriptions).
 * @param {HTMLElement} root - Container element (e.g. .vendor-form-root) that holds the form.
 * @param {Object} cfg - Configuration with ownersUrl and localized message strings.
 */
function initVendorFormModal(root, cfg) {
    if (!root || !cfg || !cfg.ownersUrl) {
        return;
    }

    var ownersUrl = cfg.ownersUrl;
    var msgSelectCompany = cfg.msgSelectCompany || 'Select a company to load owners.';
    var msgLoading = cfg.msgLoading || 'Loading…';
    var msgCouldNotLoad = cfg.msgCouldNotLoad || 'Could not load owners.';
    var msgNoneSelected = cfg.msgNoneSelected || 'None — add owners from the list above.';
    var ariaRemove = cfg.ariaRemove || 'Remove';

    var companyField = root.querySelector('[name="company"]');
    var poolWrap = root.querySelector('#vendor-owner-pool-wrap');
    var poolEl = root.querySelector('#vendor-owner-pool');
    var poolPh = root.querySelector('#vendor-owner-pool-placeholder');
    var selectedEl = root.querySelector('#vendor-selected-owners');
    var filterInput = root.querySelector('#vendor-owner-filter');
    var hiddenOwners = root.querySelector('#vendor-owners-json');
    var initialScript = root.querySelector('#vendor-owners-initial');
    var selectedById = {};
    var lastPool = [];

    function parseInitial() {
        if (!initialScript || !initialScript.textContent) {
            return [];
        }
        try {
            var data = JSON.parse(initialScript.textContent);
            return Array.isArray(data) ? data : [];
        } catch (e) {
            return [];
        }
    }

    function syncHidden() {
        var ids = Object.keys(selectedById).map(function (k) {
            return parseInt(k, 10);
        }).filter(function (n) {
            return !isNaN(n);
        });
        if (hiddenOwners) {
            hiddenOwners.value = JSON.stringify(ids);
        }
    }

    function renderSelected() {
        if (!selectedEl) {
            return;
        }
        selectedEl.innerHTML = '';
        var keys = Object.keys(selectedById);
        if (keys.length === 0) {
            selectedEl.innerHTML = '<span class="text-muted">' + msgNoneSelected + '</span>';
            syncHidden();
            return;
        }
        keys.sort(function (a, b) {
            return selectedById[a].name.localeCompare(selectedById[b].name);
        });
        keys.forEach(function (id) {
            var o = selectedById[id];
            var row = document.createElement('div');
            row.className = 'd-flex justify-content-between align-items-start border-bottom py-1';
            var info = document.createElement('div');
            info.innerHTML = '<strong></strong><div class="text-muted"></div><div class="text-muted small"></div>';
            info.querySelector('strong').textContent = o.name;
            var sub = (o.department || o.position)
                ? ((o.department || '') + (o.department && o.position ? ' | ' : '') + (o.position || ''))
                : '';
            info.querySelectorAll('div.text-muted')[0].textContent = sub;
            info.querySelectorAll('div.text-muted')[1].textContent = o.email || o.phone || '';
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'btn btn-sm btn-outline-danger';
            btn.setAttribute('aria-label', ariaRemove);
            btn.innerHTML = '<i class="fas fa-times"></i>';
            btn.addEventListener('click', function () {
                delete selectedById[id];
                renderSelected();
                renderPool(lastPool);
            });
            row.appendChild(info);
            row.appendChild(btn);
            selectedEl.appendChild(row);
        });
        syncHidden();
    }

    function renderPool(owners) {
        lastPool = owners || [];
        if (!poolEl) {
            return;
        }
        poolEl.innerHTML = '';
        var q = (filterInput && filterInput.value) ? filterInput.value.trim().toLowerCase() : '';
        var filtered = lastPool.filter(function (o) {
            if (!q) {
                return true;
            }
            var blob = [o.name, o.department, o.position, o.email, o.phone].join(' ').toLowerCase();
            return blob.indexOf(q) !== -1;
        });
        filtered.forEach(function (o) {
            var li = document.createElement('li');
            li.className = 'list-group-item list-group-item-action py-2';
            if (selectedById[o.id]) {
                li.classList.add('bg-light');
            }
            li.innerHTML = '<div class="d-flex justify-content-between align-items-center"><div><strong></strong><div class="text-muted small"></div></div><div class="form-check"><input type="checkbox" class="form-check-input"></div></div>';
            li.querySelector('strong').textContent = o.name;
            var sm = o.department || o.position
                ? ((o.department || '') + (o.department && o.position ? ' | ' : '') + (o.position || ''))
                : '';
            li.querySelector('.text-muted.small').textContent = sm + (o.email ? ' · ' + o.email : '');
            var cb = li.querySelector('input[type="checkbox"]');
            cb.checked = !!selectedById[o.id];
            li.addEventListener('click', function (ev) {
                if (ev.target === cb) {
                    return;
                }
                cb.checked = !cb.checked;
                toggleOwner(o, cb.checked);
            });
            cb.addEventListener('change', function () {
                toggleOwner(o, cb.checked);
            });
            poolEl.appendChild(li);
        });
    }

    function toggleOwner(o, on) {
        if (on) {
            selectedById[o.id] = {
                id: o.id,
                name: o.name || '',
                department: o.department || '',
                position: o.position || '',
                email: o.email || '',
                phone: o.phone || ''
            };
        } else {
            delete selectedById[o.id];
        }
        renderSelected();
        renderPool(lastPool);
    }

    function getCompanySelection() {
        if (!companyField) {
            return { id: '', name: '' };
        }
        var id = '';
        var name = '';
        if (companyField.tagName === 'SELECT') {
            id = companyField.value || '';
            if (companyField.selectedIndex >= 0) {
                var selectedOption = companyField.options[companyField.selectedIndex];
                if (selectedOption) {
                    name = (selectedOption.textContent || '').trim();
                }
            }
        } else {
            id = (companyField.value || '').trim();
            name = id;
        }
        return { id: id, name: name };
    }

    function loadOwnersForCompany(companyId, companyName) {
        if (!poolWrap || !poolPh) {
            return;
        }
        if (!companyId && !companyName) {
            poolWrap.classList.add('d-none');
            poolPh.classList.remove('d-none');
            poolPh.textContent = msgSelectCompany;
            lastPool = [];
            selectedById = {};
            renderSelected();
            return;
        }
        poolPh.textContent = msgLoading;
        var q = [];
        if (companyId) {
            q.push('company_id=' + encodeURIComponent(companyId));
        } else if (companyName) {
            q.push('company_name=' + encodeURIComponent(companyName));
        }
        fetch(ownersUrl + '?' + q.join('&'), { credentials: 'same-origin' })
            .then(function (r) {
                if (!r.ok) {
                    throw new Error('bad');
                }
                return r.json();
            })
            .then(function (data) {
                if (!Array.isArray(data)) {
                    throw new Error('bad');
                }
                data = data.slice();
                var seen = {};
                data.forEach(function (o) {
                    seen[o.id] = true;
                });
                Object.keys(selectedById).forEach(function (kid) {
                    var idNum = parseInt(kid, 10);
                    if (isNaN(idNum) || seen[idNum]) {
                        return;
                    }
                    var s = selectedById[kid];
                    data.push({
                        id: idNum,
                        name: (s && s.name) ? s.name : '',
                        department: (s && s.department) ? s.department : '',
                        position: (s && s.position) ? s.position : '',
                        email: (s && s.email) ? s.email : '',
                        phone: (s && s.phone) ? s.phone : ''
                    });
                    seen[idNum] = true;
                });
                poolPh.classList.add('d-none');
                poolWrap.classList.remove('d-none');
                poolPh.textContent = '';
                renderPool(data);
                renderSelected();
            })
            .catch(function () {
                poolPh.classList.remove('d-none');
                poolWrap.classList.add('d-none');
                poolPh.textContent = msgCouldNotLoad;
            });
    }

    parseInitial().forEach(function (o) {
        if (o && o.id) {
            selectedById[o.id] = o;
        }
    });
    renderSelected();

    if (companyField) {
        companyField.addEventListener('change', function () {
            selectedById = {};
            renderSelected();
            var s = getCompanySelection();
            loadOwnersForCompany(s.id, s.name);
        });
        var initialSelection = getCompanySelection();
        if (initialSelection.id || initialSelection.name) {
            loadOwnersForCompany(initialSelection.id, initialSelection.name);
        } else {
            if (poolPh) {
                poolPh.classList.remove('d-none');
            }
            if (poolWrap) {
                poolWrap.classList.add('d-none');
            }
        }
    }

    if (filterInput) {
        filterInput.addEventListener('input', function () {
            renderPool(lastPool);
        });
    }

    var form = root.querySelector('form[enctype="multipart/form-data"]');
    if (form) {
        form.addEventListener('submit', function () {
            syncHidden();
        });
    }

    var scriptEl = root.querySelector('#tprm-descriptions-data');
    if (scriptEl && scriptEl.textContent) {
        var descriptions;
        try {
            descriptions = JSON.parse(scriptEl.textContent);
        } catch (e) {
            descriptions = null;
        }
        if (descriptions) {
            function updateDesc(select, fieldName) {
                var descMap = descriptions[fieldName];
                if (!descMap) {
                    return;
                }
                var descEl = root.querySelector('.tprm-field-desc[data-field="' + fieldName + '"]');
                if (!descEl) {
                    return;
                }
                var val = select.value;
                descEl.textContent = (val && descMap[val]) ? descMap[val] : '';
            }
            var fieldNames = [
                'risk_level', 'status', 'criticality_level', 'sanctions_verification_status',
                'data_access_level', 'data_access_rights'
            ];
            fieldNames.forEach(function (fieldName) {
                var select = root.querySelector('select[name="' + fieldName + '"]');
                if (!select) {
                    return;
                }
                updateDesc(select, fieldName);
                select.addEventListener('change', function () {
                    updateDesc(select, fieldName);
                });
            });
        }
    }
}

if (typeof window !== 'undefined') {
    window.initVendorFormModal = initVendorFormModal;
}
