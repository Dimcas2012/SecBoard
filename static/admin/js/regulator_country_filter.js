/**
 * Dynamic filtering of companies based on selected country
 * For LocalComplianceRegulator admin
 */
(function($) {
    'use strict';
    
    $(document).ready(function() {
        // Знайти поля
        var countryField = $('#id_country');
        var companiesFromBox = $('#id_companies_from');
        var companiesToBox = $('#id_companies_to');
        
        if (countryField.length === 0) {
            console.log('Country field not found');
            return;
        }
        
        console.log('Regulator country filter initialized');
        
        // Зберегти всі опції компаній при завантаженні
        var allCompaniesOptions = [];
        if (companiesFromBox.length > 0) {
            companiesFromBox.find('option').each(function() {
                allCompaniesOptions.push({
                    value: $(this).val(),
                    text: $(this).text(),
                    countries: $(this).data('countries') || []
                });
            });
        }
        
        // Функція для отримання компаній країни через AJAX
        function filterCompaniesByCountry(countryId) {
            if (!countryId) {
                // Якщо країна не вибрана, показати всі компанії
                console.log('No country selected, showing all companies');
                return;
            }
            
            console.log('Filtering companies for country ID:', countryId);
            
            // AJAX запит для отримання компаній країни
            $.ajax({
                url: '/compliance/api/country/' + countryId + '/companies/',
                dataType: 'json',
                success: function(data) {
                    console.log('Companies for country:', data);
                    
                    if (data.companies && companiesFromBox.length > 0) {
                        var companyIds = data.companies.map(function(c) { return c.id.toString(); });
                        
                        // Фільтрувати опції
                        companiesFromBox.find('option').each(function() {
                            var optionValue = $(this).val();
                            if (companyIds.indexOf(optionValue) !== -1) {
                                $(this).show();
                            } else {
                                // Перевірити чи ця компанія вже вибрана
                                var isSelected = companiesToBox.find('option[value="' + optionValue + '"]').length > 0;
                                if (!isSelected) {
                                    $(this).hide();
                                }
                            }
                        });
                    }
                },
                error: function(xhr, status, error) {
                    console.error('Error loading companies:', error);
                    // При помилці показати всі компанії
                    if (companiesFromBox.length > 0) {
                        companiesFromBox.find('option').show();
                    }
                }
            });
        }
        
        // Обробник зміни країни
        countryField.on('change', function() {
            var selectedCountryId = $(this).val();
            console.log('Country changed to:', selectedCountryId);
            filterCompaniesByCountry(selectedCountryId);
        });
        
        // Trigger при завантаженні сторінки якщо країна вже вибрана
        if (countryField.val()) {
            console.log('Initial country:', countryField.val());
            filterCompaniesByCountry(countryField.val());
        }
        
        // Додати підказку
        if (companiesFromBox.length > 0) {
            var helpText = $('<p class="help">').css({
                'color': '#666',
                'font-size': '12px',
                'margin-top': '5px'
            }).html('<i class="fas fa-info-circle"></i> Companies are filtered based on selected country. Select country first to see relevant companies.');
            
            companiesFromBox.parent().append(helpText);
        }
    });
})(django.jQuery);

