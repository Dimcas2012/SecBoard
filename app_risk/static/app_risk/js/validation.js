/**
 * SecBoard Risk Assessment - Client-Side Validation System
 * Comprehensive validation with real-time feedback and multi-language support
 */

class ValidationSystem {
    constructor(options = {}) {
        this.options = {
            debounceTime: 300,
            showSuccessIndicators: true,
            validateOnInput: true,
            validateOnBlur: true,
            autoFocus: true,
            language: 'uk',
            ...options
        };
        
        this.validators = new Map();
        this.formValidators = new Map();
        this.debounceTimers = new Map();
        this.validationResults = new Map();
        
        this.init();
    }
    
    init() {
        this.setupDefaultValidators();
        this.setupEventListeners();
        this.loadLanguage();
    }
    
    setupDefaultValidators() {
        // Required field validator
        this.addValidator('required', (value, field) => {
            const isEmpty = !value || value.toString().trim() === '';
            return {
                valid: !isEmpty,
                message: isEmpty ? this.getMessage('required', field) : null
            };
        });
        
        // Email validator
        this.addValidator('email', (value, field) => {
            if (!value) return { valid: true, message: null };
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            const isValid = emailRegex.test(value);
            return {
                valid: isValid,
                message: isValid ? null : this.getMessage('email', field)
            };
        });
        
        // URL validator
        this.addValidator('url', (value, field) => {
            if (!value) return { valid: true, message: null };
            try {
                new URL(value);
                return { valid: true, message: null };
            } catch {
                return { valid: false, message: this.getMessage('url', field) };
            }
        });
        
        // Minimum length validator
        this.addValidator('minLength', (value, field, params) => {
            if (!value) return { valid: true, message: null };
            const minLength = parseInt(params.minLength) || 0;
            const isValid = value.length >= minLength;
            return {
                valid: isValid,
                message: isValid ? null : this.getMessage('minLength', field, { minLength })
            };
        });
        
        // Maximum length validator
        this.addValidator('maxLength', (value, field, params) => {
            if (!value) return { valid: true, message: null };
            const maxLength = parseInt(params.maxLength) || 0;
            const isValid = value.length <= maxLength;
            return {
                valid: isValid,
                message: isValid ? null : this.getMessage('maxLength', field, { maxLength })
            };
        });
        
        // Pattern validator
        this.addValidator('pattern', (value, field, params) => {
            if (!value) return { valid: true, message: null };
            const pattern = new RegExp(params.pattern);
            const isValid = pattern.test(value);
            return {
                valid: isValid,
                message: isValid ? null : this.getMessage('pattern', field)
            };
        });
        
        // Number validator
        this.addValidator('number', (value, field) => {
            if (!value) return { valid: true, message: null };
            const isValid = !isNaN(value) && isFinite(value);
            return {
                valid: isValid,
                message: isValid ? null : this.getMessage('number', field)
            };
        });
        
        // Integer validator
        this.addValidator('integer', (value, field) => {
            if (!value) return { valid: true, message: null };
            const isValid = Number.isInteger(parseFloat(value));
            return {
                valid: isValid,
                message: isValid ? null : this.getMessage('integer', field)
            };
        });
        
        // Minimum value validator
        this.addValidator('min', (value, field, params) => {
            if (!value) return { valid: true, message: null };
            const minValue = parseFloat(params.min);
            const numValue = parseFloat(value);
            const isValid = numValue >= minValue;
            return {
                valid: isValid,
                message: isValid ? null : this.getMessage('min', field, { min: minValue })
            };
        });
        
        // Maximum value validator
        this.addValidator('max', (value, field, params) => {
            if (!value) return { valid: true, message: null };
            const maxValue = parseFloat(params.max);
            const numValue = parseFloat(value);
            const isValid = numValue <= maxValue;
            return {
                valid: isValid,
                message: isValid ? null : this.getMessage('max', field, { max: maxValue })
            };
        });
        
        // Date validator
        this.addValidator('date', (value, field) => {
            if (!value) return { valid: true, message: null };
            const date = new Date(value);
            const isValid = !isNaN(date.getTime());
            return {
                valid: isValid,
                message: isValid ? null : this.getMessage('date', field)
            };
        });
        
        // Time validator
        this.addValidator('time', (value, field) => {
            if (!value) return { valid: true, message: null };
            const timeRegex = /^([01]?[0-9]|2[0-3]):[0-5][0-9]$/;
            const isValid = timeRegex.test(value);
            return {
                valid: isValid,
                message: isValid ? null : this.getMessage('time', field)
            };
        });
        
        // File validator
        this.addValidator('file', (value, field, params) => {
            const fileInput = field.element;
            if (!fileInput.files || fileInput.files.length === 0) {
                return { valid: true, message: null };
            }
            
            const file = fileInput.files[0];
            const errors = [];
            
            // Check file size
            if (params.maxSize && file.size > params.maxSize) {
                errors.push(this.getMessage('fileSizeExceeded', field, { 
                    maxSize: this.formatFileSize(params.maxSize) 
                }));
            }
            
            // Check file type
            if (params.allowedTypes && !params.allowedTypes.includes(file.type)) {
                errors.push(this.getMessage('fileTypeNotAllowed', field, { 
                    allowedTypes: params.allowedTypes.join(', ') 
                }));
            }
            
            // Check file extension
            if (params.allowedExtensions) {
                const extension = file.name.split('.').pop().toLowerCase();
                if (!params.allowedExtensions.includes(extension)) {
                    errors.push(this.getMessage('fileExtensionNotAllowed', field, { 
                        allowedExtensions: params.allowedExtensions.join(', ') 
                    }));
                }
            }
            
            return {
                valid: errors.length === 0,
                message: errors.length > 0 ? errors.join('; ') : null
            };
        });
        
        // Custom validator for password strength
        this.addValidator('passwordStrength', (value, field) => {
            if (!value) return { valid: true, message: null };
            
            const minLength = 8;
            const hasUpperCase = /[A-Z]/.test(value);
            const hasLowerCase = /[a-z]/.test(value);
            const hasNumbers = /\d/.test(value);
            const hasSpecialChar = /[!@#$%^&*(),.?":{}|<>]/.test(value);
            
            const errors = [];
            if (value.length < minLength) errors.push(this.getMessage('passwordTooShort', field, { minLength }));
            if (!hasUpperCase) errors.push(this.getMessage('passwordNoUppercase', field));
            if (!hasLowerCase) errors.push(this.getMessage('passwordNoLowercase', field));
            if (!hasNumbers) errors.push(this.getMessage('passwordNoNumbers', field));
            if (!hasSpecialChar) errors.push(this.getMessage('passwordNoSpecialChar', field));
            
            return {
                valid: errors.length === 0,
                message: errors.length > 0 ? errors.join('; ') : null
            };
        });
    }
    
    addValidator(name, validatorFunction) {
        this.validators.set(name, validatorFunction);
    }
    
    addFormValidator(formId, validatorFunction) {
        this.formValidators.set(formId, validatorFunction);
    }
    
    setupEventListeners() {
        // Auto-discover forms with validation attributes
        document.addEventListener('DOMContentLoaded', () => {
            this.discoverForms();
        });
        
        // Handle dynamic content
        document.addEventListener('DOMNodeInserted', (e) => {
            if (e.target.nodeType === Node.ELEMENT_NODE) {
                this.discoverForms(e.target);
            }
        });
    }
    
    discoverForms(container = document) {
        const forms = container.querySelectorAll('form[data-validate], form.needs-validation');
        forms.forEach(form => this.attachFormValidation(form));
    }
    
    attachFormValidation(form) {
        const fields = form.querySelectorAll('[data-validate], [required], input[type="email"], input[type="url"], input[type="number"], input[type="date"], input[type="time"], input[type="file"]');
        
        fields.forEach(field => {
            this.attachFieldValidation(field);
        });
        
        // Form submission validation
        form.addEventListener('submit', (e) => {
            if (!this.validateForm(form)) {
                e.preventDefault();
                e.stopPropagation();
            }
        });
    }
    
    attachFieldValidation(field) {
        const fieldId = field.id || field.name || `field_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        
        if (this.options.validateOnInput) {
            field.addEventListener('input', (e) => {
                this.debounceValidation(fieldId, () => {
                    this.validateField(field);
                });
            });
        }
        
        if (this.options.validateOnBlur) {
            field.addEventListener('blur', () => {
                this.validateField(field);
            });
        }
        
        // Clear validation on focus
        field.addEventListener('focus', () => {
            this.clearFieldValidation(field);
        });
    }
    
    debounceValidation(fieldId, callback) {
        if (this.debounceTimers.has(fieldId)) {
            clearTimeout(this.debounceTimers.get(fieldId));
        }
        
        const timer = setTimeout(callback, this.options.debounceTime);
        this.debounceTimers.set(fieldId, timer);
    }
    
    validateField(field) {
        const fieldConfig = this.parseFieldConfig(field);
        const value = this.getFieldValue(field);
        const results = [];
        
        // Run all validators for this field
        for (const [validatorName, params] of Object.entries(fieldConfig.validators)) {
            if (this.validators.has(validatorName)) {
                const validator = this.validators.get(validatorName);
                const result = validator(value, { element: field, name: fieldConfig.name }, params);
                
                if (!result.valid) {
                    results.push(result);
                    break; // Stop on first error
                }
            }
        }
        
        // Store validation result
        const fieldKey = field.id || field.name;
        this.validationResults.set(fieldKey, {
            valid: results.length === 0,
            errors: results.filter(r => !r.valid)
        });
        
        // Update UI
        this.updateFieldUI(field, results);
        
        return results.length === 0;
    }
    
    parseFieldConfig(field) {
        const config = {
            name: field.getAttribute('data-field-name') || field.name || field.id,
            validators: {}
        };
        
        // Parse data-validate attribute
        const validateAttr = field.getAttribute('data-validate');
        if (validateAttr) {
            validateAttr.split('|').forEach(rule => {
                const [name, ...paramParts] = rule.split(':');
                const params = {};
                
                if (paramParts.length > 0) {
                    const paramString = paramParts.join(':');
                    paramString.split(',').forEach(param => {
                        const [key, value] = param.split('=');
                        params[key] = value;
                    });
                }
                
                config.validators[name] = params;
            });
        }
        
        // Add HTML5 validation attributes
        if (field.hasAttribute('required')) {
            config.validators.required = {};
        }
        
        if (field.type === 'email') {
            config.validators.email = {};
        }
        
        if (field.type === 'url') {
            config.validators.url = {};
        }
        
        if (field.type === 'number') {
            config.validators.number = {};
            if (field.hasAttribute('min')) {
                config.validators.min = { min: field.getAttribute('min') };
            }
            if (field.hasAttribute('max')) {
                config.validators.max = { max: field.getAttribute('max') };
            }
        }
        
        if (field.hasAttribute('minlength')) {
            config.validators.minLength = { minLength: field.getAttribute('minlength') };
        }
        
        if (field.hasAttribute('maxlength')) {
            config.validators.maxLength = { maxLength: field.getAttribute('maxlength') };
        }
        
        if (field.hasAttribute('pattern')) {
            config.validators.pattern = { pattern: field.getAttribute('pattern') };
        }
        
        if (field.type === 'date') {
            config.validators.date = {};
        }
        
        if (field.type === 'time') {
            config.validators.time = {};
        }
        
        if (field.type === 'file') {
            config.validators.file = {};
            if (field.hasAttribute('accept')) {
                config.validators.file.allowedTypes = field.getAttribute('accept').split(',').map(t => t.trim());
            }
            if (field.hasAttribute('data-max-size')) {
                config.validators.file.maxSize = parseInt(field.getAttribute('data-max-size'));
            }
        }
        
        return config;
    }
    
    getFieldValue(field) {
        if (field.type === 'checkbox') {
            return field.checked;
        } else if (field.type === 'radio') {
            const form = field.closest('form');
            const checkedRadio = form.querySelector(`input[name="${field.name}"]:checked`);
            return checkedRadio ? checkedRadio.value : null;
        } else if (field.tagName.toLowerCase() === 'select' && field.multiple) {
            return Array.from(field.selectedOptions).map(option => option.value);
        } else {
            return field.value;
        }
    }
    
    updateFieldUI(field, results) {
        const hasErrors = results.some(r => !r.valid);
        
        // Update field classes
        field.classList.remove('is-valid', 'is-invalid');
        if (hasErrors) {
            field.classList.add('is-invalid');
        } else if (this.options.showSuccessIndicators && field.value) {
            field.classList.add('is-valid');
        }
        
        // Update feedback message
        this.updateFieldFeedback(field, results);
    }
    
    updateFieldFeedback(field, results) {
        const fieldContainer = field.closest('.form-group, .mb-3, .form-floating') || field.parentElement;
        
        // Remove existing feedback
        const existingFeedback = fieldContainer.querySelectorAll('.invalid-feedback, .valid-feedback');
        existingFeedback.forEach(el => el.remove());
        
        // Add new feedback
        if (results.length > 0) {
            const feedback = document.createElement('div');
            feedback.className = 'invalid-feedback';
            feedback.textContent = results[0].message;
            fieldContainer.appendChild(feedback);
        } else if (this.options.showSuccessIndicators && field.value) {
            const feedback = document.createElement('div');
            feedback.className = 'valid-feedback';
            feedback.textContent = this.getMessage('valid', { name: field.name });
            fieldContainer.appendChild(feedback);
        }
    }
    
    validateForm(form) {
        const fields = form.querySelectorAll('[data-validate], [required], input[type="email"], input[type="url"], input[type="number"], input[type="date"], input[type="time"], input[type="file"]');
        let isValid = true;
        let firstInvalidField = null;
        
        // Validate all fields
        fields.forEach(field => {
            const fieldValid = this.validateField(field);
            if (!fieldValid && !firstInvalidField) {
                firstInvalidField = field;
            }
            isValid = isValid && fieldValid;
        });
        
        // Run custom form validators
        const formId = form.id;
        if (this.formValidators.has(formId)) {
            const formValidator = this.formValidators.get(formId);
            const formResult = formValidator(form, this.getFormData(form));
            if (!formResult.valid) {
                isValid = false;
                this.showFormErrors(form, formResult.errors);
            }
        }
        
        // Focus first invalid field
        if (!isValid && firstInvalidField && this.options.autoFocus) {
            firstInvalidField.focus();
        }
        
        return isValid;
    }
    
    getFormData(form) {
        const formData = new FormData(form);
        const data = {};
        
        for (const [key, value] of formData.entries()) {
            if (data[key]) {
                if (Array.isArray(data[key])) {
                    data[key].push(value);
                } else {
                    data[key] = [data[key], value];
                }
            } else {
                data[key] = value;
            }
        }
        
        return data;
    }
    
    showFormErrors(form, errors) {
        // Remove existing form-level errors
        const existingErrors = form.querySelectorAll('.form-error');
        existingErrors.forEach(el => el.remove());
        
        // Add new errors
        errors.forEach(error => {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'alert alert-danger form-error';
            errorDiv.textContent = error;
            form.insertBefore(errorDiv, form.firstChild);
        });
    }
    
    clearFieldValidation(field) {
        field.classList.remove('is-valid', 'is-invalid');
        const fieldContainer = field.closest('.form-group, .mb-3, .form-floating') || field.parentElement;
        const feedback = fieldContainer.querySelectorAll('.invalid-feedback, .valid-feedback');
        feedback.forEach(el => el.remove());
    }
    
    clearFormValidation(form) {
        const fields = form.querySelectorAll('.is-valid, .is-invalid');
        fields.forEach(field => this.clearFieldValidation(field));
        
        const formErrors = form.querySelectorAll('.form-error');
        formErrors.forEach(el => el.remove());
    }
    
    loadLanguage() {
        // Load language-specific messages
        this.messages = this.getMessages(this.options.language);
    }
    
    getMessages(language) {
        const messages = {
            uk: {
                required: 'Поле "{name}" є обов\'язковим',
                email: 'Введіть правильну email адресу',
                url: 'Введіть правильну URL адресу',
                minLength: 'Мінімальна довжина: {minLength} символів',
                maxLength: 'Максимальна довжина: {maxLength} символів',
                pattern: 'Формат поля "{name}" неправильний',
                number: 'Введіть правильне число',
                integer: 'Введіть ціле число',
                min: 'Мінімальне значення: {min}',
                max: 'Максимальне значення: {max}',
                date: 'Введіть правильну дату',
                time: 'Введіть правильний час',
                fileSizeExceeded: 'Розмір файлу перевищує {maxSize}',
                fileTypeNotAllowed: 'Тип файлу не дозволений. Дозволені типи: {allowedTypes}',
                fileExtensionNotAllowed: 'Розширення файлу не дозволене. Дозволені розширення: {allowedExtensions}',
                passwordTooShort: 'Пароль повинен містити принаймні {minLength} символів',
                passwordNoUppercase: 'Пароль повинен містити великі літери',
                passwordNoLowercase: 'Пароль повинен містити малі літери',
                passwordNoNumbers: 'Пароль повинен містити цифри',
                passwordNoSpecialChar: 'Пароль повинен містити спеціальні символи',
                valid: 'Правильно'
            },
            en: {
                required: 'Field "{name}" is required',
                email: 'Enter a valid email address',
                url: 'Enter a valid URL',
                minLength: 'Minimum length: {minLength} characters',
                maxLength: 'Maximum length: {maxLength} characters',
                pattern: 'Field "{name}" format is invalid',
                number: 'Enter a valid number',
                integer: 'Enter a valid integer',
                min: 'Minimum value: {min}',
                max: 'Maximum value: {max}',
                date: 'Enter a valid date',
                time: 'Enter a valid time',
                fileSizeExceeded: 'File size exceeds {maxSize}',
                fileTypeNotAllowed: 'File type not allowed. Allowed types: {allowedTypes}',
                fileExtensionNotAllowed: 'File extension not allowed. Allowed extensions: {allowedExtensions}',
                passwordTooShort: 'Password must be at least {minLength} characters',
                passwordNoUppercase: 'Password must contain uppercase letters',
                passwordNoLowercase: 'Password must contain lowercase letters',
                passwordNoNumbers: 'Password must contain numbers',
                passwordNoSpecialChar: 'Password must contain special characters',
                valid: 'Valid'
            },
            ru: {
                required: 'Поле "{name}" обязательно',
                email: 'Введите правильный email адрес',
                url: 'Введите правильный URL',
                minLength: 'Минимальная длина: {minLength} символов',
                maxLength: 'Максимальная длина: {maxLength} символов',
                pattern: 'Формат поля "{name}" неправильный',
                number: 'Введите правильное число',
                integer: 'Введите целое число',
                min: 'Минимальное значение: {min}',
                max: 'Максимальное значение: {max}',
                date: 'Введите правильную дату',
                time: 'Введите правильное время',
                fileSizeExceeded: 'Размер файла превышает {maxSize}',
                fileTypeNotAllowed: 'Тип файла не разрешен. Разрешенные типы: {allowedTypes}',
                fileExtensionNotAllowed: 'Расширение файла не разрешено. Разрешенные расширения: {allowedExtensions}',
                passwordTooShort: 'Пароль должен содержать минимум {minLength} символов',
                passwordNoUppercase: 'Пароль должен содержать заглавные буквы',
                passwordNoLowercase: 'Пароль должен содержать строчные буквы',
                passwordNoNumbers: 'Пароль должен содержать цифры',
                passwordNoSpecialChar: 'Пароль должен содержать специальные символы',
                valid: 'Правильно'
            }
        };
        
        return messages[language] || messages.en;
    }
    
    getMessage(key, field, params = {}) {
        let message = this.messages[key] || key;
        
        // Replace field name
        if (field && field.name) {
            message = message.replace('{name}', field.name);
        }
        
        // Replace parameters
        for (const [paramKey, paramValue] of Object.entries(params)) {
            message = message.replace(`{${paramKey}}`, paramValue);
        }
        
        return message;
    }
    
    formatFileSize(bytes) {
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        if (bytes === 0) return '0 Bytes';
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
    }
    
    // Public API methods
    validate(formOrField) {
        if (formOrField.tagName.toLowerCase() === 'form') {
            return this.validateForm(formOrField);
        } else {
            return this.validateField(formOrField);
        }
    }
    
    reset(formOrField) {
        if (formOrField.tagName.toLowerCase() === 'form') {
            this.clearFormValidation(formOrField);
        } else {
            this.clearFieldValidation(formOrField);
        }
    }
    
    setLanguage(language) {
        this.options.language = language;
        this.loadLanguage();
    }
    
    isValid(form) {
        const formId = form.id;
        if (!formId) return false;
        
        const fields = form.querySelectorAll('[data-validate], [required], input[type="email"], input[type="url"], input[type="number"], input[type="date"], input[type="time"], input[type="file"]');
        
        for (const field of fields) {
            const fieldKey = field.id || field.name;
            const result = this.validationResults.get(fieldKey);
            if (!result || !result.valid) {
                return false;
            }
        }
        
        return true;
    }
}

// Initialize global validation system
window.ValidationSystem = ValidationSystem;
window.validation = new ValidationSystem();

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ValidationSystem;
} 