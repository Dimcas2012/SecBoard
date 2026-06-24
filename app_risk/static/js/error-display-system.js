/**
 * Comprehensive Error Display System
 * Provides categorized error display with user-friendly messages and interactive handling
 */

class ErrorDisplaySystem {
    constructor() {
        this.errorContainer = null;
        this.errorQueue = [];
        this.maxErrors = 10;
        this.autoHideTimeout = 5000;
        this.errorCategories = new Map();
        this.errorTemplates = new Map();
        this.errorHistory = [];
        this.init();
    }

    init() {
        this.setupErrorContainer();
        this.setupErrorCategories();
        this.setupErrorTemplates();
        this.bindGlobalErrorHandlers();
        this.loadErrorMessages();
    }

    setupErrorContainer() {
        // Create main error container if it doesn't exist
        this.errorContainer = document.getElementById('errorContainer');
        if (!this.errorContainer) {
            this.errorContainer = document.createElement('div');
            this.errorContainer.id = 'errorContainer';
            this.errorContainer.className = 'error-container position-fixed top-0 end-0 p-3';
            this.errorContainer.style.zIndex = '9999';
            this.errorContainer.style.maxWidth = '400px';
            document.body.appendChild(this.errorContainer);
        }
    }

    setupErrorCategories() {
        this.errorCategories.set('validation', {
            name: 'Помилки валідації',
            icon: 'fas fa-exclamation-triangle',
            color: 'warning',
            priority: 2
        });

        this.errorCategories.set('network', {
            name: 'Помилки мережі',
            icon: 'fas fa-wifi',
            color: 'danger',
            priority: 3
        });

        this.errorCategories.set('security', {
            name: 'Помилки безпеки',
            icon: 'fas fa-shield-alt',
            color: 'danger',
            priority: 4
        });

        this.errorCategories.set('file', {
            name: 'Помилки файлів',
            icon: 'fas fa-file-exclamation',
            color: 'warning',
            priority: 2
        });

        this.errorCategories.set('permission', {
            name: 'Помилки доступу',
            icon: 'fas fa-lock',
            color: 'danger',
            priority: 3
        });

        this.errorCategories.set('system', {
            name: 'Системні помилки',
            icon: 'fas fa-cog',
            color: 'danger',
            priority: 4
        });

        this.errorCategories.set('user', {
            name: 'Помилки користувача',
            icon: 'fas fa-user-exclamation',
            color: 'info',
            priority: 1
        });

        this.errorCategories.set('general', {
            name: 'Загальні помилки',
            icon: 'fas fa-exclamation-circle',
            color: 'secondary',
            priority: 1
        });
    }

    setupErrorTemplates() {
        // Validation error templates
        this.errorTemplates.set('required', {
            uk: 'Поле "{field}" є обов\'язковим для заповнення',
            en: 'Field "{field}" is required',
            ru: 'Поле "{field}" обязательно для заполнения'
        });

        this.errorTemplates.set('email', {
            uk: 'Введіть коректну email адресу в поле "{field}"',
            en: 'Please enter a valid email address in field "{field}"',
            ru: 'Введите корректный email адрес в поле "{field}"'
        });

        this.errorTemplates.set('date', {
            uk: 'Введіть коректну дату в поле "{field}"',
            en: 'Please enter a valid date in field "{field}"',
            ru: 'Введите корректную дату в поле "{field}"'
        });

        this.errorTemplates.set('file_too_large', {
            uk: 'Файл занадто великий. Максимальний розмір: {maxSize}',
            en: 'File is too large. Maximum size: {maxSize}',
            ru: 'Файл слишком большой. Максимальный размер: {maxSize}'
        });

        this.errorTemplates.set('invalid_file_type', {
            uk: 'Недопустимий тип файлу. Дозволені типи: {allowedTypes}',
            en: 'Invalid file type. Allowed types: {allowedTypes}',
            ru: 'Недопустимый тип файла. Разрешенные типы: {allowedTypes}'
        });

        this.errorTemplates.set('network_error', {
            uk: 'Помилка мережі. Перевірте з\'єднання з інтернетом',
            en: 'Network error. Please check your internet connection',
            ru: 'Ошибка сети. Проверьте подключение к интернету'
        });

        this.errorTemplates.set('server_error', {
            uk: 'Помилка сервера. Спробуйте пізніше',
            en: 'Server error. Please try again later',
            ru: 'Ошибка сервера. Попробуйте позже'
        });

        this.errorTemplates.set('permission_denied', {
            uk: 'Недостатньо прав для виконання цієї операції',
            en: 'Insufficient permissions to perform this operation',
            ru: 'Недостаточно прав для выполнения этой операции'
        });

        this.errorTemplates.set('session_expired', {
            uk: 'Сесія закінчилася. Будь ласка, увійдіть знову',
            en: 'Session expired. Please log in again',
            ru: 'Сессия истекла. Пожалуйста, войдите снова'
        });

        this.errorTemplates.set('csrf_error', {
            uk: 'Помилка безпеки. Оновіть сторінку та спробуйте знову',
            en: 'Security error. Please refresh the page and try again',
            ru: 'Ошибка безопасности. Обновите страницу и попробуйте снова'
        });
    }

