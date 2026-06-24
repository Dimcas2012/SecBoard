/**
 * Comprehensive Client-Side Validation System
 * Provides real-time form validation with detailed error messages
 */

class ValidationSystem {
    constructor() {
        this.validators = new Map();
        this.errorMessages = new Map();
        this.validationRules = new Map();
        this.debounceTimers = new Map();
        this.init();
    }

    init() {
        this.setupDefaultValidators();
        this.setupDefaultMessages();
        this.bindEvents();
    }

    setupDefaultValidators() {
        // Required field validator
        this.validators.set('required', (value, element) => {
            if (element.type === 'checkbox' || element.type === 'radio') {
                return element.checked;
            }
            return value && value.trim().length > 0;
        });

        // Email validator
        this.validators.set('email', (value) => {
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            return !value || emailRegex.test(value);
        });

        // Date validator
        this.validators.set('date', (value) => {
            if (!value) return true;
            const date = new Date(value);
            return !isNaN(date.getTime()) && date > new Date('1900-01-01');
        });

        // Date range validator
        this.validators.set('dateRange', (value, element) => {
            if (!value) return true;
            const startDate = element.dataset.startDate;
            const endDate = element.dataset.endDate;
            
            if (startDate && endDate) {
                const current = new Date(value);
                const start = new Date(startDate);
                const end = new Date(endDate);
                return current >= start && current <= end;
            }
            return true;
        });

        // Future date validator
        this.validators.set('futureDate', (value) => {
            if (!value) return true;
            const inputDate = new Date(value);
            const today = new Date();
            today.setHours(0, 0, 0, 0);
            return inputDate >= today;
        });

        // Time validator
        this.validators.set('time', (value) => {
            if (!value) return true;
            const timeRegex = /^([01]?[0-9]|2[0-3]):[0-5][0-9]$/;
            return timeRegex.test(value);
        });

        // URL validator
        this.validators.set('url', (value) => {
            if (!value) return true;
            try {
                new URL(value);
                return true;
            } catch {
                return false;
            }
        });

        // Min length validator
        this.validators.set('minLength', (value, element) => {
            if (!value) return true;
            const minLength = parseInt(element.dataset.minLength) || 0;
            return value.length >= minLength;
        });

        // Max length validator
        this.validators.set('maxLength', (value, element) => {
            if (!value) return true;
            const maxLength = parseInt(element.dataset.maxLength) || Infinity;
            return value.length <= maxLength;
        });

        // Number validator
        this.validators.set('number', (value) => {
            if (!value) return true;
            return !isNaN(parseFloat(value)) && isFinite(value);
        });

        // Integer validator
        this.validators.set('integer', (value) => {
            if (!value) return true;
            return Number.isInteger(parseFloat(value));
        });

        // Min value validator
        this.validators.set('min', (value, element) => {
            if (!value) return true;
            const minValue = parseFloat(element.dataset.min);
            return !isNaN(minValue) && parseFloat(value) >= minValue;
        });

        // Max value validator
        this.validators.set('max', (value, element) => {
            if (!value) return true;
            const maxValue = parseFloat(element.dataset.max);
            return !isNaN(maxValue) && parseFloat(value) <= maxValue;
        });

        // Pattern validator
        this.validators.set('pattern', (value, element) => {
            if (!value) return true;
            const pattern = element.dataset.pattern;
            if (!pattern) return true;
            const regex = new RegExp(pattern);
            return regex.test(value);
        });

        // Custom validator for company selection
        this.validators.set('companyRequired', (value, element) => {
            const reportType = document.getElementById('reportType')?.value;
            if (reportType === 'company-specific') {
                return value && value.trim().length > 0;
            }
            return true;
        });

        // Weekly days validator
        this.validators.set('weeklyDays', (value, element) => {
            const frequency = document.getElementById('scheduleFrequency')?.value;
            if (frequency === 'weekly') {
                const weekdayCheckboxes = document.querySelectorAll('input[id^="schedule"][id$="day"]:checked');
                return weekdayCheckboxes.length > 0;
            }
            return true;
        });

        // Email recipients validator
        this.validators.set('emailRecipients', (value, element) => {
            const sendEmail = document.getElementById('scheduleSendEmail')?.checked;
            if (sendEmail) {
                const selectedOptions = element.selectedOptions;
                return selectedOptions.length > 0;
            }
            return true;
        });

        // File size validator
        this.validators.set('fileSize', (value, element) => {
            if (!element.files || element.files.length === 0) return true;
            const maxSize = parseInt(element.dataset.maxSize) || 10485760; // 10MB default
            return Array.from(element.files).every(file => file.size <= maxSize);
        });

        // File type validator
        this.validators.set('fileType', (value, element) => {
            if (!element.files || element.files.length === 0) return true;
            const allowedTypes = element.dataset.allowedTypes?.split(',') || [];
            if (allowedTypes.length === 0) return true;
            
            return Array.from(element.files).every(file => {
                const fileType = file.type.toLowerCase();
                const fileName = file.name.toLowerCase();
                return allowedTypes.some(type => 
                    fileType.includes(type) || fileName.endsWith(type)
                );
            });
        });
    }

