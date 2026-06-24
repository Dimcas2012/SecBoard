/**
 * Comprehensive Client-Side Validation System
 * Provides real-time validation for all form inputs with multi-language support
 */

class ValidationSystem {
    constructor() {
        this.validators = new Map();
        this.validationRules = new Map();
        this.debounceTimers = new Map();
        this.customValidators = new Map();
        this.init();
    }

    init() {
        this.setupDefaultValidators();
        this.setupEventListeners();
        this.loadLanguageStrings();
    }

    setupDefaultValidators() {
        // Required field validator
        this.validators.set('required', (value, element) => {
            const trimmed = value.trim();
            return trimmed.length > 0;
        });

        // Email validator
        this.validators.set('email', (value, element) => {
            if (!value) return true; // Optional field
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            return emailRegex.test(value);
        });

        // Minimum length validator
        this.validators.set('minLength', (value, element) => {
            const minLength = parseInt(element.dataset.minLength || '0');
            return value.length >= minLength;
        });

        // Maximum length validator
        this.validators.set('maxLength', (value, element) => {
            const maxLength = parseInt(element.dataset.maxLength || '999999');
            return value.length <= maxLength;
        });

        // Date validator
        this.validators.set('date', (value, element) => {
            if (!value) return true; // Optional field
            const date = new Date(value);
            return !isNaN(date.getTime());
        });

        // Time validator
        this.validators.set('time', (value, element) => {
            if (!value) return true; // Optional field
            const timeRegex = /^([01]?[0-9]|2[0-3]):[0-5][0-9]$/;
            return timeRegex.test(value);
        });

        // Number validator
        this.validators.set('number', (value, element) => {
            if (!value) return true; // Optional field
            return !isNaN(parseFloat(value));
        });

        // Phone validator
        this.validators.set('phone', (value, element) => {
            if (!value) return true; // Optional field
            const phoneRegex = /^[\+]?[1-9][\d]{0,15}$/;
            return phoneRegex.test(value.replace(/[\s\-\(\)]/g, ''));
        });

        // URL validator
        this.validators.set('url', (value, element) => {
            if (!value) return true; // Optional field
            try {
                new URL(value);
                return true;
            } catch {
                return false;
            }
        });

        // File type validator
        this.validators.set('fileType', (value, element) => {
            if (!element.files || element.files.length === 0) return true;
            const allowedTypes = (element.dataset.allowedTypes || '').split(',');
            if (allowedTypes.length === 0) return true;
            
            for (let file of element.files) {
                const fileType = file.type.toLowerCase();
                const fileName = file.name.toLowerCase();
                let isValid = false;
                
                for (let type of allowedTypes) {
                    type = type.trim().toLowerCase();
                    if (type.startsWith('.')) {
                        // Extension check
                        if (fileName.endsWith(type)) {
                            isValid = true;
                            break;
                        }
                    } else {
                        // MIME type check
                        if (fileType.includes(type)) {
                            isValid = true;
                            break;
                        }
                    }
                }
                
                if (!isValid) return false;
            }
            return true;
        });

        // File size validator
        this.validators.set('fileSize', (value, element) => {
            if (!element.files || element.files.length === 0) return true;
            const maxSize = parseInt(element.dataset.maxSize || '10485760'); // 10MB default
            
            for (let file of element.files) {
                if (file.size > maxSize) return false;
            }
            return true;
        });

        // Pattern validator
        this.validators.set('pattern', (value, element) => {
            if (!value) return true; // Optional field
            const pattern = element.dataset.pattern || element.pattern;
            if (!pattern) return true;
            const regex = new RegExp(pattern);
            return regex.test(value);
        });

        // Custom range validator
        this.validators.set('range', (value, element) => {
            if (!value) return true; // Optional field
            const num = parseFloat(value);
            if (isNaN(num)) return false;
            
            const min = parseFloat(element.dataset.min || element.min);
            const max = parseFloat(element.dataset.max || element.max);
            
            if (!isNaN(min) && num < min) return false;
            if (!isNaN(max) && num > max) return false;
            
            return true;
        });

        // Date range validator
        this.validators.set('dateRange', (value, element) => {
            if (!value) return true; // Optional field
            const date = new Date(value);
            if (isNaN(date.getTime())) return false;
            
            const minDate = element.dataset.minDate ? new Date(element.dataset.minDate) : null;
            const maxDate = element.dataset.maxDate ? new Date(element.dataset.maxDate) : null;
            
            if (minDate && date < minDate) return false;
            if (maxDate && date > maxDate) return false;
            
            return true;
        });

        // Confirmation validator (for password confirmation, etc.)
        this.validators.set('confirmation', (value, element) => {
            const targetId = element.dataset.confirmationTarget;
            if (!targetId) return true;
            
            const targetElement = document.getElementById(targetId);
            if (!targetElement) return true;
            
            return value === targetElement.value;
        });
    }

