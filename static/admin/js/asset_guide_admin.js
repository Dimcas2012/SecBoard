/**
 * Asset Guide admin: "Translate from base" for Guide translations (TinyMCE content).
 */
(function() {
    'use strict';

    function stripHtml(html) {
        if (!html) return '';
        var d = document.createElement('div');
        d.innerHTML = html;
        return (d.textContent || d.innerText || '').trim();
    }

    function getBaseContent() {
        var sel = document.querySelector('#id_base_content');
        if (sel && typeof tinymce !== 'undefined') {
            var ed = tinymce.get('id_base_content');
            if (ed) return ed.getContent();
        }
        return (sel && sel.value) ? sel.value : '';
    }

    function setTranslationContent(fieldId, html) {
        if (!html) return;
        if (typeof tinymce !== 'undefined') {
            var ed = tinymce.get(fieldId);
            if (ed) {
                ed.setContent(html);
                return;
            }
        }
        var el = document.getElementById(fieldId);
        if (el) el.value = html;
    }

    function initTranslateButtons() {
        if (typeof django === 'undefined' || !django.jQuery) return;
        var $ = django.jQuery;
        var translateUrl = window.ASSET_GUIDE_TRANSLATE_URL;
        if (!translateUrl) return;

        $('.inline-related').each(function() {
            var $row = $(this);
            if ($row.hasClass('empty-form')) return;
            var $countrySelect = $row.find('select[id$="-country"]');
            var $contentCell = $row.find('[id$="-content"]').closest('.form-row, .module').first();
            if (!$countrySelect.length || !$contentCell.length) return;
            var contentId = $row.find('[id$="-content"]').attr('id');
            if (!contentId) return;
            if ($row.find('.asset-guide-translate-btn').length) return;

            var $btn = $('<button type="button" class="asset-guide-translate-btn button">')
                .text('Translate from base').css('marginBottom', '8px');
            $contentCell.prepend($btn);

            $btn.on('click', function() {
                var countryId = $countrySelect.val();
                if (!countryId) {
                    alert('Select a country first.');
                    return;
                }
                var base = getBaseContent();
                var text = stripHtml(base);
                if (!text) {
                    alert('Fill in Base content first.');
                    return;
                }
                var $loading = $('<span class="translation-loading">').html(' <i class="fas fa-spinner fa-spin"></i> Translating...').hide();
                $btn.after($loading);
                $btn.prop('disabled', true);
                $loading.show();

                var csrf = document.querySelector('[name=csrfmiddlewaretoken]');
                var token = csrf ? csrf.value : '';

                fetch(translateUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': token
                    },
                    body: JSON.stringify({ text: text, country_id: parseInt(countryId, 10) })
                })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    if (data.success && data.translated_text) {
                        var t = (data.translated_text || '').trim();
                        if (t && t.indexOf('<') === -1) t = '<p>' + t.replace(/\n/g, '</p><p>') + '</p>';
                        setTranslationContent(contentId, t || '');
                    } else {
                        alert(data.error || 'Translation failed.');
                    }
                })
                .catch(function() { alert('Translation request failed.'); })
                .finally(function() {
                    $loading.remove();
                    $btn.prop('disabled', false);
                });
            });
        });
    }

    function run() {
        if (typeof django !== 'undefined' && django.jQuery) {
            django.jQuery(document).ready(initTranslateButtons);
            django.jQuery(document).on('formset:added', initTranslateButtons);
        } else {
            setTimeout(run, 100);
        }
    }
    run();
})();
