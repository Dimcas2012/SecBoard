/**
 * Schedule Validation System
 * Specialized validation for scheduled report configuration forms
 */

class ScheduleValidationSystem {
    constructor() {
        this.debounceTimers = new Map();
        this.validationRules = new Map();
        this.init();
    }

    init() {
        this.setupValidationRules();
        this.setupEventListeners();
        this.loadLanguageStrings();
    }

    setupValidationRules() {
        // Schedule name validation
        this.validationRules.set('scheduleName', [
            { type: 'required', message: 'Schedule name is required' },
            { type: 'minLength', value: 3, message: 'Schedule name must be at least 3 characters' },
            { type: 'maxLength', value: 100, message: 'Schedule name must not exceed 100 characters' }
        ]);

        // Date validation
        this.validationRules.set('scheduleStartDate', [
            { type: 'required', message: 'Start date is required' },
            { type: 'futureDate', message: 'Start date must be today or in the future' }
        ]);

        this.validationRules.set('scheduleEndDate', [
            { type: 'afterStartDate', message: 'End date must be after start date' }
        ]);

        // Time validation
        this.validationRules.set('scheduleExecutionTime', [
            { type: 'required', message: 'Execution time is required' },
            { type: 'validTime', message: 'Please enter a valid time' }
        ]);

        // Email validation
        this.validationRules.set('scheduleEmailSubject', [
            { type: 'required', message: 'Email subject is required' },
            { type: 'maxLength', value: 200, message: 'Email subject must not exceed 200 characters' }
        ]);

        this.validationRules.set('scheduleEmailBody', [
            { type: 'required', message: 'Email body is required' },
            { type: 'maxLength', value: 2000, message: 'Email body must not exceed 2000 characters' }
        ]);

        // Recipients validation
        this.validationRules.set('scheduleEmailRecipients', [
            { type: 'atLeastOneRecipient', message: 'At least one email recipient is required' }
        ]);

        // Weekly schedule validation
        this.validationRules.set('weeklyDays', [
            { type: 'atLeastOneDay', message: 'At least one day must be selected for weekly schedule' }
        ]);

        // Monthly schedule validation
        this.validationRules.set('scheduleDayOfMonth', [
            { type: 'required', message: 'Day of month is required for monthly schedule' },
            { type: 'range', min: 1, max: 31, message: 'Day of month must be between 1 and 31' }
        ]);
    }

    setupEventListeners() {
        // Real-time validation with debounce
        document.addEventListener('input', (e) => {
            if (this.isScheduleField(e.target)) {
                this.debounceValidation(e.target);
            }
        });

        // Immediate validation on change
        document.addEventListener('change', (e) => {
            if (this.isScheduleField(e.target)) {
                this.validateField(e.target);
            }
        });

        // Frequency change handler
        document.addEventListener('change', (e) => {
            if (e.target.id === 'scheduleFrequency') {
                this.handleFrequencyChange(e.target.value);
            }
        });

        // Send email checkbox handler
        document.addEventListener('change', (e) => {
            if (e.target.id === 'scheduleSendEmail') {
                this.handleSendEmailChange(e.target.checked);
            }
        });

        // Form submission validation
        document.addEventListener('submit', (e) => {
            if (e.target.id === 'scheduleForm') {
                if (!this.validateScheduleForm()) {
                    e.preventDefault();
                    e.stopPropagation();
                }
            }
        });
    }

    isScheduleField(element) {
        const scheduleFields = [
            'scheduleName', 'scheduleDescription', 'scheduleStartDate', 'scheduleEndDate',
            'scheduleExecutionTime', 'scheduleEmailSubject', 'scheduleEmailBody',
            'scheduleEmailRecipients', 'scheduleDayOfMonth'
        ];
        
        return scheduleFields.includes(element.id) || 
               element.name?.startsWith('schedule') ||
               element.closest('#scheduleForm');
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
        const fieldId = element.id;
        const value = element.value?.trim() || '';
        const rules = this.validationRules.get(fieldId) || [];
        const errors = [];

        for (const rule of rules) {
            if (!this.validateRule(rule, value, element)) {
                errors.push(this.getLocalizedMessage(rule.message, element));
            }
        }

        // Special cross-field validations
        if (fieldId === 'scheduleEndDate') {
            const startDateError = this.validateEndDateAfterStartDate(element);
            if (startDateError) {
                errors.push(startDateError);
            }
        }

        this.displayFieldValidation(element, errors);
        return errors.length === 0;
    }

