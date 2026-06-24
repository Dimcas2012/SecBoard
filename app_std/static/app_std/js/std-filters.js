/**
 * Standards module — clear buttons for access-request-filters panels.
 */
(function() {
    function filterPcidssDocuments() {
        var input = document.getElementById('pciDocSearch');
        if (!input) {
            return;
        }
        var term = (input.value || '').toLowerCase().trim();
        document.querySelectorAll('#documentsContainer .pci-doc-col').forEach(function(col) {
            var card = col.querySelector('.document-card');
            if (!card) {
                col.style.display = '';
                return;
            }
            var titleEl = card.querySelector('.card-title');
            var textEl = card.querySelector('.card-text');
            var title = titleEl ? titleEl.textContent.toLowerCase() : '';
            var text = textEl ? textEl.textContent.toLowerCase() : '';
            var show = !term || title.indexOf(term) !== -1 || text.indexOf(term) !== -1;
            col.style.display = show ? '' : 'none';
        });
    }

    document.addEventListener('DOMContentLoaded', function() {
        var clearIso = document.getElementById('clearIso27002Filters');
        if (clearIso) {
            clearIso.addEventListener('click', function(e) {
                e.preventDefault();
                var btn = document.querySelector('.iso27002-page .filter-theme-btn[data-value="all"]');
                if (btn) {
                    btn.click();
                }
            });
        }

        var clearPci = document.getElementById('clearPcidssFilters');
        if (clearPci) {
            clearPci.addEventListener('click', function(e) {
                e.preventDefault();
                var btn = document.querySelector('.pcidss-page .filter-req-btn[data-value="all"]');
                if (btn) {
                    btn.click();
                }
            });
        }

        var docSearch = document.getElementById('pciDocSearch');
        if (docSearch) {
            var docTimer;
            docSearch.addEventListener('input', function() {
                clearTimeout(docTimer);
                docTimer = setTimeout(filterPcidssDocuments, 200);
            });
        }

        var clearPciDoc = document.getElementById('clearPcidssDocFilters');
        if (clearPciDoc) {
            clearPciDoc.addEventListener('click', function(e) {
                e.preventDefault();
                var inp = document.getElementById('pciDocSearch');
                if (inp) {
                    inp.value = '';
                    filterPcidssDocuments();
                }
            });
        }
    });
})();
