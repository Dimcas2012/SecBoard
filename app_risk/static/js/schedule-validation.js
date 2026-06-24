/**
 * Schedule Validation System
 * Provides comprehensive validation for scheduled report configuration
 */

class ScheduleValidation {
    constructor() {
        this.validationRules = new Map();
        this.crossFieldRules = new Map();
        this.errorMessages = new Map();
        this.validationState = new Map();
        this.init();
    }

    init() {
        this.setupValidationRules();
        this.setupCrossFieldRules();
        this.setupErrorMessages();
        this.bindEvents();
    }

    setupValidationRules() {
        // Schedule name validation
        this.validationRules.set('scheduleName', [
            {
                rule: 'required',
                message: 'Назва розкладу є обов\'язковою'
            },
            {
                rule: 'minLength',
                params: { min: 3 },
                message: 'Назва повинна містити принаймні 3 символи'
            },
            {
                rule: 'maxLength',
                params: { max: 100 },
                message: 'Назва не може перевищувати 100 символів'
            },
            {
                rule: 'pattern',
                params: { pattern: /^[a-zA-Zа-яА-ЯёЁ0-9\s\-_.,()]+$/ },
                message: 'Назва містить недопустимі символи'
            }
        ]);

        // Description validation
        this.validationRules.set('scheduleDescription', [
            {
                rule: 'maxLength',
                params: { max: 500 },
                message: 'Опис не може перевищувати 500 символів'
            }
        ]);

        // Report type validation
        this.validationRules.set('scheduleReportType', [
            {
                rule: 'required',
                message: 'Виберіть тип звіту'
            },
            {
                rule: 'choice',
                params: { choices: ['full', 'summary', 'compliance'] },
                message: 'Недопустимий тип звіту'
            }
        ]);

        // Report format validation
        this.validationRules.set('scheduleReportFormat', [
            {
                rule: 'required',
                message: 'Виберіть формат звіту'
            },
            {
                rule: 'choice',
                                    params: { choices: ['pdf', 'word'] },
                message: 'Недопустимий формат звіту'
            }
        ]);

        // Language validation
        this.validationRules.set('scheduleReportLanguage', [
            {
                rule: 'required',
                message: 'Виберіть мову звіту'
            },
            {
                rule: 'choice',
                params: { choices: ['uk', 'en', 'ru'] },
                message: 'Недопустима мова звіту'
            }
        ]);

        // Frequency validation
        this.validationRules.set('scheduleFrequency', [
            {
                rule: 'required',
                message: 'Виберіть частоту виконання'
            },
            {
                rule: 'choice',
                params: { choices: ['once', 'daily', 'weekly', 'monthly', 'quarterly', 'yearly'] },
                message: 'Недопустима частота виконання'
            }
        ]);

        // Start date validation
        this.validationRules.set('scheduleStartDate', [
            {
                rule: 'required',
                message: 'Дата початку є обов\'язковою'
            },
            {
                rule: 'date',
                message: 'Введіть коректну дату'
            },
            {
                rule: 'futureDate',
                message: 'Дата початку повинна бути в майбутньому'
            }
        ]);

        // End date validation
        this.validationRules.set('scheduleEndDate', [
            {
                rule: 'date',
                message: 'Введіть коректну дату закінчення'
            }
        ]);

        // Execution time validation
        this.validationRules.set('scheduleExecutionTime', [
            {
                rule: 'required',
                message: 'Час виконання є обов\'язковим'
            },
            {
                rule: 'time',
                message: 'Введіть коректний час у форматі ГГ:ХХ'
            }
        ]);

        // Day of month validation (for monthly frequency)
        this.validationRules.set('scheduleDayOfMonth', [
            {
                rule: 'number',
                message: 'День місяця повинен бути числом'
            },
            {
                rule: 'range',
                params: { min: 1, max: 31 },
                message: 'День місяця повинен бути від 1 до 31'
            }
        ]);

        // Email subject validation
        this.validationRules.set('scheduleEmailSubject', [
            {
                rule: 'maxLength',
                params: { max: 200 },
                message: 'Тема листа не може перевищувати 200 символів'
            }
        ]);

        // Email body validation
        this.validationRules.set('scheduleEmailBody', [
            {
                rule: 'maxLength',
                params: { max: 2000 },
                message: 'Текст листа не може перевищувати 2000 символів'
            }
        ]);

        // Status validation
        this.validationRules.set('scheduleStatus', [
            {
                rule: 'required',
                message: 'Виберіть статус розкладу'
            },
            {
                rule: 'choice',
                params: { choices: ['active', 'paused', 'completed'] },
                message: 'Недопустимий статус розкладу'
            }
        ]);
    }

