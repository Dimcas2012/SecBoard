/**
 * SecBoard Risk Reports - Asynchronous UX Components
 * Enhanced user experience for async operations with real-time feedback
 */

class AsyncUX {
    constructor() {
        this.activeOperations = new Map();
        this.progressTrackers = new Map();
        this.notificationQueue = [];
        this.init();
    }

    init() {
        this.setupProgressComponents();
        this.setupPollingFallback();
        this.setupEventListeners();
        this.initializeAsyncForms();
        this.setupRetryMechanisms();
    }

    // ===== PROGRESS TRACKING =====
    setupProgressComponents() {
        this.createProgressContainer();
        this.createToastContainer();
        this.setupProgressTemplates();
    }

    createProgressContainer() {
        if (document.getElementById('progress-container')) return;

        const container = document.createElement('div');
        container.id = 'progress-container';
        container.className = 'progress-container';
        container.innerHTML = `
            <div class="progress-header">
                <h4 class="progress-title">Виконання операцій</h4>
                <button class="progress-toggle btn btn-ghost btn-sm">
                    <i class="fas fa-chevron-down"></i>
                </button>
            </div>
            <div class="progress-list"></div>
        `;
        
        document.body.appendChild(container);
        this.setupProgressContainerEvents(container);
    }

    setupProgressContainerEvents(container) {
        const toggle = container.querySelector('.progress-toggle');
        const list = container.querySelector('.progress-list');
        
        toggle.addEventListener('click', () => {
            const isExpanded = list.style.display !== 'none';
            list.style.display = isExpanded ? 'none' : 'block';
            toggle.querySelector('i').className = isExpanded 
                ? 'fas fa-chevron-down' 
                : 'fas fa-chevron-up';
        });
    }

    createToastContainer() {
        if (document.getElementById('toast-container')) return;

        const container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    setupProgressTemplates() {
        this.progressTemplate = `
            <div class="progress-item" data-operation-id="{{id}}">
                <div class="progress-item-header">
                    <div class="progress-item-info">
                        <h5 class="progress-item-title">{{title}}</h5>
                        <p class="progress-item-description">{{description}}</p>
                    </div>
                    <div class="progress-item-actions">
                        <button class="btn btn-ghost btn-xs progress-cancel" data-operation-id="{{id}}">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                </div>
                <div class="progress-item-body">
                    <div class="progress-bar-container">
                        <div class="progress-bar" data-progress="{{progress}}"></div>
                        <span class="progress-text">{{progress}}%</span>
                    </div>
                    <div class="progress-details">
                        <span class="progress-status">{{status}}</span>
                        <span class="progress-time">{{elapsed}}</span>
                    </div>
                </div>
                <div class="progress-item-footer">
                    <div class="progress-logs"></div>
                </div>
            </div>
        `;

        this.toastTemplate = `
            <div class="toast toast-{{type}}" data-toast-id="{{id}}">
                <div class="toast-content">
                    <div class="toast-icon">
                        <i class="fas fa-{{icon}}"></i>
                    </div>
                    <div class="toast-body">
                        <h5 class="toast-title">{{title}}</h5>
                        <p class="toast-message">{{message}}</p>
                    </div>
                    <button class="toast-close">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="toast-progress"></div>
            </div>
        `;
    }

    // ===== HTTP POLLING FALLBACK =====

    setupPollingFallback() {
        // Fallback to HTTP polling for progress updates
        this.pollingInterval = setInterval(() => {
            this.pollProgressUpdates();
        }, 2000); // Poll every 2 seconds
    }

    async pollProgressUpdates() {
        if (this.activeOperations.size === 0) return;

        try {
            const operationIds = Array.from(this.activeOperations.keys());
            const response = await fetch('/api/risk-reports/progress/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({ operation_ids: operationIds })
            });

            if (response.ok) {
                const updates = await response.json();
                updates.forEach(update => {
                    this.updateProgress(update.operation_id, update.progress, update.status, update.details);
                });
            }
        } catch (error) {
            console.error('Polling error:', error);
        }
    }

    // ===== OPERATION MANAGEMENT =====
    startOperation(operationId, title, description = '') {
        const operation = {
            id: operationId,
            title: title,
            description: description,
            startTime: Date.now(),
            progress: 0,
            status: 'Початок...',
            logs: []
        };

        this.activeOperations.set(operationId, operation);
        this.createProgressItem(operation);
        this.showProgressContainer();
        
        // Show initial toast
        this.showToast('info', 'Операція розпочата', title);
        
        return operation;
    }

