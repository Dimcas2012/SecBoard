/**
 * Study module — clear buttons and client-side list filters.
 */
(function() {
    function reloadWithoutCompanyParam() {
        var url = new URL(window.location.href);
        if (!url.searchParams.has('company')) {
            return false;
        }
        url.searchParams.delete('company');
        window.location.href = url.toString();
        return true;
    }

    function filterLearningHub() {
        var input = document.getElementById('learningHubSearch');
        if (!input) {
            return;
        }
        var term = (input.value || '').toLowerCase().trim();
        var materialsTab = document.getElementById('materials');
        var filterMaterials = materialsTab && materialsTab.classList.contains('show');

        if (filterMaterials) {
            document.querySelectorAll('.learning-hub-page .material-card').forEach(function(card) {
                var title = (card.querySelector('.material-title') || {}).textContent || '';
                var desc = (card.querySelector('.material-description') || {}).textContent || '';
                var show = !term || title.toLowerCase().indexOf(term) !== -1 || desc.toLowerCase().indexOf(term) !== -1;
                card.style.display = show ? '' : 'none';
            });
        } else {
            document.querySelectorAll('.learning-hub-page .test-card').forEach(function(card) {
                var title = (card.querySelector('.test-title') || {}).textContent || '';
                var desc = (card.querySelector('.test-description') || {}).textContent || '';
                var show = !term || title.toLowerCase().indexOf(term) !== -1 || desc.toLowerCase().indexOf(term) !== -1;
                card.style.display = show ? '' : 'none';
            });
        }
    }

    function filterQuizList() {
        var input = document.getElementById('quizListSearch');
        if (!input) {
            return;
        }
        var term = (input.value || '').toLowerCase().trim();
        document.querySelectorAll('.quiz-list-page .quiz-list-col').forEach(function(col) {
            var title = (col.querySelector('.card-title') || {}).textContent || '';
            var text = (col.querySelector('.card-text') || {}).textContent || '';
            var show = !term || title.toLowerCase().indexOf(term) !== -1 || text.toLowerCase().indexOf(term) !== -1;
            col.style.display = show ? '' : 'none';
        });
    }

    document.addEventListener('DOMContentLoaded', function() {
        var clearQuizResults = document.getElementById('clearQuizResultsFilters');
        if (clearQuizResults) {
            clearQuizResults.addEventListener('click', function(e) {
                e.preventDefault();
                var userSearch = document.getElementById('userSearch');
                if (userSearch) {
                    userSearch.value = '';
                    userSearch.dispatchEvent(new Event('input'));
                }
                var quizTabsSearch = document.getElementById('quizTabsSearch');
                if (quizTabsSearch) {
                    quizTabsSearch.value = '';
                    quizTabsSearch.dispatchEvent(new Event('input'));
                }
                var companyFilter = document.getElementById('companyFilter');
                if (companyFilter && companyFilter.value) {
                    if (!reloadWithoutCompanyParam()) {
                        companyFilter.value = '';
                        companyFilter.dispatchEvent(new Event('change'));
                    }
                }
            });
        }

        ['clearPageManagerFilters', 'clearQuizManagerFilters'].forEach(function(btnId) {
            var btn = document.getElementById(btnId);
            if (!btn) {
                return;
            }
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                var companyFilter = document.getElementById('companyFilter');
                if (companyFilter && companyFilter.value) {
                    companyFilter.value = '';
                    companyFilter.dispatchEvent(new Event('change'));
                } else {
                    reloadWithoutCompanyParam();
                }
            });
        });

        var hubSearch = document.getElementById('learningHubSearch');
        if (hubSearch) {
            var hubTimer;
            hubSearch.addEventListener('input', function() {
                clearTimeout(hubTimer);
                hubTimer = setTimeout(filterLearningHub, 200);
            });
            document.querySelectorAll('#learningTabs button[data-bs-toggle="tab"]').forEach(function(tabBtn) {
                tabBtn.addEventListener('shown.bs.tab', filterLearningHub);
            });
        }

        var clearHub = document.getElementById('clearLearningHubFilters');
        if (clearHub) {
            clearHub.addEventListener('click', function(e) {
                e.preventDefault();
                var inp = document.getElementById('learningHubSearch');
                if (inp) {
                    inp.value = '';
                    filterLearningHub();
                }
            });
        }

        var listSearch = document.getElementById('quizListSearch');
        if (listSearch) {
            var listTimer;
            listSearch.addEventListener('input', function() {
                clearTimeout(listTimer);
                listTimer = setTimeout(filterQuizList, 200);
            });
        }

        var clearList = document.getElementById('clearQuizListFilters');
        if (clearList) {
            clearList.addEventListener('click', function(e) {
                e.preventDefault();
                var inp = document.getElementById('quizListSearch');
                if (inp) {
                    inp.value = '';
                    filterQuizList();
                }
            });
        }
    });
})();
