/**
 * Auto-submit GET filters on compliance list pages.
 * Collapse: secboard-filter-collapse.js (.access-request-filters).
 */
(function() {
    function initComplianceFilterForms() {
        document.querySelectorAll('.compliance-filters-card form[method="get"]').forEach(function(form) {
            form.querySelectorAll('select').forEach(function(el) {
                el.addEventListener('change', function() { form.submit(); });
            });
            const searchInput = form.querySelector('input[name="search"]');
            if (searchInput) {
                let timer;
                searchInput.addEventListener('input', function() {
                    clearTimeout(timer);
                    timer = setTimeout(function() { form.submit(); }, 400);
                });
            }
        });
    }

    document.addEventListener('DOMContentLoaded', initComplianceFilterForms);
})();
