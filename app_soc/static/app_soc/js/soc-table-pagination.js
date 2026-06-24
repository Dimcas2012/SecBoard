/**
 * Per-page selector for SOC server-side table pagination (GET ?per_page=&page=1).
 */
(function () {
    function changeSocTablePageSize(size) {
        var urlParams = new URLSearchParams(window.location.search);
        urlParams.set('per_page', size);
        urlParams.set('page', '1');
        window.location.search = urlParams.toString();
    }

    document.addEventListener('change', function (e) {
        var el = e.target;
        if (!el || !el.matches || !el.matches('[data-soc-page-size-select]')) {
            return;
        }
        changeSocTablePageSize(el.value);
    });

    window.changeSocTablePageSize = changeSocTablePageSize;
    window.changePerPage = changeSocTablePageSize;
})();
