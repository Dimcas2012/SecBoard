/**
 * Per-page selector for GDPR list pagination (GET ?per_page=&page=1).
 */
(function () {
    function changeGdprTablePageSize(size) {
        var urlParams = new URLSearchParams(window.location.search);
        urlParams.set('per_page', size);
        urlParams.set('page', '1');
        window.location.search = urlParams.toString();
    }

    document.addEventListener('change', function (e) {
        var el = e.target;
        if (!el || !el.matches || !el.matches('[data-gdpr-page-size-select]')) {
            return;
        }
        changeGdprTablePageSize(el.value);
    });

    window.changeGdprTablePageSize = changeGdprTablePageSize;
})();
