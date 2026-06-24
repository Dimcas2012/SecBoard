/**
 * SecBoard Risk Assessment - Error Display System
 * Unified error handling and display with categorization and priority management
 */

class ErrorDisplaySystem {
    constructor(options = {}) {
        this.options = {
            container: '#error-container',
            autoHide: true,
            autoHideDelay: 8000,
            maxErrors: 10,
            showRetryButton: true,
            enableSound: false,
            position: 'top-right',
            animation: 'slide',
            language: 'uk',
            ...options
        };
        
        this.errors = new Map();
        this.errorQueue = [];
        this.categories = new Map();
        this.retryCallbacks = new Map();
        this.soundEnabled = this.options.enableSound;
        
        this.init();
    }
    
    init() {
        this.setupContainer();
        this.setupCategories();
        this.setupEventListeners();
        this.loadLanguage();
    }
    
    setupContainer() {
        let container = document.querySelector(this.options.container);
        if (!container) {
            container = document.createElement('div');
            container.id = 'error-container';
            container.className = `error-display-container position-${this.options.position}`;
            document.body.appendChild(container);
        }
        
        // Add CSS classes
        container.classList.add('error-display-container');
        container.classList.add(`position-${this.options.position}`);
        
        this.container = container;
    }
    
    setupCategories() {
        // Define error categories with their properties
        this.categories.set('validation', {
            name: 'Validation Error',
            icon: 'fas fa-exclamation-triangle',
            color: 'warning',
            priority: 3,
            autoHide: true,
            sound: false
        });
        
        this.categories.set('network', {
            name: 'Network Error',
            icon: 'fas fa-wifi',
            color: 'danger',
            priority: 4,
            autoHide: false,
            sound: true
        });
        
        this.categories.set('security', {
            name: 'Security Error',
            icon: 'fas fa-shield-alt',
            color: 'danger',
            priority: 5,
            autoHide: false,
            sound: true
        });
        
        this.categories.set('file', {
            name: 'File Error',
            icon: 'fas fa-file-alt',
            color: 'warning',
            priority: 3,
            autoHide: true,
            sound: false
        });
        
        this.categories.set('permission', {
            name: 'Permission Error',
            icon: 'fas fa-lock',
            color: 'danger',
            priority: 4,
            autoHide: false,
            sound: true
        });
        
        this.categories.set('system', {
            name: 'System Error',
            icon: 'fas fa-cog',
            color: 'danger',
            priority: 5,
            autoHide: false,
            sound: true
        });
        
        this.categories.set('user', {
            name: 'User Error',
            icon: 'fas fa-user',
            color: 'info',
            priority: 2,
            autoHide: true,
            sound: false
        });
        
        this.categories.set('general', {
            name: 'Error',
            icon: 'fas fa-exclamation-circle',
            color: 'secondary',
            priority: 1,
            autoHide: true,
            sound: false
        });
    }
    
    setupEventListeners() {
        // Listen for global errors
        window.addEventListener('error', (event) => {
            this.showError({
                message: event.message,
                category: 'system',
                details: {
                    filename: event.filename,
                    lineno: event.lineno,
                    colno: event.colno,
                    error: event.error
                }
            });
        });
        
        // Listen for unhandled promise rejections
        window.addEventListener('unhandledrejection', (event) => {
            this.showError({
                message: 'Unhandled promise rejection',
                category: 'system',
                details: {
                    reason: event.reason
                }
            });
        });
        
        // Listen for AJAX errors
        $(document).ajaxError((event, jqXHR, ajaxSettings, thrownError) => {
            this.handleAjaxError(jqXHR, ajaxSettings, thrownError);
        });
    }
    
    loadLanguage() {
        this.messages = this.getMessages(this.options.language);
    }
    
