/**
 * Auto-submit GET filter forms on Incident Register.
 */
(function() {
    function initIncidentFilterForms() {
        document.querySelectorAll('.incident-page .access-request-filters form[method="get"]').forEach(function(form) {
            form.querySelectorAll('select').forEach(function(el) {
                el.addEventListener('change', function() { form.submit(); });
            });
            form.querySelectorAll('input[type="date"]').forEach(function(el) {
                el.addEventListener('change', function() { form.submit(); });
            });
        });
    }

    document.addEventListener('DOMContentLoaded', initIncidentFilterForms);
})();
