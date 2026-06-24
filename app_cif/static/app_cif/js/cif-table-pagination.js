/**
 * Per-page selector for CIF list pagination (GET ?per_page=&page=1).
 */
(function () {
    function changeCifTablePageSize(size) {
        var urlParams = new URLSearchParams(window.location.search);
        urlParams.set('per_page', size);
        urlParams.set('page', '1');
        window.location.search = urlParams.toString();
    }

    document.addEventListener('change', function (e) {
        var el = e.target;
        if (!el || !el.matches || !el.matches('[data-cif-page-size-select]')) {
            return;
        }
        changeCifTablePageSize(el.value);
    });

    window.changeCifTablePageSize = changeCifTablePageSize;
})();