    setupCrossFieldRules() {
        // End date must be after start date
        this.crossFieldRules.set('dateRange', {
            fields: ['scheduleStartDate', 'scheduleEndDate'],
            validator: (values) => {
                const startDate = values.scheduleStartDate;
                const endDate = values.scheduleEndDate;
                
                if (startDate && endDate) {
                    const start = new Date(startDate);
                    const end = new Date(endDate);
                    return end > start;
                }
                return true;
            },
            message: 'Дата закінчення повинна бути пізніше дати початку',
            errorField: 'scheduleEndDate'
        });

        // Weekly frequency requires at least one day selected
        this.crossFieldRules.set('weeklyDays', {
            fields: ['scheduleFrequency'],
            validator: (values) => {
                if (values.scheduleFrequency === 'weekly') {
                    const weekdays = ['scheduleMonday', 'scheduleTuesday', 'scheduleWednesday', 
                                    'scheduleThursday', 'scheduleFriday', 'scheduleSaturday', 'scheduleSunday'];
                    return weekdays.some(day => document.getElementById(day)?.checked);
                }
                return true;
            },
            message: 'Для тижневого розкладу виберіть принаймні один день',
            errorField: 'scheduleFrequency'
        });

        // Monthly frequency requires day of month
        this.crossFieldRules.set('monthlyDay', {
            fields: ['scheduleFrequency', 'scheduleDayOfMonth'],
            validator: (values) => {
                if (values.scheduleFrequency === 'monthly') {
                    const dayOfMonth = values.scheduleDayOfMonth;
                    return dayOfMonth && dayOfMonth >= 1 && dayOfMonth <= 31;
                }
                return true;
            },
            message: 'Для місячного розкладу вкажіть день місяця (1-31)',
            errorField: 'scheduleDayOfMonth'
        });

        // Email settings validation
        this.crossFieldRules.set('emailSettings', {
            fields: ['scheduleSendEmail', 'scheduleEmailSubject', 'scheduleEmailRecipients'],
            validator: (values) => {
                const sendEmail = document.getElementById('scheduleSendEmail')?.checked;
                if (sendEmail) {
                    const subject = values.scheduleEmailSubject;
                    const recipients = document.getElementById('scheduleEmailRecipients')?.selectedOptions;
                    
                    return subject && subject.trim().length > 0 && recipients && recipients.length > 0;
                }
                return true;
            },
            message: 'При відправці email вкажіть тему та отримувачів',
            errorField: 'scheduleEmailSubject'
        });

        // Company validation for compliance reports
        this.crossFieldRules.set('complianceCompany', {
            fields: ['scheduleReportType', 'scheduleCompany'],
            validator: (values) => {
                if (values.scheduleReportType === 'compliance') {
                    return values.scheduleCompany && values.scheduleCompany.trim().length > 0;
                }
                return true;
            },
            message: 'Для звітів відповідності виберіть компанію',
            errorField: 'scheduleCompany'
        });
    }

    setupErrorMessages() {
        this.errorMessages.set('uk', {
            required: 'Це поле є обов\'язковим',
            minLength: 'Мінімальна довжина: {min} символів',
            maxLength: 'Максимальна довжина: {max} символів',
            pattern: 'Формат не відповідає вимогам',
            choice: 'Недопустиме значення',
            date: 'Введіть коректну дату',
            futureDate: 'Дата повинна бути в майбутньому',
            time: 'Введіть коректний час (ГГ:ХХ)',
            number: 'Введіть коректне число',
            range: 'Значення повинно бути від {min} до {max}',
            email: 'Введіть коректну email адресу'
        });

        this.errorMessages.set('en', {
            required: 'This field is required',
            minLength: 'Minimum length: {min} characters',
            maxLength: 'Maximum length: {max} characters',
            pattern: 'Format does not match requirements',
            choice: 'Invalid value',
            date: 'Please enter a valid date',
            futureDate: 'Date must be in the future',
            time: 'Please enter a valid time (HH:MM)',
            number: 'Please enter a valid number',
            range: 'Value must be between {min} and {max}',
            email: 'Please enter a valid email address'
        });
    }

