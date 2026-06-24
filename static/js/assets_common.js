//// SecBoard\SecBoard\static\js\assets_common.js
//const AssetUtils = {
//    criticalityLevels: null,
//
//    async loadCriticalityLevels() {
//        if (this.criticalityLevels) {
//            return this.criticalityLevels;
//        }
//
//        try {
//            const response = await $.ajax({
//                url: window.ASSET_CONFIG.urls.criticalityLevels,
//                type: 'GET'
//            });
//            console.log("Criticality levels loaded:", response);
//
//            if (response.levels && Array.isArray(response.levels)) {
//                this.criticalityLevels = response.levels.reduce((acc, level) => {
//                    acc[level.id] = level;
//                    return acc;
//                }, {});
//                return this.criticalityLevels;
//            } else {
//                throw new Error('Invalid criticality levels data');
//            }
//        } catch (error) {
//            console.error("Error loading criticality levels:", error);
//            throw error;
//        }
//    },
//
//
//    getCriticalityLevel(id) {
//        return this.criticalityLevels?.[id] || null;
//    },
//
//    formatDate(dateString) {
//        if (!dateString) return '';
//        const date = new Date(dateString);
//        return date.toLocaleDateString('uk-UA', {
//            day: '2-digit',
//            month: '2-digit',
//            year: 'numeric'
//        });
//    },
//
//    initializeDatepickers() {
//        $('.datepicker-input, #editRegistrationDate, #editDeletionDate').datepicker({
//            format: 'dd.mm.yyyy',
//            autoclose: true,
//            todayHighlight: true,
//            language: 'uk',
//            clearBtn: true,
//            orientation: "bottom auto"
//        }).on('changeDate', function(e) {
//            $(this).removeClass('is-invalid');
//        });
//    },
//
//    initializeTooltips() {
//        $('[data-bs-toggle="tooltip"]').tooltip({
//            trigger: 'hover'
//        });
//    },
//
//    initializeSelects() {
//        $('.select2-input').select2({
//            width: '100%',
//            theme: 'bootstrap-5',
//            placeholder: "Select...",
//            allowClear: true
//        });
//    },
//
//    showLoading() {
//        $('.loading-spinner').fadeIn(200);
//    },
//
//    hideLoading() {
//        $('.loading-spinner').fadeOut(200);
//    },
//
//    showNotification(message, type = 'success') {
//        const toast = `
//            <div class="toast align-items-center text-white bg-${type} border-0"
//                 role="alert"
//                 aria-live="assertive"
//                 aria-atomic="true">
//                <div class="d-flex">
//                    <div class="toast-body">
//                        ${message}
//                    </div>
//                    <button type="button"
//                            class="btn-close btn-close-white me-2 m-auto"
//                            data-bs-dismiss="toast"
//                            aria-label="Close">
//                    </button>
//                </div>
//            </div>
//        `;
//
//        const $toastContainer = $('.toast-container');
//        if (!$toastContainer.length) {
//            $('body').append('<div class="toast-container position-fixed top-0 end-0 p-3"></div>');
//        }
//
//        const $toast = $(toast).appendTo('.toast-container');
//        const bsToast = new bootstrap.Toast($toast[0], {
//            autohide: true,
//            delay: 5000
//        });
//
//        bsToast.show();
//
//        // Remove toast after it's hidden
//        $toast.on('hidden.bs.toast', function() {
//            $(this).remove();
//        });
//    },
//
//    handleAjaxError(xhr) {
//        console.error('Ajax error:', xhr);
//        let errorMessage = 'An error occurred';
//
//        // Try to get error message from response
//        try {
//            const response = JSON.parse(xhr.responseText);
//            errorMessage = response.message || response.error || errorMessage;
//        } catch (e) {
//            // If can't parse JSON, try to get status text
//            errorMessage = xhr.statusText || errorMessage;
//        }
//
//        // Add status code info for debugging
//        const statusInfo = xhr.status ? ` (${xhr.status})` : '';
//        console.error(`Error details: ${errorMessage}${statusInfo}`);
//
//        this.showNotification(errorMessage, 'danger');
//    },
//
//
//     updateCriticalityDescription(selectElement) {
//        if (!selectElement) return;
//
//        const selectedId = $(selectElement).val();
//        const level = this.getCriticalityLevel(selectedId);
//
//        const elementId = selectElement.id;
//        const descriptionElement = '#' + elementId + 'Description';
//        const colorElement = '#' + elementId + 'Color';
//
//        console.log('Updating criticality description:', {
//            elementId,
//            selectedId,
//            level,
//            descriptionElement,
//            colorElement
//        });
//
//        if (level) {
//            let description = '';
//            if (elementId.includes('confidentiality')) {
//                description = level.description_confid;
//            } else if (elementId.includes('integrity')) {
//                description = level.description_integ;
//            } else if (elementId.includes('availability')) {
//                description = level.description_avail;
//            }
//
//            $(descriptionElement).text(description).show();
//            $(colorElement).css('background-color', level.color).show();
//        } else {
//            $(descriptionElement).hide();
//            $(colorElement).hide();
//        }
//    },
//
//    clearValidationErrors() {
//        $('.is-invalid').removeClass('is-invalid');
//        $('.invalid-feedback').remove();
//    }
//};
//
//// Initialize tooltips when dynamic content is loaded
//$(document).on('shown.bs.modal', function() {
//    AssetUtils.initializeTooltips();
//});
//
//window.AssetUtils = AssetUtils;