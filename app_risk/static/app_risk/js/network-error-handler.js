/**
 * SecBoard Risk Assessment - Network Error Handler
 * Robust network error handling with retry mechanisms and offline support
 */

class NetworkErrorHandler {
    constructor(options = {}) {
        this.options = {
            maxRetries: 3,
            retryDelay: 1000,
            retryMultiplier: 2,
            maxRetryDelay: 30000,
            timeoutDuration: 30000,
            enableOfflineQueue: true,
            enableConnectionMonitoring: true,
            enableRetryOnReconnect: true,
            showConnectionStatus: true,
            statusContainerSelector: '#connection-status',
            language: 'uk',
            ...options
        };
        
        this.isOnline = navigator.onLine;
        this.retryQueue = new Map();
        this.offlineQueue = [];
        this.connectionStatus = null;
        this.retryTimers = new Map();
        this.requestHistory = new Map();
        
        this.init();
    }
    
    init() {
        this.setupConnectionMonitoring();
        this.setupConnectionStatusDisplay();
        this.setupAjaxInterceptors();
        this.loadLanguage();
    }
    
    setupConnectionMonitoring() {
        if (!this.options.enableConnectionMonitoring) return;
        
        // Listen for online/offline events
        window.addEventListener('online', () => {
            this.handleConnectionChange(true);
        });
        
        window.addEventListener('offline', () => {
            this.handleConnectionChange(false);
        });
        
        // Periodic connection check
        setInterval(() => {
            this.checkConnection();
        }, 30000); // Check every 30 seconds
    }
    
    setupConnectionStatusDisplay() {
        if (!this.options.showConnectionStatus) return;
        
        let container = document.querySelector(this.options.statusContainerSelector);
        if (!container) {
            container = document.createElement('div');
            container.id = 'connection-status';
            container.className = 'connection-status-container';
            document.body.appendChild(container);
        }
        
        this.connectionStatus = container;
        this.updateConnectionStatus();
    }
    
    setupAjaxInterceptors() {
        // Store original jQuery ajax method
        const originalAjax = $.ajax;
        const self = this;
        
        // Override jQuery ajax
        $.ajax = function(options) {
            // Generate unique request ID
            const requestId = self.generateRequestId();
            
            // Store original options
            const originalOptions = { ...options };
            
            // Add timeout if not specified
            if (!options.timeout) {
                options.timeout = self.options.timeoutDuration;
            }
            
            // Add request headers
            options.headers = {
                'X-Request-ID': requestId,
                'X-Requested-With': 'XMLHttpRequest',
                ...options.headers
            };
            
            // Store request for retry
            self.requestHistory.set(requestId, {
                options: originalOptions,
                timestamp: Date.now(),
                retryCount: 0
            });
            
            // If offline and queuing enabled, add to queue
            if (!self.isOnline && self.options.enableOfflineQueue) {
                self.addToOfflineQueue(requestId, originalOptions);
                return $.Deferred().reject({
                    status: 0,
                    statusText: 'Offline',
                    responseText: 'Request queued for when connection is restored'
                }).promise();
            }
            
            // Execute request with error handling
            return self.executeRequest(originalAjax, options, requestId);
        };
        
        // Also intercept fetch API
        if (window.fetch) {
            const originalFetch = window.fetch;
            window.fetch = function(url, options = {}) {
                return self.handleFetchRequest(originalFetch, url, options);
            };
        }
    }
    
    executeRequest(ajaxMethod, options, requestId) {
        const self = this;
        
        return ajaxMethod(options)
            .done(function(data, textStatus, jqXHR) {
                // Request successful, remove from retry queue
                self.retryQueue.delete(requestId);
                self.clearRetryTimer(requestId);
                
                // Update connection status
                if (!self.isOnline) {
                    self.handleConnectionChange(true);
                }
            })
            .fail(function(jqXHR, textStatus, errorThrown) {
                // Handle request failure
                self.handleRequestFailure(jqXHR, textStatus, errorThrown, requestId);
            });
    }
    