    bindEvents() {
        // Bind validation to form fields
        const scheduleForm = document.getElementById('scheduleForm');
        if (scheduleForm) {
            // Real-time validation on input
            scheduleForm.addEventListener('input', (e) => {
                if (e.target.matches('[id^="schedule"]')) {
                    this.debounceValidation(e.target);
                }
            });

            // Validation on change
            scheduleForm.addEventListener('change', (e) => {
                if (e.target.matches('[id^="schedule"]')) {
                    this.validateField(e.target);
                    this.validateCrossFields();
                }
            });

            // Validation on blur
            scheduleForm.addEventListener('blur', (e) => {
                if (e.target.matches('[id^="schedule"]')) {
                    this.validateField(e.target);
                }
            }, true);
        }

        // Frequency change handler
        const frequencySelect = document.getElementById('scheduleFrequency');
        if (frequencySelect) {
            frequencySelect.addEventListener('change', () => {
                this.handleFrequencyChange();
                this.validateCrossFields();
            });
        }

        // Send email checkbox handler
        const sendEmailCheckbox = document.getElementById('scheduleSendEmail');
        if (sendEmailCheckbox) {
            sendEmailCheckbox.addEventListener('change', () => {
                this.handleSendEmailChange();
                this.validateCrossFields();
            });
        }
    }

    debounceValidation(element) {
        const fieldId = element.id;
        if (this.debounceTimers && this.debounceTimers.has(fieldId)) {
            clearTimeout(this.debounceTimers.get(fieldId));
        }

        if (!this.debounceTimers) {
            this.debounceTimers = new Map();
        }

        const timer = setTimeout(() => {
            this.validateField(element);
        }, 300);

        this.debounceTimers.set(fieldId, timer);
    }

    validateField(element) {
        const fieldId = element.id;
        const rules = this.validationRules.get(fieldId);
        
        if (!rules) return true;

        const value = this.getFieldValue(element);
        const errors = [];

        // Apply validation rules
        for (const rule of rules) {
            const isValid = this.applyValidationRule(rule, value, element);
            if (!isValid) {
                errors.push(rule.message);
            }
        }

        // Update validation state
        this.validationState.set(fieldId, {
            isValid: errors.length === 0,
            errors: errors
        });

        // Display errors
        this.displayFieldErrors(element, errors);

        return errors.length === 0;
    }

    validateCrossFields() {
        const formData = this.getFormData();
        
        for (const [ruleName, rule] of this.crossFieldRules) {
            const isValid = rule.validator(formData);
            
            if (!isValid) {
                const errorField = document.getElementById(rule.errorField);
                if (errorField) {
                    this.displayFieldErrors(errorField, [rule.message]);
                    this.validationState.set(rule.errorField, {
                        isValid: false,
                        errors: [rule.message]
                    });
                }
            } else {
                // Clear cross-field errors if validation passes
                const errorField = document.getElementById(rule.errorField);
                if (errorField) {
                    const currentState = this.validationState.get(rule.errorField);
                    if (currentState && currentState.errors.includes(rule.message)) {
                        const newErrors = currentState.errors.filter(err => err !== rule.message);
                        this.displayFieldErrors(errorField, newErrors);
                        this.validationState.set(rule.errorField, {
                            isValid: newErrors.length === 0,
                            errors: newErrors
                        });
                    }
                }
            }
        }
    }

    applyValidationRule(rule, value, element) {
        switch (rule.rule) {
            case 'required':
                return this.validateRequired(value, element);
            
            case 'minLength':
                return !value || value.length >= rule.params.min;
            
            case 'maxLength':
                return !value || value.length <= rule.params.max;
            
            case 'pattern':
                return !value || rule.params.pattern.test(value);
            
            case 'choice':
                return !value || rule.params.choices.includes(value);
            
            case 'date':
                return this.validateDate(value);
            
            case 'futureDate':
                return this.validateFutureDate(value);
            
            case 'time':
                return this.validateTime(value);
            
            case 'number':
                return this.validateNumber(value);
            
            case 'range':
                return this.validateRange(value, rule.params.min, rule.params.max);
            
            case 'email':
                return this.validateEmail(value);
            
            default:
                return true;
        }
    }

    validateRequired(value, element) {
        if (element.type === 'checkbox' || element.type === 'radio') {
            return element.checked;
        }
        return value && value.trim().length > 0;
    }

    validateDate(value) {
        if (!value) return true;
        const date = new Date(value);
        return !isNaN(date.getTime()) && date > new Date('1900-01-01');
    }

    validateFutureDate(value) {
        if (!value) return true;
        const inputDate = new Date(value);
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        return inputDate >= today;
    }

    validateTime(value) {
        if (!value) return true;
        const timeRegex = /^([01]?[0-9]|2[0-3]):[0-5][0-9]$/;
        return timeRegex.test(value);
    }

    validateNumber(value) {
        if (!value) return true;
        return !isNaN(parseFloat(value)) && isFinite(value);
    }