    setupEventListeners() {
        // Listen for form inputs
        document.addEventListener('input', (e) => {
            if (e.target.matches('[data-validate]')) {
                this.debounceValidation(e.target);
            }
        });

        // Listen for form changes
        document.addEventListener('change', (e) => {
            if (e.target.matches('[data-validate]')) {
                this.validateField(e.target);
            }
        });

        // Listen for form submissions
        document.addEventListener('submit', (e) => {
            if (e.target.matches('[data-validate-form]')) {
                if (!this.validateForm(e.target)) {
                    e.preventDefault();
                    e.stopPropagation();
                }
            }
        });

        // Listen for blur events
        document.addEventListener('blur', (e) => {
            if (e.target.matches('[data-validate]')) {
                this.validateField(e.target);
            }
        }, true);
    }

    debounceValidation(element, delay = 300) {
        const fieldId = element.id || element.name || 'unknown';
        
        if (this.debounceTimers.has(fieldId)) {
            clearTimeout(this.debounceTimers.get(fieldId));
        }
        
        const timer = setTimeout(() => {
            this.validateField(element);
            this.debounceTimers.delete(fieldId);
        }, delay);
        
        this.debounceTimers.set(fieldId, timer);
    }

    validateField(element) {
        const rules = this.getValidationRules(element);
        const value = element.value || '';
        const errors = [];

        for (const rule of rules) {
            const validator = this.validators.get(rule.type) || this.customValidators.get(rule.type);
            if (validator && !validator(value, element)) {
                errors.push(this.getErrorMessage(rule.type, element, rule.params));
            }
        }

        this.displayFieldValidation(element, errors);
        return errors.length === 0;
    }

    getValidationRules(element) {
        const rules = [];
        const validateAttr = element.dataset.validate || '';
        
        if (validateAttr) {
            const ruleStrings = validateAttr.split('|');
            for (const ruleString of ruleStrings) {
                const [type, ...params] = ruleString.split(':');
                rules.push({ type: type.trim(), params: params.join(':') });
            }
        }

        // Add HTML5 validation attributes
        if (element.required) {
            rules.push({ type: 'required', params: '' });
        }
        if (element.type === 'email') {
            rules.push({ type: 'email', params: '' });
        }
        if (element.type === 'number') {
            rules.push({ type: 'number', params: '' });
        }
        if (element.type === 'date') {
            rules.push({ type: 'date', params: '' });
        }
        if (element.type === 'time') {
            rules.push({ type: 'time', params: '' });
        }
        if (element.type === 'url') {
            rules.push({ type: 'url', params: '' });
        }
        if (element.type === 'file') {
            rules.push({ type: 'fileType', params: '' });
            rules.push({ type: 'fileSize', params: '' });
        }

        return rules;
    }

    displayFieldValidation(element, errors) {
        // Remove existing validation classes and feedback
        element.classList.remove('is-valid', 'is-invalid');
        
        const existingFeedback = element.parentNode.querySelector('.invalid-feedback, .valid-feedback');
        if (existingFeedback) {
            existingFeedback.remove();
        }

        if (errors.length > 0) {
            // Field is invalid
            element.classList.add('is-invalid');
            
            const feedback = document.createElement('div');
            feedback.className = 'invalid-feedback';
            feedback.innerHTML = errors.join('<br>');
            
            element.parentNode.appendChild(feedback);
        } else if (element.value.trim() !== '') {
            // Field is valid and has content
            element.classList.add('is-valid');
            
            const feedback = document.createElement('div');
            feedback.className = 'valid-feedback';
            feedback.textContent = this.getSuccessMessage(element);
            
            element.parentNode.appendChild(feedback);
        }
    }

    validateForm(form) {
        const fields = form.querySelectorAll('[data-validate]');
        let isValid = true;
        const errors = [];

        for (const field of fields) {
            if (!this.validateField(field)) {
                isValid = false;
                errors.push({
                    field: field.name || field.id,
                    element: field,
                    message: field.parentNode.querySelector('.invalid-feedback')?.textContent || 'Invalid field'
                });
            }
        }

        // Cross-field validation
        const crossFieldErrors = this.validateCrossFields(form);
        if (crossFieldErrors.length > 0) {
            isValid = false;
            errors.push(...crossFieldErrors);
        }

        if (!isValid) {
            this.displayFormErrors(form, errors);
            // Focus on first invalid field
            const firstInvalidField = form.querySelector('.is-invalid');
            if (firstInvalidField) {
                firstInvalidField.focus();
            }
        }

        return isValid;
    }

