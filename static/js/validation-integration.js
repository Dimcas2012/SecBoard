/**
 * Validation Integration Script
 * Integrates all validation improvements with existing templates
 */

class ValidationIntegration {
    constructor() {
        this.systems = {};
        this.init();
    }

    init() {
        this.initializeSystems();
        this.setupFormEnhancements();
        this.setupGlobalErrorHandling();
        this.setupCSRFProtection();
        this.setupFileUploadValidation();
        this.setupConnectionStatusMonitoring();
        this.enhanceExistingForms();
        this.addCustomStyles();
    }

    initializeSystems() {
        // Wait for other systems to initialize
        setTimeout(() => {
            this.systems.validation = window.validationSystem;
            this.systems.errorDisplay = window.errorDisplaySystem;
            this.systems.scheduleValidation = window.scheduleValidation;
            this.systems.networkHandler = window.networkErrorHandler;
            
            console.log('Validation Integration: Systems initialized', {
                validation: !!this.systems.validation,
                errorDisplay: !!this.systems.errorDisplay,
                scheduleValidation: !!this.systems.scheduleValidation,
                networkHandler: !!this.systems.networkHandler
            });
        }, 100);
    }

    setupFormEnhancements() {
        // Enhance forms as they appear
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (node.nodeType === Node.ELEMENT_NODE) {
                        if (node.tagName === 'FORM') {
                            this.enhanceForm(node);
                        } else {
                            const forms = node.querySelectorAll('form');
                            forms.forEach(form => this.enhanceForm(form));
                        }
                    }
                });
            });
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });

        // Enhance existing forms
        document.querySelectorAll('form').forEach(form => {
            this.enhanceForm(form);
        });
    }

    enhanceForm(form) {
        if (form.hasAttribute('data-validation-enhanced')) return;
        
        form.setAttribute('data-validation-enhanced', 'true');
        
        // Add validation attributes based on field types and constraints
        const fields = form.querySelectorAll('input, select, textarea');
        fields.forEach(field => {
            this.enhanceField(field);
        });
        
        // Add form-level validation
        form.addEventListener('submit', (e) => {
            this.handleFormSubmission(e);
        });
        
        // Add real-time validation
        form.addEventListener('input', (e) => {
            if (this.systems.validation && e.target.matches('input, select, textarea')) {
                this.systems.validation.validateField(e.target);
            }
        });
        
        // Add form status indicator
        this.addFormStatusIndicator(form);
    }

    enhanceField(field) {
        const validationRules = this.getFieldValidationRules(field);
        if (validationRules.length > 0) {
            field.setAttribute('data-validate', validationRules.join('|'));
        }
        
        // Add field-specific enhancements
        if (field.type === 'email') {
            field.setAttribute('data-validate', (field.getAttribute('data-validate') || '') + '|email');
        }
        
        if (field.type === 'file') {
            this.enhanceFileField(field);
        }
        
        // Add label association if missing
        const label = this.getFieldLabel(field);
        if (label && !field.getAttribute('aria-label') && !field.getAttribute('aria-labelledby')) {
            field.setAttribute('aria-label', label);
        }
        
        // Add placeholder if appropriate
        if (!field.placeholder && field.type !== 'file' && field.type !== 'checkbox' && field.type !== 'radio') {
            const placeholder = this.generatePlaceholder(field);
            if (placeholder) {
                field.placeholder = placeholder;
            }
        }
    }

    getFieldValidationRules(field) {
        const rules = [];
        
        // Required fields
        if (field.required || field.hasAttribute('required')) {
            rules.push('required');
        }
        
        // Length constraints
        if (field.minLength) {
            rules.push(`minLength:${field.minLength}`);
        }
        if (field.maxLength) {
            rules.push(`maxLength:${field.maxLength}`);
        }
        
        // Number constraints
        if (field.type === 'number') {
            if (field.min !== '') {
                rules.push(`min:${field.min}`);
            }
            if (field.max !== '') {
                rules.push(`max:${field.max}`);
            }
            if (field.step !== '') {
                rules.push(`step:${field.step}`);
            }
        }
        
        // Pattern matching
        if (field.pattern) {
            rules.push(`pattern:${field.pattern}`);
        }
        
        // Field-specific rules based on name/id
        const fieldName = field.name || field.id || '';
        if (fieldName.includes('email')) {
            rules.push('email');
        }
        if (fieldName.includes('phone')) {
            rules.push('phone');
        }
        if (fieldName.includes('date')) {
            rules.push('date');
        }
        if (fieldName.includes('time')) {
            rules.push('time');
        }
        if (fieldName.includes('url')) {
            rules.push('url');
        }
        
        return rules;
    }

    getFieldLabel(field) {
        // Try to find associated label
        const labelElement = document.querySelector(`label[for="${field.id}"]`);
        if (labelElement) {
            return labelElement.textContent.trim();
        }
        
        // Try parent label
        const parentLabel = field.closest('label');
        if (parentLabel) {
            return parentLabel.textContent.replace(field.value, '').trim();
        }
        
        // Try previous sibling
        let sibling = field.previousElementSibling;
        while (sibling) {
            if (sibling.tagName === 'LABEL') {
                return sibling.textContent.trim();
            }
            sibling = sibling.previousElementSibling;
        }
        
        return null;
    }

    enhanceFileField(field) {
        // Add file validation attributes
        const accept = field.accept;
        if (accept) {
            const allowedTypes = accept.split(',').map(type => type.trim());
            field.setAttribute('data-validate', 
                (field.getAttribute('data-validate') || '') + `|fileType:${allowedTypes.join(',')}`);
        }
        
        // Add file size limit (default 10MB)
        if (!field.getAttribute('data-validate')?.includes('fileSize')) {
            field.setAttribute('data-validate', 
                (field.getAttribute('data-validate') || '') + '|fileSize:10485760');
        }
        
        // Add file preview
        field.addEventListener('change', (e) => {
            this.showFilePreview(e.target);
        });
    }

    handleFormSubmission(event) {
        const form = event.target;
        
        // Validate form if validation system is available
        if (this.systems.validation) {
            const isValid = this.systems.validation.validateForm(form);
            if (!isValid) {
                event.preventDefault();
                
                if (this.systems.errorDisplay) {
                    this.systems.errorDisplay.showValidationError(
                        'Form validation failed',
                        'Please correct the errors in the form before submitting.'
                    );
                }
                return false;
            }
        }
        
        // Show loading state
        this.showFormLoadingState(form);
        
        // Store form submission for potential retry
        window.lastFormSubmission = () => {
            this.hideFormLoadingState(form);
            form.submit();
        };
        
        return true;
    }

    showFormLoadingState(form) {
        const submitButtons = form.querySelectorAll('button[type="submit"], input[type="submit"]');
        submitButtons.forEach(button => {
            button.disabled = true;
            button.dataset.originalText = button.textContent || button.value;
            
            if (button.tagName === 'BUTTON') {
                button.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Processing...';
            } else {
                button.value = 'Processing...';
            }
        });
        
        // Add loading overlay
        const overlay = document.createElement('div');
        overlay.className = 'form-loading-overlay';
        overlay.innerHTML = '<div class="spinner-border text-primary" role="status"></div>';
        form.style.position = 'relative';
        form.appendChild(overlay);
    }

    hideFormLoadingState(form) {
        const submitButtons = form.querySelectorAll('button[type="submit"], input[type="submit"]');
        submitButtons.forEach(button => {
            button.disabled = false;
            
            if (button.dataset.originalText) {
                if (button.tagName === 'BUTTON') {
                    button.textContent = button.dataset.originalText;
                } else {
                    button.value = button.dataset.originalText;
                }
                delete button.dataset.originalText;
            }
        });
        
        // Remove loading overlay
        const overlay = form.querySelector('.form-loading-overlay');
        if (overlay) {
            overlay.remove();
        }
    }

    setupGlobalErrorHandling() {
        // Handle uncaught errors
        window.addEventListener('error', (event) => {
            if (this.systems.errorDisplay) {
                this.systems.errorDisplay.showSystemError(
                    'JavaScript Error',
                    `${event.message} at ${event.filename}:${event.lineno}`
                );
            }
        });
        
        // Handle unhandled promise rejections
        window.addEventListener('unhandledrejection', (event) => {
            if (this.systems.errorDisplay) {
                this.systems.errorDisplay.showSystemError(
                    'Promise Rejection',
                    event.reason?.message || 'Unhandled promise rejection'
                );
            }
        });
        
        // Override fetch for automatic error handling
        const originalFetch = window.fetch;
        window.fetch = async (...args) => {
            try {
                const response = await originalFetch(...args);
                
                if (!response.ok && this.systems.networkHandler) {
                    return this.systems.networkHandler.handleHttpError(response, args[0], args[1]);
                }
                
                return response;
            } catch (error) {
                if (this.systems.networkHandler) {
                    return this.systems.networkHandler.handleNetworkError(error, args[0], args[1]);
                }
                throw error;
            }
        };
    }

    setupCSRFProtection() {
        // Add CSRF token to all forms
        const csrfToken = this.getCSRFToken();
        if (csrfToken) {
            document.querySelectorAll('form').forEach(form => {
                if (!form.querySelector('[name="csrfmiddlewaretoken"]')) {
                    const csrfInput = document.createElement('input');
                    csrfInput.type = 'hidden';
                    csrfInput.name = 'csrfmiddlewaretoken';
                    csrfInput.value = csrfToken;
                    form.appendChild(csrfInput);
                }
            });
        }
        
        // Add CSRF token to AJAX requests
        if (typeof $ !== 'undefined') {
            $.ajaxSetup({
                beforeSend: function(xhr, settings) {
                    if (!this.crossDomain && csrfToken) {
                        xhr.setRequestHeader("X-CSRFToken", csrfToken);
                    }
                }
            });
        }
    }

    getCSRFToken() {
        // Try to get CSRF token from various sources
        const tokenInput = document.querySelector('[name=csrfmiddlewaretoken]');
        if (tokenInput) {
            return tokenInput.value;
        }
        
        const tokenMeta = document.querySelector('meta[name=csrf-token]');
        if (tokenMeta) {
            return tokenMeta.getAttribute('content');
        }
        
        // Try to get from cookie
        const cookieValue = document.cookie
            .split('; ')
            .find(row => row.startsWith('csrftoken='))
            ?.split('=')[1];
        
        return cookieValue;
    }

    setupFileUploadValidation() {
        document.addEventListener('change', (e) => {
            if (e.target.type === 'file') {
                this.validateFileUpload(e.target);
            }
        });
    }

    validateFileUpload(fileInput) {
        const files = Array.from(fileInput.files);
        const errors = [];
        
        // Get validation rules
        const validateAttr = fileInput.getAttribute('data-validate') || '';
        const rules = validateAttr.split('|').reduce((acc, rule) => {
            const [key, value] = rule.split(':');
            acc[key] = value;
            return acc;
        }, {});
        
        files.forEach(file => {
            // File size validation
            if (rules.fileSize) {
                const maxSize = parseInt(rules.fileSize);
                if (file.size > maxSize) {
                    errors.push(`File "${file.name}" is too large. Maximum size: ${this.formatFileSize(maxSize)}.`);
                }
            }
            
            // File type validation
            if (rules.fileType) {
                const allowedTypes = rules.fileType.split(',');
                const fileName = file.name.toLowerCase();
                const fileType = file.type.toLowerCase();
                
                let isValidType = false;
                for (let type of allowedTypes) {
                    type = type.trim().toLowerCase();
                    if (type.startsWith('.')) {
                        if (fileName.endsWith(type)) {
                            isValidType = true;
                            break;
                        }
                    } else if (fileType.includes(type)) {
                        isValidType = true;
                        break;
                    }
                }
                
                if (!isValidType) {
                    errors.push(`File "${file.name}" has an invalid type. Allowed types: ${allowedTypes.join(', ')}.`);
                }
            }
        });

        if (errors.length > 0 && this.systems.errorDisplay) {
            this.systems.errorDisplay.showFileError(
                'File validation failed',
                errors.join('\n')
            );
        }

        return errors.length === 0;
    }

    formatFileSize(bytes) {
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        if (bytes === 0) return '0 Bytes';
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
    }

    setupConnectionStatusMonitoring() {
        // Add connection status indicator to forms
        const forms = document.querySelectorAll('form');
        forms.forEach(form => {
            this.addConnectionStatusToForm(form);
        });

        // Monitor connection status changes
        if (this.systems.networkHandler) {
            // Update form states based on connection
            setInterval(() => {
                this.updateFormConnectionStatus();
            }, 5000); // Check every 5 seconds
        }
    }

    addConnectionStatusToForm(form) {
        if (form.querySelector('.connection-status')) return;

        const statusIndicator = document.createElement('div');
        statusIndicator.className = 'connection-status small text-muted mt-2';
        statusIndicator.innerHTML = `
            <i class="fas fa-wifi me-1"></i>
            <span class="status-text">Connected</span>
        `;
        
        form.appendChild(statusIndicator);
    }

    updateFormConnectionStatus() {
        const isOnline = this.systems.networkHandler ? 
            this.systems.networkHandler.isConnectionOnline() : 
            navigator.onLine;
        
        const statusIndicators = document.querySelectorAll('.connection-status');
        statusIndicators.forEach(indicator => {
            const icon = indicator.querySelector('i');
            const text = indicator.querySelector('.status-text');
            
            if (isOnline) {
                icon.className = 'fas fa-wifi me-1 text-success';
                text.textContent = 'Connected';
                text.className = 'status-text text-success';
            } else {
                icon.className = 'fas fa-wifi me-1 text-danger';
                text.textContent = 'Offline';
                text.className = 'status-text text-danger';
            }
        });
    }

    enhanceExistingForms() {
        // Add character counters to text areas
        const textareas = document.querySelectorAll('textarea[maxlength]');
        textareas.forEach(textarea => {
            this.addCharacterCounter(textarea);
        });

        // Add form validation summary
        const forms = document.querySelectorAll('form[data-validate-form]');
        forms.forEach(form => {
            this.addValidationSummary(form);
        });
    }

    addCharacterCounter(textarea) {
        if (textarea.nextElementSibling?.classList.contains('character-counter')) return;

        const counter = document.createElement('div');
        counter.className = 'character-counter small text-muted mt-1';
        counter.innerHTML = `
            <span class="current">0</span>/<span class="max">${textarea.maxLength}</span> characters
        `;
        
        textarea.parentNode.insertBefore(counter, textarea.nextSibling);
        
        const updateCounter = () => {
            const current = textarea.value.length;
            const max = textarea.maxLength;
            const currentSpan = counter.querySelector('.current');
            
            currentSpan.textContent = current;
            
            if (current > max * 0.9) {
                counter.className = 'character-counter small text-warning mt-1';
            } else if (current === max) {
                counter.className = 'character-counter small text-danger mt-1';
            } else {
                counter.className = 'character-counter small text-muted mt-1';
            }
        };
        
        textarea.addEventListener('input', updateCounter);
        updateCounter();
    }

    addValidationSummary(form) {
        if (form.querySelector('.validation-summary')) return;

        const summary = document.createElement('div');
        summary.className = 'validation-summary alert alert-info d-none';
        summary.innerHTML = `
            <h6><i class="fas fa-info-circle me-2"></i>Form Status</h6>
            <div class="summary-content">
                <div class="valid-fields">Valid fields: <span class="count">0</span></div>
                <div class="invalid-fields">Invalid fields: <span class="count">0</span></div>
            </div>
        `;
        
        form.insertBefore(summary, form.firstChild);
        
        // Update summary periodically
        setInterval(() => {
            this.updateValidationSummary(form);
        }, 2000);
    }

    updateValidationSummary(form) {
        const summary = form.querySelector('.validation-summary');
        if (!summary) return;

        const validFields = form.querySelectorAll('.is-valid').length;
        const invalidFields = form.querySelectorAll('.is-invalid').length;
        const totalFields = form.querySelectorAll('input, select, textarea').length;

        const validCount = summary.querySelector('.valid-fields .count');
        const invalidCount = summary.querySelector('.invalid-fields .count');

        if (validCount) validCount.textContent = validFields;
        if (invalidCount) invalidCount.textContent = invalidFields;

        // Show/hide summary based on validation state
        if (validFields > 0 || invalidFields > 0) {
            summary.classList.remove('d-none');
            
            if (invalidFields > 0) {
                summary.className = 'validation-summary alert alert-warning';
            } else if (validFields === totalFields) {
                summary.className = 'validation-summary alert alert-success';
            } else {
                summary.className = 'validation-summary alert alert-info';
            }
        } else {
            summary.classList.add('d-none');
        }
    }

    addFormStatusIndicator(form) {
        if (form.querySelector('.form-status-indicator')) return;

        const indicator = document.createElement('div');
        indicator.className = 'form-status-indicator mt-2';
        indicator.innerHTML = `
            <div class="d-flex align-items-center">
                <div class="form-status-icon me-2">
                    <i class="fas fa-circle text-secondary"></i>
                </div>
                <div class="form-status-text small text-muted">
                    Form ready
                </div>
            </div>
        `;
        
        form.appendChild(indicator);
        
        // Update status based on form state
        const updateStatus = () => {
            const validFields = form.querySelectorAll('.is-valid').length;
            const invalidFields = form.querySelectorAll('.is-invalid').length;
            const totalFields = form.querySelectorAll('input, select, textarea').length;
            
            const icon = indicator.querySelector('.form-status-icon i');
            const text = indicator.querySelector('.form-status-text');
            
            if (invalidFields > 0) {
                icon.className = 'fas fa-exclamation-circle text-danger';
                text.textContent = `${invalidFields} field${invalidFields > 1 ? 's' : ''} need${invalidFields === 1 ? 's' : ''} attention`;
                text.className = 'form-status-text small text-danger';
            } else if (validFields > 0 && validFields === totalFields) {
                icon.className = 'fas fa-check-circle text-success';
                text.textContent = 'Form is valid and ready to submit';
                text.className = 'form-status-text small text-success';
            } else if (validFields > 0) {
                icon.className = 'fas fa-clock text-warning';
                text.textContent = `${totalFields - validFields} field${totalFields - validFields > 1 ? 's' : ''} remaining`;
                text.className = 'form-status-text small text-warning';
            } else {
                icon.className = 'fas fa-circle text-secondary';
                text.textContent = 'Form ready';
                text.className = 'form-status-text small text-muted';
            }
        };
        
        form.addEventListener('input', updateStatus);
        form.addEventListener('change', updateStatus);
    }

    generatePlaceholder(field) {
        const fieldName = field.name || field.id || '';
        const fieldType = field.type;
        
        // Generate contextual placeholders
        if (fieldName.includes('name')) {
            return 'Enter name...';
        }
        if (fieldName.includes('email')) {
            return 'Enter email address...';
        }
        if (fieldName.includes('phone')) {
            return 'Enter phone number...';
        }
        if (fieldName.includes('description') || fieldName.includes('notes')) {
            return 'Enter description...';
        }
        if (fieldType === 'date') {
            return 'YYYY-MM-DD';
        }
        if (fieldType === 'time') {
            return 'HH:MM';
        }
        if (fieldType === 'number') {
            return 'Enter number...';
        }
        if (fieldType === 'url') {
            return 'https://example.com';
        }
        
        return null;
    }

    showFilePreview(fileInput) {
        const files = Array.from(fileInput.files);
        let preview = fileInput.parentNode.querySelector('.file-preview');
        
        if (!preview) {
            preview = document.createElement('div');
            preview.className = 'file-preview mt-2';
            fileInput.parentNode.appendChild(preview);
        }
        
        preview.innerHTML = '';
        
        files.forEach(file => {
            const fileItem = document.createElement('div');
            fileItem.className = 'file-preview-item d-flex align-items-center mb-1';
            
            fileItem.innerHTML = `
                <i class="fas fa-file me-2"></i>
                <span class="file-name me-2">${file.name}</span>
                <span class="file-size text-muted">(${this.formatFileSize(file.size)})</span>
            `;
            
            preview.appendChild(fileItem);
        });
    }

    addCustomStyles() {
        const validationIntegrationStyle = document.createElement('style');
        validationIntegrationStyle.textContent = `
            .form-loading-overlay {
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(255, 255, 255, 0.8);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 1000;
            }
            
            .character-counter {
                text-align: right;
            }
            
            .validation-summary {
                border-radius: 0.375rem;
            }
            
            .form-status-indicator {
                border-top: 1px solid #dee2e6;
                padding-top: 0.5rem;
            }
            
            .file-preview {
                border: 1px solid #dee2e6;
                border-radius: 0.375rem;
                padding: 0.5rem;
                background-color: #f8f9fa;
            }
            
            .file-preview-item {
                font-size: 0.875rem;
            }
            
            .connection-status {
                border-top: 1px solid #dee2e6;
                padding-top: 0.25rem;
            }
        `;
        document.head.appendChild(validationIntegrationStyle);
    }

    // Public API methods
    validateAllForms() {
        const forms = document.querySelectorAll('form[data-validate-form]');
        let allValid = true;
        
        forms.forEach(form => {
            if (!this.systems.validation.validateForm(form)) {
                allValid = false;
            }
        });
        
        return allValid;
    }

    clearAllValidation() {
        const forms = document.querySelectorAll('form[data-validate-form]');
        forms.forEach(form => {
            if (this.systems.validation) {
                this.systems.validation.clearFormValidation(form);
            }
        });
    }

    getValidationStatus() {
        const forms = document.querySelectorAll('form[data-validate-form]');
        const status = {
            totalForms: forms.length,
            validForms: 0,
            invalidForms: 0,
            totalFields: 0,
            validFields: 0,
            invalidFields: 0
        };

        forms.forEach(form => {
            const validFields = form.querySelectorAll('.is-valid').length;
            const invalidFields = form.querySelectorAll('.is-invalid').length;
            const totalFields = form.querySelectorAll('input, select, textarea').length;

            status.totalFields += totalFields;
            status.validFields += validFields;
            status.invalidFields += invalidFields;

            if (invalidFields === 0 && validFields > 0) {
                status.validForms++;
            } else if (invalidFields > 0) {
                status.invalidForms++;
            }
        });

        return status;
    }
}

// Initialize the validation integration system
document.addEventListener('DOMContentLoaded', function() {
    window.validationIntegration = new ValidationIntegration();
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ValidationIntegration;
}
