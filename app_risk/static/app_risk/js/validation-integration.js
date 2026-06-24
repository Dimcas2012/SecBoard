/**
 * SecBoard Risk Assessment - Validation Integration
 * Unifies all validation systems and enhances existing forms
 */

class ValidationIntegration {
    constructor() {
        this.validationSystem = null;
        this.errorDisplay = null;
        this.networkHandler = null;
        this.scheduleValidator = null;
        this.forms = new Map();
        this.initialized = false;
        
        this.init();
    }
    
    init() {
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.initialize());
        } else {
            this.initialize();
        }
    }
    
    initialize() {
        if (this.initialized) return;
        
        try {
            // Initialize core systems
            this.initializeCoreSystem();
            
            // Enhance existing forms
            this.enhanceExistingForms();
            
            // Setup global error handling
            this.setupGlobalErrorHandling();
            
            // Setup CSRF token handling
            this.setupCSRFHandling();
            
            // Setup form utilities
            this.setupFormUtilities();
            
            // Setup file upload enhancements
            this.setupFileUploadEnhancements();
            
            // Setup connection monitoring
            this.setupConnectionMonitoring();
            
            this.initialized = true;
            console.log('SecBoard Validation Integration initialized successfully');
            
        } catch (error) {
            console.error('Failed to initialize validation integration:', error);
        }
    }
    
    initializeCoreSystem() {
        // Initialize validation system
        if (window.ValidationSystem) {
            this.validationSystem = window.validation || new ValidationSystem({
                language: document.documentElement.lang || 'uk'
            });
        }
        
        // Initialize error display
        if (window.ErrorDisplaySystem) {
            this.errorDisplay = window.errorDisplay || new ErrorDisplaySystem({
                language: document.documentElement.lang || 'uk'
            });
        }
        
        // Initialize network handler
        if (window.NetworkErrorHandler) {
            this.networkHandler = window.networkErrorHandler || new NetworkErrorHandler({
                language: document.documentElement.lang || 'uk'
            });
        }
    }
    
    enhanceExistingForms() {
        // Risk report form
        this.enhanceRiskReportForm();
        
        // Schedule form
        this.enhanceScheduleForm();
        
        // Threat forms
        this.enhanceThreatForms();
        
        // Vulnerability forms
        this.enhanceVulnerabilityForms();
        
        // Asset forms
        this.enhanceAssetForms();
        
        // General forms
        this.enhanceGeneralForms();
    }
    
    enhanceRiskReportForm() {
        const reportForm = document.querySelector('#reportForm');
        if (!reportForm) return;
        
        // Add validation attributes
        this.addValidationAttributes(reportForm, {
            '#reportType': { 'data-validate': 'required' },
            '#reportFormat': { 'data-validate': 'required' },
            '#reportLanguage': { 'data-validate': 'required' },
            '#reportNotes': { 'data-validate': 'maxLength:1000' }
        });
        
        // Add custom validators
        if (this.validationSystem) {
            this.validationSystem.addFormValidator('reportForm', (form, data) => {
                const errors = [];
                
                // Validate date range if both dates are provided
                if (data.startDate && data.endDate) {
                    const start = new Date(data.startDate);
                    const end = new Date(data.endDate);
                    
                    if (start > end) {
                        errors.push('Start date must be before end date');
                    }
                    
                    const daysDiff = (end - start) / (1000 * 60 * 60 * 24);
                    if (daysDiff > 365 * 3) {
                        errors.push('Date range is very large (more than 3 years). This may impact performance.');
                    }
                }
                
                return {
                    valid: errors.length === 0,
                    errors: errors
                };
            });
        }
        
        // Add real-time validation feedback
        this.addRealTimeValidation(reportForm);
        
        // Store form reference
        this.forms.set('reportForm', reportForm);
    }
    
    enhanceScheduleForm() {
        const scheduleForm = document.querySelector('#scheduleForm');
        if (!scheduleForm) return;
        
        // Initialize specialized schedule validator
        if (window.ScheduleValidationSystem) {
            this.scheduleValidator = new ScheduleValidationSystem({
                formSelector: '#scheduleForm',
                language: document.documentElement.lang || 'uk'
            });
        }
        
        // Add validation attributes
        this.addValidationAttributes(scheduleForm, {
            '#scheduleName': { 'data-validate': 'required|minLength:3|maxLength:100' },
            '#scheduleFrequency': { 'data-validate': 'required' },
            '#scheduleStartDate': { 'data-validate': 'required|date' },
            '#scheduleEndDate': { 'data-validate': 'date' },
            '#scheduleExecutionTime': { 'data-validate': 'required|time' },
            '#scheduleEmailSubject': { 'data-validate': 'maxLength:200' },
            '#scheduleEmailRecipients': { 'data-validate': 'required' }
        });
        
        this.forms.set('scheduleForm', scheduleForm);
    }
    
    enhanceThreatForms() {
        const threatForms = document.querySelectorAll('#threatForm, .threat-form');
        
        threatForms.forEach(form => {
            this.addValidationAttributes(form, {
                '[name="name_uk"]': { 'data-validate': 'required|minLength:3|maxLength:200' },
                '[name="description_uk"]': { 'data-validate': 'required|minLength:10|maxLength:1000' },
                '[name="probability"]': { 'data-validate': 'required|number|min:0|max:1' },
                '[name="impact"]': { 'data-validate': 'required|number|min:1|max:5' }
            });
            
            this.addRealTimeValidation(form);
        });
    }
    
    enhanceVulnerabilityForms() {
        const vulnForms = document.querySelectorAll('#vulnerabilityForm, .vulnerability-form');
        
        vulnForms.forEach(form => {
            this.addValidationAttributes(form, {
                '[name="name"]': { 'data-validate': 'required|minLength:3|maxLength:200' },
                '[name="description"]': { 'data-validate': 'required|minLength:10|maxLength:1000' },
                '[name="severity"]': { 'data-validate': 'required' },
                '[name="cvss_score"]': { 'data-validate': 'number|min:0|max:10' }
            });
            
            this.addRealTimeValidation(form);
        });
    }
    
    enhanceAssetForms() {
        const assetForms = document.querySelectorAll('#assetForm, .asset-form');
        
        assetForms.forEach(form => {
            this.addValidationAttributes(form, {
                '[name="name"]': { 'data-validate': 'required|minLength:2|maxLength:100' },
                '[name="description"]': { 'data-validate': 'maxLength:500' },
                '[name="ip_address"]': { 'data-validate': 'pattern:^(?:[0-9]{1,3}\\.){3}[0-9]{1,3}$' },
                '[name="confidentiality"]': { 'data-validate': 'required|number|min:1|max:5' },
                '[name="integrity"]': { 'data-validate': 'required|number|min:1|max:5' },
                '[name="availability"]': { 'data-validate': 'required|number|min:1|max:5' }
            });
            
            this.addRealTimeValidation(form);
        });
    }
    
    enhanceGeneralForms() {
        // Find all forms that haven't been enhanced yet
        const allForms = document.querySelectorAll('form:not(.validation-enhanced)');
        
        allForms.forEach(form => {
            // Skip if already processed
            if (this.forms.has(form.id)) return;
            
            // Add basic validation
            this.addBasicValidation(form);
            
            // Add validation enhancement class
            form.classList.add('validation-enhanced');
        });
    }
    
    addValidationAttributes(form, attributeMap) {
        Object.entries(attributeMap).forEach(([selector, attributes]) => {
            const elements = form.querySelectorAll(selector);
            elements.forEach(element => {
                Object.entries(attributes).forEach(([attr, value]) => {
                    element.setAttribute(attr, value);
                });
            });
        });
    }
    
    addRealTimeValidation(form) {
        if (!this.validationSystem) return;
        
        // Attach validation to the form
        this.validationSystem.attachFormValidation(form);
        
        // Add form status indicator
        this.addFormStatusIndicator(form);
        
        // Add character counters for text fields
        this.addCharacterCounters(form);
        
        // Add validation summary
        this.addValidationSummary(form);
    }
    
    addBasicValidation(form) {
        // Add required validation to required fields
        const requiredFields = form.querySelectorAll('[required]');
        requiredFields.forEach(field => {
            if (!field.hasAttribute('data-validate')) {
                field.setAttribute('data-validate', 'required');
            }
        });
        
        // Add email validation to email fields
        const emailFields = form.querySelectorAll('input[type="email"]');
        emailFields.forEach(field => {
            if (!field.hasAttribute('data-validate')) {
                field.setAttribute('data-validate', 'required|email');
            } else {
                const current = field.getAttribute('data-validate');
                if (!current.includes('email')) {
                    field.setAttribute('data-validate', current + '|email');
                }
            }
        });
        
        // Add number validation to number fields
        const numberFields = form.querySelectorAll('input[type="number"]');
        numberFields.forEach(field => {
            const validations = ['number'];
            if (field.hasAttribute('min')) {
                validations.push(`min:${field.getAttribute('min')}`);
            }
            if (field.hasAttribute('max')) {
                validations.push(`max:${field.getAttribute('max')}`);
            }
            
            field.setAttribute('data-validate', validations.join('|'));
        });
        
        this.addRealTimeValidation(form);
    }
    
    addFormStatusIndicator(form) {
        // Check if indicator already exists
        if (form.querySelector('.form-status-indicator')) return;
        
        const indicator = document.createElement('div');
        indicator.className = 'form-status-indicator';
        indicator.innerHTML = `
            <div class="status-item" data-status="valid">
                <i class="fas fa-check-circle text-success"></i>
                <span>Form is valid</span>
            </div>
            <div class="status-item" data-status="invalid">
                <i class="fas fa-exclamation-circle text-danger"></i>
                <span>Form has errors</span>
            </div>
            <div class="status-item" data-status="validating">
                <i class="fas fa-spinner fa-spin text-info"></i>
                <span>Validating...</span>
            </div>
        `;
        
        // Insert at the beginning of the form
        form.insertBefore(indicator, form.firstChild);
        
        // Update status on validation
        form.addEventListener('validation:complete', (e) => {
            this.updateFormStatus(indicator, e.detail.isValid);
        });
    }
    
    updateFormStatus(indicator, isValid) {
        const statusItems = indicator.querySelectorAll('.status-item');
        statusItems.forEach(item => item.style.display = 'none');
        
        const activeStatus = isValid ? 'valid' : 'invalid';
        const activeItem = indicator.querySelector(`[data-status="${activeStatus}"]`);
        if (activeItem) {
            activeItem.style.display = 'flex';
        }
    }
    
    addCharacterCounters(form) {
        const textFields = form.querySelectorAll('textarea, input[type="text"][maxlength]');
        
        textFields.forEach(field => {
            const maxLength = field.getAttribute('maxlength');
            if (!maxLength) return;
            
            // Check if counter already exists
            if (field.parentElement.querySelector('.character-counter')) return;
            
            const counter = document.createElement('div');
            counter.className = 'character-counter text-muted small';
            counter.innerHTML = `<span class="current">0</span> / <span class="max">${maxLength}</span>`;
            
            // Insert after the field
            field.parentElement.appendChild(counter);
            
            // Update counter on input
            const updateCounter = () => {
                const current = field.value.length;
                const currentSpan = counter.querySelector('.current');
                currentSpan.textContent = current;
                
                // Color coding
                const percentage = current / maxLength;
                if (percentage > 0.9) {
                    counter.className = 'character-counter text-danger small';
                } else if (percentage > 0.8) {
                    counter.className = 'character-counter text-warning small';
                } else {
                    counter.className = 'character-counter text-muted small';
                }
            };
            
            field.addEventListener('input', updateCounter);
            updateCounter(); // Initial update
        });
    }
    
    addValidationSummary(form) {
        // Check if summary already exists
        if (form.querySelector('.validation-summary')) return;
        
        const summary = document.createElement('div');
        summary.className = 'validation-summary alert alert-danger';
        summary.style.display = 'none';
        summary.innerHTML = `
            <h6><i class="fas fa-exclamation-triangle me-2"></i>Please correct the following errors:</h6>
            <ul class="error-list mb-0"></ul>
        `;
        
        // Insert at the beginning of the form
        form.insertBefore(summary, form.firstChild);
        
        // Update summary on validation
        form.addEventListener('validation:complete', (e) => {
            this.updateValidationSummary(summary, e.detail.errors);
        });
    }
    
    updateValidationSummary(summary, errors) {
        const errorList = summary.querySelector('.error-list');
        
        if (errors && errors.length > 0) {
            errorList.innerHTML = errors.map(error => `<li>${error}</li>`).join('');
            summary.style.display = 'block';
        } else {
            summary.style.display = 'none';
        }
    }
    
    setupGlobalErrorHandling() {
        // Handle form submission errors
        document.addEventListener('submit', (e) => {
            const form = e.target;
            if (!form.matches('form')) return;
            
            // Validate form before submission
            if (this.validationSystem && !this.validationSystem.validate(form)) {
                e.preventDefault();
                e.stopPropagation();
                
                // Show error message
                if (this.errorDisplay) {
                    this.errorDisplay.showError({
                        message: 'Please correct the form errors before submitting',
                        category: 'validation'
                    });
                }
            }
        });
        
        // Handle AJAX form submissions
        $(document).on('ajaxError', (event, jqXHR, ajaxSettings, thrownError) => {
            // Parse validation errors from response
            try {
                const response = JSON.parse(jqXHR.responseText);
                if (response.errors && typeof response.errors === 'object') {
                    this.displayServerValidationErrors(response.errors);
                }
            } catch (e) {
                // Response is not JSON or doesn't contain validation errors
            }
        });
    }
    
    displayServerValidationErrors(errors) {
        Object.entries(errors).forEach(([field, fieldErrors]) => {
            const fieldElement = document.querySelector(`[name="${field}"], #${field}`);
            if (fieldElement && this.validationSystem) {
                // Clear existing validation state
                this.validationSystem.clearFieldValidation(fieldElement);
                
                // Add server error
                fieldElement.classList.add('is-invalid');
                
                const container = fieldElement.closest('.form-group, .mb-3, .form-floating') || fieldElement.parentElement;
                const feedback = document.createElement('div');
                feedback.className = 'invalid-feedback';
                feedback.textContent = Array.isArray(fieldErrors) ? fieldErrors[0] : fieldErrors;
                container.appendChild(feedback);
            }
        });
    }
    
    setupCSRFHandling() {
        // Get CSRF token
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
                         document.querySelector('meta[name=csrf-token]')?.getAttribute('content');
        
        if (!csrfToken) return;
        
        // Add CSRF token to all AJAX requests
        $.ajaxSetup({
            beforeSend: function(xhr, settings) {
                if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
                    xhr.setRequestHeader("X-CSRFToken", csrfToken);
                }
            }
        });
        
        // Add CSRF token to fetch requests
        const originalFetch = window.fetch;
        window.fetch = function(url, options = {}) {
            if (options.method && !/^(GET|HEAD|OPTIONS|TRACE)$/i.test(options.method)) {
                options.headers = {
                    'X-CSRFToken': csrfToken,
                    ...options.headers
                };
            }
            return originalFetch(url, options);
        };
    }
    
    setupFormUtilities() {
        // Add form reset functionality
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-action="reset-form"]')) {
                const formId = e.target.getAttribute('data-target');
                const form = document.querySelector(formId);
                if (form) {
                    this.resetForm(form);
                }
            }
        });
        
        // Add form validation trigger
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-action="validate-form"]')) {
                const formId = e.target.getAttribute('data-target');
                const form = document.querySelector(formId);
                if (form && this.validationSystem) {
                    this.validationSystem.validate(form);
                }
            }
        });
    }
    
    resetForm(form) {
        // Reset form data
        form.reset();
        
        // Clear validation state
        if (this.validationSystem) {
            this.validationSystem.reset(form);
        }
        
        // Reset custom elements
        const statusIndicator = form.querySelector('.form-status-indicator');
        if (statusIndicator) {
            statusIndicator.querySelectorAll('.status-item').forEach(item => {
                item.style.display = 'none';
            });
        }
        
        const validationSummary = form.querySelector('.validation-summary');
        if (validationSummary) {
            validationSummary.style.display = 'none';
        }
        
        // Reset character counters
        const counters = form.querySelectorAll('.character-counter .current');
        counters.forEach(counter => {
            counter.textContent = '0';
        });
    }
    
    setupFileUploadEnhancements() {
        const fileInputs = document.querySelectorAll('input[type="file"]');
        
        fileInputs.forEach(input => {
            this.enhanceFileInput(input);
        });
    }
    
    enhanceFileInput(input) {
        // Add drag and drop functionality
        const container = input.closest('.form-group, .mb-3') || input.parentElement;
        
        container.addEventListener('dragover', (e) => {
            e.preventDefault();
            container.classList.add('drag-over');
        });
        
        container.addEventListener('dragleave', (e) => {
            e.preventDefault();
            container.classList.remove('drag-over');
        });
        
        container.addEventListener('drop', (e) => {
            e.preventDefault();
            container.classList.remove('drag-over');
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                input.files = files;
                input.dispatchEvent(new Event('change'));
            }
        });
        
        // Add file preview
        input.addEventListener('change', (e) => {
            this.showFilePreview(input, e.target.files);
        });
    }
    
    showFilePreview(input, files) {
        const container = input.closest('.form-group, .mb-3') || input.parentElement;
        
        // Remove existing preview
        const existingPreview = container.querySelector('.file-preview');
        if (existingPreview) {
            existingPreview.remove();
        }
        
        if (files.length === 0) return;
        
        const preview = document.createElement('div');
        preview.className = 'file-preview mt-2';
        
        Array.from(files).forEach(file => {
            const fileItem = document.createElement('div');
            fileItem.className = 'file-item d-flex align-items-center mb-1';
            fileItem.innerHTML = `
                <i class="fas fa-file me-2"></i>
                <span class="file-name">${file.name}</span>
                <small class="file-size text-muted ms-2">(${this.formatFileSize(file.size)})</small>
            `;
            preview.appendChild(fileItem);
        });
        
        container.appendChild(preview);
    }
    
    formatFileSize(bytes) {
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        if (bytes === 0) return '0 Bytes';
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
    }
    
    setupConnectionMonitoring() {
        if (!this.networkHandler) return;
        
        // Monitor connection status and update forms accordingly
        window.addEventListener('online', () => {
            this.enableForms();
        });
        
        window.addEventListener('offline', () => {
            this.disableForms();
        });
    }
    
    enableForms() {
        this.forms.forEach(form => {
            const submitButtons = form.querySelectorAll('button[type="submit"], input[type="submit"]');
            submitButtons.forEach(button => {
                button.disabled = false;
                button.title = '';
            });
        });
    }
    
    disableForms() {
        this.forms.forEach(form => {
            const submitButtons = form.querySelectorAll('button[type="submit"], input[type="submit"]');
            submitButtons.forEach(button => {
                button.disabled = true;
                button.title = 'Cannot submit while offline';
            });
        });
    }
    
    // Public API
    getFormValidationStatus(formId) {
        const form = document.querySelector(`#${formId}`);
        if (!form || !this.validationSystem) return null;
        
        return this.validationSystem.isValid(form);
    }
    
    validateForm(formId) {
        const form = document.querySelector(`#${formId}`);
        if (!form || !this.validationSystem) return false;
        
        return this.validationSystem.validate(form);
    }
    
    resetFormValidation(formId) {
        const form = document.querySelector(`#${formId}`);
        if (!form) return;
        
        this.resetForm(form);
    }
    
    addCustomValidator(formId, validatorFunction) {
        if (this.validationSystem) {
            this.validationSystem.addFormValidator(formId, validatorFunction);
        }
    }
}

