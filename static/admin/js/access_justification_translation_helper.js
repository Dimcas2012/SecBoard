/**
 * Auto-Translation helper for Access Justification Template translations.
 * Mirrors Asset Type behavior: when country is selected, auto-fill empty
 * localized fields from base English fields.
 */
(function() {
    'use strict';

    function getTranslateUrl() {
        if (typeof window.TPRM_LEVEL_TRANSLATE_URL !== 'undefined' && window.TPRM_LEVEL_TRANSLATE_URL) {
            return window.TPRM_LEVEL_TRANSLATE_URL;
        }
        const pathParts = window.location.pathname.split('/').filter(Boolean);
        const langPrefix = (pathParts.length > 0 && pathParts[0].length === 2) ? pathParts[0] : 'en';
        return '/' + langPrefix + '/app_compliance/api/translate/';
    }

    function initWhenReady() {
        if (typeof django !== 'undefined' && typeof django.jQuery !== 'undefined') {
            initHelper(django.jQuery);
        } else {
            setTimeout(initWhenReady, 100);
        }
    }

    function callTranslateApi(text, countryId, csrfToken) {
        if (!text || !String(text).trim()) return Promise.resolve('');
        return fetch(getTranslateUrl(), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
            },
            body: JSON.stringify({
                text: String(text).trim(),
                country_id: countryId,
            }),
        })
            .then((response) => response.json())
            .then((data) => (data.success && data.translated_text ? data.translated_text : ''))
            .catch(() => '');
    }

    function showTooltip($element, message, type) {
        django.jQuery('.auto-translate-tooltip').remove();
        let backgroundColor = '#dc3545';
        if (type === 'success') backgroundColor = '#28a745';
        if (type === 'warning') backgroundColor = '#ffc107';

        const $tooltip = django.jQuery('<div class="auto-translate-tooltip">')
            .text(message)
            .css({
                position: 'absolute',
                padding: '6px 12px',
                borderRadius: '4px',
                backgroundColor: backgroundColor,
                color: type === 'warning' ? '#000' : 'white',
                fontSize: '12px',
                fontWeight: 'bold',
                zIndex: 10000,
                boxShadow: '0 2px 6px rgba(0,0,0,0.2)',
                whiteSpace: 'nowrap',
            });

        const offset = $element.offset();
        $tooltip.css({
            top: offset.top - 35,
            left: offset.left,
        });

        django.jQuery('body').append($tooltip);
        setTimeout(function() {
            $tooltip.fadeOut(200, function() {
                django.jQuery(this).remove();
            });
        }, 2500);
    }

    function initHelper($) {
        function bindRows() {
            $('.tabular.inline-related tbody tr').each(function() {
                const $row = $(this);
                if ($row.hasClass('empty-form')) return;

                const $country = $row.find('select[name$="-country"]');
                const $nameLocal = $row.find('input[name$="-name_local"]');
                const $contentLocal = $row.find('textarea[name$="-content"]');

                if (!$country.length || (!$nameLocal.length && !$contentLocal.length)) return;
                if ($country.data('ajt-initialized')) return;
                $country.data('ajt-initialized', true);

                if ($row.find('.translation-loading').length === 0) {
                    const $loading = $('<span class="translation-loading" style="display:none; margin-left:8px; color:#666; font-size:12px;">')
                        .text('Translating...');
                    ($nameLocal.length ? $nameLocal : $contentLocal).after($loading);
                }

                $country.on('change', async function() {
                    const countryId = $(this).val();
                    if (!countryId) return;

                    const $form = $row.closest('form');
                    const baseName = ($form.find('input[name="name"]').first().val() || '').trim();
                    const baseContent = ($form.find('textarea[name="content"]').first().val() || '').trim();

                    const tasks = [];
                    if ($nameLocal.length && !$nameLocal.val() && baseName) {
                        tasks.push({ source: baseName, $target: $nameLocal });
                    }
                    if ($contentLocal.length && !$contentLocal.val() && baseContent) {
                        tasks.push({ source: baseContent, $target: $contentLocal });
                    }

                    if (!tasks.length) {
                        showTooltip($country, 'No source text or fields are filled', 'warning');
                        return;
                    }

                    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
                    const $loadingIndicator = $row.find('.translation-loading');
                    let $targets = $();
                    tasks.forEach((t) => { $targets = $targets.add(t.$target); });
                    $targets.prop('disabled', true).css('opacity', '0.6');
                    $loadingIndicator.show();

                    try {
                        const results = await Promise.all(
                            tasks.map(async (t) => ({ t, translated: await callTranslateApi(t.source, countryId, csrfToken) }))
                        );
                        let translatedCount = 0;
                        results.forEach(({ t, translated }) => {
                            if (translated && !t.$target.val()) {
                                t.$target.val(translated).trigger('change');
                                t.$target.css('background-color', '#d4edda');
                                setTimeout(() => t.$target.css('background-color', ''), 2000);
                                translatedCount += 1;
                            }
                        });
                        if (translatedCount > 0) {
                            showTooltip($country, `Translated ${translatedCount} field(s)`, 'success');
                        } else {
                            showTooltip($country, 'Translation returned empty result', 'warning');
                        }
                    } catch (e) {
                        showTooltip($country, 'Translation error', 'error');
                    } finally {
                        $loadingIndicator.hide();
                        $targets.prop('disabled', false).css('opacity', '1');
                    }
                });
            });
        }

        $(document).ready(bindRows);
        $(document).on('formset:added', bindRows);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initWhenReady);
    } else {
        initWhenReady();
    }
})();