    validateRule(rule, value, element) {
        switch (rule.type) {
            case 'required':
                return value.length > 0;
            
            case 'minLength':
                return value.length >= rule.value;
            
            case 'maxLength':
                return value.length <= rule.value;
            
            case 'futureDate':
                if (!value) return true;
                const inputDate = new Date(value);
                const today = new Date();
                today.setHours(0, 0, 0, 0);
                return inputDate >= today;
            
            case 'afterStartDate':
                return this.validateEndDateAfterStartDate(element) === null;
            
            case 'validTime':
                if (!value) return true;
                const timeRegex = /^([01]?[0-9]|2[0-3]):[0-5][0-9]$/;
                return timeRegex.test(value);
            
            case 'range':
                const num = parseInt(value);
                return !isNaN(num) && num >= rule.min && num <= rule.max;
            
            case 'atLeastOneRecipient':
                const recipientsSelect = document.getElementById('scheduleEmailRecipients');
                return recipientsSelect && recipientsSelect.selectedOptions.length > 0;
            
            case 'atLeastOneDay':
                return this.validateWeeklyDays();
            
            default:
                return true;
        }
    }

    validateEndDateAfterStartDate(endDateElement) {
        const startDateElement = document.getElementById('scheduleStartDate');
        if (!startDateElement || !endDateElement.value || !startDateElement.value) {
            return null;
        }

        const startDate = new Date(startDateElement.value);
        const endDate = new Date(endDateElement.value);

        if (endDate <= startDate) {
            return this.getLocalizedMessage('End date must be after start date');
        }

        return null;
    }

    validateWeeklyDays() {
        const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
        return days.some(day => {
            const checkbox = document.getElementById(`schedule${day}`);
            return checkbox && checkbox.checked;
        });
    }

    handleFrequencyChange(frequency) {
        const weeklyOptions = document.getElementById('weeklyOptions');
        const monthlyOptions = document.getElementById('monthlyOptions');
        
        if (weeklyOptions) {
            weeklyOptions.style.display = frequency === 'weekly' ? 'block' : 'none';
        }
        
        if (monthlyOptions) {
            monthlyOptions.style.display = frequency === 'monthly' ? 'block' : 'none';
        }

        // Validate relevant fields based on frequency
        if (frequency === 'weekly') {
            this.validateWeeklySchedule();
        } else if (frequency === 'monthly') {
            this.validateMonthlySchedule();
        }
    }

    handleSendEmailChange(sendEmail) {
        const emailFields = [
            'scheduleEmailSubject', 'scheduleEmailBody', 'scheduleEmailRecipients'
        ];

        emailFields.forEach(fieldId => {
            const element = document.getElementById(fieldId);
            if (element) {
                if (sendEmail) {
                    element.setAttribute('data-validate', 'required');
                    this.validateField(element);
                } else {
                    element.removeAttribute('data-validate');
                    this.clearFieldValidation(element);
                }
            }
        });
    }

    validateWeeklySchedule() {
        const weeklyContainer = document.getElementById('weeklyOptions');
        if (weeklyContainer && weeklyContainer.style.display !== 'none') {
            const isValid = this.validateWeeklyDays();
            this.displayWeeklyValidation(isValid);
        }
    }