    getMessages(language) {
        const messages = {
            uk: {
                retry: 'Повторити',
                dismiss: 'Приховати',
                details: 'Деталі',
                hideDetails: 'Приховати деталі',
                reportError: 'Повідомити про помилку',
                errorReported: 'Помилка відправлена',
                categories: {
                    validation: 'Помилка валідації',
                    network: 'Помилка мережі',
                    security: 'Помилка безпеки',
                    file: 'Помилка файлу',
                    permission: 'Помилка доступу',
                    system: 'Системна помилка',
                    user: 'Помилка користувача',
                    general: 'Помилка'
                }
            },
            en: {
                retry: 'Retry',
                dismiss: 'Dismiss',
                details: 'Details',
                hideDetails: 'Hide Details',
                reportError: 'Report Error',
                errorReported: 'Error Reported',
                categories: {
                    validation: 'Validation Error',
                    network: 'Network Error',
                    security: 'Security Error',
                    file: 'File Error',
                    permission: 'Permission Error',
                    system: 'System Error',
                    user: 'User Error',
                    general: 'Error'
                }
            },
            ru: {
                retry: 'Повторить',
                dismiss: 'Скрыть',
                details: 'Детали',
                hideDetails: 'Скрыть детали',
                reportError: 'Сообщить об ошибке',
                errorReported: 'Ошибка отправлена',
                categories: {
                    validation: 'Ошибка валидации',
                    network: 'Сетевая ошибка',
                    security: 'Ошибка безопасности',
                    file: 'Ошибка файла',
                    permission: 'Ошибка доступа',
                    system: 'Системная ошибка',
                    user: 'Ошибка пользователя',
                    general: 'Ошибка'
                }
            }
        };
        
        return messages[language] || messages.en;
    }
    
    showError(errorConfig) {
        // Don't show network errors (status 0) to users
        const categoryName = errorConfig.category || 'general';
        const status = errorConfig.details?.status || 0;
        
        if (categoryName === 'network' && (status === 0 || errorConfig.message?.includes('HTTP error 0') || errorConfig.message?.includes('NetworkError'))) {
            // Only log to console, don't show to user
            console.error('Network error (not shown to user):', errorConfig);
            return null;
        }
        
        const errorId = this.generateErrorId();
        const category = this.categories.get(categoryName);
        
        const error = {
            id: errorId,
            message: errorConfig.message,
            category: categoryName,
            details: errorConfig.details || {},
            timestamp: new Date(),
            priority: category.priority,
            autoHide: errorConfig.autoHide !== undefined ? errorConfig.autoHide : category.autoHide,
            retryCallback: errorConfig.retryCallback,
            reportCallback: errorConfig.reportCallback
        };
        
        this.errors.set(errorId, error);
        this.displayError(error);
        
        // Play sound if enabled
        if (this.soundEnabled && category.sound) {
            this.playErrorSound(error.category);
        }
        
        // Auto-hide if configured
        if (error.autoHide) {
            setTimeout(() => {
                this.hideError(errorId);
            }, this.options.autoHideDelay);
        }
        
        // Manage error queue
        this.manageErrorQueue();
        
        return errorId;
    }
    
    displayError(error) {
        const category = this.categories.get(error.category);
        const errorElement = this.createErrorElement(error, category);
        
        // Add to container
        this.container.appendChild(errorElement);
        
        // Apply animation
        this.applyAnimation(errorElement, 'show');
        
        // Store reference
        error.element = errorElement;
    }
    