    bindGlobalErrorHandlers() {
        // Handle uncaught JavaScript errors
        window.addEventListener('error', (event) => {
            this.showError({
                category: 'system',
                code: 'javascript_error',
                message: event.message,
                details: {
                    filename: event.filename,
                    lineno: event.lineno,
                    colno: event.colno
                }
            });
        });

        // Handle unhandled promise rejections
        window.addEventListener('unhandledrejection', (event) => {
            this.showError({
                category: 'system',
                code: 'promise_rejection',
                message: event.reason?.message || 'Unhandled promise rejection',
                details: {
                    reason: event.reason
                }
            });
        });

        // Handle AJAX errors
        document.addEventListener('ajaxError', (event) => {
            this.handleAjaxError(event.detail);
        });
    }

    loadErrorMessages() {
        // Load error messages from server or local storage
        const language = document.documentElement.lang || 'uk';
        this.currentLanguage = language;
    }

    showError(error) {
        // Validate error object
        if (!error || typeof error !== 'object') {
            error = {
                category: 'general',
                code: 'unknown_error',
                message: 'Невідома помилка'
            };
        }

        // Set default values
        error.category = error.category || 'general';
        error.code = error.code || 'unknown_error';
        error.severity = error.severity || 'error';
        error.timestamp = new Date();
        error.id = this.generateErrorId();

        // Get user-friendly message
        error.displayMessage = this.getDisplayMessage(error);

        // Add to error history
        this.errorHistory.unshift(error);
        if (this.errorHistory.length > 50) {
            this.errorHistory = this.errorHistory.slice(0, 50);
        }

        // Add to queue
        this.errorQueue.push(error);

        // Process queue
        this.processErrorQueue();

        // Log error for debugging
        this.logError(error);

        return error.id;
    }

    showValidationErrors(errors) {
        if (!Array.isArray(errors)) {
            errors = [errors];
        }

        errors.forEach(error => {
            this.showError({
                category: 'validation',
                code: error.code || 'validation_error',
                message: error.message,
                field: error.field,
                severity: error.severity || 'error',
                details: error.details
            });
        });
    }

    showNetworkError(xhr, textStatus, errorThrown) {
        let errorCode = 'network_error';
        let message = 'Помилка мережі';

        if (xhr.status === 0) {
            errorCode = 'connection_error';
            message = 'Немає з\'єднання з сервером';
        } else if (xhr.status === 400) {
            errorCode = 'bad_request';
            message = 'Некоректний запит';
        } else if (xhr.status === 401) {
            errorCode = 'unauthorized';
            message = 'Необхідна авторизація';
        } else if (xhr.status === 403) {
            errorCode = 'permission_denied';
            message = 'Доступ заборонено';
        } else if (xhr.status === 404) {
            errorCode = 'not_found';
            message = 'Ресурс не знайдено';
        } else if (xhr.status === 422) {
            errorCode = 'validation_error';
            message = 'Помилка валідації даних';
        } else if (xhr.status === 500) {
            errorCode = 'server_error';
            message = 'Внутрішня помилка сервера';
        } else if (xhr.status === 502) {
            errorCode = 'bad_gateway';
            message = 'Помилка шлюзу';
        } else if (xhr.status === 503) {
            errorCode = 'service_unavailable';
            message = 'Сервіс недоступний';
        }

        this.showError({
            category: 'network',
            code: errorCode,
            message: message,
            details: {
                status: xhr.status,
                statusText: xhr.statusText,
                responseText: xhr.responseText,
                textStatus: textStatus,
                errorThrown: errorThrown
            }
        });
    }

    showFileError(fileError) {
        this.showError({
            category: 'file',
            code: fileError.code || 'file_error',
            message: fileError.message,
            details: fileError.details
        });
    }