    handleFetchRequest(originalFetch, url, options = {}) {
        const requestId = this.generateRequestId();
        
        // Add request headers
        options.headers = {
            'X-Request-ID': requestId,
            'X-Requested-With': 'XMLHttpRequest',
            ...options.headers
        };
        
        // Add timeout
        if (!options.timeout) {
            options.timeout = this.options.timeoutDuration;
        }
        
        // Store request for retry
        this.requestHistory.set(requestId, {
            url: url,
            options: { ...options },
            timestamp: Date.now(),
            retryCount: 0
        });
        
        // If offline and queuing enabled, add to queue
        if (!this.isOnline && this.options.enableOfflineQueue) {
            this.addToOfflineQueue(requestId, { url, options });
            return Promise.reject(new Error('Request queued for when connection is restored'));
        }
        
        return originalFetch(url, options)
            .then(response => {
                // Request successful, remove from retry queue
                this.retryQueue.delete(requestId);
                this.clearRetryTimer(requestId);
                
                // Update connection status
                if (!this.isOnline) {
                    this.handleConnectionChange(true);
                }
                
                return response;
            })
            .catch(error => {
                // Handle request failure
                this.handleFetchFailure(error, requestId);
                throw error;
            });
    }
    
    handleRequestFailure(jqXHR, textStatus, errorThrown, requestId) {
        const request = this.requestHistory.get(requestId);
        if (!request) return;
        
        // Determine if retry is appropriate
        const shouldRetry = this.shouldRetryRequest(jqXHR.status, textStatus, request.retryCount);
        
        if (shouldRetry) {
            this.scheduleRetry(requestId, request);
        } else {
            // Max retries reached or non-retryable error
            this.handleFinalFailure(jqXHR, textStatus, errorThrown, requestId);
        }
        
        // Show error to user
        this.showNetworkError(jqXHR, textStatus, errorThrown, requestId);
    }
    
    handleFetchFailure(error, requestId) {
        const request = this.requestHistory.get(requestId);
        if (!request) return;
        
        // Determine if retry is appropriate
        const shouldRetry = this.shouldRetryRequest(0, 'error', request.retryCount);
        
        if (shouldRetry) {
            this.scheduleRetry(requestId, request);
        } else {
            // Max retries reached
            this.handleFinalFailure(error, 'error', error.message, requestId);
        }
        
        // Show error to user
        this.showNetworkError(error, 'error', error.message, requestId);
    }
    
    shouldRetryRequest(status, textStatus, retryCount) {
        // Don't retry if max retries reached
        if (retryCount >= this.options.maxRetries) {
            return false;
        }
        
        // Don't retry client errors (4xx), except for specific cases
        if (status >= 400 && status < 500) {
            // Retry on these specific client errors
            return [408, 429].includes(status);
        }
        
        // Retry on network errors and server errors (5xx)
        if (status === 0 || status >= 500 || textStatus === 'timeout' || textStatus === 'error') {
            return true;
        }
        
        return false;
    }
    
    scheduleRetry(requestId, request) {
        const retryDelay = this.calculateRetryDelay(request.retryCount);
        
        // Clear existing timer
        this.clearRetryTimer(requestId);
        
        // Schedule retry
        const timer = setTimeout(() => {
            this.retryRequest(requestId);
        }, retryDelay);
        
        this.retryTimers.set(requestId, timer);
        
        // Add to retry queue
        this.retryQueue.set(requestId, {
            ...request,
            retryCount: request.retryCount + 1,
            nextRetryTime: Date.now() + retryDelay
        });
    }
    
    calculateRetryDelay(retryCount) {
        const baseDelay = this.options.retryDelay;
        const multiplier = Math.pow(this.options.retryMultiplier, retryCount);
        const delay = baseDelay * multiplier;
        
        // Add jitter to prevent thundering herd
        const jitter = Math.random() * 0.1 * delay;
        
        return Math.min(delay + jitter, this.options.maxRetryDelay);
    }
    