    createErrorElement(error, category) {
        const errorDiv = document.createElement('div');
        errorDiv.className = `alert alert-${category.color} error-item`;
        errorDiv.setAttribute('data-error-id', error.id);
        errorDiv.setAttribute('role', 'alert');
        
        const headerDiv = document.createElement('div');
        headerDiv.className = 'error-header d-flex justify-content-between align-items-center';
        
        const titleDiv = document.createElement('div');
        titleDiv.className = 'error-title';
        titleDiv.innerHTML = `
            <i class="${category.icon} me-2"></i>
            <strong>${this.messages.categories[error.category]}</strong>
            <small class="text-muted ms-2">${this.formatTimestamp(error.timestamp)}</small>
        `;
        
        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'error-actions';
        
        // Retry button
        if (error.retryCallback && this.options.showRetryButton) {
            const retryBtn = document.createElement('button');
            retryBtn.className = 'btn btn-sm btn-outline-secondary me-2';
            retryBtn.innerHTML = `<i class="fas fa-redo me-1"></i>${this.messages.retry}`;
            retryBtn.onclick = () => this.retryError(error.id);
            actionsDiv.appendChild(retryBtn);
        }
        
        // Dismiss button
        const dismissBtn = document.createElement('button');
        dismissBtn.className = 'btn btn-sm btn-outline-secondary';
        dismissBtn.innerHTML = `<i class="fas fa-times me-1"></i>${this.messages.dismiss}`;
        dismissBtn.onclick = () => this.hideError(error.id);
        actionsDiv.appendChild(dismissBtn);
        
        headerDiv.appendChild(titleDiv);
        headerDiv.appendChild(actionsDiv);
        
        const messageDiv = document.createElement('div');
        messageDiv.className = 'error-message mt-2';
        messageDiv.textContent = error.message;
        
        errorDiv.appendChild(headerDiv);
        errorDiv.appendChild(messageDiv);
        
        // Add details if available
        if (error.details && Object.keys(error.details).length > 0) {
            const detailsDiv = this.createDetailsSection(error);
            errorDiv.appendChild(detailsDiv);
        }
        
        // Add report button if callback provided
        if (error.reportCallback) {
            const reportDiv = document.createElement('div');
            reportDiv.className = 'error-report mt-2';
            
            const reportBtn = document.createElement('button');
            reportBtn.className = 'btn btn-sm btn-outline-info';
            reportBtn.innerHTML = `<i class="fas fa-bug me-1"></i>${this.messages.reportError}`;
            reportBtn.onclick = () => this.reportError(error.id);
            
            reportDiv.appendChild(reportBtn);
            errorDiv.appendChild(reportDiv);
        }
        
        return errorDiv;
    }
    