    validateCrossFields(form) {
        const errors = [];
        
        // Date range validation
        const startDate = form.querySelector('[data-cross-validate="date-range-start"]');
        const endDate = form.querySelector('[data-cross-validate="date-range-end"]');
        
        if (startDate && endDate && startDate.value && endDate.value) {
            const start = new Date(startDate.value);
            const end = new Date(endDate.value);
            
            if (start > end) {
                errors.push({
                    field: 'date-range',
                    element: endDate,
                    message: this.getErrorMessage('dateRangeInvalid', endDate)
                });
            }
        }

        return errors;
    }

    displayFormErrors(form, errors) {
        // Remove existing form-level error display
        const existingAlert = form.querySelector('.validation-alert');
        if (existingAlert) {
            existingAlert.remove();
        }

        if (errors.length > 0) {
            const alert = document.createElement('div');
            alert.className = 'alert alert-danger validation-alert';
            alert.innerHTML = `
                <h6><i class="fas fa-exclamation-triangle me-2"></i>${this.getErrorMessage('formValidationFailed')}</h6>
                <ul class="mb-0">
                    ${errors.map(error => `<li>${error.message}</li>`).join('')}
                </ul>
            `;
            
            form.insertBefore(alert, form.firstChild);
        }
    }

    getErrorMessage(type, element, params = '') {
        const messages = this.getLanguageStrings();
        const fieldName = element?.dataset.fieldName || element?.placeholder || element?.name || 'Field';
        
        switch (type) {
            case 'required':
                return messages.required.replace('{field}', fieldName);
            case 'email':
                return messages.email.replace('{field}', fieldName);
            case 'minLength':
                const minLength = element?.dataset.minLength || params;
                return messages.minLength.replace('{field}', fieldName).replace('{min}', minLength);
            case 'maxLength':
                const maxLength = element?.dataset.maxLength || params;
                return messages.maxLength.replace('{field}', fieldName).replace('{max}', maxLength);
            case 'date':
                return messages.date.replace('{field}', fieldName);
            case 'time':
                return messages.time.replace('{field}', fieldName);
            case 'number':
                return messages.number.replace('{field}', fieldName);
            case 'phone':
                return messages.phone.replace('{field}', fieldName);
            case 'url':
                return messages.url.replace('{field}', fieldName);
            case 'fileType':
                const allowedTypes = element?.dataset.allowedTypes || '';
                return messages.fileType.replace('{field}', fieldName).replace('{types}', allowedTypes);
            case 'fileSize':
                const maxSize = this.formatFileSize(element?.dataset.maxSize || '10485760');
                return messages.fileSize.replace('{field}', fieldName).replace('{size}', maxSize);
            case 'pattern':
                return messages.pattern.replace('{field}', fieldName);
            case 'range':
                const min = element?.dataset.min || element?.min || '';
                const max = element?.dataset.max || element?.max || '';
                return messages.range.replace('{field}', fieldName).replace('{min}', min).replace('{max}', max);
            case 'dateRange':
                return messages.dateRange.replace('{field}', fieldName);
            case 'confirmation':
                return messages.confirmation.replace('{field}', fieldName);
            case 'dateRangeInvalid':
                return messages.dateRangeInvalid;
            case 'formValidationFailed':
                return messages.formValidationFailed;
            default:
                return messages.default.replace('{field}', fieldName);
        }
    }

    getSuccessMessage(element) {
        const messages = this.getLanguageStrings();
        const fieldName = element?.dataset.fieldName || element?.placeholder || element?.name || 'Field';
        return messages.success.replace('{field}', fieldName);
    }

    formatFileSize(bytes) {
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        if (bytes === 0) return '0 Bytes';
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
    }

    loadLanguageStrings() {
        // Default to Ukrainian, but can be overridden
        const currentLang = document.documentElement.lang || 'uk';
        this.currentLanguage = currentLang;
    }