    setupDefaultMessages() {
        // Ukrainian messages
        this.errorMessages.set('uk', {
            required: 'Це поле є обов\'язковим',
            email: 'Введіть коректну email адресу',
            date: 'Введіть коректну дату',
            dateRange: 'Дата повинна бути в межах дозволеного діапазону',
            futureDate: 'Дата повинна бути в майбутньому',
            time: 'Введіть коректний час (HH:MM)',
            url: 'Введіть коректний URL',
            minLength: 'Мінімальна довжина: {min} символів',
            maxLength: 'Максимальна довжина: {max} символів',
            number: 'Введіть коректне число',
            integer: 'Введіть ціле число',
            min: 'Мінімальне значення: {min}',
            max: 'Максимальне значення: {max}',
            pattern: 'Формат не відповідає вимогам',
            companyRequired: 'Виберіть компанію для цього типу звіту',
            weeklyDays: 'Виберіть принаймні один день тижня',
            emailRecipients: 'Виберіть принаймні одного отримувача',
            fileSize: 'Розмір файлу перевищує дозволений ({maxSize})',
            fileType: 'Недозволений тип файлу'
        });

        // English messages
        this.errorMessages.set('en', {
            required: 'This field is required',
            email: 'Please enter a valid email address',
            date: 'Please enter a valid date',
            dateRange: 'Date must be within the allowed range',
            futureDate: 'Date must be in the future',
            time: 'Please enter a valid time (HH:MM)',
            url: 'Please enter a valid URL',
            minLength: 'Minimum length: {min} characters',
            maxLength: 'Maximum length: {max} characters',
            number: 'Please enter a valid number',
            integer: 'Please enter a whole number',
            min: 'Minimum value: {min}',
            max: 'Maximum value: {max}',
            pattern: 'Format does not match requirements',
            companyRequired: 'Please select a company for this report type',
            weeklyDays: 'Please select at least one day of the week',
            emailRecipients: 'Please select at least one recipient',
            fileSize: 'File size exceeds allowed limit ({maxSize})',
            fileType: 'File type not allowed'
        });

        // Russian messages
        this.errorMessages.set('ru', {
            required: 'Это поле обязательно',
            email: 'Введите корректный email адрес',
            date: 'Введите корректную дату',
            dateRange: 'Дата должна быть в пределах разрешенного диапазона',
            futureDate: 'Дата должна быть в будущем',
            time: 'Введите корректное время (HH:MM)',
            url: 'Введите корректный URL',
            minLength: 'Минимальная длина: {min} символов',
            maxLength: 'Максимальная длина: {max} символов',
            number: 'Введите корректное число',
            integer: 'Введите целое число',
            min: 'Минимальное значение: {min}',
            max: 'Максимальное значение: {max}',
            pattern: 'Формат не соответствует требованиям',
            companyRequired: 'Выберите компанию для этого типа отчета',
            weeklyDays: 'Выберите хотя бы один день недели',
            emailRecipients: 'Выберите хотя бы одного получателя',
            fileSize: 'Размер файла превышает разрешенный ({maxSize})',
            fileType: 'Недопустимый тип файла'
        });
    }