    processErrorQueue() {
        // Remove old errors if queue is too long
        while (this.errorQueue.length > this.maxErrors) {
            const oldError = this.errorQueue.shift();
            this.removeErrorElement(oldError.id);
        }

        // Display new errors
        this.errorQueue.forEach(error => {
            if (!error.displayed) {
                this.displayError(error);
                error.displayed = true;
            }
        });
    }

    displayError(error) {
        const category = this.errorCategories.get(error.category);
        const errorElement = this.createErrorElement(error, category);
        
        // Add to container
        this.errorContainer.insertBefore(errorElement, this.errorContainer.firstChild);

        // Animate in
        setTimeout(() => {
            errorElement.classList.add('show');
        }, 10);

        // Auto-hide for non-critical errors
        if (error.severity !== 'critical' && error.category !== 'security') {
            setTimeout(() => {
                this.hideError(error.id);
            }, this.autoHideTimeout);
        }
    }

    createErrorElement(error, category) {
        const errorElement = document.createElement('div');
        errorElement.className = `alert alert-${category.color} alert-dismissible fade error-item`;
        errorElement.setAttribute('data-error-id', error.id);
        errorElement.setAttribute('data-error-category', error.category);
        errorElement.setAttribute('data-error-severity', error.severity);

        const iconHtml = `<i class="${category.icon} me-2"></i>`;
        const titleHtml = `<strong>${category.name}</strong>`;
        const messageHtml = `<div class="error-message">${error.displayMessage}</div>`;
        
        let detailsHtml = '';
        if (error.details && Object.keys(error.details).length > 0) {
            detailsHtml = `
                <div class="error-details mt-2" style="display: none;">
                    <small class="text-muted">
                        <strong>Деталі:</strong><br>
                        ${this.formatErrorDetails(error.details)}
                    </small>
                </div>
            `;
        }

        let actionsHtml = '';
        if (error.category === 'network' || error.category === 'system') {
            actionsHtml = `
                <div class="error-actions mt-2">
                    <button type="button" class="btn btn-sm btn-outline-${category.color} me-2" onclick="window.errorDisplaySystem.retryLastAction('${error.id}')">
                        <i class="fas fa-redo me-1"></i>Спробувати знову
                    </button>
                    <button type="button" class="btn btn-sm btn-outline-secondary" onclick="window.errorDisplaySystem.reportError('${error.id}')">
                        <i class="fas fa-bug me-1"></i>Повідомити про помилку
                    </button>
                </div>
            `;
        }

        errorElement.innerHTML = `
            <div class="d-flex align-items-start">
                <div class="flex-shrink-0">
                    ${iconHtml}
                </div>
                <div class="flex-grow-1">
                    ${titleHtml}
                    ${messageHtml}
                    ${detailsHtml}
                    ${actionsHtml}
                </div>
                <div class="flex-shrink-0">
                    ${detailsHtml ? `<button type="button" class="btn btn-sm btn-link p-0 me-2" onclick="window.errorDisplaySystem.toggleErrorDetails('${error.id}')">
                        <i class="fas fa-info-circle"></i>
                    </button>` : ''}
                    <button type="button" class="btn-close" onclick="window.errorDisplaySystem.hideError('${error.id}')"></button>
                </div>
            </div>
        `;

        return errorElement;
    }

    formatErrorDetails(details) {
        let formatted = '';
        for (const [key, value] of Object.entries(details)) {
            if (value !== null && value !== undefined) {
                formatted += `<strong>${key}:</strong> ${value}<br>`;
            }
        }
        return formatted;
    }

    getDisplayMessage(error) {
        const language = this.currentLanguage || 'uk';
        
        // Check if we have a template for this error code
        if (this.errorTemplates.has(error.code)) {
            const template = this.errorTemplates.get(error.code);
            let message = template[language] || template.uk || template.en;
            
            // Replace placeholders
            if (error.field) {
                message = message.replace('{field}', error.field);
            }
            if (error.details) {
                for (const [key, value] of Object.entries(error.details)) {
                    message = message.replace(`{${key}}`, value);
                }
            }
            
            return message;
        }
        
        // Return original message if no template found
        return error.message || 'Невідома помилка';
    }

    hideError(errorId) {
        const errorElement = document.querySelector(`[data-error-id="${errorId}"]`);
        if (errorElement) {
            errorElement.classList.remove('show');
            setTimeout(() => {
                this.removeErrorElement(errorId);
            }, 300);
        }
    }

