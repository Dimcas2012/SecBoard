(function($) {
    'use strict';

    $(document).ready(function() {
        // Handle mutual exclusivity between department and parent_position
        var $departmentField = $('#id_department');
        var $parentPositionField = $('#id_parent_position');

        if ($departmentField.length && $parentPositionField.length) {
            // When department is selected, clear parent_position
            $departmentField.on('change', function() {
                if ($(this).val()) {
                    $parentPositionField.val('').trigger('change');
                }
            });

            // When parent_position is selected, clear department
            $parentPositionField.on('change', function() {
                if ($(this).val()) {
                    $departmentField.val('').trigger('change');
                }
            });
        }
    });
})(django.jQuery);