    retryRequest(requestId) {
        const request = this.requestHistory.get(requestId);
        if (!request) return;
        
        // Update retry count
        request.retryCount++;
        
        // Clear from retry queue
        this.retryQueue.delete(requestId);
        this.clearRetryTimer(requestId);
        
        // Execute retry
        if (request.options) {
            // jQuery request
            this.executeRequest($.ajax, request.options, requestId);
        } else if (request.url) {
            // Fetch request
            this.handleFetchRequest(fetch, request.url, request.options);
        }
    }
    
    clearRetryTimer(requestId) {
        const timer = this.retryTimers.get(requestId);
        if (timer) {
            clearTimeout(timer);
            this.retryTimers.delete(requestId);
        }
    }
    
    handleFinalFailure(error, textStatus, errorMessage, requestId) {
        // Remove from all queues
        this.retryQueue.delete(requestId);
        this.clearRetryTimer(requestId);
        
        // Log final failure
        console.error('Request failed after all retries:', {
            requestId,
            error: errorMessage,
            status: error.status || 0
        });
    }
    
    showNetworkError(error, textStatus, errorMessage, requestId) {
        // Don't show network errors (status 0) to users
        const status = error.status || 0;
        if (status === 0 || textStatus === 'error' || textStatus === 'timeout') {
            // Only log to console, don't show to user
            console.error('Network error (not shown to user):', {
                status: status,
                textStatus: textStatus,
                errorMessage: errorMessage,
                requestId: requestId
            });
            return;
        }
        
        // Show other errors (non-network)
        if (window.errorDisplay) {
            const request = this.requestHistory.get(requestId);
            const category = this.categorizeError(status, textStatus);
            
            window.errorDisplay.showError({
                message: this.getErrorMessage(status, textStatus, errorMessage),
                category: category,
                details: {
                    requestId: requestId,
                    status: status,
                    statusText: error.statusText || textStatus,
                    retryCount: request ? request.retryCount : 0,
                    url: request ? request.options?.url || request.url : 'unknown'
                },
                retryCallback: () => {
                    this.retryRequest(requestId);
                }
            });
        }
    }
    
    categorizeError(status, textStatus) {
        if (status === 0 || textStatus === 'timeout' || textStatus === 'error') {
            return 'network';
        } else if (status === 401) {
            return 'permission';
        } else if (status === 403) {
            return 'permission';
        } else if (status === 404) {
            return 'network';
        } else if (status === 422) {
            return 'validation';
        } else if (status >= 500) {
            return 'system';
        } else {
            return 'network';
        }
    }
    
    getErrorMessage(status, textStatus, errorMessage) {
        const messages = this.messages.errors;
        
        if (status === 0) {
            return messages.networkUnavailable;
        } else if (status === 401) {
            return messages.authenticationRequired;
        } else if (status === 403) {
            return messages.accessForbidden;
        } else if (status === 404) {
            return messages.resourceNotFound;
        } else if (status === 408) {
            return messages.requestTimeout;
        } else if (status === 422) {
            return messages.validationFailed;
        } else if (status === 429) {
            return messages.tooManyRequests;
        } else if (status >= 500) {
            return messages.serverError;
        } else if (textStatus === 'timeout') {
            return messages.requestTimeout;
        } else {
            return errorMessage || messages.unknownError;
        }
    }
    
    handleConnectionChange(isOnline) {
        const wasOnline = this.isOnline;
        this.isOnline = isOnline;
        
        if (isOnline && !wasOnline) {
            // Just came back online
            this.handleReconnection();
        } else if (!isOnline && wasOnline) {
            // Just went offline
            this.handleDisconnection();
        }
        
        this.updateConnectionStatus();
    }
    