    updateProgress(operationId, progress, status, details = {}) {
        const operation = this.activeOperations.get(operationId);
        if (!operation) return;

        operation.progress = progress;
        operation.status = status;
        operation.lastUpdate = Date.now();

        if (details.logs) {
            operation.logs.push(...details.logs);
        }

        this.updateProgressItem(operation);
        
        // Update progress tracker if exists
        const tracker = this.progressTrackers.get(operationId);
        if (tracker) {
            tracker.update(progress, status, details);
        }
    }

    completeOperation(operationId, result = {}) {
        const operation = this.activeOperations.get(operationId);
        if (!operation) return;

        operation.progress = 100;
        operation.status = 'Завершено';
        operation.endTime = Date.now();
        operation.result = result;

        this.updateProgressItem(operation);
        
        // Show completion toast
        this.showToast('success', 'Операція завершена', operation.title);
        
        // Auto-remove after delay
        setTimeout(() => {
            this.removeOperation(operationId);
        }, 5000);

        // Trigger completion event
        this.dispatchOperationEvent('completed', operation);
    }

    errorOperation(operationId, error) {
        const operation = this.activeOperations.get(operationId);
        if (!operation) return;

        operation.status = 'Помилка';
        operation.error = error;
        operation.endTime = Date.now();

        this.updateProgressItem(operation);
        
        // Show error toast with retry option
        this.showToast('error', 'Помилка операції', error.message || 'Невідома помилка', {
            actions: [{
                text: 'Повторити',
                action: () => this.retryOperation(operationId)
            }]
        });

        // Trigger error event
        this.dispatchOperationEvent('error', operation);
    }

    removeOperation(operationId) {
        const operation = this.activeOperations.get(operationId);
        if (!operation) return;

        this.activeOperations.delete(operationId);
        this.progressTrackers.delete(operationId);
        
        const progressItem = document.querySelector(`[data-operation-id="${operationId}"]`);
        if (progressItem) {
            progressItem.style.animation = 'slideOut 0.3s ease-out forwards';
            setTimeout(() => {
                progressItem.remove();
                this.checkProgressContainerVisibility();
            }, 300);
        }
    }

    // ===== PROGRESS UI =====
    createProgressItem(operation) {
        const progressList = document.querySelector('.progress-list');
        if (!progressList) return;

        const html = this.progressTemplate
            .replace(/{{id}}/g, operation.id)
            .replace(/{{title}}/g, operation.title)
            .replace(/{{description}}/g, operation.description)
            .replace(/{{progress}}/g, operation.progress)
            .replace(/{{status}}/g, operation.status)
            .replace(/{{elapsed}}/g, this.formatElapsedTime(operation));

        const div = document.createElement('div');
        div.innerHTML = html;
        const progressItem = div.firstElementChild;
        
        progressList.appendChild(progressItem);
        
        // Add event listeners
        this.setupProgressItemEvents(progressItem, operation);
        
        // Animate in
        progressItem.style.animation = 'slideIn 0.3s ease-out forwards';
    }

    updateProgressItem(operation) {
        const progressItem = document.querySelector(`[data-operation-id="${operation.id}"]`);
        if (!progressItem) return;

        // Update progress bar
        const progressBar = progressItem.querySelector('.progress-bar');
        const progressText = progressItem.querySelector('.progress-text');
        const progressStatus = progressItem.querySelector('.progress-status');
        const progressTime = progressItem.querySelector('.progress-time');

        if (progressBar) {
            progressBar.style.width = `${operation.progress}%`;
            progressBar.setAttribute('data-progress', operation.progress);
        }
        
        if (progressText) {
            progressText.textContent = `${operation.progress}%`;
        }
        
        if (progressStatus) {
            progressStatus.textContent = operation.status;
        }
        
        if (progressTime) {
            progressTime.textContent = this.formatElapsedTime(operation);
        }

        // Update logs
        this.updateProgressLogs(progressItem, operation);
        
        // Update item state
        this.updateProgressItemState(progressItem, operation);
    }

    updateProgressLogs(progressItem, operation) {
        const logsContainer = progressItem.querySelector('.progress-logs');
        if (!logsContainer || !operation.logs.length) return;

        const latestLogs = operation.logs.slice(-3); // Show last 3 logs
        logsContainer.innerHTML = latestLogs.map(log => `
            <div class="progress-log">
                <span class="progress-log-time">${new Date(log.timestamp).toLocaleTimeString()}</span>
                <span class="progress-log-message">${log.message}</span>
            </div>
        `).join('');
    }

