(function($) {
    'use strict';

    $(document).ready(function() {
        var $companyField = $('#id_company');
        var $positionField = $('#id_position');
        var $parentPositionField = $('#id_parent_position');

        // Filter parent_position options based on company and exclude current position
        function filterParentPositionOptions() {
            if (!$parentPositionField.length) return;

            var companyId = $companyField.val();
            var positionId = $positionField.val();

            // Filter options: show only positions from the same company, excluding current position
            $parentPositionField.find('option').each(function() {
                var $option = $(this);
                var optionValue = $option.val();
                
                // Keep the empty option
                if (!optionValue) {
                    return;
                }

                // Get option data attributes if available, or check via text
                var optionCompany = $option.data('company-id');
                
                // Hide options that don't match company or match current position
                if (companyId && optionCompany && optionCompany != companyId) {
                    $option.hide();
                } else if (positionId && optionValue == positionId) {
                    $option.hide();
                } else {
                    $option.show();
                }
            });
        }

        // Update when company or position changes
        if ($companyField.length && $positionField.length && $parentPositionField.length) {
            $companyField.on('change', function() {
                filterParentPositionOptions();
                // Clear parent_position if company changed
                var selectedParentId = $parentPositionField.val();
                if (selectedParentId) {
                    var $selectedOption = $parentPositionField.find('option[value="' + selectedParentId + '"]');
                    if (!$selectedOption.is(':visible')) {
                        $parentPositionField.val('');
                    }
                }
            });

            $positionField.on('change', function() {
                filterParentPositionOptions();
                // Clear parent_position if it's the same as position
                var selectedParentId = $parentPositionField.val();
                var positionId = $(this).val();
                if (selectedParentId == positionId) {
                    $parentPositionField.val('');
                }
            });

            // Initial filter
            filterParentPositionOptions();
        }
    });
})(django.jQuery);