    handleReconnection() {
        console.log('Connection restored');
        
        // Process offline queue
        if (this.options.enableOfflineQueue) {
            this.processOfflineQueue();
        }
        
        // Retry failed requests if enabled
        if (this.options.enableRetryOnReconnect) {
            this.retryFailedRequests();
        }
        
        // Don't show connection restored message
        // if (window.errorDisplay) {
        //     window.errorDisplay.showError({
        //         message: this.messages.status.connectionRestored,
        //         category: 'network',
        //         autoHide: true
        //     });
        // }
    }
    
    handleDisconnection() {
        console.log('Connection lost');
        
        // Don't show offline message
        // if (window.errorDisplay) {
        //     window.errorDisplay.showError({
        //         message: this.messages.status.connectionLost,
        //         category: 'network',
        //         autoHide: false
        //     });
        // }
    }
    
    processOfflineQueue() {
        const queue = [...this.offlineQueue];
        this.offlineQueue = [];
        
        queue.forEach(queueItem => {
            setTimeout(() => {
                if (queueItem.options) {
                    // jQuery request
                    $.ajax(queueItem.options);
                } else if (queueItem.url) {
                    // Fetch request
                    fetch(queueItem.url, queueItem.options);
                }
            }, Math.random() * 2000); // Stagger requests
        });
    }
    
    retryFailedRequests() {
        const failedRequests = Array.from(this.retryQueue.keys());
        
        failedRequests.forEach(requestId => {
            // Add random delay to prevent thundering herd
            setTimeout(() => {
                this.retryRequest(requestId);
            }, Math.random() * 5000);
        });
    }
    
    addToOfflineQueue(requestId, requestData) {
        this.offlineQueue.push({
            requestId: requestId,
            timestamp: Date.now(),
            ...requestData
        });
        
        // Limit queue size
        if (this.offlineQueue.length > 100) {
            this.offlineQueue.shift(); // Remove oldest
        }
    }
    
    checkConnection() {
        // Try to fetch a small resource to check connectivity
        const testUrl = '/api/health/ping';
        
        fetch(testUrl, {
            method: 'HEAD',
            cache: 'no-cache',
            timeout: 5000
        })
        .then(response => {
            if (!this.isOnline) {
                this.handleConnectionChange(true);
            }
        })
        .catch(error => {
            if (this.isOnline) {
                this.handleConnectionChange(false);
            }
        });
    }
    
    updateConnectionStatus() {
        if (!this.connectionStatus) return;
        
        const statusClass = this.isOnline ? 'online' : 'offline';
        const statusText = this.isOnline ? 
            this.messages.status.online : 
            this.messages.status.offline;
        
        this.connectionStatus.className = `connection-status-container ${statusClass}`;
        this.connectionStatus.innerHTML = `
            <div class="connection-status-indicator">
                <i class="fas fa-${this.isOnline ? 'wifi' : 'wifi-slash'}"></i>
                <span>${statusText}</span>
            </div>
        `;
        
        // Auto-hide when online
        if (this.isOnline) {
            setTimeout(() => {
                this.connectionStatus.classList.add('hidden');
            }, 3000);
        } else {
            this.connectionStatus.classList.remove('hidden');
        }
    }
    
