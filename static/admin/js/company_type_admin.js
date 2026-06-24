/**
 * JavaScript для Company Type Admin
 */
(function($) {
    'use strict';
    
    $(document).ready(function() {
        console.log('Company Type Admin JS loaded');
        
        // ============================================
        // Color Picker Enhancement
        // ============================================
        var colorField = $('#id_color');
        
        if (colorField.length > 0) {
            // Додати type="color" для нативного color picker
            colorField.attr('type', 'color');
            colorField.css({
                'width': '60px',
                'height': '35px',
                'border': '1px solid #ccc',
                'cursor': 'pointer'
            });
            
            // Додати preview
            var colorPreview = $('<span class="color-preview"></span>');
            colorPreview.css('background-color', colorField.val());
            colorField.after(colorPreview);
            
            // Додати hex display
            var hexDisplay = $('<span class="hex-display"></span>').text(colorField.val());
            hexDisplay.css({
                'margin-left': '10px',
                'font-family': 'monospace',
                'font-weight': 'bold'
            });
            colorPreview.after(hexDisplay);
            
            // Update on change
            colorField.on('change input', function() {
                var color = $(this).val();
                colorPreview.css('background-color', color);
                hexDisplay.text(color);
            });
        }
        
        // ============================================
        // Icon Picker Enhancement
        // ============================================
        var iconField = $('#id_icon');
        
        if (iconField.length > 0) {
            // Popular Font Awesome icons for company types
            var popularIcons = [
                'fa-university', 'fa-building', 'fa-landmark', 'fa-credit-card',
                'fa-coins', 'fa-hand-holding-usd', 'fa-shield-alt', 'fa-chart-line',
                'fa-briefcase', 'fa-mobile-alt', 'fa-file-contract', 'fa-exchange-alt',
                'fa-users', 'fa-piggy-bank', 'fa-clipboard-check', 'fa-file-invoice-dollar',
                'fa-bolt', 'fa-hospital', 'fa-broadcast-tower', 'fa-lock',
                'fa-home', 'fa-store', 'fa-warehouse', 'fa-truck'
            ];
            
            // Додати preview
            var iconPreview = $('<span class="icon-preview"></span>');
            var currentIcon = iconField.val();
            if (currentIcon) {
                iconPreview.html('<i class="fas ' + currentIcon + '"></i>');
            }
            iconField.after(iconPreview);
            
            // Додати кнопку вибору
            var iconPickerBtn = $('<button type="button" class="button">Choose Icon</button>');
            iconPickerBtn.css('margin-left', '10px');
            iconPreview.after(iconPickerBtn);
            
            // Створити dropdown з іконками
            var iconPicker = $('<div class="icon-picker"></div>');
            popularIcons.forEach(function(iconClass) {
                var iconOption = $('<div class="icon-option"></div>');
                iconOption.html('<i class="fas ' + iconClass + '"></i>');
                iconOption.attr('data-icon', iconClass);
                iconOption.attr('title', iconClass);
                
                iconOption.on('click', function() {
                    var selectedIcon = $(this).attr('data-icon');
                    iconField.val(selectedIcon);
                    iconPreview.html('<i class="fas ' + selectedIcon + '"></i>');
                    iconPicker.removeClass('show');
                });
                
                iconPicker.append(iconOption);
            });
            
            iconField.parent().css('position', 'relative');
            iconField.parent().append(iconPicker);
            
            // Toggle picker
            iconPickerBtn.on('click', function(e) {
                e.preventDefault();
                iconPicker.toggleClass('show');
            });
            
            // Close on outside click
            $(document).on('click', function(e) {
                if (!$(e.target).closest('.field-icon').length) {
                    iconPicker.removeClass('show');
                }
            });
            
            // Update preview on manual input
            iconField.on('input', function() {
                var icon = $(this).val();
                if (icon) {
                    iconPreview.html('<i class="fas ' + icon + '"></i>');
                } else {
                    iconPreview.html('');
                }
            });
        }
        
        // ============================================
        // Companies count link
        // ============================================
        $('.field-companies_count').each(function() {
            var count = parseInt($(this).text());
            if (count > 0) {
                $(this).css({
                    'color': '#28a745',
                    'font-weight': 'bold'
                });
            }
        });
        
        // ============================================
        // Regulatory requirements textarea enhancement
        // ============================================
        var regReqField = $('#id_regulatory_requirements');
        
        if (regReqField.length > 0) {
            regReqField.attr('rows', 4);
            regReqField.css({
                'width': '100%',
                'font-size': '13px'
            });
            
            // Character counter
            var charCounter = $('<div class="char-counter"></div>');
            charCounter.css({
                'text-align': 'right',
                'color': '#666',
                'font-size': '11px',
                'margin-top': '5px'
            });
            regReqField.after(charCounter);
            
            function updateCharCount() {
                var length = regReqField.val().length;
                charCounter.text(length + ' characters');
                if (length > 500) {
                    charCounter.css('color', '#ffc107');
                }
                if (length > 1000) {
                    charCounter.css('color', '#dc3545');
                }
            }
            
            updateCharCount();
            regReqField.on('input', updateCharCount);
        }
        
        // ============================================
        // Description textarea enhancement
        // ============================================
        var descField = $('#id_description');
        
        if (descField.length > 0) {
            descField.attr('rows', 3);
            descField.css({
                'width': '100%',
                'font-size': '13px'
            });
        }
        
        // ============================================
        // Save notification
        // ============================================
        $('form').on('submit', function() {
            var submitBtn = $(this).find('input[type="submit"]');
            submitBtn.val('Saving...').prop('disabled', true);
        });
    });
})(django.jQuery);

