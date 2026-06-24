/**
 * Page-size selector for incident list pagination (GET ?page_size=&page=1).
 */
(function () {
    function changeIncidentTablePageSize(size) {
        var urlParams = new URLSearchParams(window.location.search);
        urlParams.set('page_size', size);
        urlParams.set('page', '1');
        window.location.search = urlParams.toString();
    }

    document.addEventListener('change', function (e) {
        var el = e.target;
        if (!el || !el.matches || !el.matches('[data-incident-page-size-select]')) {
            return;
        }
        changeIncidentTablePageSize(el.value);
    });

    window.changeIncidentTablePageSize = changeIncidentTablePageSize;
})();
