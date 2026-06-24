/**
 * Auto-submit GET filter forms on GDPR list pages.
 */
(function() {
    function initGdprFilterForms() {
        document.querySelectorAll('.gdpr-page .access-request-filters form[method="get"]').forEach(function(form) {
            if (form.classList.contains('gdpr-company-filter-form')) {
                return;
            }
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

    document.addEventListener('DOMContentLoaded', initGdprFilterForms);
})();