    validateRange(value, min, max) {
        if (!value) return true;
        const numValue = parseFloat(value);
        return numValue >= min && numValue <= max;
    }

    validateEmail(value) {
        if (!value) return true;
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(value);
    }

    getFieldValue(element) {
        if (element.type === 'checkbox' || element.type === 'radio') {
            return element.checked;
        }
        return element.value;
    }

    getFormData() {
        const form = document.getElementById('scheduleForm');
        const formData = {};
        
        if (form) {
            const elements = form.querySelectorAll('[id^="schedule"]');
            elements.forEach(element => {
                formData[element.id] = this.getFieldValue(element);
            });
        }
        
        return formData;
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
            container.className = 'field-validation-errors';
            container.setAttribute('data-field', element.id);
            
            // Insert after the element or its parent group
            const parent = element.closest('.form-group, .mb-3, .col') || element.parentElement;
            parent.appendChild(container);
        }
        return container;
    }

    getErrorContainer(element) {
        return document.querySelector(`[data-field="${element.id}"]`);
    }

    handleFrequencyChange() {
        const frequency = document.getElementById('scheduleFrequency')?.value;
        const weeklyOptions = document.getElementById('weeklyOptions');
        const monthlyOptions = document.getElementById('monthlyOptions');
        
        // Show/hide frequency-specific options
        if (weeklyOptions) {
            weeklyOptions.style.display = frequency === 'weekly' ? 'block' : 'none';
        }
        if (monthlyOptions) {
            monthlyOptions.style.display = frequency === 'monthly' ? 'block' : 'none';
        }

        // Reset validation for hidden fields
        if (frequency !== 'weekly') {
            const weekdayCheckboxes = document.querySelectorAll('[id^="schedule"][id$="day"]');
            weekdayCheckboxes.forEach(checkbox => {
                this.clearFieldErrors(checkbox);
            });
        }

        if (frequency !== 'monthly') {
            const dayOfMonthField = document.getElementById('scheduleDayOfMonth');
            if (dayOfMonthField) {
                this.clearFieldErrors(dayOfMonthField);
            }
        }
    }

    handleSendEmailChange() {
        const sendEmail = document.getElementById('scheduleSendEmail')?.checked;
        const emailFields = ['scheduleEmailSubject', 'scheduleEmailBody', 'scheduleEmailRecipients'];
        
        emailFields.forEach(fieldId => {
            const field = document.getElementById(fieldId);
            if (field) {
                if (sendEmail) {
                    field.setAttribute('required', 'required');
                } else {
                    field.removeAttribute('required');
                    this.clearFieldErrors(field);
                }
            }
        });
    }

    validateForm() {
        const form = document.getElementById('scheduleForm');
        if (!form) return false;

        let isValid = true;
        const fields = form.querySelectorAll('[id^="schedule"]');
        
        // Validate all fields
        fields.forEach(field => {
            const fieldValid = this.validateField(field);
            if (!fieldValid) {
                isValid = false;
            }
        });

        // Validate cross-field rules
        this.validateCrossFields();

        // Check if any cross-field validation failed
        for (const [fieldId, state] of this.validationState) {
            if (!state.isValid) {
                isValid = false;
            }
        }

        return isValid;
    }

    getValidationSummary() {
        const summary = {
            isValid: true,
            errors: [],
            fieldErrors: {}
        };

        for (const [fieldId, state] of this.validationState) {
            if (!state.isValid) {
                summary.isValid = false;
                summary.fieldErrors[fieldId] = state.errors;
                summary.errors.push(...state.errors);
            }
        }

        return summary;
    }

    resetValidation() {
        const form = document.getElementById('scheduleForm');
        if (form) {
            const fields = form.querySelectorAll('[id^="schedule"]');
            fields.forEach(field => {
                this.clearFieldErrors(field);
            });
        }
        
        this.validationState.clear();
    }

    // Integration with error display system
    showValidationErrors() {
        const summary = this.getValidationSummary();
        if (!summary.isValid && window.errorDisplaySystem) {
            window.errorDisplaySystem.clearErrorsByCategory('validation');
            
            const errors = Object.entries(summary.fieldErrors).map(([field, errors]) => ({
                field: field,
                code: 'validation_error',
                message: errors[0], // Show first error
                severity: 'error',
                category: 'validation'
            }));
            
            window.errorDisplaySystem.showValidationErrors(errors);
        }
    }
}

// Initialize schedule validation
const scheduleValidation = new ScheduleValidation();

// Make it globally available
window.scheduleValidation = scheduleValidation;

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ScheduleValidation;
} 