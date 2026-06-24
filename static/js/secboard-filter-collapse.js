/**
 * Collapsible .access-request-filters panels (same behaviour as user-access-request).
 * Supports Bootstrap 5 (getOrCreateInstance) and Bootstrap 4 (jQuery .collapse).
 */
(function() {
    function createCollapseController(collapseEl) {
        if (window.bootstrap && window.bootstrap.Collapse &&
            typeof window.bootstrap.Collapse.getOrCreateInstance === 'function') {
            var inst = window.bootstrap.Collapse.getOrCreateInstance(collapseEl, { toggle: false });
            return {
                toggle: function() { inst.toggle(); }
            };
        }
        if (typeof jQuery !== 'undefined' && jQuery.fn && jQuery.fn.collapse) {
            var $el = jQuery(collapseEl);
            if (!$el.data('bs.collapse')) {
                $el.collapse({ toggle: false });
            }
            return {
                toggle: function() { $el.collapse('toggle'); }
            };
        }
        return {
            toggle: function() {
                collapseEl.classList.toggle('show');
            }
        };
    }

    function initAccessRequestFiltersCollapse() {
        document.querySelectorAll('.access-request-filters').forEach(function(card) {
            var collapseEl = card.querySelector('.collapse');
            var toggleBtn = card.querySelector('[aria-controls]');
            if (!collapseEl || !toggleBtn) {
                return;
            }
            var controlsId = toggleBtn.getAttribute('aria-controls');
            if (controlsId && collapseEl.id && controlsId !== collapseEl.id) {
                return;
            }
            var icon = toggleBtn.querySelector('i') ||
                (collapseEl.id ? document.getElementById(collapseEl.id + 'ToggleIcon') : null);
            var collapse = createCollapseController(collapseEl);

            function syncToggleState(expanded) {
                toggleBtn.setAttribute('aria-expanded', expanded ? 'true' : 'false');
                if (icon) {
                    icon.classList.toggle('bi-chevron-down', !expanded);
                    icon.classList.toggle('bi-chevron-up', expanded);
                }
            }

            collapseEl.addEventListener('show.bs.collapse', function() { syncToggleState(true); });
            collapseEl.addEventListener('hide.bs.collapse', function() { syncToggleState(false); });
            collapseEl.addEventListener('shown.bs.collapse', function() { syncToggleState(true); });
            collapseEl.addEventListener('hidden.bs.collapse', function() { syncToggleState(false); });
            toggleBtn.addEventListener('click', function(e) {
                e.preventDefault();
                collapse.toggle();
            });
            syncToggleState(collapseEl.classList.contains('show'));
        });
    }

    document.addEventListener('DOMContentLoaded', initAccessRequestFiltersCollapse);
})();