// Initialize validation integration
const validationIntegration = new ValidationIntegration();

// Export to global scope
window.ValidationIntegration = ValidationIntegration;
window.validationIntegration = validationIntegration;

// Add CSS styles
const style = document.createElement('style');
style.textContent = `
.form-status-indicator {
    margin-bottom: 1rem;
    padding: 0.75rem;
    border-radius: 0.375rem;
    background-color: #f8f9fa;
    border: 1px solid #dee2e6;
}

.form-status-indicator .status-item {
    display: none;
    align-items: center;
    font-size: 0.875rem;
}

.form-status-indicator .status-item i {
    margin-right: 0.5rem;
}

.character-counter {
    text-align: right;
    margin-top: 0.25rem;
}

.validation-summary {
    margin-bottom: 1rem;
}

.validation-summary .error-list {
    margin-bottom: 0;
}

.file-preview {
    border: 1px solid #dee2e6;
    border-radius: 0.375rem;
    padding: 0.5rem;
    background-color: #f8f9fa;
}

.file-item {
    font-size: 0.875rem;
}

.file-item .file-name {
    flex-grow: 1;
    word-break: break-all;
}

.drag-over {
    border-color: #007bff !important;
    background-color: rgba(0, 123, 255, 0.1) !important;
}

.validation-enhanced .form-control:focus {
    box-shadow: 0 0 0 0.2rem rgba(0, 123, 255, 0.25);
}

.validation-enhanced .is-valid {
    border-color: #28a745;
    background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 8 8'%3e%3cpath fill='%2328a745' d='m2.3 6.73.4.42c.2.18.5.18.7 0L6.7 4.1c.2-.18.2-.48 0-.66L6.3 3c-.2-.18-.5-.18-.7 0L3.9 4.7l-.4-.42c-.2-.18-.5-.18-.7 0L2.3 4.7c-.2.18-.2.48 0 .66z'/%3e%3c/svg%3e");
    background-repeat: no-repeat;
    background-position: right calc(0.375em + 0.1875rem) center;
    background-size: calc(0.75em + 0.375rem) calc(0.75em + 0.375rem);
}

.validation-enhanced .is-invalid {
    border-color: #dc3545;
    background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 12' width='12' height='12' fill='none' stroke='%23dc3545'%3e%3ccircle cx='6' cy='6' r='4.5'/%3e%3cpath d='m5.8 4.6 2.4 2.4M8.2 4.6l-2.4 2.4'/%3e%3c/svg%3e");
    background-repeat: no-repeat;
    background-position: right calc(0.375em + 0.1875rem) center;
    background-size: calc(0.75em + 0.375rem) calc(0.75em + 0.375rem);
}
`;
document.head.appendChild(style);

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ValidationIntegration;
} 