    validateMonthlySchedule() {
        const dayOfMonthElement = document.getElementById('scheduleDayOfMonth');
        if (dayOfMonthElement) {
            this.validateField(dayOfMonthElement);
        }
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
        } else if (element.value?.trim()) {
            // Field is valid and has content
            element.classList.add('is-valid');
        }
    }

    displayWeeklyValidation(isValid) {
        const weeklyContainer = document.getElementById('weeklyOptions');
        if (!weeklyContainer) return;

        // Remove existing validation feedback
        const existingFeedback = weeklyContainer.querySelector('.invalid-feedback');
        if (existingFeedback) {
            existingFeedback.remove();
        }

        if (!isValid) {
            const feedback = document.createElement('div');
            feedback.className = 'invalid-feedback d-block';
            feedback.textContent = this.getLocalizedMessage('At least one day must be selected for weekly schedule');
            weeklyContainer.appendChild(feedback);
        }
    }

    clearFieldValidation(element) {
        element.classList.remove('is-valid', 'is-invalid');
        const feedback = element.parentNode.querySelector('.invalid-feedback, .valid-feedback');
        if (feedback) {
            feedback.remove();
        }
    }

    validateScheduleForm() {
        const form = document.getElementById('scheduleForm');
        if (!form) return true;

        let isValid = true;
        const errors = [];

        // Validate all schedule fields
        const fields = form.querySelectorAll('input, select, textarea');
        fields.forEach(field => {
            if (this.isScheduleField(field) && !this.validateField(field)) {
                isValid = false;
                const fieldError = field.parentNode.querySelector('.invalid-feedback');
                if (fieldError) {
                    errors.push({
                        field: field.id || field.name,
                        message: fieldError.textContent
                    });
                }
            }
        });

        // Special validations
        const frequency = document.getElementById('scheduleFrequency')?.value;
        
        if (frequency === 'weekly' && !this.validateWeeklyDays()) {
            isValid = false;
            errors.push({
                field: 'weeklyDays',
                message: this.getLocalizedMessage('At least one day must be selected for weekly schedule')
            });
            this.displayWeeklyValidation(false);
        }

        const sendEmail = document.getElementById('scheduleSendEmail')?.checked;
        if (sendEmail) {
            const recipientsValid = this.validateRule(
                { type: 'atLeastOneRecipient' }, 
                '', 
                document.getElementById('scheduleEmailRecipients')
            );
            
            if (!recipientsValid) {
                isValid = false;
                errors.push({
                    field: 'scheduleEmailRecipients',
                    message: this.getLocalizedMessage('At least one email recipient is required')
                });
            }
        }

        // Display form-level errors if any
        if (!isValid) {
            this.displayFormErrors(form, errors);
        } else {
            this.clearFormErrors(form);
        }

        return isValid;
    }

    displayFormErrors(form, errors) {
        // Remove existing form-level error display
        const existingAlert = form.querySelector('.schedule-validation-alert');
        if (existingAlert) {
            existingAlert.remove();
        }

        if (errors.length > 0) {
            const alert = document.createElement('div');
            alert.className = 'alert alert-danger schedule-validation-alert';
            alert.innerHTML = `
                <h6><i class="fas fa-exclamation-triangle me-2"></i>${this.getLocalizedMessage('Please correct the following errors:')}</h6>
                <ul class="mb-0">
                    ${errors.map(error => `<li>${error.message}</li>`).join('')}
                </ul>
            `;
            
            form.insertBefore(alert, form.firstChild);
        }
    }

    clearFormErrors(form) {
        const alert = form.querySelector('.schedule-validation-alert');
        if (alert) {
            alert.remove();
        }
    }

    loadLanguageStrings() {
        const currentLang = document.documentElement.lang || 'uk';
        this.currentLanguage = currentLang;
    }

    getLocalizedMessage(message, element = null) {
        const strings = this.getLanguageStrings();
        const fieldName = element?.dataset.fieldName || element?.placeholder || element?.name || '';
        
        // Try to find localized message
        const messageKey = this.getMessageKey(message);
        if (strings[messageKey]) {
            return strings[messageKey].replace('{field}', fieldName);
        }
        
        // Fallback to original message
        return message.replace('{field}', fieldName);
    }

    getMessageKey(message) {
        const keyMap = {
            'Schedule name is required': 'scheduleNameRequired',
            'Schedule name must be at least 3 characters': 'scheduleNameMinLength',
            'Schedule name must not exceed 100 characters': 'scheduleNameMaxLength',
            'Start date is required': 'startDateRequired',
            'Start date must be today or in the future': 'startDateFuture',
            'End date must be after start date': 'endDateAfterStart',
            'Execution time is required': 'executionTimeRequired',
            'Please enter a valid time': 'validTimeRequired',
            'Email subject is required': 'emailSubjectRequired',
            'Email subject must not exceed 200 characters': 'emailSubjectMaxLength',
            'Email body is required': 'emailBodyRequired',
            'Email body must not exceed 2000 characters': 'emailBodyMaxLength',
            'At least one email recipient is required': 'recipientRequired',
            'At least one day must be selected for weekly schedule': 'weeklyDayRequired',
            'Day of month is required for monthly schedule': 'dayOfMonthRequired',
            'Day of month must be between 1 and 31': 'dayOfMonthRange',
            'Please correct the following errors:': 'correctErrors'
        };
        
        return keyMap[message] || 'default';
    }

    getLanguageStrings() {
        const lang = this.currentLanguage || 'uk';
        
        const strings = {
            uk: {
                scheduleNameRequired: "Назва розкладу є обов'язковою",
                scheduleNameMinLength: "Назва розкладу повинна містити принаймні 3 символи",
                scheduleNameMaxLength: "Назва розкладу не повинна перевищувати 100 символів",
                startDateRequired: "Дата початку є обов'язковою",
                startDateFuture: "Дата початку повинна бути сьогодні або в майбутньому",
                endDateAfterStart: "Дата закінчення повинна бути після дати початку",
                executionTimeRequired: "Час виконання є обов'язковим",
                validTimeRequired: "Будь ласка, введіть правильний час",
                emailSubjectRequired: "Тема електронної пошти є обов'язковою",
                emailSubjectMaxLength: "Тема електронної пошти не повинна перевищувати 200 символів",
                emailBodyRequired: "Текст електронної пошти є обов'язковим",
                emailBodyMaxLength: "Текст електронної пошти не повинен перевищувати 2000 символів",
                recipientRequired: "Принаймні один отримувач електронної пошти є обов'язковим",
                weeklyDayRequired: "Принаймні один день повинен бути вибраний для тижневого розкладу",
                dayOfMonthRequired: "День місяця є обов'язковим для щомісячного розкладу",
                dayOfMonthRange: "День місяця повинен бути між 1 та 31",
                correctErrors: "Будь ласка, виправте наступні помилки:",
                default: "Поле містить помилку"
            },
            en: {
                scheduleNameRequired: "Schedule name is required",
                scheduleNameMinLength: "Schedule name must be at least 3 characters",
                scheduleNameMaxLength: "Schedule name must not exceed 100 characters",
                startDateRequired: "Start date is required",
                startDateFuture: "Start date must be today or in the future",
                endDateAfterStart: "End date must be after start date",
                executionTimeRequired: "Execution time is required",
                validTimeRequired: "Please enter a valid time",
                emailSubjectRequired: "Email subject is required",
                emailSubjectMaxLength: "Email subject must not exceed 200 characters",
                emailBodyRequired: "Email body is required",
                emailBodyMaxLength: "Email body must not exceed 2000 characters",
                recipientRequired: "At least one email recipient is required",
                weeklyDayRequired: "At least one day must be selected for weekly schedule",
                dayOfMonthRequired: "Day of month is required for monthly schedule",
                dayOfMonthRange: "Day of month must be between 1 and 31",
                correctErrors: "Please correct the following errors:",
                default: "Field contains an error"
            },
            ru: {
                scheduleNameRequired: "Название расписания обязательно",
                scheduleNameMinLength: "Название расписания должно содержать не менее 3 символов",
                scheduleNameMaxLength: "Название расписания не должно превышать 100 символов",
                startDateRequired: "Дата начала обязательна",
                startDateFuture: "Дата начала должна быть сегодня или в будущем",
                endDateAfterStart: "Дата окончания должна быть после даты начала",
                executionTimeRequired: "Время выполнения обязательно",
                validTimeRequired: "Пожалуйста, введите правильное время",
                emailSubjectRequired: "Тема электронной почты обязательна",
                emailSubjectMaxLength: "Тема электронной почты не должна превышать 200 символов",
                emailBodyRequired: "Текст электронной почты обязателен",
                emailBodyMaxLength: "Текст электронной почты не должен превышать 2000 символов",
                recipientRequired: "Необходим хотя бы один получатель электронной почты",
                weeklyDayRequired: "Для еженедельного расписания должен быть выбран хотя бы один день",
                dayOfMonthRequired: "День месяца обязателен для ежемесячного расписания",
                dayOfMonthRange: "День месяца должен быть между 1 и 31",
                correctErrors: "Пожалуйста, исправьте следующие ошибки:",
                default: "Поле содержит ошибку"
            }
        };

        return strings[lang] || strings.uk;
    }

    // Public API methods
    validateScheduleFormById(formId = 'scheduleForm') {
        return this.validateScheduleForm();
    }

    clearAllValidation() {
        const form = document.getElementById('scheduleForm');
        if (form) {
            const fields = form.querySelectorAll('input, select, textarea');
            fields.forEach(field => this.clearFieldValidation(field));
            this.clearFormErrors(form);
        }
    }

    addCustomRule(fieldId, rule) {
        if (!this.validationRules.has(fieldId)) {
            this.validationRules.set(fieldId, []);
        }
        this.validationRules.get(fieldId).push(rule);
    }
}