    generateRequestId() {
        return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
    
    loadLanguage() {
        this.messages = this.getMessages(this.options.language);
    }
    
    getMessages(language) {
        const messages = {
            uk: {
                status: {
                    online: 'В мережі',
                    offline: 'Відсутнє з\'єднання',
                    connectionLost: 'З\'єднання з сервером втрачено',
                    connectionRestored: 'З\'єднання з сервером відновлено'
                },
                errors: {
                    networkUnavailable: 'Мережа недоступна',
                    authenticationRequired: 'Необхідна автентифікація',
                    accessForbidden: 'Доступ заборонено',
                    resourceNotFound: 'Ресурс не знайдено',
                    requestTimeout: 'Час очікування запиту вичерпано',
                    validationFailed: 'Помилка валідації',
                    tooManyRequests: 'Занадто багато запитів',
                    serverError: 'Помилка сервера',
                    unknownError: 'Невідома помилка'
                }
            },
            en: {
                status: {
                    online: 'Online',
                    offline: 'Offline',
                    connectionLost: 'Connection to server lost',
                    connectionRestored: 'Connection to server restored'
                },
                errors: {
                    networkUnavailable: 'Network unavailable',
                    authenticationRequired: 'Authentication required',
                    accessForbidden: 'Access forbidden',
                    resourceNotFound: 'Resource not found',
                    requestTimeout: 'Request timeout',
                    validationFailed: 'Validation failed',
                    tooManyRequests: 'Too many requests',
                    serverError: 'Server error',
                    unknownError: 'Unknown error'
                }
            },
            ru: {
                status: {
                    online: 'В сети',
                    offline: 'Отсутствует соединение',
                    connectionLost: 'Соединение с сервером потеряно',
                    connectionRestored: 'Соединение с сервером восстановлено'
                },
                errors: {
                    networkUnavailable: 'Сеть недоступна',
                    authenticationRequired: 'Необходима аутентификация',
                    accessForbidden: 'Доступ запрещен',
                    resourceNotFound: 'Ресурс не найден',
                    requestTimeout: 'Время ожидания запроса истекло',
                    validationFailed: 'Ошибка валидации',
                    tooManyRequests: 'Слишком много запросов',
                    serverError: 'Ошибка сервера',
                    unknownError: 'Неизвестная ошибка'
                }
            }
        };
        
        return messages[language] || messages.en;
    }
    
    // Public API
    setLanguage(language) {
        this.options.language = language;
        this.loadLanguage();
        this.updateConnectionStatus();
    }
    
    getConnectionStatus() {
        return {
            isOnline: this.isOnline,
            retryQueueSize: this.retryQueue.size,
            offlineQueueSize: this.offlineQueue.length,
            activeRequests: this.requestHistory.size
        };
    }
    
    clearQueues() {
        this.retryQueue.clear();
        this.offlineQueue = [];
        this.retryTimers.forEach(timer => clearTimeout(timer));
        this.retryTimers.clear();
    }
    
    forceRetryAll() {
        this.retryFailedRequests();
    }
    
    enableOfflineMode() {
        this.options.enableOfflineQueue = true;
    }
    
    disableOfflineMode() {
        this.options.enableOfflineQueue = false;
        this.offlineQueue = [];
    }
}

// Initialize network error handler
window.NetworkErrorHandler = NetworkErrorHandler;
window.networkErrorHandler = new NetworkErrorHandler();

// Add CSS styles for connection status
const style = document.createElement('style');
style.textContent = `
.connection-status-container {
    position: fixed;
    top: 20px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 10000;
    transition: opacity 0.3s ease, transform 0.3s ease;
}

.connection-status-container.hidden {
    opacity: 0;
    transform: translateX(-50%) translateY(-100%);
    pointer-events: none;
}

.connection-status-indicator {
    display: flex;
    align-items: center;
    padding: 8px 16px;
    border-radius: 20px;
    font-size: 14px;
    font-weight: 500;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
    white-space: nowrap;
}

.connection-status-container.online .connection-status-indicator {
    background-color: #28a745;
    color: white;
}

.connection-status-container.offline .connection-status-indicator {
    background-color: #dc3545;
    color: white;
}

.connection-status-indicator i {
    margin-right: 8px;
}

@media (max-width: 768px) {
    .connection-status-container {
        top: 10px;
        left: 10px;
        right: 10px;
        transform: none;
    }
    
    .connection-status-container.hidden {
        transform: translateY(-100%);
    }
}
`;
document.head.appendChild(style);

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = NetworkErrorHandler;
} 