    createDetailsSection(error) {
        const detailsDiv = document.createElement('div');
        detailsDiv.className = 'error-details mt-2';
        
        const toggleBtn = document.createElement('button');
        toggleBtn.className = 'btn btn-sm btn-link p-0 text-decoration-none';
        toggleBtn.innerHTML = `<i class="fas fa-chevron-down me-1"></i>${this.messages.details}`;
        
        const detailsContent = document.createElement('div');
        detailsContent.className = 'error-details-content mt-2';
        detailsContent.style.display = 'none';
        
        const detailsTable = document.createElement('table');
        detailsTable.className = 'table table-sm table-borderless';
        
        for (const [key, value] of Object.entries(error.details)) {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td class="fw-bold">${key}:</td>
                <td>${this.formatDetailValue(value)}</td>
            `;
            detailsTable.appendChild(row);
        }
        
        detailsContent.appendChild(detailsTable);
        
        toggleBtn.onclick = () => {
            const isVisible = detailsContent.style.display !== 'none';
            detailsContent.style.display = isVisible ? 'none' : 'block';
            toggleBtn.innerHTML = isVisible 
                ? `<i class="fas fa-chevron-down me-1"></i>${this.messages.details}`
                : `<i class="fas fa-chevron-up me-1"></i>${this.messages.hideDetails}`;
        };
        
        detailsDiv.appendChild(toggleBtn);
        detailsDiv.appendChild(detailsContent);
        
        return detailsDiv;
    }
    
    formatDetailValue(value) {
        if (typeof value === 'object') {
            return `<pre class="mb-0">${JSON.stringify(value, null, 2)}</pre>`;
        }
        return String(value);
    }
    
    hideError(errorId) {
        const error = this.errors.get(errorId);
        if (!error || !error.element) return;
        
        this.applyAnimation(error.element, 'hide', () => {
            if (error.element.parentNode) {
                error.element.parentNode.removeChild(error.element);
            }
            this.errors.delete(errorId);
        });
    }
    
    retryError(errorId) {
        const error = this.errors.get(errorId);
        if (!error || !error.retryCallback) return;
        
        try {
            error.retryCallback();
            this.hideError(errorId);
        } catch (e) {
            console.error('Error in retry callback:', e);
        }
    }
    
    reportError(errorId) {
        const error = this.errors.get(errorId);
        if (!error || !error.reportCallback) return;
        
        try {
            error.reportCallback(error);
            
            // Update button to show success
            const reportBtn = error.element.querySelector('.error-report button');
            if (reportBtn) {
                reportBtn.innerHTML = `<i class="fas fa-check me-1"></i>${this.messages.errorReported}`;
                reportBtn.disabled = true;
                reportBtn.classList.remove('btn-outline-info');
                reportBtn.classList.add('btn-outline-success');
            }
        } catch (e) {
            console.error('Error in report callback:', e);
        }
    }
    
    applyAnimation(element, type, callback) {
        const animations = {
            slide: {
                show: 'slideInRight',
                hide: 'slideOutRight'
            },
            fade: {
                show: 'fadeIn',
                hide: 'fadeOut'
            },
            bounce: {
                show: 'bounceIn',
                hide: 'bounceOut'
            }
        };
        
        const animationName = animations[this.options.animation] || animations.slide;
        const className = `animated ${animationName[type]}`;
        
        element.classList.add(...className.split(' '));
        
        if (callback) {
            const duration = type === 'show' ? 500 : 300;
            setTimeout(callback, duration);
        }
    }
    
    handleAjaxError(jqXHR, ajaxSettings, thrownError) {
        let category = 'network';
        let message = 'Network request failed';
        let details = {
            status: jqXHR.status,
            statusText: jqXHR.statusText,
            url: ajaxSettings.url,
            method: ajaxSettings.type || 'GET'
        };
        
        // Categorize based on status code
        if (jqXHR.status === 401) {
            category = 'permission';
            message = 'Authentication required';
        } else if (jqXHR.status === 403) {
            category = 'permission';
            message = 'Access forbidden';
        } else if (jqXHR.status === 404) {
            category = 'network';
            message = 'Resource not found';
        } else if (jqXHR.status === 422) {
            category = 'validation';
            message = 'Validation failed';
        } else if (jqXHR.status >= 500) {
            category = 'system';
            message = 'Server error';
        }
        
        // Try to parse error response
        try {
            const response = JSON.parse(jqXHR.responseText);
            if (response.message) {
                message = response.message;
            }
            if (response.errors) {
                details.errors = response.errors;
            }
        } catch (e) {
            // Response is not JSON, use as-is
            if (jqXHR.responseText) {
                details.response = jqXHR.responseText;
            }
        }
        
        this.showError({
            message: message,
            category: category,
            details: details,
            retryCallback: () => {
                // Retry the original request
                $.ajax(ajaxSettings);
            }
        });
    }
    
    manageErrorQueue() {
        const errorElements = this.container.querySelectorAll('.error-item');
        
        if (errorElements.length > this.options.maxErrors) {
            // Remove oldest errors
            const elementsToRemove = errorElements.length - this.options.maxErrors;
            for (let i = 0; i < elementsToRemove; i++) {
                const element = errorElements[i];
                const errorId = element.getAttribute('data-error-id');
                this.hideError(errorId);
            }
        }
    }
    
    playErrorSound(category) {
        if (!this.soundEnabled) return;
        
        // Create audio context if not exists
        if (!this.audioContext) {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        }
        
        // Different sounds for different categories
        const frequencies = {
            validation: 800,
            network: 600,
            security: 400,
            file: 700,
            permission: 500,
            system: 300,
            user: 900,
            general: 650
        };
        
        const frequency = frequencies[category] || 650;
        
        // Create beep sound
        const oscillator = this.audioContext.createOscillator();
        const gainNode = this.audioContext.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(this.audioContext.destination);
        
        oscillator.frequency.value = frequency;
        oscillator.type = 'sine';
        
        gainNode.gain.setValueAtTime(0.1, this.audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, this.audioContext.currentTime + 0.3);
        
        oscillator.start(this.audioContext.currentTime);
        oscillator.stop(this.audioContext.currentTime + 0.3);
    }
    
    formatTimestamp(timestamp) {
        return timestamp.toLocaleTimeString();
    }
    
    generateErrorId() {
        return `error_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
    
    // Public API methods
    clear() {
        this.errors.forEach((error, id) => {
            this.hideError(id);
        });
    }
    
    clearCategory(category) {
        this.errors.forEach((error, id) => {
            if (error.category === category) {
                this.hideError(id);
            }
        });
    }
    
    getErrors() {
        return Array.from(this.errors.values());
    }
    
    getErrorsByCategory(category) {
        return this.getErrors().filter(error => error.category === category);
    }
    
    setLanguage(language) {
        this.options.language = language;
        this.loadLanguage();
    }
    
    enableSound() {
        this.soundEnabled = true;
    }
    
    disableSound() {
        this.soundEnabled = false;
    }
    
    updateOptions(newOptions) {
        this.options = { ...this.options, ...newOptions };
        this.loadLanguage();
    }
}

// Global error display system
window.ErrorDisplaySystem = ErrorDisplaySystem;

// Initialize global instance
window.errorDisplay = new ErrorDisplaySystem();

// Add CSS styles
const style = document.createElement('style');
style.textContent = `
.error-display-container {
    position: fixed;
    z-index: 9999;
    max-width: 400px;
    pointer-events: none;
}

.error-display-container.position-top-right {
    top: 20px;
    right: 20px;
}

.error-display-container.position-top-left {
    top: 20px;
    left: 20px;
}

.error-display-container.position-bottom-right {
    bottom: 20px;
    right: 20px;
}

.error-display-container.position-bottom-left {
    bottom: 20px;
    left: 20px;
}

.error-item {
    pointer-events: auto;
    margin-bottom: 10px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    border-left: 4px solid;
    animation-duration: 0.5s;
}

.error-header {
    font-size: 0.9em;
}

.error-title {
    flex-grow: 1;
}

.error-actions {
    flex-shrink: 0;
}

.error-message {
    font-size: 0.95em;
    line-height: 1.4;
}

.error-details-content {
    background-color: rgba(0, 0, 0, 0.05);
    border-radius: 4px;
    padding: 10px;
    font-size: 0.85em;
}

.error-details-content pre {
    font-size: 0.8em;
    background-color: rgba(0, 0, 0, 0.1);
    padding: 5px;
    border-radius: 3px;
}

.error-report {
    border-top: 1px solid rgba(0, 0, 0, 0.1);
    padding-top: 10px;
}

@keyframes slideInRight {
    from { transform: translateX(100%); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
}

@keyframes slideOutRight {
    from { transform: translateX(0); opacity: 1; }
    to { transform: translateX(100%); opacity: 0; }
}

@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

@keyframes fadeOut {
    from { opacity: 1; }
    to { opacity: 0; }
}

@keyframes bounceIn {
    0%, 20%, 40%, 60%, 80% { transform: translateY(0); opacity: 0; }
    100% { transform: translateY(0); opacity: 1; }
}

@keyframes bounceOut {
    0% { transform: translateY(0); opacity: 1; }
    100% { transform: translateY(-20px); opacity: 0; }
}
`;
document.head.appendChild(style);

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ErrorDisplaySystem;
} 