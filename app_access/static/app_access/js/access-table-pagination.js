/**
 * Page-size selector for server-side access table pagination (GET ?page_size=&page=1).
 */
(function () {
    function changeAccessTablePageSize(size) {
        var urlParams = new URLSearchParams(window.location.search);
        urlParams.set('page_size', size);
        urlParams.set('page', '1');
        window.location.search = urlParams.toString();
    }

    document.addEventListener('change', function (e) {
        var el = e.target;
        if (!el || !el.matches || !el.matches('[data-access-page-size-select]')) {
            return;
        }
        changeAccessTablePageSize(el.value);
    });

    window.changeAccessTablePageSize = changeAccessTablePageSize;
    // Legacy aliases used by some templates
    window.changePageSize = changeAccessTablePageSize;
    window.changeAccessRecordsPageSize = changeAccessTablePageSize;
})();
