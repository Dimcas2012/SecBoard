/**
 * Auto-Translation Helper for Django Admin
 * Automatically translates Local Name when Country is selected.
 * For Criticality Level Translations: also translates Confidentiality, Integrity, Availability descriptions.
 * For Asset Group / Asset Type Translations: also translates Description (same as Criticality Level).
 * For Financial Impact Level Translations (app_risk): also translates Description, Criteria, Examples.
 * For Vulnerability Translations (app_risk): also translates Description, Scope, Risk Mitigation Controls;
 *   uses Legacy (vulnerability_uk/en/ru, description_uk/en/ru) as fallback source when name/description empty.
 */

(function() {
    'use strict';

    function getTranslateUrl() {
        if (typeof window.TPRM_LEVEL_TRANSLATE_URL !== 'undefined' && window.TPRM_LEVEL_TRANSLATE_URL) {
            return window.TPRM_LEVEL_TRANSLATE_URL;
        }
        var pathParts = window.location.pathname.split('/').filter(Boolean);
        var langPrefix = (pathParts.length > 0 && pathParts[0].length === 2) ? pathParts[0] : 'en';
        return '/' + langPrefix + '/app_compliance/api/translate/';
    }

    // Wait for django.jQuery to be available
    function initWhenReady() {
        if (typeof django !== 'undefined' && typeof django.jQuery !== 'undefined') {
            console.log('✅ django.jQuery found, initializing translation helper');
            initTranslationHelper(django.jQuery);
        } else {
            console.log('⏳ Waiting for django.jQuery...');
            setTimeout(initWhenReady, 100);
        }
    }

    // Start checking for jQuery
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initWhenReady);
    } else {
        initWhenReady();
    }

    function initTranslationHelper($) {
        console.log('🎯 Translation helper starting...');

        // Wait for document ready
        $(document).ready(function() {
            initAutoTranslation();

            // Re-initialize when new inline forms are added
            $(document).on('formset:added', function(event, $row, formsetName) {
                initAutoTranslation();
            });
        });

        function initAutoTranslation() {
            console.log('🔄 Initializing auto-translation...');

            // Find all inline forms with translations (country + name_local, or Criticality Level with description fields)
            $('.tabular.inline-related tbody tr').each(function() {
                const $row = $(this);

                // Skip Django's empty template row to avoid copying flags to new forms
                if ($row.hasClass('empty-form')) {
                    console.log('🧱 Skipping empty form template row');
                    return;
                }

                const $countrySelect = $row.find('select[name$="-country"]');
                // name_local can be input (CharField) or textarea (TextField, e.g. Vulnerability)
                const $nameLocalInput = $row.find('input[name$="-name_local"]').length
                    ? $row.find('input[name$="-name_local"]')
                    : $row.find('textarea[name$="-name_local"]');
                const $descConfid = $row.find('textarea[name$="-description_confid"]');
                const $descInteg = $row.find('textarea[name$="-description_integ"]');
                const $descAvail = $row.find('textarea[name$="-description_avail"]');
                const isCriticalityLevelRow = $descConfid.length > 0 || $descInteg.length > 0 || $descAvail.length > 0;
                // Asset Group / Asset Type: description field (Django inline name e.g. translations-0-description)
                const $descInline = $row.find('textarea[name*="description"]').filter(function() {
                    var n = $(this).attr('name') || '';
                    return n.indexOf('description_confid') === -1 && n.indexOf('description_integ') === -1 && n.indexOf('description_avail') === -1;
                }).first();
                // Financial Impact Level Translation: criteria and examples (same pattern as description)
                const $criteriaInline = $row.find('textarea[name$="-criteria"]').first();
                const $examplesInline = $row.find('textarea[name$="-examples"]').first();
                const isImpactTranslationRow = $criteriaInline.length > 0 || $examplesInline.length > 0;
                // Threat Translation: description + risks (app_risk)
                const $risksInline = $row.find('textarea[name$="-risks"]').first();
                const isThreatTranslationRow = $risksInline.length > 0;
                // Vulnerability Translation: scope, risk_mitigation_controls (app_risk)
                const $scopeInline = $row.find('textarea[name$="-scope"]').first();
                const $riskMitigationInline = $row.find('textarea[name$="-risk_mitigation_controls"]').first();
                const isVulnerabilityTranslationRow = $scopeInline.length > 0 || $riskMitigationInline.length > 0;

                if ($countrySelect.length === 0) return;
                if ($nameLocalInput.length === 0 && !isCriticalityLevelRow && $descInline.length === 0 && !isImpactTranslationRow && !isThreatTranslationRow && !isVulnerabilityTranslationRow) return;

                // Skip if already initialized
                if ($countrySelect.data('translation-initialized')) {
                    console.log('⏭️ Already initialized, skipping...');
                    return;
                }

                $countrySelect.data('translation-initialized', true);

                const $firstField = $nameLocalInput.length ? $nameLocalInput : ($descConfid.length ? $descConfid : ($descInteg.length ? $descInteg : $descAvail));
                if ($row.find('.translation-loading').length === 0) {
                    const $loadingIndicator = $('<span class="translation-loading" style="display: none; margin-left: 8px; color: #666; font-size: 12px;">')
                        .html('<i class="fas fa-spinner fa-spin"></i> Перекладаємо...');
                    $firstField.after($loadingIndicator);
                }

                $countrySelect.on('change', function() {
                    const countryId = $(this).val();
                    if (countryId) {
                        autoTranslateField($countrySelect, $row, {
                            $nameLocalInput: $nameLocalInput,
                            $descConfid: $descConfid,
                            $descInteg: $descInteg,
                            $descAvail: $descAvail,
                            $descInline: $descInline,
                            $criteriaInline: $criteriaInline,
                            $examplesInline: $examplesInline,
                            $risksInline: $risksInline,
                            $scopeInline: $scopeInline,
                            $riskMitigationInline: $riskMitigationInline,
                            isCriticalityLevelRow: isCriticalityLevelRow,
                            isImpactTranslationRow: isImpactTranslationRow,
                            isThreatTranslationRow: isThreatTranslationRow,
                            isVulnerabilityTranslationRow: isVulnerabilityTranslationRow
                        });
                    }
                });
            });

            console.log('✅ Auto-translation initialization complete');
        }

        function callTranslateApi(text, countryId, csrfToken) {
            if (!text || !String(text).trim()) return Promise.resolve('');
            var translateUrl = getTranslateUrl();
            return fetch(translateUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ text: String(text).trim(), country_id: countryId })
            })
            .then(function(response) { return response.json(); })
            .then(function(data) {
                return (data.success && data.translated_text) ? data.translated_text : '';
            })
            .catch(function() { return ''; });
        }

        function autoTranslateField($countrySelect, $row, opts) {
            var countryId = $countrySelect.val();
            if (!countryId) return;

            // Use the row that contains the country select (in case of dynamic rows)
            var $row = $countrySelect.closest('tr');
            // name_local can be input (CharField) or textarea (TextField, e.g. Vulnerability)
            var $nameLocalInput = $row.find('input[name$="-name_local"]').length
                ? $row.find('input[name$="-name_local"]')
                : $row.find('textarea[name$="-name_local"]');
            // CriticalityLevelTranslationInline: with delete column: 0=delete, 1=country, 2=name_local, 3=confid, 4=integ, 5=avail; without: 0=country, 1=name_local, 2=confid, 3=integ, 4=avail
            var $cells = $row.children('td');
            var descIdx = $cells.length >= 6 ? 3 : 2;
            var $descConfid = $cells.length >= 5 ? $cells.eq(descIdx).find('textarea') : $row.find('textarea[name$="-description_confid"]');
            var $descInteg = $cells.length >= 5 ? $cells.eq(descIdx + 1).find('textarea') : $row.find('textarea[name$="-description_integ"]');
            var $descAvail = $cells.length >= 5 ? $cells.eq(descIdx + 2).find('textarea') : $row.find('textarea[name$="-description_avail"]');
            if ($descConfid.length === 0) $descConfid = $row.find('textarea[name*="description_confid"]').filter(function() { return $(this).attr('name').indexOf('_en') === -1; });
            if ($descInteg.length === 0) $descInteg = $row.find('textarea[name*="description_integ"]').filter(function() { return $(this).attr('name').indexOf('_en') === -1; });
            if ($descAvail.length === 0) $descAvail = $row.find('textarea[name*="description_avail"]').filter(function() { return $(this).attr('name').indexOf('_en') === -1; });
            var isCriticalityLevelRow = $descConfid.length > 0 || $descInteg.length > 0 || $descAvail.length > 0;
            // Asset Group / Asset Type: single Description field (columns: country, name_local, description; or + delete)
            var $descInline = (opts && opts.$descInline && opts.$descInline.length) ? opts.$descInline : $();
            if ($descInline.length === 0 && !isCriticalityLevelRow && $cells.length >= 3) {
                $descInline = $cells.eq($cells.length - 1).find('textarea').first();
            }
            if ($descInline.length === 0 && !isCriticalityLevelRow) {
                $descInline = $row.find('textarea[name*="description"]').filter(function() {
                    var n = $(this).attr('name') || '';
                    return n.indexOf('description_confid') === -1 && n.indexOf('description_integ') === -1 && n.indexOf('description_avail') === -1;
                }).first();
            }
            if ($descInline.length === 0 && !isCriticalityLevelRow) {
                $descInline = $row.find('textarea').filter(function() {
                    var n = $(this).attr('name') || '';
                    return n.indexOf('description_confid') === -1 && n.indexOf('description_integ') === -1 && n.indexOf('description_avail') === -1;
                }).first();
            }
            // Financial Impact Level Translation: criteria and examples
            var $criteriaInline = (opts && opts.$criteriaInline && opts.$criteriaInline.length) ? opts.$criteriaInline : $row.find('textarea[name$="-criteria"]').first();
            var $examplesInline = (opts && opts.$examplesInline && opts.$examplesInline.length) ? opts.$examplesInline : $row.find('textarea[name$="-examples"]').first();
            // Threat Translation: risks
            var $risksInline = (opts && opts.$risksInline && opts.$risksInline.length) ? opts.$risksInline : $row.find('textarea[name$="-risks"]').first();

            var $form = $row.closest('form');
            // Parent name: input (CharField) or textarea (TextField, e.g. Vulnerability)
            var $parentName = $form.find('input[name="name"]').not('.inline-related input');
            if ($parentName.length === 0) $parentName = $form.find('input[id="id_name"]');
            if ($parentName.length === 0) {
                $parentName = $form.find('textarea[name="name"]').not('.inline-related textarea');
            }
            if ($parentName.length === 0) {
                $parentName = $form.find('textarea[id="id_name"]').not('.inline-related textarea');
            }
            if ($parentName.length === 0) {
                $parentName = $form.find('.form-row input[type="text"]').filter(function() {
                    var n = $(this).attr('name'), i = $(this).attr('id');
                    return (n === 'name' || i === 'id_name');
                }).first();
            }
            if ($parentName.length === 0) {
                $parentName = $form.find('.form-row textarea').filter(function() {
                    var n = $(this).attr('name'), i = $(this).attr('id');
                    return (n === 'name' || i === 'id_name') && $(this).closest('.inline-related').length === 0;
                }).first();
            }
            // Legacy (Vulnerability): fallback to vulnerability_en, vulnerability_uk if name empty
            if (($parentName.length === 0 || !$parentName.val() || !$parentName.val().trim()) && $nameLocalInput.length) {
                var $legacyName = $form.find('textarea[name="vulnerability_en"]').not('.inline-related textarea').first();
                if ($legacyName.length === 0 || !$legacyName.val()) $legacyName = $form.find('textarea[name="vulnerability_uk"]').not('.inline-related textarea').first();
                if ($legacyName.length === 0 || !$legacyName.val()) $legacyName = $form.find('textarea[name="vulnerability_ru"]').not('.inline-related textarea').first();
                if ($legacyName.length && $legacyName.val() && $legacyName.val().trim()) $parentName = $legacyName;
            }

            // Parent CIA descriptions (main form, not inline): CriticalityLevel uses id_description_confid/integ/avail; other models may use _en suffix
            var $parentDescConfid = $(document.getElementById('id_description_confid') || null);
            if ($parentDescConfid.length === 0) $parentDescConfid = $(document.getElementById('id_description_confid_en') || document.querySelector('textarea[name="description_confid_en"]'));
            if ($parentDescConfid.closest('.inline-related').length) $parentDescConfid = $();
            if ($parentDescConfid.length === 0) $parentDescConfid = $form.find('textarea[name="description_confid_en"]').not('.inline-related textarea').first();
            if ($parentDescConfid.length === 0) $parentDescConfid = $form.find('textarea[name="description_confid"]').filter(function() { return $(this).attr('name') === 'description_confid'; }).first();
            var $parentDescInteg = $(document.getElementById('id_description_integ') || null);
            if ($parentDescInteg.length === 0) $parentDescInteg = $(document.getElementById('id_description_integ_en') || document.querySelector('textarea[name="description_integ_en"]'));
            if ($parentDescInteg.closest('.inline-related').length) $parentDescInteg = $();
            if ($parentDescInteg.length === 0) $parentDescInteg = $form.find('textarea[name="description_integ_en"]').not('.inline-related textarea').first();
            if ($parentDescInteg.length === 0) $parentDescInteg = $form.find('textarea[name="description_integ"]').filter(function() { return $(this).attr('name') === 'description_integ'; }).first();
            var $parentDescAvail = $(document.getElementById('id_description_avail') || null);
            if ($parentDescAvail.length === 0) $parentDescAvail = $(document.getElementById('id_description_avail_en') || document.querySelector('textarea[name="description_avail_en"]'));
            if ($parentDescAvail.closest('.inline-related').length) $parentDescAvail = $();
            if ($parentDescAvail.length === 0) $parentDescAvail = $form.find('textarea[name="description_avail_en"]').not('.inline-related textarea').first();
            if ($parentDescAvail.length === 0) $parentDescAvail = $form.find('textarea[name="description_avail"]').filter(function() { return $(this).attr('name') === 'description_avail'; }).first();

            // Parent "description" for Asset Group / Asset Type (main form; fieldset may be collapsed)
            var $parentDesc = $(document.getElementById('id_description') || null);
            if ($parentDesc.length === 0 || $parentDesc.closest('.inline-related').length) {
                $parentDesc = $form.find('textarea[name="description"]').filter(function() {
                    return $(this).attr('name') === 'description' && $(this).closest('.inline-related').length === 0;
                }).first();
            }
            if ($parentDesc.length === 0) {
                $parentDesc = $form.find('textarea').filter(function() {
                    var $el = $(this);
                    return $el.attr('name') === 'description' && $el.closest('.inline-related').length === 0 && $el.closest('.empty-form').length === 0;
                }).first();
            }
            // Legacy (Vulnerability): fallback to description_en, description_uk if description empty
            if (($parentDesc.length === 0 || !$parentDesc.val() || !$parentDesc.val().trim()) && $descInline.length) {
                var $legacyDesc = $form.find('textarea[name="description_en"]').not('.inline-related textarea').first();
                if ($legacyDesc.length === 0 || !$legacyDesc.val()) $legacyDesc = $form.find('textarea[name="description_uk"]').not('.inline-related textarea').first();
                if ($legacyDesc.length === 0 || !$legacyDesc.val()) $legacyDesc = $form.find('textarea[name="description_ru"]').not('.inline-related textarea').first();
                if ($legacyDesc.length && $legacyDesc.val() && $legacyDesc.val().trim()) $parentDesc = $legacyDesc;
            }

            // Parent criteria and examples (Financial Impact Level: main form default EN)
            var $parentCriteria = $(document.getElementById('id_criteria') || null);
            if ($parentCriteria.length === 0 || $parentCriteria.closest('.inline-related').length) {
                $parentCriteria = $form.find('textarea[name="criteria"]').not('.inline-related textarea').first();
            }
            var $parentExamples = $(document.getElementById('id_examples') || null);
            if ($parentExamples.length === 0 || $parentExamples.closest('.inline-related').length) {
                $parentExamples = $form.find('textarea[name="examples"]').not('.inline-related textarea').first();
            }
            // Parent risks (Threat: main form default EN)
            var $parentRisks = $(document.getElementById('id_risks') || null);
            if ($parentRisks.length === 0 || $parentRisks.closest('.inline-related').length) {
                $parentRisks = $form.find('textarea[name="risks"]').not('.inline-related textarea').first();
            }

            // Parent scope and risk_mitigation_controls (Vulnerability: main form per-language, use first non-empty)
            var $parentScope = $(document.getElementById('id_scope_en') || null);
            if ($parentScope.length === 0 || $parentScope.closest('.inline-related').length) $parentScope = $form.find('textarea[name="scope_en"]').not('.inline-related textarea').first();
            if ($parentScope.length === 0 || !$parentScope.val()) $parentScope = $form.find('textarea[name="scope_uk"]').not('.inline-related textarea').first();
            if ($parentScope.length === 0 || !$parentScope.val()) $parentScope = $form.find('textarea[name="scope_ru"]').not('.inline-related textarea').first();
            var $parentRiskMitigation = $(document.getElementById('id_risk_mitigation_controls_en') || null);
            if ($parentRiskMitigation.length === 0 || $parentRiskMitigation.closest('.inline-related').length) $parentRiskMitigation = $form.find('textarea[name="risk_mitigation_controls_en"]').not('.inline-related textarea').first();
            if ($parentRiskMitigation.length === 0 || !$parentRiskMitigation.val()) $parentRiskMitigation = $form.find('textarea[name="risk_mitigation_controls_uk"]').not('.inline-related textarea').first();
            if ($parentRiskMitigation.length === 0 || !$parentRiskMitigation.val()) $parentRiskMitigation = $form.find('textarea[name="risk_mitigation_controls_ru"]').not('.inline-related textarea').first();
            var $scopeInline = (opts && opts.$scopeInline && opts.$scopeInline.length) ? opts.$scopeInline : $row.find('textarea[name$="-scope"]').first();
            var $riskMitigationInline = (opts && opts.$riskMitigationInline && opts.$riskMitigationInline.length) ? opts.$riskMitigationInline : $row.find('textarea[name$="-risk_mitigation_controls"]').first();

            var tasks = [];
            if ($nameLocalInput.length && $parentName.length && $parentName.val() && !$nameLocalInput.val()) {
                tasks.push({ source: $parentName.val(), $target: $nameLocalInput, name: 'name_local' });
            }
            if (isCriticalityLevelRow) {
                if ($descConfid.length && $parentDescConfid.length && $parentDescConfid.val() && !$descConfid.val()) {
                    tasks.push({ source: $parentDescConfid.val(), $target: $descConfid, name: 'description_confid' });
                }
                if ($descInteg.length && $parentDescInteg.length && $parentDescInteg.val() && !$descInteg.val()) {
                    tasks.push({ source: $parentDescInteg.val(), $target: $descInteg, name: 'description_integ' });
                }
                if ($descAvail.length && $parentDescAvail.length && $parentDescAvail.val() && !$descAvail.val()) {
                    tasks.push({ source: $parentDescAvail.val(), $target: $descAvail, name: 'description_avail' });
                }
            }
            if ($descInline.length && $parentDesc.length && $parentDesc.val() && !$descInline.val()) {
                tasks.push({ source: $parentDesc.val(), $target: $descInline, name: 'description' });
            }
            if ($criteriaInline.length && $parentCriteria.length && $parentCriteria.val() && !$criteriaInline.val()) {
                tasks.push({ source: $parentCriteria.val(), $target: $criteriaInline, name: 'criteria' });
            }
            if ($examplesInline.length && $parentExamples.length && $parentExamples.val() && !$examplesInline.val()) {
                tasks.push({ source: $parentExamples.val(), $target: $examplesInline, name: 'examples' });
            }
            if ($risksInline.length && $parentRisks.length && $parentRisks.val() && !$risksInline.val()) {
                tasks.push({ source: $parentRisks.val(), $target: $risksInline, name: 'risks' });
            }
            if ($scopeInline.length && $parentScope.length && $parentScope.val() && $parentScope.val().trim() && !$scopeInline.val()) {
                tasks.push({ source: $parentScope.val(), $target: $scopeInline, name: 'scope' });
            }
            if ($riskMitigationInline.length && $parentRiskMitigation.length && $parentRiskMitigation.val() && $parentRiskMitigation.val().trim() && !$riskMitigationInline.val()) {
                tasks.push({ source: $parentRiskMitigation.val(), $target: $riskMitigationInline, name: 'risk_mitigation_controls' });
            }

            if (tasks.length === 0) {
                showTooltip($countrySelect, '✗ Немає тексту для перекладу або поля вже заповнені', 'error');
                return;
            }

            var $loadingIndicator = $row.find('.translation-loading');
            $loadingIndicator.show();
            var $allTargets = $();
            tasks.forEach(function(t) { $allTargets = $allTargets.add(t.$target); });
            $allTargets.prop('disabled', true).css('opacity', '0.6');

            var csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

            var promises = tasks.map(function(task) {
                return callTranslateApi(task.source, countryId, csrfToken).then(function(translated) {
                    return { task: task, translated: translated };
                });
            });

            Promise.all(promises).then(function(results) {
                results.forEach(function(r) {
                    if (r.translated) {
                        var $t = r.task.$target;
                        if (!$t.val()) {
                            $t.val(r.translated);
                            $t.trigger('change');
                            $t.css('background-color', '#d4edda');
                            setTimeout(function() { $t.css('background-color', ''); }, 2000);
                        }
                    }
                });
                showTooltip($countrySelect, '✓ Переклад: ' + (results.length) + ' полів', 'success');
            }).catch(function(err) {
                console.error('Translation error', err);
                showTooltip($countrySelect, '✗ Помилка перекладу', 'error');
            }).finally(function() {
                $loadingIndicator.hide();
                $allTargets.prop('disabled', false).css('opacity', '1');
            });
        }

        function showTooltip($element, message, type) {
            // Remove any existing tooltips
            $('.auto-translate-tooltip').remove();
            
            // Determine background color based on type
            let backgroundColor;
            if (type === 'success') {
                backgroundColor = '#28a745';
            } else if (type === 'warning') {
                backgroundColor = '#ffc107';
            } else {
                backgroundColor = '#dc3545';
            }
            
            const $tooltip = $('<div class="auto-translate-tooltip">')
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
                    whiteSpace: 'nowrap'
                });
            
            // Position tooltip near the element
            const offset = $element.offset();
            $tooltip.css({
                top: offset.top - 35,
                left: offset.left
            });
            
            $('body').append($tooltip);
            
            // Auto-remove after 2.5 seconds
            setTimeout(function() {
                $tooltip.fadeOut(200, function() {
                    $(this).remove();
                });
            }, 2500);
        }
    }

})();