    removeErrorElement(errorId) {
        const errorElement = document.querySelector(`[data-error-id="${errorId}"]`);
        if (errorElement) {
            errorElement.remove();
        }
        
        // Remove from queue
        this.errorQueue = this.errorQueue.filter(error => error.id !== errorId);
    }

    toggleErrorDetails(errorId) {
        const errorElement = document.querySelector(`[data-error-id="${errorId}"]`);
        if (errorElement) {
            const detailsElement = errorElement.querySelector('.error-details');
            if (detailsElement) {
                const isVisible = detailsElement.style.display !== 'none';
                detailsElement.style.display = isVisible ? 'none' : 'block';
                
                const toggleButton = errorElement.querySelector('.fa-info-circle');
                if (toggleButton) {
                    toggleButton.className = isVisible ? 'fas fa-info-circle' : 'fas fa-info-circle text-primary';
                }
            }
        }
    }

    retryLastAction(errorId) {
        const error = this.errorHistory.find(e => e.id === errorId);
        if (error && error.retryCallback) {
            error.retryCallback();
        } else {
            // Try to reload the page or retry the last form submission
            if (window.lastFormSubmission) {
                window.lastFormSubmission();
            } else {
                window.location.reload();
            }
        }
    }

    reportError(errorId) {
        const error = this.errorHistory.find(e => e.id === errorId);
        if (error) {
            // Create error report
            const errorReport = {
                id: error.id,
                category: error.category,
                code: error.code,
                message: error.message,
                timestamp: error.timestamp,
                url: window.location.href,
                userAgent: navigator.userAgent,
                details: error.details
            };
            
            // Send to server or show modal for user to report
            this.sendErrorReport(errorReport);
        }
    }

    sendErrorReport(errorReport) {
        // Send error report to server
        fetch('/api/error-report/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCsrfToken()
            },
            body: JSON.stringify(errorReport)
        }).then(response => {
            if (response.ok) {
                this.showSuccess('Повідомлення про помилку надіслано');
            } else {
                this.showError({
                    category: 'network',
                    code: 'report_error',
                    message: 'Не вдалося надіслати повідомлення про помилку'
                });
            }
        }).catch(error => {
            console.error('Error sending error report:', error);
        });
    }

    showSuccess(message) {
        const successElement = document.createElement('div');
        successElement.className = 'alert alert-success alert-dismissible fade show';
        successElement.innerHTML = `
            <i class="fas fa-check-circle me-2"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        this.errorContainer.insertBefore(successElement, this.errorContainer.firstChild);
        
        setTimeout(() => {
            successElement.remove();
        }, 3000);
    }

    clearAllErrors() {
        this.errorQueue = [];
        this.errorContainer.innerHTML = '';
    }

    clearErrorsByCategory(category) {
        this.errorQueue = this.errorQueue.filter(error => error.category !== category);
        
        const errorElements = this.errorContainer.querySelectorAll(`[data-error-category="${category}"]`);
        errorElements.forEach(element => element.remove());
    }

    getErrorHistory() {
        return this.errorHistory;
    }

    getActiveErrors() {
        return this.errorQueue;
    }

    generateErrorId() {
        return 'error_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    getCsrfToken() {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
        return csrfToken ? csrfToken.value : '';
    }

    logError(error) {
        if (console && console.error) {
            console.error('Error Display System:', error);
        }
    }

    // Helper methods for common error scenarios
    handleFormValidation(form, validationResult) {
        if (!validationResult.is_valid) {
            this.clearErrorsByCategory('validation');
            this.showValidationErrors(validationResult.errors);
            
            // Scroll to first error
            const firstError = this.errorContainer.querySelector('.alert');
            if (firstError) {
                firstError.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        }
    }

    handleAjaxError(xhr, textStatus, errorThrown) {
        // Try to parse JSON error response
        let errorData = null;
        try {
            errorData = JSON.parse(xhr.responseText);
        } catch (e) {
            // Not JSON, use default handling
        }

        if (errorData && errorData.errors) {
            this.showValidationErrors(errorData.errors);
        } else {
            this.showNetworkError(xhr, textStatus, errorThrown);
        }
    }

    // Integration with form validation
    integrateWithValidation(validationSystem) {
        if (validationSystem) {
            validationSystem.onValidationError = (errors) => {
                this.showValidationErrors(errors);
            };
        }
    }
}

// Initialize error display system
const errorDisplaySystem = new ErrorDisplaySystem();

// Make it globally available
window.errorDisplaySystem = errorDisplaySystem;

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ErrorDisplaySystem;
} 