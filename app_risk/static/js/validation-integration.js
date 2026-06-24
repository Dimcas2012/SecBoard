/**
 * Validation Integration Script
 * Integrates all validation improvements with existing templates
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('Validation Integration: Initializing comprehensive validation system...');
    
    // Initialize validation systems
    initializeValidationSystems();
    
    // Enhance existing forms
    enhanceReportForm();
    enhanceScheduleForm();
    enhanceRiskAssessmentForm();
    
    // Setup global error handling
    setupGlobalErrorHandling();
    
    console.log('Validation Integration: All systems initialized successfully');
});

function initializeValidationSystems() {
    // Validation systems are already initialized in their respective files
    // Just verify they're available
    if (typeof window.validationSystem === 'undefined') {
        console.warn('Validation System not available');
    }
    
    if (typeof window.errorDisplaySystem === 'undefined') {
        console.warn('Error Display System not available');
    }
    
    if (typeof window.scheduleValidation === 'undefined') {
        console.warn('Schedule Validation not available');
    }
    
    if (typeof window.networkErrorHandler === 'undefined') {
        console.warn('Network Error Handler not available');
    }
}

function enhanceReportForm() {
    const reportForm = document.getElementById('reportForm');
    if (!reportForm) return;
    
    console.log('Enhancing report form with validation...');
    
    // Add validation attributes
    addValidationAttributes(reportForm, {
        'reportType': 'required|choice:full,summary,compliance',
        'reportFormat': 'required|choice:pdf,word',
        'reportLanguage': 'required|choice:uk,en,ru',
        'reportCompany': 'companyRequired',
        'reportNotes': 'maxLength:1000'
    });
    
    // Add form validation flag
    reportForm.setAttribute('data-validate-form', 'true');
    
    // Enhanced form submission
    const generateBtn = document.getElementById('generateReport');
    if (generateBtn) {
        generateBtn.addEventListener('click', function(e) {
            e.preventDefault();
            
            if (window.validationSystem && !window.validationSystem.validateForm(reportForm)) {
                if (window.errorDisplaySystem) {
                    window.errorDisplaySystem.showError({
                        category: 'validation',
                        code: 'form_validation_failed',
                        message: 'Будь ласка, виправте помилки у формі перед генерацією звіту'
                    });
                }
                return false;
            }
            
            // Store form submission for retry
            window.lastFormSubmission = () => generateReport();
            
            generateReport();
        });
    }
    
    // Enhanced preview
    const previewBtn = document.getElementById('previewReport');
    if (previewBtn) {
        previewBtn.addEventListener('click', function(e) {
            e.preventDefault();
            
            if (window.validationSystem && !window.validationSystem.validateForm(reportForm)) {
                if (window.errorDisplaySystem) {
                    window.errorDisplaySystem.showError({
                        category: 'validation',
                        code: 'form_validation_failed',
                        message: 'Будь ласка, виправте помилки у формі перед попереднім переглядом'
                    });
                }
                return false;
            }
            
            loadReportPreview();
        });
    }
}

function enhanceScheduleForm() {
    const scheduleForm = document.getElementById('scheduleForm');
    if (!scheduleForm) return;
    
    console.log('Enhancing schedule form with validation...');
    
    // Add validation attributes
    addValidationAttributes(scheduleForm, {
        'scheduleName': 'required|minLength:3|maxLength:100|pattern:^[a-zA-Zа-яА-ЯёЁ0-9\\s\\-_.,()]+$',
        'scheduleDescription': 'maxLength:500',
        'scheduleReportType': 'required|choice:full,summary,compliance',
        'scheduleReportFormat': 'required|choice:pdf,word',
        'scheduleReportLanguage': 'required|choice:uk,en,ru',
        'scheduleFrequency': 'required|choice:once,daily,weekly,monthly,quarterly,yearly',
        'scheduleStartDate': 'required|date|futureDate',
        'scheduleEndDate': 'date',
        'scheduleExecutionTime': 'required|time',
        'scheduleDayOfMonth': 'number|min:1|max:31',
        'scheduleEmailSubject': 'maxLength:200',
        'scheduleEmailBody': 'maxLength:2000',
        'scheduleStatus': 'required|choice:active,paused,completed'
    });
    
    // Add form validation flag
    scheduleForm.setAttribute('data-validate-form', 'true');
    
    // Enhanced save button
    const saveBtn = document.getElementById('saveScheduleBtn');
    if (saveBtn) {
        // Remove existing event listeners
        const newSaveBtn = saveBtn.cloneNode(true);
        saveBtn.parentNode.replaceChild(newSaveBtn, saveBtn);
        
        newSaveBtn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            // Validate with schedule validation system
            if (window.scheduleValidation) {
                const isValid = window.scheduleValidation.validateForm();
                if (!isValid) {
                    window.scheduleValidation.showValidationErrors();
                    return false;
                }
            }
            
            // Store form submission for retry
            window.lastFormSubmission = () => saveSchedule();
            
            saveSchedule();
        });
    }
}

function enhanceRiskAssessmentForm() {
    // Enhance vulnerability forms
    const vulnerabilityForms = document.querySelectorAll('#vulnerabilitiesForm');
    vulnerabilityForms.forEach(form => {
        form.setAttribute('data-validate-form', 'true');
    });
    
    // Enhance file upload validation
    const fileInputs = document.querySelectorAll('input[type="file"]');
    fileInputs.forEach(input => {
        input.setAttribute('data-validate', 'fileSize:10485760|fileType:pdf,docx,xlsx,csv,txt');
        
        input.addEventListener('change', function(e) {
            if (window.validationSystem) {
                window.validationSystem.validateField(this);
            }
        });
    });
}

function addValidationAttributes(form, attributeMap) {
    Object.entries(attributeMap).forEach(([fieldId, validation]) => {
        const field = form.querySelector(`#${fieldId}`);
        if (field) {
            field.setAttribute('data-validate', validation);
        }
    });
}

function setupGlobalErrorHandling() {
    // Override existing AJAX error handling
    if (typeof $ !== 'undefined') {
        $(document).ajaxError(function(event, xhr, settings, thrownError) {
            if (window.networkErrorHandler) {
                window.networkErrorHandler.handleAjaxError(xhr, settings, thrownError);
            }
        });
        
        // Add CSRF token to all AJAX requests
        $.ajaxSetup({
            beforeSend: function(xhr, settings) {
                if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
                    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
                    if (csrfToken) {
                        xhr.setRequestHeader("X-CSRFToken", csrfToken.value);
                    }
                }
            }
        });
    }
    
    // Enhanced error display for existing functions
    if (typeof window.showAlert === 'function') {
        const originalShowAlert = window.showAlert;
        window.showAlert = function(type, message) {
            if (window.errorDisplaySystem) {
                const category = type === 'success' ? 'general' : 
                               type === 'error' ? 'system' : 'general';
                
                if (type === 'success') {
                    window.errorDisplaySystem.showSuccess(message);
                } else {
                    window.errorDisplaySystem.showError({
                        category: category,
                        code: 'alert_message',
                        message: message,
                        severity: type === 'error' ? 'error' : 'info'
                    });
                }
            } else {
                originalShowAlert(type, message);
            }
        };
    }
}

// Enhanced AJAX functions with validation
function enhancedAjaxRequest(url, options = {}) {
    // Add default error handling
    const originalError = options.error;
    options.error = function(xhr, textStatus, errorThrown) {
        if (window.networkErrorHandler) {
            window.networkErrorHandler.handleAjaxError(xhr, options, errorThrown);
        }
        
        if (originalError) {
            originalError(xhr, textStatus, errorThrown);
        }
    };
    
    // Add success handling
    const originalSuccess = options.success;
    options.success = function(data, textStatus, xhr) {
        // Clear any network-related errors on success
        if (window.errorDisplaySystem) {
            window.errorDisplaySystem.clearErrorsByCategory('network');
        }
        
        if (originalSuccess) {
            originalSuccess(data, textStatus, xhr);
        }
    };
    
    return $.ajax(url, options);
}

// Enhanced form validation for existing forms
function validateFormBeforeSubmit(formId, callback) {
    const form = document.getElementById(formId);
    if (!form) {
        console.error(`Form ${formId} not found`);
        return false;
    }
    
    // Use validation system if available
    if (window.validationSystem) {
        const isValid = window.validationSystem.validateForm(form);
        if (!isValid) {
            if (window.errorDisplaySystem) {
                window.errorDisplaySystem.showError({
                    category: 'validation',
                    code: 'form_validation_failed',
                    message: 'Будь ласка, виправте помилки у формі'
                });
            }
            return false;
        }
    }
    
    // Execute callback if validation passes
    if (callback && typeof callback === 'function') {
        return callback();
    }
    
    return true;
}

// File upload validation
function validateFileUpload(fileInput, options = {}) {
    if (!fileInput.files || fileInput.files.length === 0) {
        return { isValid: true, errors: [] };
    }
    
    const errors = [];
    const maxSize = options.maxSize || 10 * 1024 * 1024; // 10MB
    const allowedTypes = options.allowedTypes || ['pdf', 'docx', 'xlsx', 'csv', 'txt'];
    
    Array.from(fileInput.files).forEach((file, index) => {
        // Size validation
        if (file.size > maxSize) {
            errors.push(`Файл "${file.name}" занадто великий (${formatFileSize(file.size)}). Максимальний розмір: ${formatFileSize(maxSize)}`);
        }
        
        // Type validation
        const fileExt = file.name.split('.').pop().toLowerCase();
        if (!allowedTypes.includes(fileExt)) {
            errors.push(`Недопустимий тип файлу "${file.name}". Дозволені типи: ${allowedTypes.join(', ')}`);
        }
    });
    
    const result = {
        isValid: errors.length === 0,
        errors: errors
    };
    
    // Display errors if validation system is available
    if (!result.isValid && window.errorDisplaySystem) {
        errors.forEach(error => {
            window.errorDisplaySystem.showFileError({
                code: 'file_validation_error',
                message: error
            });
        });
    }
    
    return result;
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Connection status indicator
function updateConnectionStatus() {
    if (window.networkErrorHandler) {
        const isConnected = window.networkErrorHandler.isConnected();
        
        // Update UI indicators
        const indicators = document.querySelectorAll('.connection-status');
        indicators.forEach(indicator => {
            indicator.className = `connection-status ${isConnected ? 'online' : 'offline'}`;
            indicator.textContent = isConnected ? 'Онлайн' : 'Офлайн';
        });
        
        // Show/hide offline indicator
        if (isConnected) {
            window.networkErrorHandler.hideOfflineIndicator();
        }
    }
}

// Add connection status listener
if (window.networkErrorHandler) {
    window.networkErrorHandler.addConnectionListener(updateConnectionStatus);
}

// Periodic connection check
setInterval(updateConnectionStatus, 30000);

// Export enhanced functions for global use
window.enhancedAjaxRequest = enhancedAjaxRequest;
window.validateFormBeforeSubmit = validateFormBeforeSubmit;
window.validateFileUpload = validateFileUpload;
window.updateConnectionStatus = updateConnectionStatus;

console.log('Validation Integration: Enhanced functions exported to global scope'); 