    updateProgressItemState(progressItem, operation) {
        // Remove existing state classes
        progressItem.classList.remove('progress-item-running', 'progress-item-completed', 'progress-item-error');
        
        // Add appropriate state class
        if (operation.error) {
            progressItem.classList.add('progress-item-error');
        } else if (operation.progress === 100) {
            progressItem.classList.add('progress-item-completed');
        } else {
            progressItem.classList.add('progress-item-running');
        }
    }

    setupProgressItemEvents(progressItem, operation) {
        // Cancel button
        const cancelBtn = progressItem.querySelector('.progress-cancel');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => {
                this.cancelOperation(operation.id);
            });
        }

        // Expand/collapse logs
        const header = progressItem.querySelector('.progress-item-header');
        if (header) {
            header.addEventListener('click', () => {
                const footer = progressItem.querySelector('.progress-item-footer');
                const isExpanded = footer.style.display !== 'none';
                footer.style.display = isExpanded ? 'none' : 'block';
            });
        }
    }

    showProgressContainer() {
        const container = document.getElementById('progress-container');
        if (container && !container.classList.contains('show')) {
            container.classList.add('show');
        }
    }

    checkProgressContainerVisibility() {
        const container = document.getElementById('progress-container');
        const progressList = container?.querySelector('.progress-list');
        
        if (container && progressList && progressList.children.length === 0) {
            container.classList.remove('show');
        }
    }

    // ===== TOAST NOTIFICATIONS =====
    showToast(type, title, message, options = {}) {
        const toastId = this.generateId();
        const iconMap = {
            success: 'check-circle',
            error: 'exclamation-circle',
            warning: 'exclamation-triangle',
            info: 'info-circle'
        };

        const html = this.toastTemplate
            .replace(/{{id}}/g, toastId)
            .replace(/{{type}}/g, type)
            .replace(/{{icon}}/g, iconMap[type] || 'info-circle')
            .replace(/{{title}}/g, title)
            .replace(/{{message}}/g, message);

        const div = document.createElement('div');
        div.innerHTML = html;
        const toast = div.firstElementChild;
        
        const container = document.getElementById('toast-container');
        if (container) {
            container.appendChild(toast);
            this.setupToastEvents(toast, options);
            
            // Animate in
            requestAnimationFrame(() => {
                toast.classList.add('show');
            });
            
            // Auto-remove after duration
            const duration = options.duration || 5000;
            if (duration > 0) {
                setTimeout(() => {
                    this.removeToast(toast);
                }, duration);
            }
        }

        return toast;
    }

    setupToastEvents(toast, options) {
        // Close button
        const closeBtn = toast.querySelector('.toast-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                this.removeToast(toast);
            });
        }

        // Action buttons
        if (options.actions) {
            const toastBody = toast.querySelector('.toast-body');
            const actionsDiv = document.createElement('div');
            actionsDiv.className = 'toast-actions';
            
            options.actions.forEach(action => {
                const btn = document.createElement('button');
                btn.className = 'btn btn-sm btn-outline';
                btn.textContent = action.text;
                btn.addEventListener('click', () => {
                    action.action();
                    this.removeToast(toast);
                });
                actionsDiv.appendChild(btn);
            });
            
            toastBody.appendChild(actionsDiv);
        }

        // Progress bar for timed toasts
        if (options.duration && options.duration > 0) {
            const progressBar = toast.querySelector('.toast-progress');
            if (progressBar) {
                progressBar.style.animation = `toastProgress ${options.duration}ms linear`;
            }
        }
    }

    removeToast(toast) {
        toast.classList.remove('show');
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }

    // ===== ASYNC FORMS =====
    initializeAsyncForms() {
        const asyncForms = document.querySelectorAll('form[data-async]');
        asyncForms.forEach(form => {
            this.setupAsyncForm(form);
        });
    }

    setupAsyncForm(form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
            const originalText = submitBtn?.textContent || submitBtn?.value;
            
            try {
                // Show loading state
                if (submitBtn) {
                    this.setLoadingState(submitBtn, true);
                }
                
                // Start operation tracking
                const operationId = this.generateId();
                const operationTitle = form.getAttribute('data-operation-title') || 'Обробка форми';
                this.startOperation(operationId, operationTitle);
                
                // Submit form
                const formData = new FormData(form);
                formData.append('operation_id', operationId);
                
                const response = await fetch(form.action || window.location.href, {
                    method: form.method || 'POST',
                    headers: {
                        'X-CSRFToken': this.getCSRFToken()
                    },
                    body: formData
                });
                
                if (response.ok) {
                    const result = await response.json();
                    
                    if (result.async) {
                        // Operation started, will be tracked via HTTP polling
                        this.showToast('info', 'Операція розпочата', 'Ви отримаєте сповіщення після завершення');
                    } else {
                        // Synchronous response
                        this.completeOperation(operationId, result);
                        this.handleFormSuccess(form, result);
                    }
                } else {
                    const error = await response.json().catch(() => ({ message: 'Помилка сервера' }));
                    this.errorOperation(operationId, error);
                    this.handleFormError(form, error);
                }
                
            } catch (error) {
                console.error('Form submission error:', error);
                this.showToast('error', 'Помилка відправки', error.message);
            } finally {
                // Restore button state
                if (submitBtn) {
                    this.setLoadingState(submitBtn, false, originalText);
                }
            }
        });
    }

    handleFormSuccess(form, result) {
        // Clear form if specified
        if (form.hasAttribute('data-clear-on-success')) {
            form.reset();
        }
        
        // Redirect if specified
        if (result.redirect) {
            window.location.href = result.redirect;
        }
        
        // Show success message
        if (result.message) {
            this.showToast('success', 'Успіх', result.message);
        }
        
        // Trigger custom event
        form.dispatchEvent(new CustomEvent('formSuccess', { detail: result }));
    }

    handleFormError(form, error) {
        // Show field errors
        if (error.field_errors) {
            this.showFieldErrors(form, error.field_errors);
        }
        
        // Show general error
        if (error.message) {
            this.showToast('error', 'Помилка форми', error.message);
        }
        
        // Trigger custom event
        form.dispatchEvent(new CustomEvent('formError', { detail: error }));
    }

    showFieldErrors(form, fieldErrors) {
        // Clear existing errors
        form.querySelectorAll('.field-error').forEach(el => el.remove());
        form.querySelectorAll('.form-input.error').forEach(el => el.classList.remove('error'));
        
        // Show new errors
        Object.keys(fieldErrors).forEach(fieldName => {
            const field = form.querySelector(`[name="${fieldName}"]`);
            if (field) {
                field.classList.add('error');
                
                const errorDiv = document.createElement('div');
                errorDiv.className = 'field-error text-error text-sm';
                errorDiv.textContent = fieldErrors[fieldName][0]; // First error
                
                field.parentNode.appendChild(errorDiv);
            }
        });
    }

    // ===== RETRY MECHANISMS =====
    setupRetryMechanisms() {
        // Add retry buttons to failed operations
        document.addEventListener('click', (e) => {
            if (e.target.matches('.retry-operation')) {
                const operationId = e.target.getAttribute('data-operation-id');
                this.retryOperation(operationId);
            }
        });
    }

    async retryOperation(operationId) {
        const operation = this.activeOperations.get(operationId);
        if (!operation) return;
        
        try {
            // Reset operation state
            operation.progress = 0;
            operation.status = 'Повторна спроба...';
            operation.error = null;
            operation.logs = [];
            operation.startTime = Date.now();
            delete operation.endTime;
            
            this.updateProgressItem(operation);
            
            // Make retry request
            const response = await fetch('/api/risk-reports/retry/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({ operation_id: operationId })
            });
            
            if (!response.ok) {
                throw new Error('Не вдалося повторити операцію');
            }
            
            this.showToast('info', 'Повторна спроба', 'Операція перезапущена');
            
        } catch (error) {
            console.error('Retry error:', error);
            this.showToast('error', 'Помилка повтору', error.message);
        }
    }

    async cancelOperation(operationId) {
        try {
            const response = await fetch('/api/risk-reports/cancel/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({ operation_id: operationId })
            });
            
            if (response.ok) {
                this.removeOperation(operationId);
                this.showToast('info', 'Операція скасована', 'Операція була зупинена');
            } else {
                throw new Error('Не вдалося скасувати операцію');
            }
            
        } catch (error) {
            console.error('Cancel error:', error);
            this.showToast('error', 'Помилка скасування', error.message);
        }
    }

    // ===== UTILITY METHODS =====
    setLoadingState(element, isLoading, originalText = null) {
        if (isLoading) {
            element.disabled = true;
            element.classList.add('loading');
            
            if (!element.hasAttribute('data-original-content')) {
                element.setAttribute('data-original-content', element.innerHTML);
            }
            
            element.innerHTML = '<i class="fas fa-spinner animate-spin"></i> Завантаження...';
        } else {
            element.disabled = false;
            element.classList.remove('loading');
            
            const original = originalText || element.getAttribute('data-original-content');
            if (original) {
                element.innerHTML = original;
            }
        }
    }

    formatElapsedTime(operation) {
        const start = operation.startTime;
        const end = operation.endTime || Date.now();
        const elapsed = Math.floor((end - start) / 1000);
        
        if (elapsed < 60) {
            return `${elapsed}с`;
        } else if (elapsed < 3600) {
            return `${Math.floor(elapsed / 60)}хв ${elapsed % 60}с`;
        } else {
            const hours = Math.floor(elapsed / 3600);
            const minutes = Math.floor((elapsed % 3600) / 60);
            return `${hours}г ${minutes}хв`;
        }
    }

    generateId() {
        return 'op_' + Math.random().toString(36).substr(2, 9) + Date.now().toString(36);
    }

    getCSRFToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
               document.querySelector('meta[name=csrf-token]')?.content || '';
    }

    dispatchOperationEvent(type, operation) {
        const event = new CustomEvent(`operation${type.charAt(0).toUpperCase() + type.slice(1)}`, {
            detail: operation
        });
        document.dispatchEvent(event);
    }

    // ===== EVENT LISTENERS =====
    setupEventListeners() {
        // Page visibility change
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                // Check if polling is active
            }
        });

        // Window beforeunload
        window.addEventListener('beforeunload', (e) => {
            if (this.activeOperations.size > 0) {
                e.preventDefault();
                e.returnValue = 'У вас є активні операції. Ви впевнені, що хочете покинути сторінку?';
            }
        });

        // Custom events
        document.addEventListener('operationCompleted', (e) => {
            console.log('Operation completed:', e.detail);
        });

        document.addEventListener('operationError', (e) => {
            console.error('Operation error:', e.detail);
        });
    }

    // ===== PUBLIC API =====
    static getInstance() {
        if (!AsyncUX.instance) {
            AsyncUX.instance = new AsyncUX();
        }
        return AsyncUX.instance;
    }

    // Public methods for external use
    createProgressTracker(operationId, config = {}) {
        const tracker = new ProgressTracker(operationId, config);
        this.progressTrackers.set(operationId, tracker);
        return tracker;
    }

    getOperationStatus(operationId) {
        return this.activeOperations.get(operationId);
    }

    getAllOperations() {
        return Array.from(this.activeOperations.values());
    }

    clearAllOperations() {
        this.activeOperations.forEach((operation, id) => {
            this.removeOperation(id);
        });
    }
}

