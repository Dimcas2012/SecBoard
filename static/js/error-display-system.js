/**
 * Error Display System
 * Provides categorized error display with priority handling and auto-hide functionality
 */

class ErrorDisplaySystem {
    constructor() {
        this.errorContainer = null;
        this.errorQueue = [];
        this.activeErrors = new Map();
        this.maxErrors = 5;
        this.defaultTimeout = 5000;
        this.categories = {
            validation: { icon: 'fas fa-exclamation-triangle', color: 'warning', priority: 1 },
            network: { icon: 'fas fa-wifi', color: 'danger', priority: 2 },
            security: { icon: 'fas fa-shield-alt', color: 'danger', priority: 3 },
            file: { icon: 'fas fa-file-alt', color: 'warning', priority: 1 },
            permission: { icon: 'fas fa-lock', color: 'danger', priority: 2 },
            system: { icon: 'fas fa-cog', color: 'danger', priority: 3 },
            user: { icon: 'fas fa-user', color: 'info', priority: 0 },
            general: { icon: 'fas fa-info-circle', color: 'info', priority: 0 }
        };
        this.init();
    }

    init() {
        this.createErrorContainer();
        this.setupEventListeners();
        this.loadLanguageStrings();
    }

    createErrorContainer() {
        // Check if container already exists
        this.errorContainer = document.getElementById('error-display-container');
        
        if (!this.errorContainer) {
            this.errorContainer = document.createElement('div');
            this.errorContainer.id = 'error-display-container';
            this.errorContainer.className = 'error-display-container position-fixed top-0 end-0 p-3';
            this.errorContainer.style.cssText = `
                z-index: 9999;
                max-width: 400px;
                pointer-events: none;
            `;
            document.body.appendChild(this.errorContainer);
        }
    }

    setupEventListeners() {
        // Listen for global errors
        window.addEventListener('error', (event) => {
            this.showError('system', 'JavaScript Error', event.error?.message || 'An unexpected error occurred');
        });

        // Listen for unhandled promise rejections
        window.addEventListener('unhandledrejection', (event) => {
            this.showError('system', 'Promise Rejection', event.reason?.message || 'An unhandled promise rejection occurred');
        });

        // Listen for custom error events
        document.addEventListener('customError', (event) => {
            const { category, title, message, details } = event.detail;
            this.showError(category, title, message, details);
        });
    }

    showError(category = 'general', title = '', message = '', details = null, options = {}) {
        // Don't show network errors (status 0) to users
        if (category === 'network') {
            const status = details?.status || 0;
            if (status === 0 || message?.includes('HTTP error 0') || message?.includes('NetworkError') || message?.includes('Failed to fetch')) {
                // Only log to console, don't show to user
                console.error('Network error (not shown to user):', { category, title, message, details });
                return null;
            }
        }
        
        const errorId = this.generateErrorId();
        const categoryConfig = this.categories[category] || this.categories.general;
        
        const errorData = {
            id: errorId,
            category,
            title,
            message,
            details,
            timestamp: new Date(),
            priority: categoryConfig.priority,
            timeout: options.timeout || this.defaultTimeout,
            persistent: options.persistent || false,
            retryable: options.retryable || false,
            onRetry: options.onRetry || null
        };

        this.errorQueue.push(errorData);
        this.processErrorQueue();
        
        return errorId;
    }

    processErrorQueue() {
        // Sort by priority (higher priority first)
        this.errorQueue.sort((a, b) => b.priority - a.priority);
        
        // Remove excess errors if queue is too long
        while (this.errorQueue.length > this.maxErrors) {
            this.errorQueue.shift();
        }

        // Display errors
        while (this.errorQueue.length > 0 && this.activeErrors.size < this.maxErrors) {
            const errorData = this.errorQueue.shift();
            this.displayError(errorData);
        }
    }

    displayError(errorData) {
        const categoryConfig = this.categories[errorData.category] || this.categories.general;
        const errorElement = this.createErrorElement(errorData, categoryConfig);
        
        // Add to active errors
        this.activeErrors.set(errorData.id, errorData);
        
        // Add to container
        this.errorContainer.appendChild(errorElement);
        
        // Trigger animation
        setTimeout(() => {
            errorElement.classList.add('show');
        }, 10);

        // Auto-hide if not persistent
        if (!errorData.persistent && errorData.timeout > 0) {
            setTimeout(() => {
                this.hideError(errorData.id);
            }, errorData.timeout);
        }
    }