    bindEvents() {
        // Bind to form elements
        document.addEventListener('input', (e) => {
            if (e.target.matches('[data-validate]')) {
                this.debounceValidation(e.target);
            }
        });

        document.addEventListener('change', (e) => {
            if (e.target.matches('[data-validate]')) {
                this.validateField(e.target);
            }
        });

        document.addEventListener('blur', (e) => {
            if (e.target.matches('[data-validate]')) {
                this.validateField(e.target);
            }
        });

        // Form submission validation
        document.addEventListener('submit', (e) => {
            if (e.target.matches('[data-validate-form]')) {
                if (!this.validateForm(e.target)) {
                    e.preventDefault();
                    e.stopPropagation();
                }
            }
        });
    }

    debounceValidation(element) {
        const fieldId = element.id || element.name;
        if (this.debounceTimers.has(fieldId)) {
            clearTimeout(this.debounceTimers.get(fieldId));
        }

        const timer = setTimeout(() => {
            this.validateField(element);
        }, 300);

        this.debounceTimers.set(fieldId, timer);
    }

    validateField(element) {
        const rules = this.parseValidationRules(element);
        const value = this.getFieldValue(element);
        const errors = [];

        for (const [rule, params] of rules) {
            if (this.validators.has(rule)) {
                const validator = this.validators.get(rule);
                if (!validator(value, element, params)) {
                    const message = this.getErrorMessage(rule, params);
                    errors.push(message);
                }
            }
        }

        this.displayFieldErrors(element, errors);
        return errors.length === 0;
    }

    validateForm(form) {
        const fields = form.querySelectorAll('[data-validate]');
        let isValid = true;
        const errors = [];

        fields.forEach(field => {
            const fieldValid = this.validateField(field);
            if (!fieldValid) {
                isValid = false;
                const fieldErrors = this.getFieldErrors(field);
                errors.push({
                    field: field.name || field.id,
                    errors: fieldErrors
                });
            }
        });

        // Display form-level errors if any
        if (!isValid) {
            this.displayFormErrors(form, errors);
        }

        return isValid;
    }

    parseValidationRules(element) {
        const rules = new Map();
        const validateAttr = element.getAttribute('data-validate');
        
        if (!validateAttr) return rules;

        const ruleStrings = validateAttr.split('|');
        
        ruleStrings.forEach(ruleString => {
            const [rule, ...params] = ruleString.split(':');
            rules.set(rule.trim(), params.join(':'));
        });

        return rules;
    }

    getFieldValue(element) {
        if (element.type === 'checkbox' || element.type === 'radio') {
            return element.checked;
        }
        return element.value;
    }

    getErrorMessage(rule, params) {
        const language = document.documentElement.lang || 'uk';
        const messages = this.errorMessages.get(language) || this.errorMessages.get('uk');
        let message = messages[rule] || `Validation error: ${rule}`;

        // Replace placeholders
        if (params) {
            message = message.replace(/\{(\w+)\}/g, (match, key) => {
                return params[key] || match;
            });
        }

        return message;
    }

    displayFieldErrors(element, errors) {
        this.clearFieldErrors(element);

        if (errors.length === 0) {
            element.classList.remove('is-invalid');
            element.classList.add('is-valid');
            return;
        }

        element.classList.remove('is-valid');
        element.classList.add('is-invalid');

        const errorContainer = this.getOrCreateErrorContainer(element);
        errorContainer.innerHTML = '';

        errors.forEach(error => {
            const errorElement = document.createElement('div');
            errorElement.className = 'invalid-feedback d-block';
            errorElement.textContent = error;
            errorContainer.appendChild(errorElement);
        });
    }