// Initialize the schedule validation system when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    window.scheduleValidationSystem = new ScheduleValidationSystem();
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ScheduleValidationSystem;
}

// Add CSS for enhanced form styling and validation feedback
const scheduleValidationStyle = document.createElement('style');
scheduleValidationStyle.textContent = `
    /* Enhanced form styling for schedule validation */
    .schedule-form-group {
        position: relative;
        margin-bottom: 1.5rem;
    }
    
    .schedule-form-group .form-label {
        font-weight: 500;
        color: #495057;
        margin-bottom: 0.5rem;
    }
    
    .schedule-form-group .form-control,
    .schedule-form-group .form-select {
        transition: all 0.2s ease-in-out;
        border: 1px solid #ced4da;
    }
    
    .schedule-form-group .form-control:focus,
    .schedule-form-group .form-select:focus {
        border-color: #80bdff;
        box-shadow: 0 0 0 0.2rem rgba(0, 123, 255, 0.25);
    }
    
    .schedule-form-group .form-control.is-valid,
    .schedule-form-group .form-select.is-valid {
        border-color: #28a745;
        background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 8 8'%3e%3cpath fill='%2328a745' d='m2.3 6.73.4.5.4-.5c1.4-1.5 2.1-2.4 2.1-3.4 0-1.1-.6-1.8-1.5-1.8C2.8 1.5 2.2 2.2 2.2 3.3c0 1 .6 1.9 2.1 3.4z'/%3e%3c/svg%3e");
        background-repeat: no-repeat;
        background-position: right calc(0.375em + 0.1875rem) center;
        background-size: calc(0.75em + 0.375rem) calc(0.75em + 0.375rem);
    }
    
    .schedule-form-group .form-control.is-invalid,
    .schedule-form-group .form-select.is-invalid {
        border-color: #dc3545;
        background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 12' width='12' height='12' fill='none' stroke='%23dc3545'%3e%3ccircle cx='6' cy='6' r='4.5'/%3e%3cpath d='m5.8 3.6h.4L6 6.5z'/%3e%3ccircle cx='6' cy='8.2' r='.6' fill='%23dc3545' stroke='none'/%3e%3c/svg%3e");
        background-repeat: no-repeat;
        background-position: right calc(0.375em + 0.1875rem) center;
        background-size: calc(0.75em + 0.375rem) calc(0.75em + 0.375rem);
    }
    
    .schedule-validation-feedback {
        width: 100%;
        margin-top: 0.25rem;
        font-size: 0.875rem;
    }
    
    .schedule-validation-feedback.valid-feedback {
        color: #28a745;
    }
    
    .schedule-validation-feedback.invalid-feedback {
        color: #dc3545;
    }
    
    .schedule-validation-summary {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 0.375rem;
        padding: 1rem;
        margin-bottom: 1rem;
    }
    
    .schedule-validation-summary.has-errors {
        background-color: #f8d7da;
        border-color: #f5c6cb;
        color: #721c24;
    }
    
    .schedule-validation-summary.is-valid {
        background-color: #d4edda;
        border-color: #c3e6cb;
        color: #155724;
    }
    
    .schedule-field-status {
        display: inline-flex;
        align-items: center;
        margin-left: 0.5rem;
        font-size: 0.875rem;
    }
    
    .schedule-field-status.valid {
        color: #28a745;
    }
    
    .schedule-field-status.invalid {
        color: #dc3545;
    }
    
    .schedule-field-status.pending {
        color: #ffc107;
    }
    
    .schedule-cross-validation-info {
        background-color: #e7f3ff;
        border: 1px solid #b8daff;
        border-radius: 0.375rem;
        padding: 0.75rem;
        margin-top: 0.5rem;
        font-size: 0.875rem;
        color: #004085;
    }
    
    .schedule-frequency-options {
        transition: all 0.3s ease-in-out;
        overflow: hidden;
    }
    
    .schedule-frequency-options.hidden {
        max-height: 0;
        opacity: 0;
        margin: 0;
        padding: 0;
    }
    
    .schedule-frequency-options.visible {
        max-height: 500px;
        opacity: 1;
    }
    
    .schedule-day-checkbox {
        margin-right: 1rem;
        margin-bottom: 0.5rem;
    }
    
    .schedule-day-checkbox .form-check-input:checked {
        background-color: #007bff;
        border-color: #007bff;
    }
    
    .schedule-email-preview {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 0.375rem;
        padding: 1rem;
        margin-top: 1rem;
        font-family: monospace;
        font-size: 0.875rem;
    }
    
    .schedule-recipients-count {
        font-size: 0.875rem;
        color: #6c757d;
        margin-top: 0.25rem;
    }
    
    .schedule-form-section {
        border-top: 1px solid #dee2e6;
        padding-top: 1.5rem;
        margin-top: 1.5rem;
    }
    
    .schedule-form-section:first-child {
        border-top: none;
        padding-top: 0;
        margin-top: 0;
    }
    
    .schedule-form-section h6 {
        color: #495057;
        font-weight: 600;
        margin-bottom: 1rem;
    }
    
    /* Responsive adjustments */
    @media (max-width: 768px) {
        .schedule-form-group {
            margin-bottom: 1rem;
        }
        
        .schedule-validation-summary {
            padding: 0.75rem;
        }
        
        .schedule-day-checkbox {
            margin-right: 0.5rem;
            margin-bottom: 0.25rem;
        }
    }
    
    /* Animation for validation state changes */
    .schedule-form-group .form-control,
    .schedule-form-group .form-select {
        transition: border-color 0.15s ease-in-out, box-shadow 0.15s ease-in-out, background-image 0.15s ease-in-out;
    }
    
    /* Custom select styling for better UX */
    .schedule-form-group .form-select {
        background-position: right 0.75rem center;
        background-size: 16px 12px;
    }
    
    .schedule-form-group .form-select:focus {
        background-position: right 0.75rem center;
    }
    
    /* Enhanced checkbox and radio styling */
    .schedule-form-group .form-check-input {
        width: 1.125em;
        height: 1.125em;
        margin-top: 0.125em;
    }
    
    .schedule-form-group .form-check-input:checked {
        background-color: #007bff;
        border-color: #007bff;
    }
    
    .schedule-form-group .form-check-input:focus {
        border-color: #80bdff;
        box-shadow: 0 0 0 0.2rem rgba(0, 123, 255, 0.25);
    }
    
    /* Textarea specific styling */
    .schedule-form-group textarea.form-control {
        resize: vertical;
        min-height: calc(1.5em + 0.75rem + 2px);
    }
    
    /* Loading state styling */
    .schedule-form-group.loading .form-control,
    .schedule-form-group.loading .form-select {
        background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 12'%3e%3cpath fill='%236c757d' d='M6 0c3.3 0 6 2.7 6 6s-2.7 6-6 6S0 9.3 0 6s2.7-6 6-6zm0 2c-2.2 0-4 1.8-4 4s1.8 4 4 4 4-1.8 4-4-1.8-4-4-4z'/%3e%3cpath fill='%23007bff' d='M6 0c1.7 0 3.2.7 4.2 1.8L8.8 3.2C8.1 2.5 7.1 2 6 2V0z'%3e%3canimateTransform attributeName='transform' type='rotate' values='0 6 6;360 6 6' dur='1s' repeatCount='indefinite'/%3e%3c/path%3e%3c/svg%3e");
        background-repeat: no-repeat;
        background-position: right calc(0.375em + 0.1875rem) center;
        background-size: calc(0.75em + 0.375rem) calc(0.75em + 0.375rem);
    }
`;
document.head.appendChild(scheduleValidationStyle);
