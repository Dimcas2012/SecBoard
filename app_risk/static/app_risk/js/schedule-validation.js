/**
 * SecBoard Risk Assessment - Schedule Validation System
 * Specialized validation for scheduled report configurations
 */

class ScheduleValidationSystem {
    constructor(options = {}) {
        this.options = {
            formSelector: '#scheduleForm',
            enableRealTimeValidation: true,
            debounceTime: 300,
            language: 'uk',
            ...options
        };
        
        this.form = null;
        this.validationResults = new Map();
        this.debounceTimers = new Map();
        this.crossFieldValidators = new Map();
        
        this.init();
    }
    
    init() {
        this.setupForm();
        this.setupValidators();
        this.setupEventListeners();
        this.loadLanguage();
    }
    
    setupForm() {
        this.form = document.querySelector(this.options.formSelector);
        if (!this.form) {
            console.warn('Schedule form not found:', this.options.formSelector);
            return;
        }
        
        // Add validation classes
        this.form.classList.add('needs-validation');
        this.form.setAttribute('novalidate', '');
    }
    
    setupValidators() {
        // Setup cross-field validators
        this.crossFieldValidators.set('dateRange', this.validateDateRange.bind(this));
        this.crossFieldValidators.set('weeklyDays', this.validateWeeklyDays.bind(this));
        this.crossFieldValidators.set('emailSettings', this.validateEmailSettings.bind(this));
        this.crossFieldValidators.set('timeSettings', this.validateTimeSettings.bind(this));
    }
    
    setupEventListeners() {
        if (!this.form) return;
        
        // Form submission
        this.form.addEventListener('submit', (e) => {
            if (!this.validateForm()) {
                e.preventDefault();
                e.stopPropagation();
            }
        });
        
        // Real-time validation
        if (this.options.enableRealTimeValidation) {
            this.setupRealTimeValidation();
        }
        
        // Frequency change handler
        const frequencySelect = this.form.querySelector('#scheduleFrequency');
        if (frequencySelect) {
            frequencySelect.addEventListener('change', () => {
                this.updateFrequencyDependentFields();
                this.validateForm();
            });
        }
        
        // Email enabled checkbox
        const emailCheckbox = this.form.querySelector('#scheduleEmailEnabled');
        if (emailCheckbox) {
            emailCheckbox.addEventListener('change', () => {
                this.updateEmailDependentFields();
                this.validateForm();
            });
        }
    }
    