    createErrorElement(errorData, categoryConfig) {
        const errorElement = document.createElement('div');
        errorElement.className = `alert alert-${categoryConfig.color} alert-dismissible fade error-alert`;
        errorElement.style.cssText = `
            pointer-events: auto;
            margin-bottom: 10px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            border-left: 4px solid var(--bs-${categoryConfig.color});
        `;
        errorElement.dataset.errorId = errorData.id;

        const timeString = errorData.timestamp.toLocaleTimeString();
        const hasDetails = errorData.details && (typeof errorData.details === 'object' || errorData.details.length > 0);
        
        errorElement.innerHTML = `
            <div class="d-flex align-items-start">
                <div class="me-2">
                    <i class="${categoryConfig.icon}"></i>
                </div>
                <div class="flex-grow-1">
                    <div class="fw-bold">${errorData.title}</div>
                    <div class="small text-muted mb-1">${timeString} • ${this.getCategoryLabel(errorData.category)}</div>
                    <div>${errorData.message}</div>
                    ${hasDetails ? `
                        <div class="mt-2">
                            <button class="btn btn-sm btn-outline-secondary toggle-details" type="button">
                                <i class="fas fa-chevron-down me-1"></i>
                                ${this.getLanguageStrings().showDetails}
                            </button>
                        </div>
                        <div class="error-details mt-2" style="display: none;">
                            <small class="text-muted">
                                ${this.formatErrorDetails(errorData.details)}
                            </small>
                        </div>
                    ` : ''}
                    ${errorData.retryable ? `
                        <div class="mt-2">
                            <button class="btn btn-sm btn-outline-primary retry-button" type="button">
                                <i class="fas fa-redo me-1"></i>
                                ${this.getLanguageStrings().retry}
                            </button>
                        </div>
                    ` : ''}
                </div>
                <button type="button" class="btn-close" aria-label="Close"></button>
            </div>
        `;

        // Add event listeners
        this.addErrorEventListeners(errorElement, errorData);

        return errorElement;
    }

