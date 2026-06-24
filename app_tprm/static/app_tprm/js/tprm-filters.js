/**
 * TPRM module — auto-submit GET filter forms and client-side list search.
 */
(function() {
    function filterCardCols(selector, inputId) {
        var input = document.getElementById(inputId);
        if (!input) {
            return;
        }
        var term = (input.value || '').toLowerCase().trim();
        document.querySelectorAll(selector).forEach(function(col) {
            var card = col.querySelector('.card');
            if (!card) {
                col.style.display = '';
                return;
            }
            var text = card.textContent.toLowerCase();
            col.style.display = !term || text.indexOf(term) !== -1 ? '' : 'none';
        });
    }

    document.addEventListener('DOMContentLoaded', function() {
        document.querySelectorAll('.tprm-page .access-request-filters form[method="get"]').forEach(function(form) {
            form.querySelectorAll('select').forEach(function(el) {
                el.addEventListener('change', function() {
                    form.submit();
                });
            });
            form.querySelectorAll('input[type="checkbox"]').forEach(function(el) {
                el.addEventListener('change', function() {
                    form.submit();
                });
            });
            var searchInput = form.querySelector('input[type="text"], input[type="search"], input[type="email"]');
            if (searchInput && searchInput.name) {
                var timer;
                searchInput.addEventListener('input', function() {
                    clearTimeout(timer);
                    timer = setTimeout(function() {
                        form.submit();
                    }, 400);
                });
            }
        });

        var bindings = [
            { input: 'questionnaireListSearch', selector: '.questionnaire-list-col', clear: 'clearQuestionnaireListFilters' },
            { input: 'templateListSearch', selector: '.template-list-col', clear: 'clearTemplateListFilters' }
        ];

        bindings.forEach(function(cfg) {
            var inp = document.getElementById(cfg.input);
            if (!inp) {
                return;
            }
            var timer;
            inp.addEventListener('input', function() {
                clearTimeout(timer);
                timer = setTimeout(function() {
                    filterCardCols(cfg.selector, cfg.input);
                }, 200);
            });
            var clearBtn = document.getElementById(cfg.clear);
            if (clearBtn) {
                clearBtn.addEventListener('click', function(e) {
                    if (cfg.selector) {
                        e.preventDefault();
                        inp.value = '';
                        filterCardCols(cfg.selector, cfg.input);
                    }
                });
            }
        });
    });
})();