// ===== PROGRESS TRACKER CLASS =====
class ProgressTracker {
    constructor(operationId, config = {}) {
        this.operationId = operationId;
        this.config = {
            showPercentage: true,
            showTimeRemaining: true,
            showSpeed: false,
            ...config
        };
        this.callbacks = {};
    }

    update(progress, status, details = {}) {
        this.progress = progress;
        this.status = status;
        this.details = details;
        
        // Calculate time remaining
        if (this.config.showTimeRemaining && details.startTime) {
            this.timeRemaining = this.calculateTimeRemaining(progress, details.startTime);
        }
        
        // Calculate speed
        if (this.config.showSpeed && details.processed && details.total) {
            this.speed = this.calculateSpeed(details.processed, details.startTime);
        }
        
        // Trigger callbacks
        this.triggerCallback('update', { progress, status, details });
        
        if (progress >= 100) {
            this.triggerCallback('complete', { progress, status, details });
        }
    }

    calculateTimeRemaining(progress, startTime) {
        if (progress <= 0) return null;
        
        const elapsed = Date.now() - startTime;
        const rate = progress / elapsed;
        const remaining = (100 - progress) / rate;
        
        return Math.round(remaining / 1000); // seconds
    }

    calculateSpeed(processed, startTime) {
        const elapsed = (Date.now() - startTime) / 1000; // seconds
        return Math.round(processed / elapsed); // items per second
    }

    onUpdate(callback) {
        this.callbacks.update = callback;
        return this;
    }

    onComplete(callback) {
        this.callbacks.complete = callback;
        return this;
    }

    onError(callback) {
        this.callbacks.error = callback;
        return this;
    }

    triggerCallback(event, data) {
        if (this.callbacks[event]) {
            this.callbacks[event](data);
        }
    }
}

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.AsyncUX = AsyncUX.getInstance();
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { AsyncUX, ProgressTracker };
} 