    addErrorEventListeners(errorElement, errorData) {
        // Close button
        const closeBtn = errorElement.querySelector('.btn-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                this.hideError(errorData.id);
            });
        }

        // Details toggle
        const detailsBtn = errorElement.querySelector('.toggle-details');
        if (detailsBtn) {
            detailsBtn.addEventListener('click', () => {
                const details = errorElement.querySelector('.error-details');
                const icon = detailsBtn.querySelector('i');
                
                if (details.style.display === 'none') {
                    details.style.display = 'block';
                    icon.className = 'fas fa-chevron-up me-1';
                    detailsBtn.innerHTML = `<i class="fas fa-chevron-up me-1"></i>${this.getLanguageStrings().hideDetails}`;
                } else {
                    details.style.display = 'none';
                    icon.className = 'fas fa-chevron-down me-1';
                    detailsBtn.innerHTML = `<i class="fas fa-chevron-down me-1"></i>${this.getLanguageStrings().showDetails}`;
                }
            });
        }

        // Retry button
        const retryBtn = errorElement.querySelector('.retry-button');
        if (retryBtn && errorData.onRetry) {
            retryBtn.addEventListener('click', () => {
                retryBtn.disabled = true;
                retryBtn.innerHTML = `<i class="fas fa-spinner fa-spin me-1"></i>${this.getLanguageStrings().retrying}`;
                
                try {
                    const result = errorData.onRetry();
                    if (result instanceof Promise) {
                        result.then(() => {
                            this.hideError(errorData.id);
                        }).catch((error) => {
                            retryBtn.disabled = false;
                            retryBtn.innerHTML = `<i class="fas fa-redo me-1"></i>${this.getLanguageStrings().retry}`;
                        });
                    } else {
                        this.hideError(errorData.id);
                    }
                } catch (error) {
                    retryBtn.disabled = false;
                    retryBtn.innerHTML = `<i class="fas fa-redo me-1"></i>${this.getLanguageStrings().retry}`;
                }
            });
        }
    }

    hideError(errorId) {
        const errorElement = this.errorContainer.querySelector(`[data-error-id="${errorId}"]`);
        if (errorElement) {
            errorElement.classList.remove('show');
            errorElement.classList.add('fade-out');
            
            setTimeout(() => {
                if (errorElement.parentNode) {
                    errorElement.parentNode.removeChild(errorElement);
                }
                this.activeErrors.delete(errorId);
                this.processErrorQueue(); // Process any queued errors
            }, 300);
        }
    }

    clearAllErrors() {
        this.errorQueue = [];
        this.activeErrors.forEach((errorData, errorId) => {
            this.hideError(errorId);
        });
    }

    formatErrorDetails(details) {
        if (typeof details === 'string') {
            return details;
        } else if (typeof details === 'object') {
            if (details.stack) {
                return `<pre class="small">${details.stack}</pre>`;
            } else {
                return `<pre class="small">${JSON.stringify(details, null, 2)}</pre>`;
            }
        } else {
            return String(details);
        }
    }

    getCategoryLabel(category) {
        const labels = this.getLanguageStrings().categories;
        return labels[category] || labels.general;
    }

    generateErrorId() {
        return 'error_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    loadLanguageStrings() {
        const currentLang = document.documentElement.lang || 'uk';
        this.currentLanguage = currentLang;
    }

    getLanguageStrings() {
        const lang = this.currentLanguage || 'uk';
        
        const strings = {
            uk: {
                showDetails: 'Показати деталі',
                hideDetails: 'Сховати деталі',
                retry: 'Повторити',
                retrying: 'Повторення...',
                categories: {
                    validation: 'Валідація',
                    network: 'Мережа',
                    security: 'Безпека',
                    file: 'Файл',
                    permission: 'Дозволи',
                    system: 'Система',
                    user: 'Користувач',
                    general: 'Загальне'
                }
            },
            en: {
                showDetails: 'Show Details',
                hideDetails: 'Hide Details',
                retry: 'Retry',
                retrying: 'Retrying...',
                categories: {
                    validation: 'Validation',
                    network: 'Network',
                    security: 'Security',
                    file: 'File',
                    permission: 'Permission',
                    system: 'System',
                    user: 'User',
                    general: 'General'
                }
            },
            ru: {
                showDetails: 'Показать детали',
                hideDetails: 'Скрыть детали',
                retry: 'Повторить',
                retrying: 'Повторение...',
                categories: {
                    validation: 'Валидация',
                    network: 'Сеть',
                    security: 'Безопасность',
                    file: 'Файл',
                    permission: 'Разрешения',
                    system: 'Система',
                    user: 'Пользователь',
                    general: 'Общее'
                }
            }
        };

        return strings[lang] || strings.uk;
    }

    // Public API methods
    showValidationError(message, details = null) {
        return this.showError('validation', 'Validation Error', message, details);
    }

    showNetworkError(message, details = null, retryCallback = null) {
        // Don't show network errors (status 0) to users
        const status = details?.status || 0;
        if (status === 0 || message?.includes('HTTP error 0') || message?.includes('NetworkError') || message?.includes('Failed to fetch')) {
            // Only log to console, don't show to user
            console.error('Network error (not shown to user):', { message, details, retryCallback });
            return null;
        }
        
        return this.showError('network', 'Network Error', message, details, {
            retryable: !!retryCallback,
            onRetry: retryCallback
        });
    }

    showSecurityError(message, details = null) {
        return this.showError('security', 'Security Error', message, details, {
            persistent: true
        });
    }

    showFileError(message, details = null) {
        return this.showError('file', 'File Error', message, details);
    }

    showPermissionError(message, details = null) {
        return this.showError('permission', 'Permission Error', message, details);
    }

    showSystemError(message, details = null) {
        return this.showError('system', 'System Error', message, details);
    }

    showUserMessage(message, details = null) {
        return this.showError('user', 'Information', message, details);
    }

    showSuccess(message, timeout = 3000) {
        const successId = this.generateErrorId();
        const successElement = document.createElement('div');
        successElement.className = 'alert alert-success alert-dismissible fade show';
        successElement.style.cssText = `
            pointer-events: auto;
            margin-bottom: 10px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            border-left: 4px solid var(--bs-success);
        `;
        successElement.dataset.errorId = successId;

        successElement.innerHTML = `
            <div class="d-flex align-items-start">
                <div class="me-2">
                    <i class="fas fa-check-circle"></i>
                </div>
                <div class="flex-grow-1">
                    ${message}
                </div>
                <button type="button" class="btn-close" aria-label="Close"></button>
            </div>
        `;

        // Add close event listener
        const closeBtn = successElement.querySelector('.btn-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                this.hideSuccess(successId);
            });
        }

        this.errorContainer.appendChild(successElement);

        // Auto-hide
        if (timeout > 0) {
            setTimeout(() => {
                this.hideSuccess(successId);
            }, timeout);
        }

        return successId;
    }

    hideSuccess(successId) {
        const successElement = this.errorContainer.querySelector(`[data-error-id="${successId}"]`);
        if (successElement) {
            successElement.classList.remove('show');
            successElement.classList.add('fade-out');
            
            setTimeout(() => {
                if (successElement.parentNode) {
                    successElement.parentNode.removeChild(successElement);
                }
            }, 300);
        }
    }
}

// Add CSS for animations
const errorDisplayStyle = document.createElement('style');
errorDisplayStyle.textContent = `
    .error-alert {
        transform: translateX(100%);
        transition: transform 0.3s ease-in-out;
    }
    
    .error-alert.show {
        transform: translateX(0);
    }
    
    .error-alert.fade-out {
        transform: translateX(100%);
        opacity: 0;
    }
    
    .error-display-container {
        max-height: 100vh;
        overflow-y: auto;
    }
    
    .error-details pre {
        background-color: rgba(0,0,0,0.05);
        padding: 8px;
        border-radius: 4px;
        max-height: 200px;
        overflow-y: auto;
    }
`;
document.head.appendChild(errorDisplayStyle);

// Initialize the error display system when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    window.errorDisplaySystem = new ErrorDisplaySystem();
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ErrorDisplaySystem;
}