    setupRealTimeValidation() {
        const fields = this.form.querySelectorAll('input, select, textarea');
        
        fields.forEach(field => {
            // Input validation
            field.addEventListener('input', () => {
                this.debounceValidation(field.name || field.id, () => {
                    this.validateField(field);
                    this.runCrossFieldValidation();
                });
            });
            
            // Blur validation
            field.addEventListener('blur', () => {
                this.validateField(field);
                this.runCrossFieldValidation();
            });
            
            // Change validation for selects
            if (field.tagName.toLowerCase() === 'select') {
                field.addEventListener('change', () => {
                    this.validateField(field);
                    this.runCrossFieldValidation();
                });
            }
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
        const fieldName = field.name || field.id;
        const value = this.getFieldValue(field);
        const errors = [];
        
        // Required field validation
        if (field.hasAttribute('required') && this.isEmpty(value)) {
            errors.push(this.getMessage('required', fieldName));
        }
        
        // Skip further validation if empty and not required
        if (this.isEmpty(value) && !field.hasAttribute('required')) {
            this.updateFieldUI(field, []);
            return true;
        }
        
        // Field-specific validation
        switch (fieldName) {
            case 'scheduleName':
                errors.push(...this.validateScheduleName(value));
                break;
            case 'scheduleFrequency':
                errors.push(...this.validateFrequency(value));
                break;
            case 'scheduleStartDate':
                errors.push(...this.validateStartDate(value));
                break;
            case 'scheduleEndDate':
                errors.push(...this.validateEndDate(value));
                break;
            case 'scheduleExecutionTime':
                errors.push(...this.validateExecutionTime(value));
                break;
            case 'scheduleEmailSubject':
                errors.push(...this.validateEmailSubject(value));
                break;
            case 'scheduleEmailRecipients':
                errors.push(...this.validateEmailRecipients(value));
                break;
            case 'scheduleWeeklyDays':
                errors.push(...this.validateWeeklyDays(value));
                break;
            case 'scheduleMonthlyDay':
                errors.push(...this.validateMonthlyDay(value));
                break;
        }
        
        // Update UI
        this.updateFieldUI(field, errors);
        
        // Store validation result
        this.validationResults.set(fieldName, {
            valid: errors.length === 0,
            errors: errors
        });
        
        return errors.length === 0;
    }
    
    validateScheduleName(value) {
        const errors = [];
        
        if (value.length < 3) {
            errors.push(this.getMessage('minLength', 'scheduleName', { min: 3 }));
        }
        
        if (value.length > 100) {
            errors.push(this.getMessage('maxLength', 'scheduleName', { max: 100 }));
        }
        
        // Check for special characters
        if (!/^[a-zA-Z0-9\s\-_]+$/.test(value)) {
            errors.push(this.getMessage('invalidCharacters', 'scheduleName'));
        }
        
        return errors;
    }
    
    validateFrequency(value) {
        const errors = [];
        const validFrequencies = ['daily', 'weekly', 'monthly', 'yearly'];
        
        if (!validFrequencies.includes(value)) {
            errors.push(this.getMessage('invalidChoice', 'scheduleFrequency'));
        }
        
        return errors;
    }
    
    validateStartDate(value) {
        const errors = [];
        
        if (!this.isValidDate(value)) {
            errors.push(this.getMessage('invalidDate', 'scheduleStartDate'));
            return errors;
        }
        
        const startDate = new Date(value);
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        
        if (startDate < today) {
            errors.push(this.getMessage('pastDate', 'scheduleStartDate'));
        }
        
        return errors;
    }
    
    validateEndDate(value) {
        const errors = [];
        
        if (!value) return errors; // End date is optional
        
        if (!this.isValidDate(value)) {
            errors.push(this.getMessage('invalidDate', 'scheduleEndDate'));
            return errors;
        }
        
        return errors;
    }
    
    validateExecutionTime(value) {
        const errors = [];
        
        if (!this.isValidTime(value)) {
            errors.push(this.getMessage('invalidTime', 'scheduleExecutionTime'));
        }
        
        return errors;
    }
    
    validateEmailSubject(value) {
        const errors = [];
        
        if (value.length > 200) {
            errors.push(this.getMessage('maxLength', 'scheduleEmailSubject', { max: 200 }));
        }
        
        return errors;
    }
    
    validateEmailRecipients(value) {
        const errors = [];
        
        if (!Array.isArray(value)) {
            value = [value];
        }
        
        if (value.length === 0) {
            errors.push(this.getMessage('required', 'scheduleEmailRecipients'));
            return errors;
        }
        
        // Validate each email
        value.forEach(email => {
            if (!this.isValidEmail(email)) {
                errors.push(this.getMessage('invalidEmail', 'scheduleEmailRecipients', { email }));
            }
        });
        
        return errors;
    }
    
    validateWeeklyDays(value) {
        const errors = [];
        
        if (!Array.isArray(value)) {
            value = [value];
        }
        
        if (value.length === 0) {
            errors.push(this.getMessage('required', 'scheduleWeeklyDays'));
            return errors;
        }
        
        const validDays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
        
        value.forEach(day => {
            if (!validDays.includes(day)) {
                errors.push(this.getMessage('invalidDay', 'scheduleWeeklyDays', { day }));
            }
        });
        
        return errors;
    }
    
    validateMonthlyDay(value) {
        const errors = [];
        
        const day = parseInt(value);
        if (isNaN(day) || day < 1 || day > 31) {
            errors.push(this.getMessage('invalidMonthlyDay', 'scheduleMonthlyDay'));
        }
        
        return errors;
    }
    
    // Cross-field validation methods
    validateDateRange() {
        const startDateField = this.form.querySelector('#scheduleStartDate');
        const endDateField = this.form.querySelector('#scheduleEndDate');
        
        if (!startDateField || !endDateField) return [];
        
        const startDate = startDateField.value;
        const endDate = endDateField.value;
        
        if (!startDate || !endDate) return [];
        
        const errors = [];
        
        if (new Date(startDate) >= new Date(endDate)) {
            errors.push({
                field: 'scheduleEndDate',
                message: this.getMessage('endDateBeforeStart')
            });
        }
        
        // Check if date range is reasonable
        const daysDiff = Math.ceil((new Date(endDate) - new Date(startDate)) / (1000 * 60 * 60 * 24));
        if (daysDiff > 365 * 5) { // 5 years
            errors.push({
                field: 'scheduleEndDate',
                message: this.getMessage('dateRangeTooLong')
            });
        }
        
        return errors;
    }
    
    validateWeeklyDays() {
        const frequencyField = this.form.querySelector('#scheduleFrequency');
        const weeklyDaysField = this.form.querySelector('#scheduleWeeklyDays');
        
        if (!frequencyField || !weeklyDaysField) return [];
        
        const frequency = frequencyField.value;
        const errors = [];
        
        if (frequency === 'weekly') {
            const selectedDays = Array.from(weeklyDaysField.selectedOptions).map(option => option.value);
            
            if (selectedDays.length === 0) {
                errors.push({
                    field: 'scheduleWeeklyDays',
                    message: this.getMessage('weeklyDaysRequired')
                });
            }
            
            if (selectedDays.length > 7) {
                errors.push({
                    field: 'scheduleWeeklyDays',
                    message: this.getMessage('tooManyWeeklyDays')
                });
            }
        }
        
        return errors;
    }
    
    validateEmailSettings() {
        const emailEnabledField = this.form.querySelector('#scheduleEmailEnabled');
        const emailRecipientsField = this.form.querySelector('#scheduleEmailRecipients');
        
        if (!emailEnabledField || !emailRecipientsField) return [];
        
        const errors = [];
        
        if (emailEnabledField.checked) {
            const recipients = Array.from(emailRecipientsField.selectedOptions).map(option => option.value);
            
            if (recipients.length === 0) {
                errors.push({
                    field: 'scheduleEmailRecipients',
                    message: this.getMessage('emailRecipientsRequired')
                });
            }
            
            if (recipients.length > 50) {
                errors.push({
                    field: 'scheduleEmailRecipients',
                    message: this.getMessage('tooManyEmailRecipients')
                });
            }
        }
        
        return errors;
    }
    
    validateTimeSettings() {
        const frequencyField = this.form.querySelector('#scheduleFrequency');
        const executionTimeField = this.form.querySelector('#scheduleExecutionTime');
        
        if (!frequencyField || !executionTimeField) return [];
        
        const frequency = frequencyField.value;
        const executionTime = executionTimeField.value;
        const errors = [];
        
        if (frequency === 'daily') {
            // For daily reports, warn if time is during business hours
            const time = new Date(`1970-01-01T${executionTime}:00`);
            const hour = time.getHours();
            
            if (hour >= 9 && hour <= 17) {
                errors.push({
                    field: 'scheduleExecutionTime',
                    message: this.getMessage('businessHoursWarning'),
                    type: 'warning'
                });
            }
        }
        
        return errors;
    }
    
    runCrossFieldValidation() {
        const allErrors = [];
        
        // Run all cross-field validators
        this.crossFieldValidators.forEach((validator, name) => {
            const errors = validator();
            allErrors.push(...errors);
        });
        
        // Update UI for cross-field errors
        allErrors.forEach(error => {
            const field = this.form.querySelector(`#${error.field}`);
            if (field) {
                this.updateFieldUI(field, [error.message], error.type);
            }
        });
        
        return allErrors.length === 0;
    }
    
    updateFrequencyDependentFields() {
        const frequencyField = this.form.querySelector('#scheduleFrequency');
        if (!frequencyField) return;
        
        const frequency = frequencyField.value;
        
        // Show/hide frequency-specific fields
        const weeklyDaysContainer = this.form.querySelector('#weeklyDaysContainer');
        const monthlyDayContainer = this.form.querySelector('#monthlyDayContainer');
        
        if (weeklyDaysContainer) {
            weeklyDaysContainer.style.display = frequency === 'weekly' ? 'block' : 'none';
            const weeklyDaysField = weeklyDaysContainer.querySelector('#scheduleWeeklyDays');
            if (weeklyDaysField) {
                weeklyDaysField.required = frequency === 'weekly';
            }
        }
        
        if (monthlyDayContainer) {
            monthlyDayContainer.style.display = frequency === 'monthly' ? 'block' : 'none';
            const monthlyDayField = monthlyDayContainer.querySelector('#scheduleMonthlyDay');
            if (monthlyDayField) {
                monthlyDayField.required = frequency === 'monthly';
            }
        }
    }
    
    updateEmailDependentFields() {
        const emailEnabledField = this.form.querySelector('#scheduleEmailEnabled');
        if (!emailEnabledField) return;
        
        const emailEnabled = emailEnabledField.checked;
        
        // Show/hide email-specific fields
        const emailFieldsContainer = this.form.querySelector('#emailFieldsContainer');
        if (emailFieldsContainer) {
            emailFieldsContainer.style.display = emailEnabled ? 'block' : 'none';
            
            // Update required status
            const emailFields = emailFieldsContainer.querySelectorAll('input[type="email"], select[multiple]');
            emailFields.forEach(field => {
                field.required = emailEnabled;
            });
        }
    }
    
    validateForm() {
        let isValid = true;
        
        // Validate all fields
        const fields = this.form.querySelectorAll('input, select, textarea');
        fields.forEach(field => {
            const fieldValid = this.validateField(field);
            isValid = isValid && fieldValid;
        });
        
        // Run cross-field validation
        const crossFieldValid = this.runCrossFieldValidation();
        isValid = isValid && crossFieldValid;
        
        // Update form validation state
        this.form.classList.toggle('was-validated', true);
        
        return isValid;
    }
    
    updateFieldUI(field, errors, type = 'error') {
        const fieldContainer = field.closest('.form-group, .mb-3, .form-floating') || field.parentElement;
        
        // Remove existing feedback
        const existingFeedback = fieldContainer.querySelectorAll('.invalid-feedback, .valid-feedback, .warning-feedback');
        existingFeedback.forEach(el => el.remove());
        
        // Update field classes
        field.classList.remove('is-valid', 'is-invalid', 'is-warning');
        
        if (errors.length > 0) {
            if (type === 'warning') {
                field.classList.add('is-warning');
            } else {
                field.classList.add('is-invalid');
            }
            
            // Add error feedback
            const feedback = document.createElement('div');
            feedback.className = type === 'warning' ? 'warning-feedback' : 'invalid-feedback';
            feedback.textContent = errors[0]; // Show first error
            fieldContainer.appendChild(feedback);
        } else {
            field.classList.add('is-valid');
        }
    }
    
    // Utility methods
    isEmpty(value) {
        if (value === null || value === undefined) return true;
        if (typeof value === 'string') return value.trim() === '';
        if (Array.isArray(value)) return value.length === 0;
        return false;
    }
    
    isValidDate(dateString) {
        const date = new Date(dateString);
        return !isNaN(date.getTime());
    }
    
    isValidTime(timeString) {
        const timeRegex = /^([01]?[0-9]|2[0-3]):[0-5][0-9]$/;
        return timeRegex.test(timeString);
    }
    
    isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }
    
    getFieldValue(field) {
        if (field.type === 'checkbox') {
            return field.checked;
        } else if (field.type === 'radio') {
            const form = field.closest('form');
            const checkedRadio = form.querySelector(`input[name="${field.name}"]:checked`);
            return checkedRadio ? checkedRadio.value : null;
        } else if (field.multiple) {
            return Array.from(field.selectedOptions).map(option => option.value);
        } else {
            return field.value;
        }
    }
    
    loadLanguage() {
        this.messages = this.getMessages(this.options.language);
    }
    
    getMessages(language) {
        const messages = {
            uk: {
                required: 'Це поле є обов\'язковим',
                minLength: 'Мінімальна довжина: {min} символів',
                maxLength: 'Максимальна довжина: {max} символів',
                invalidCharacters: 'Недопустимі символи в назві',
                invalidChoice: 'Невірний вибір',
                invalidDate: 'Невірний формат дати',
                invalidTime: 'Невірний формат часу',
                invalidEmail: 'Невірний email: {email}',
                invalidDay: 'Невірний день: {day}',
                invalidMonthlyDay: 'День місяця повинен бути від 1 до 31',
                pastDate: 'Дата не може бути в минулому',
                endDateBeforeStart: 'Дата закінчення повинна бути після дати початку',
                dateRangeTooLong: 'Діапазон дат занадто великий (більше 5 років)',
                weeklyDaysRequired: 'Виберіть принаймні один день тижня',
                tooManyWeeklyDays: 'Не можна вибрати більше 7 днів',
                emailRecipientsRequired: 'Виберіть принаймні одного отримувача',
                tooManyEmailRecipients: 'Занадто багато отримувачів (максимум 50)',
                businessHoursWarning: 'Увага: звіт буде генеруватися в робочий час'
            },
            en: {
                required: 'This field is required',
                minLength: 'Minimum length: {min} characters',
                maxLength: 'Maximum length: {max} characters',
                invalidCharacters: 'Invalid characters in name',
                invalidChoice: 'Invalid choice',
                invalidDate: 'Invalid date format',
                invalidTime: 'Invalid time format',
                invalidEmail: 'Invalid email: {email}',
                invalidDay: 'Invalid day: {day}',
                invalidMonthlyDay: 'Monthly day must be between 1 and 31',
                pastDate: 'Date cannot be in the past',
                endDateBeforeStart: 'End date must be after start date',
                dateRangeTooLong: 'Date range is too long (more than 5 years)',
                weeklyDaysRequired: 'Select at least one day of the week',
                tooManyWeeklyDays: 'Cannot select more than 7 days',
                emailRecipientsRequired: 'Select at least one recipient',
                tooManyEmailRecipients: 'Too many recipients (maximum 50)',
                businessHoursWarning: 'Warning: report will be generated during business hours'
            },
            ru: {
                required: 'Это поле обязательно',
                minLength: 'Минимальная длина: {min} символов',
                maxLength: 'Максимальная длина: {max} символов',
                invalidCharacters: 'Недопустимые символы в названии',
                invalidChoice: 'Неверный выбор',
                invalidDate: 'Неверный формат даты',
                invalidTime: 'Неверный формат времени',
                invalidEmail: 'Неверный email: {email}',
                invalidDay: 'Неверный день: {day}',
                invalidMonthlyDay: 'День месяца должен быть от 1 до 31',
                pastDate: 'Дата не может быть в прошлом',
                endDateBeforeStart: 'Дата окончания должна быть после даты начала',
                dateRangeTooLong: 'Диапазон дат слишком большой (более 5 лет)',
                weeklyDaysRequired: 'Выберите хотя бы один день недели',
                tooManyWeeklyDays: 'Нельзя выбрать более 7 дней',
                emailRecipientsRequired: 'Выберите хотя бы одного получателя',
                tooManyEmailRecipients: 'Слишком много получателей (максимум 50)',
                businessHoursWarning: 'Внимание: отчет будет генерироваться в рабочее время'
            }
        };
        
        return messages[language] || messages.en;
    }
    
    getMessage(key, fieldName = '', params = {}) {
        let message = this.messages[key] || key;
        
        // Replace parameters
        Object.keys(params).forEach(param => {
            message = message.replace(`{${param}}`, params[param]);
        });
        
        return message;
    }
    
    // Public API
    setLanguage(language) {
        this.options.language = language;
        this.loadLanguage();
    }
    
    reset() {
        this.validationResults.clear();
        this.form.classList.remove('was-validated');
        
        // Clear all field states
        const fields = this.form.querySelectorAll('input, select, textarea');
        fields.forEach(field => {
            field.classList.remove('is-valid', 'is-invalid', 'is-warning');
        });
        
        // Remove all feedback
        const feedback = this.form.querySelectorAll('.invalid-feedback, .valid-feedback, .warning-feedback');
        feedback.forEach(el => el.remove());
    }
    
    getValidationResults() {
        return Object.fromEntries(this.validationResults);
    }
    
    isFormValid() {
        return Array.from(this.validationResults.values()).every(result => result.valid);
    }
}

// Initialize schedule validation when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Look for schedule forms
    const scheduleForms = document.querySelectorAll('#scheduleForm, .schedule-form');
    
