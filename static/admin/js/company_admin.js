/**
 * JavaScript для Company Admin - покращення відображення Company Types та Countries
 */
(function($) {
    'use strict';
    
    $(document).ready(function() {
        console.log('Company Admin JS loaded');
        
        // ============================================
        // Enhanced Company Types Selector
        // ============================================
        var companyTypesSelect = $('#id_company_types');
        
        if (companyTypesSelect.length > 0) {
            console.log('Enhancing company types selector');
            
            // Fetch company types data with icons and colors
            $.ajax({
                url: '/admin/app_compliance/companytype/',
                success: function(data) {
                    // Parse the HTML response to extract company type info
                    var $data = $(data);
                    
                    // Find all options and enhance them
                    companyTypesSelect.find('option').each(function() {
                        var $option = $(this);
                        var typeId = $option.val();
                        
                        if (typeId) {
                            // Try to get icon and color from the page
                            // This is a simplified version - in production, you'd fetch this via API
                            var text = $option.text();
                            
                            // Add icon prefix if available (this would come from API)
                            // For now, just enhance the styling
                            $option.css({
                                'padding': '8px 12px',
                                'font-weight': '500'
                            });
                        }
                    });
                    
                    // Style the chosen options differently
                    var chosenSelect = $('#id_company_types_to');
                    if (chosenSelect.length > 0) {
                        chosenSelect.find('option').css({
                            'background': '#e7f3ff',
                            'color': '#0066cc',
                            'font-weight': '600'
                        });
                    }
                },
                error: function() {
                    console.log('Could not fetch company types data');
                }
            });
            
            // Add visual feedback when moving items
            $('#id_company_types_add_link, #id_company_types_remove_link').on('click', function() {
                setTimeout(function() {
                    var chosenSelect = $('#id_company_types_to');
                    chosenSelect.find('option').css({
                        'background': '#e7f3ff',
                        'color': '#0066cc',
                        'font-weight': '600'
                    });
                }, 100);
            });
        }
        
        // ============================================
        // Enhanced Countries Selector
        // ============================================
        var countriesSelect = $('#id_countries');
        
        if (countriesSelect.length > 0) {
            console.log('Enhancing countries selector');
            
            // Add emoji flags to options if available
            countriesSelect.find('option').each(function() {
                var $option = $(this);
                var text = $option.text();
                
                // Check if text already has emoji
                if (!/[\u{1F1E6}-\u{1F1FF}]/u.test(text)) {
                    // Try to add flag based on country code (this is simplified)
                    // In production, you'd fetch this from the backend
                }
                
                $option.css({
                    'padding': '8px 12px',
                    'font-size': '14px'
                });
            });
            
            // Style the chosen options differently
            var chosenSelect = $('#id_countries_to');
            if (chosenSelect.length > 0) {
                chosenSelect.find('option').css({
                    'background': '#e7f3ff',
                    'color': '#0066cc',
                    'font-weight': '600'
                });
            }
            
            // Add visual feedback when moving items
            $('#id_countries_add_link, #id_countries_remove_link').on('click', function() {
                setTimeout(function() {
                    var chosenSelect = $('#id_countries_to');
                    chosenSelect.find('option').css({
                        'background': '#e7f3ff',
                        'color': '#0066cc',
                        'font-weight': '600'
                    });
                }, 100);
            });
        }
        
        // ============================================
        // Filter enhancement
        // ============================================
        $('.selector-filter input').on('focus', function() {
            $(this).css({
                'border-color': '#007bff',
                'box-shadow': '0 0 5px rgba(0, 123, 255, 0.3)'
            });
        }).on('blur', function() {
            $(this).css({
                'border-color': '#dee2e6',
                'box-shadow': 'none'
            });
        });
        
        // ============================================
        // Help text for empty selections
        // ============================================
        function checkEmptySelections() {
            var companyTypesChosen = $('#id_company_types_to option').length;
            var countriesChosen = $('#id_countries_to option').length;
            
            if (companyTypesChosen === 0) {
                $('.field-company_types').find('.help').css({
                    'background': '#fff3cd',
                    'border-left-color': '#ffc107'
                });
            } else {
                $('.field-company_types').find('.help').css({
                    'background': '#d4edda',
                    'border-left-color': '#28a745'
                });
            }
            
            if (countriesChosen === 0) {
                $('.field-countries').find('.help').css({
                    'background': '#d1ecf1',
                    'border-left-color': '#17a2b8'
                });
            } else {
                $('.field-countries').find('.help').css({
                    'background': '#d4edda',
                    'border-left-color': '#28a745'
                });
            }
        }
        
        // Check on page load
        checkEmptySelections();
        
        // Check when items are moved
        $('#id_company_types_add_link, #id_company_types_remove_link, #id_countries_add_link, #id_countries_remove_link').on('click', function() {
            setTimeout(checkEmptySelections, 100);
        });
        
        // ============================================
        // Improve selector buttons
        // ============================================
        $('.selector-chooser a').css({
            'cursor': 'pointer',
            'user-select': 'none'
        }).hover(
            function() {
                $(this).css('transform', 'scale(1.1)');
            },
            function() {
                $(this).css('transform', 'scale(1)');
            }
        );
        
        // ============================================
        // Add count indicators
        // ============================================
        function updateCounts() {
            var companyTypesAvailable = $('#id_company_types_from option').length;
            var companyTypesChosen = $('#id_company_types_to option').length;
            var countriesAvailable = $('#id_countries_from option').length;
            var countriesChosen = $('#id_countries_to option').length;
            
            // Update company types count
            var companyTypesTitle = $('.field-company_types h2').first();
            if (companyTypesTitle.length > 0) {
                var titleText = companyTypesTitle.text().split('(')[0].trim();
                companyTypesTitle.html(titleText + ' <span style="color: #6c757d; font-size: 12px;">(' + companyTypesChosen + ' selected)</span>');
            }
            
            // Update countries count
            var countriesTitle = $('.field-countries h2').first();
            if (countriesTitle.length > 0) {
                var titleText = countriesTitle.text().split('(')[0].trim();
                countriesTitle.html(titleText + ' <span style="color: #6c757d; font-size: 12px;">(' + countriesChosen + ' selected)</span>');
            }
        }
        
        // Update on page load
        setTimeout(updateCounts, 200);
        
        // Update when items are moved
        $('#id_company_types_add_link, #id_company_types_remove_link, #id_countries_add_link, #id_countries_remove_link').on('click', function() {
            setTimeout(updateCounts, 100);
        });
        
        // ============================================
        // Keyboard shortcuts
        // ============================================
        $(document).on('keydown', function(e) {
            // Ctrl/Cmd + Right Arrow: Add selected
            if ((e.ctrlKey || e.metaKey) && e.keyCode === 39) {
                if ($('#id_company_types_from:focus').length > 0) {
                    $('#id_company_types_add_link').click();
                    e.preventDefault();
                }
                if ($('#id_countries_from:focus').length > 0) {
                    $('#id_countries_add_link').click();
                    e.preventDefault();
                }
            }
            
            // Ctrl/Cmd + Left Arrow: Remove selected
            if ((e.ctrlKey || e.metaKey) && e.keyCode === 37) {
                if ($('#id_company_types_to:focus').length > 0) {
                    $('#id_company_types_remove_link').click();
                    e.preventDefault();
                }
                if ($('#id_countries_to:focus').length > 0) {
                    $('#id_countries_remove_link').click();
                    e.preventDefault();
                }
            }
        });
        
        console.log('Company Admin JS initialization complete');
    });
})(django.jQuery);

