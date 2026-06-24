/**
 * Auto-submit GET filter forms on Gophish list pages.
 */
(function() {
    function initGophishFilterForms() {
        document.querySelectorAll('.gophish-page .access-request-filters form[method="get"]').forEach(function(form) {
            form.querySelectorAll('select').forEach(function(el) {
                el.addEventListener('change', function() { form.submit(); });
            });
            var searchInput = form.querySelector('input[name="search"]');
            if (searchInput) {
                var timer;
                searchInput.addEventListener('input', function() {
                    clearTimeout(timer);
                    timer = setTimeout(function() { form.submit(); }, 400);
                });
            }
        });
    }

    document.addEventListener('DOMContentLoaded', initGophishFilterForms);
})();
