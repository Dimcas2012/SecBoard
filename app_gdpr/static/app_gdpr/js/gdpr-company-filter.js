/**
 * GDPR dashboard/report — multi-company filter with auto-submit.
 */
(function() {
    function initCompanyBadgeRemove() {
        document.querySelectorAll('.company-badge-remove').forEach(function(badge) {
            if (badge.dataset.gdprBadgeBound) {
                return;
            }
            badge.dataset.gdprBadgeBound = '1';
            badge.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                var companyId = this.getAttribute('data-company-id');
                var currentUrl = new URL(window.location.href);
                var params = currentUrl.searchParams;
                var selectedCompanies = params.getAll('company');
                if (selectedCompanies.length === 0) {
                    selectedCompanies = Array.from(document.querySelectorAll('.company-badge-remove'))
                        .map(function(b) { return b.getAttribute('data-company-id'); });
                }
                params.delete('company');
                selectedCompanies.filter(function(id) { return id !== String(companyId); })
                    .forEach(function(id) { params.append('company', id); });
                window.location.href = currentUrl.toString();
            });
        });
    }

    function initCompanyMultiselect(companySelect) {
        if (!companySelect || companySelect.dataset.gdprMultiselectInit) {
            return;
        }
        companySelect.dataset.gdprMultiselectInit = '1';
        var form = companySelect.closest('form');
        if (!form) {
            return;
        }
        var placeholder = form.getAttribute('data-placeholder') || '';
        var allLabel = form.getAttribute('data-all-label') || '';
        var submitTimer;
        var originalSelect = companySelect;
        var selectedValues = Array.from(originalSelect.selectedOptions).map(function(opt) { return opt.value; });

        var wrapper = document.createElement('div');
        wrapper.className = 'company-multiselect-wrapper';

        var displayBox = document.createElement('div');
        displayBox.className = 'form-control form-control-sm gdpr-company-display';

        var dropdown = document.createElement('div');
        dropdown.className = 'gdpr-company-dropdown';

        function scheduleSubmit() {
            clearTimeout(submitTimer);
            submitTimer = setTimeout(function() {
                if (typeof form.requestSubmit === 'function') {
                    form.requestSubmit();
                } else {
                    form.submit();
                }
            }, 400);
        }

        function updateOriginalSelect() {
            var checkedBoxes = dropdown.querySelectorAll('input[type="checkbox"]:checked');
            Array.from(originalSelect.options).forEach(function(option) {
                option.selected = false;
            });
            checkedBoxes.forEach(function(checkbox) {
                var option = originalSelect.querySelector('option[value="' + checkbox.value + '"]');
                if (option) {
                    option.selected = true;
                }
            });
            scheduleSubmit();
        }

        function updateDisplay() {
            var checkedBoxes = dropdown.querySelectorAll('input[type="checkbox"]:checked');
            displayBox.innerHTML = '';
            if (checkedBoxes.length === 0) {
                var ph = document.createElement('span');
                ph.className = 'text-muted small';
                ph.textContent = placeholder;
                displayBox.appendChild(ph);
            } else if (checkedBoxes.length === originalSelect.options.length) {
                var badge = document.createElement('span');
                badge.className = 'badge bg-secondary';
                badge.innerHTML = '<i class="fas fa-globe"></i> ' + allLabel;
                displayBox.appendChild(badge);
            } else {
                checkedBoxes.forEach(function(checkbox) {
                    var badge = document.createElement('span');
                    badge.className = 'badge bg-info d-inline-flex align-items-center gap-1';
                    var label = dropdown.querySelector('label[for="' + checkbox.id + '"]');
                    badge.innerHTML = '<i class="fas fa-building"></i> ' + (label ? label.textContent : '');
                    var removeBtn = document.createElement('span');
                    removeBtn.innerHTML = '&times;';
                    removeBtn.className = 'gdpr-company-remove-chip';
                    removeBtn.addEventListener('click', function(e) {
                        e.stopPropagation();
                        checkbox.checked = false;
                        updateDisplay();
                        updateOriginalSelect();
                    });
                    badge.appendChild(removeBtn);
                    displayBox.appendChild(badge);
                });
            }
        }

        Array.from(originalSelect.options).forEach(function(option) {
            var item = document.createElement('div');
            item.className = 'gdpr-company-dropdown-item';
            var checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = option.value;
            checkbox.checked = selectedValues.indexOf(option.value) !== -1;
            checkbox.id = 'gdpr_company_' + option.value;
            var label = document.createElement('label');
            label.htmlFor = checkbox.id;
            label.textContent = option.textContent;
            item.appendChild(checkbox);
            item.appendChild(label);
            item.addEventListener('click', function(e) {
                e.stopPropagation();
                checkbox.checked = !checkbox.checked;
                updateDisplay();
                updateOriginalSelect();
            });
            dropdown.appendChild(item);
        });

        displayBox.addEventListener('click', function(e) {
            e.stopPropagation();
            dropdown.classList.toggle('show');
        });
        document.addEventListener('click', function() {
            dropdown.classList.remove('show');
        });

        originalSelect.classList.add('visually-hidden');
        wrapper.appendChild(displayBox);
        wrapper.appendChild(dropdown);
        originalSelect.parentNode.insertBefore(wrapper, originalSelect);
        wrapper.appendChild(originalSelect);
        updateDisplay();
    }

    document.addEventListener('DOMContentLoaded', function() {
        initCompanyBadgeRemove();
        var companySelect = document.getElementById('companySelect');
        initCompanyMultiselect(companySelect);
    });
})();
