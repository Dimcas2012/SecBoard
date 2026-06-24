/**
 * Risk Assessment filter panel: clear header button + auto-apply hooks.
 * Expects page to define applyFilters(), clearAllFilters(), and jQuery filter field ids.
 */
(function() {
    function riskFilterFieldHasValue() {
        var ids = [
            'filterCompany', 'filterCriticality', 'filterAssetGroup', 'filterAssetType',
            'filterVulnerabilityStatus', 'filterRiskLevel', 'filterTreatmentStatus', 'filterSearch'
        ];
        return ids.some(function(id) {
            var el = document.getElementById(id);
            return el && el.value;
        });
    }

    function syncRiskFiltersExpanded() {
        if (!riskFilterFieldHasValue()) {
            return;
        }
        var collapseEl = document.getElementById('riskFiltersCollapse');
        var toggleBtn = document.getElementById('toggleRiskFilters');
        var icon = document.getElementById('riskFiltersToggleIcon');
        if (!collapseEl || !window.bootstrap) {
            return;
        }
        if (typeof bootstrap.Collapse.getOrCreateInstance === 'function') {
            bootstrap.Collapse.getOrCreateInstance(collapseEl, { toggle: false }).show();
        } else if (typeof jQuery !== 'undefined' && jQuery.fn.collapse) {
            jQuery(collapseEl).collapse('show');
        } else {
            collapseEl.classList.add('show');
        }
        if (toggleBtn) {
            toggleBtn.setAttribute('aria-expanded', 'true');
        }
        if (icon) {
            icon.classList.remove('bi-chevron-down');
            icon.classList.add('bi-chevron-up');
        }
    }

    function bindRiskFilterAutoApply() {
        var selectIds = [
            'filterCompany', 'filterCriticality', 'filterAssetGroup', 'filterAssetType',
            'filterVulnerabilityStatus', 'filterRiskLevel', 'filterTreatmentStatus'
        ];
        selectIds.forEach(function(id) {
            var el = document.getElementById(id);
            if (!el) {
                return;
            }
            el.addEventListener('change', function() {
                if (typeof jQuery !== 'undefined') {
                    jQuery('.quick-filter').removeClass('active');
                }
                if (typeof window.applyFilters === 'function') {
                    window.applyFilters();
                }
            });
        });
    }

    function bindRiskFilterClear() {
        var clearBtn = document.getElementById('clearRiskFilters');
        if (!clearBtn) {
            return;
        }
        clearBtn.addEventListener('click', function(e) {
            e.preventDefault();
            if (typeof window.clearAllFilters === 'function') {
                window.clearAllFilters();
            }
        });
    }

    document.addEventListener('DOMContentLoaded', function() {
        bindRiskFilterClear();
        bindRiskFilterAutoApply();
        setTimeout(syncRiskFiltersExpanded, 0);
    });
})();