    getLanguageStrings() {
        const lang = this.currentLanguage || 'uk';
        
        const strings = {
            uk: {
                required: "Поле '{field}' є обов'язковим",
                email: "Поле '{field}' повинно містити правильну email адресу",
                minLength: "Поле '{field}' повинно містити принаймні {min} символів",
                maxLength: "Поле '{field}' не повинно перевищувати {max} символів",
                date: "Поле '{field}' повинно містити правильну дату",
                time: "Поле '{field}' повинно містити правильний час",
                number: "Поле '{field}' повинно містити число",
                phone: "Поле '{field}' повинно містити правильний номер телефону",
                url: "Поле '{field}' повинно містити правильний URL",
                fileType: "Поле '{field}' повинно містити файл одного з типів: {types}",
                fileSize: "Файл у полі '{field}' не повинен перевищувати {size}",
                pattern: "Поле '{field}' має неправильний формат",
                range: "Поле '{field}' повинно бути між {min} та {max}",
                dateRange: "Поле '{field}' повинно бути у допустимому діапазоні дат",
                confirmation: "Поле '{field}' не співпадає з підтвердженням",
                dateRangeInvalid: "Кінцева дата не може бути раніше початкової",
                formValidationFailed: "Форма містить помилки",
                success: "✓ Правильно",
                default: "Поле '{field}' має неправильне значення"
            },
            en: {
                required: "The '{field}' field is required",
                email: "The '{field}' field must contain a valid email address",
                minLength: "The '{field}' field must contain at least {min} characters",
                maxLength: "The '{field}' field must not exceed {max} characters",
                date: "The '{field}' field must contain a valid date",
                time: "The '{field}' field must contain a valid time",
                number: "The '{field}' field must contain a number",
                phone: "The '{field}' field must contain a valid phone number",
                url: "The '{field}' field must contain a valid URL",
                fileType: "The '{field}' field must contain a file of one of these types: {types}",
                fileSize: "The file in '{field}' field must not exceed {size}",
                pattern: "The '{field}' field has an invalid format",
                range: "The '{field}' field must be between {min} and {max}",
                dateRange: "The '{field}' field must be within the allowed date range",
                confirmation: "The '{field}' field does not match the confirmation",
                dateRangeInvalid: "End date cannot be earlier than start date",
                formValidationFailed: "The form contains errors",
                success: "✓ Valid",
                default: "The '{field}' field has an invalid value"
            },
            ru: {
                required: "Поле '{field}' обязательно для заполнения",
                email: "Поле '{field}' должно содержать правильный email адрес",
                minLength: "Поле '{field}' должно содержать не менее {min} символов",
                maxLength: "Поле '{field}' не должно превышать {max} символов",
                date: "Поле '{field}' должно содержать правильную дату",
                time: "Поле '{field}' должно содержать правильное время",
                number: "Поле '{field}' должно содержать число",
                phone: "Поле '{field}' должно содержать правильный номер телефона",
                url: "Поле '{field}' должно содержать правильный URL",
                fileType: "Поле '{field}' должно содержать файл одного из типов: {types}",
                fileSize: "Файл в поле '{field}' не должен превышать {size}",
                pattern: "Поле '{field}' имеет неправильный формат",
                range: "Поле '{field}' должно быть между {min} и {max}",
                dateRange: "Поле '{field}' должно быть в допустимом диапазоне дат",
                confirmation: "Поле '{field}' не совпадает с подтверждением",
                dateRangeInvalid: "Конечная дата не может быть раньше начальной",
                formValidationFailed: "Форма содержит ошибки",
                success: "✓ Правильно",
                default: "Поле '{field}' имеет неправильное значение"
            }
        };

        return strings[lang] || strings.uk;
    }

    // Public API methods
    addCustomValidator(name, validator) {
        this.customValidators.set(name, validator);
    }

    validateFieldById(fieldId) {
        const element = document.getElementById(fieldId);
        if (element) {
            return this.validateField(element);
        }
        return false;
    }

    validateFormById(formId) {
        const form = document.getElementById(formId);
        if (form) {
            return this.validateForm(form);
        }
        return false;
    }

    clearValidation(element) {
        element.classList.remove('is-valid', 'is-invalid');
        const feedback = element.parentNode.querySelector('.invalid-feedback, .valid-feedback');
        if (feedback) {
            feedback.remove();
        }
    }

    clearFormValidation(form) {
        const fields = form.querySelectorAll('[data-validate]');
        fields.forEach(field => this.clearValidation(field));
        
        const alert = form.querySelector('.validation-alert');
        if (alert) {
            alert.remove();
        }
    }
}

// Initialize the validation system when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    window.validationSystem = new ValidationSystem();
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ValidationSystem;
}