    clearFieldErrors(element) {
        element.classList.remove('is-invalid', 'is-valid');
        const errorContainer = this.getErrorContainer(element);
        if (errorContainer) {
            errorContainer.innerHTML = '';
        }
    }

    getOrCreateErrorContainer(element) {
        let container = this.getErrorContainer(element);
        if (!container) {
            container = document.createElement('div');
            container.className = 'validation-errors';
            container.setAttribute('data-field', element.id || element.name);
            
            // Insert after the element or its parent group
            const parent = element.closest('.form-group, .mb-3, .col') || element.parentElement;
            parent.appendChild(container);
        }
        return container;
    }

    getErrorContainer(element) {
        const fieldId = element.id || element.name;
        return document.querySelector(`[data-field="${fieldId}"]`);
    }

    getFieldErrors(element) {
        const errorContainer = this.getErrorContainer(element);
        if (!errorContainer) return [];
        
        const errorElements = errorContainer.querySelectorAll('.invalid-feedback');
        return Array.from(errorElements).map(el => el.textContent);
    }

    displayFormErrors(form, errors) {
        const formErrorContainer = this.getOrCreateFormErrorContainer(form);
        formErrorContainer.innerHTML = '';

        if (errors.length === 0) return;

        const errorList = document.createElement('ul');
        errorList.className = 'list-unstyled mb-0';

        errors.forEach(fieldError => {
            fieldError.errors.forEach(error => {
                const listItem = document.createElement('li');
                listItem.innerHTML = `<i class="fas fa-exclamation-circle me-2"></i>${error}`;
                errorList.appendChild(listItem);
            });
        });

        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-danger';
        alertDiv.innerHTML = `
            <h6 class="alert-heading">
                <i class="fas fa-exclamation-triangle me-2"></i>
                Помилки валідації
            </h6>
            <p class="mb-2">Будь ласка, виправте наступні помилки:</p>
        `;
        alertDiv.appendChild(errorList);

        formErrorContainer.appendChild(alertDiv);
    }

    getOrCreateFormErrorContainer(form) {
        let container = form.querySelector('.form-validation-errors');
        if (!container) {
            container = document.createElement('div');
            container.className = 'form-validation-errors mb-3';
            form.insertBefore(container, form.firstChild);
        }
        return container;
    }

    // Custom validation rules
    addValidator(name, validator) {
        this.validators.set(name, validator);
    }

    addErrorMessage(language, rule, message) {
        if (!this.errorMessages.has(language)) {
            this.errorMessages.set(language, {});
        }
        this.errorMessages.get(language)[rule] = message;
    }

    // Utility methods
    validateEmail(email) {
        return this.validators.get('email')(email);
    }

    validateDate(date) {
        return this.validators.get('date')(date);
    }

    validateRequired(value, element) {
        return this.validators.get('required')(value, element);
    }

    // Reset validation state
    resetForm(form) {
        const fields = form.querySelectorAll('[data-validate]');
        fields.forEach(field => {
            this.clearFieldErrors(field);
        });

        const formErrorContainer = form.querySelector('.form-validation-errors');
        if (formErrorContainer) {
            formErrorContainer.innerHTML = '';
        }
    }

    // Get form validation state
    getFormState(form) {
        const fields = form.querySelectorAll('[data-validate]');
        const state = {
            isValid: true,
            errors: {},
            validFields: 0,
            totalFields: fields.length
        };

        fields.forEach(field => {
            const fieldValid = this.validateField(field);
            if (fieldValid) {
                state.validFields++;
            } else {
                state.isValid = false;
                state.errors[field.name || field.id] = this.getFieldErrors(field);
            }
        });

        return state;
    }
}

// Initialize validation system
const validationSystem = new ValidationSystem();

// Export for use in other scripts
window.ValidationSystem = ValidationSystem;
window.validationSystem = validationSystem; 