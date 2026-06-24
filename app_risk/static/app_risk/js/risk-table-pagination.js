/**
 * Risk table pagination — identical markup/classes to app_access access_table_pagination.html
 * Default: 25 per page; options: 10, 25, 50, 100.
 */
(function () {
    var PAGE_SIZE_OPTIONS = [10, 25, 50, 100];
    var DEFAULT_PAGE_SIZE = 25;

    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function pageRange(current, total) {
        var pages = [];
        var i;
        for (i = 1; i <= total; i++) {
            if (i === current || (i > current - 3 && i < current + 3)) {
                pages.push(i);
            }
        }
        return pages;
    }

    function buildNavHtml(currentPage, totalPages, ariaLabel) {
        if (totalPages <= 1) {
            return '';
        }

        var pagesHtml = pageRange(currentPage, totalPages).map(function (num) {
            if (num === currentPage) {
                return '<li class="page-item active"><span class="page-link">' + num + '</span></li>';
            }
            return '<li class="page-item"><a class="page-link" href="#" data-page="' + num + '">' + num + '</a></li>';
        }).join('');

        var nav = '';
        if (currentPage > 1) {
            nav +=
                '<li class="page-item">' +
                    '<a class="page-link" href="#" data-page="1" aria-label="First">' +
                        '<i class="bi bi-chevron-double-left"></i>' +
                    '</a>' +
                '</li>' +
                '<li class="page-item">' +
                    '<a class="page-link" href="#" data-page="' + (currentPage - 1) + '" aria-label="Previous">' +
                        '<i class="bi bi-chevron-left"></i>' +
                    '</a>' +
                '</li>';
        }
        nav += pagesHtml;
        if (currentPage < totalPages) {
            nav +=
                '<li class="page-item">' +
                    '<a class="page-link" href="#" data-page="' + (currentPage + 1) + '" aria-label="Next">' +
                        '<i class="bi bi-chevron-right"></i>' +
                    '</a>' +
                '</li>' +
                '<li class="page-item">' +
                    '<a class="page-link" href="#" data-page="' + totalPages + '" aria-label="Last">' +
                        '<i class="bi bi-chevron-double-right"></i>' +
                    '</a>' +
                '</li>';
        }

        return (
            '<nav aria-label="' + escapeHtml(ariaLabel || 'Pagination') + '">' +
                '<ul class="pagination pagination-sm mb-0">' + nav + '</ul>' +
            '</nav>'
        );
    }

    function applyAccessPaginationChrome(container) {
        container.className = 'access-table-pagination d-flex flex-wrap justify-content-between align-items-center gap-2 mt-3 px-3 pb-3';
    }

    function renderAccessStylePagination(container, config) {
        var labels = config.labels || {};
        var showingLabel = labels.showing || 'Showing';
        var ofLabel = labels.of || 'of';
        var itemsLabel = labels.items || 'entries';
        var perPageLabel = labels.perPage || 'Per page';
        var ariaLabel = config.ariaLabel || 'Pagination';
        var selectId = config.selectId;
        var total = config.total || 0;
        var startIndex = config.startIndex || 0;
        var endIndex = config.endIndex || 0;
        var pageSize = config.pageSize || DEFAULT_PAGE_SIZE;
        var currentPage = config.currentPage || 1;
        var totalPages = config.totalPages || 1;

        if (total === 0) {
            container.innerHTML = '';
            container.style.display = 'none';
            return;
        }

        applyAccessPaginationChrome(container);
        container.style.display = '';

        var sizeOptionsHtml = PAGE_SIZE_OPTIONS.map(function (size) {
            return '<option value="' + size + '"' + (size === pageSize ? ' selected' : '') + '>' + size + '</option>';
        }).join('');

        var navHtml = buildNavHtml(currentPage, totalPages, ariaLabel);

        container.innerHTML =
            '<div class="pagination-info">' +
                '<small class="text-muted">' +
                    escapeHtml(showingLabel) + ' ' + startIndex + ' - ' + endIndex + ' ' +
                    escapeHtml(ofLabel) + ' ' + total + ' ' + escapeHtml(itemsLabel) +
                '</small>' +
            '</div>' +
            '<div class="d-flex flex-wrap align-items-center gap-3">' +
                '<div class="d-flex align-items-center page-size-selector">' +
                    '<label for="' + escapeHtml(selectId) + '" class="form-label me-2 mb-0 small">' +
                        escapeHtml(perPageLabel) + ':' +
                    '</label>' +
                    '<select class="form-select form-select-sm risk-table-page-size-select" ' +
                        'id="' + escapeHtml(selectId) + '" data-risk-page-size-select ' +
                        'style="width: auto; min-width: 4.5rem;">' +
                        sizeOptionsHtml +
                    '</select>' +
                '</div>' +
                navHtml +
            '</div>';
    }

    function bindPaginationEvents(container, handlers) {
        if (container._riskPaginationBound) {
            return;
        }
        container._riskPaginationBound = true;

        container.addEventListener('click', function (e) {
            var link = e.target.closest('[data-page]');
            if (!link || !container.contains(link)) {
                return;
            }
            e.preventDefault();
            var page = parseInt(link.getAttribute('data-page'), 10) || 1;
            if (handlers.onPageChange) {
                handlers.onPageChange(page);
            }
        });

        container.addEventListener('change', function (e) {
            if (!e.target.matches('[data-risk-page-size-select]')) {
                return;
            }
            var size = parseInt(e.target.value, 10) || DEFAULT_PAGE_SIZE;
            if (PAGE_SIZE_OPTIONS.indexOf(size) === -1) {
                size = DEFAULT_PAGE_SIZE;
            }
            if (handlers.onPageSizeChange) {
                handlers.onPageSizeChange(size);
            }
        });
    }

    window.initRiskDataTablePagination = function (options) {
        var api = options.api;
        var container = document.getElementById(options.containerId);
        if (!api || !container) {
            return null;
        }

        var labels = options.labels || {};
        var ariaLabel = options.paginationAriaLabel || 'Pagination';
        var selectId = options.containerId + 'PageSize';

        function render() {
            var info = api.page.info();
            renderAccessStylePagination(container, {
                labels: labels,
                ariaLabel: ariaLabel,
                selectId: selectId,
                total: info.recordsDisplay,
                startIndex: info.recordsDisplay === 0 ? 0 : info.start + 1,
                endIndex: info.end,
                pageSize: info.length,
                currentPage: info.page + 1,
                totalPages: info.pages
            });
        }

        bindPaginationEvents(container, {
            onPageChange: function (page) {
                api.page(page - 1).draw('page');
            },
            onPageSizeChange: function (size) {
                api.page.len(size).draw();
            }
        });

        api.on('draw', render);
        render();

        return { refresh: render };
    };
})();