    scheduleForms.forEach(form => {
        const formId = form.id || 'schedule-form';
        window[`${formId}Validation`] = new ScheduleValidationSystem({
            formSelector: `#${form.id}`,
            language: document.documentElement.lang || 'uk'
        });
    });
});

// Global export
window.ScheduleValidationSystem = ScheduleValidationSystem;

// Add warning feedback styles
const style = document.createElement('style');
style.textContent = `
.is-warning {
    border-color: #ffc107 !important;
    background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 12' width='12' height='12' fill='none' stroke='%23ffc107'%3e%3ccircle cx='6' cy='6' r='4.5'/%3e%3cpath d='M6 3v3'/%3e%3cpath d='M6 9h0'/%3e%3c/svg%3e") !important;
    background-repeat: no-repeat !important;
    background-position: right calc(0.375em + 0.1875rem) center !important;
    background-size: calc(0.75em + 0.375rem) calc(0.75em + 0.375rem) !important;
}

.warning-feedback {
    width: 100%;
    margin-top: 0.25rem;
    font-size: 0.875em;
    color: #856404;
}

.form-control.is-warning:focus {
    border-color: #ffc107;
    box-shadow: 0 0 0 0.2rem rgba(255, 193, 7, 0.25);
}

.form-select.is-warning:focus {
    border-color: #ffc107;
    box-shadow: 0 0 0 0.2rem rgba(255, 193, 7, 0.25);
}
`;
document.head.appendChild(style);

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ScheduleValidationSystem;
} 