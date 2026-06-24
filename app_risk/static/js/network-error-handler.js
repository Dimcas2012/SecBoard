/**
 * Network Error Handler
 * Provides comprehensive network error handling with retry mechanisms and offline detection
 */

class NetworkErrorHandler {
    constructor() {
        this.isOnline = navigator.onLine;
        this.retryAttempts = new Map();
        this.maxRetryAttempts = 3;
        this.retryDelay = 1000; // 1 second
        this.maxRetryDelay = 30000; // 30 seconds
        this.connectionCheckInterval = null;
        this.pendingRequests = new Map();
        this.offlineQueue = [];
        this.connectionListeners = [];
        this.init();
    }

    init() {
        this.bindEvents();
        this.startConnectionMonitoring();
        this.setupRequestInterceptors();
    }

    bindEvents() {
        // Online/offline events
        window.addEventListener('online', () => {
            this.handleOnlineEvent();
        });

        window.addEventListener('offline', () => {
            this.handleOfflineEvent();
        });

        // Visibility change (tab becomes visible/hidden)
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden && !this.isOnline) {
                this.checkConnection();
            }
        });

        // Focus event (window becomes active)
        window.addEventListener('focus', () => {
            if (!this.isOnline) {
                this.checkConnection();
            }
        });
    }

    startConnectionMonitoring() {
        // Check connection every 30 seconds when offline
        this.connectionCheckInterval = setInterval(() => {
            if (!this.isOnline) {
                this.checkConnection();
            }
        }, 30000);
    }

    setupRequestInterceptors() {
        // Intercept fetch requests
        const originalFetch = window.fetch;
        window.fetch = async (...args) => {
            return this.interceptedFetch(originalFetch, ...args);
        };

        // Intercept jQuery AJAX requests if jQuery is available
        if (typeof $ !== 'undefined' && $.ajaxSetup) {
            const self = this;
            $(document).ajaxError(function(event, xhr, settings, thrownError) {
                self.handleAjaxError(xhr, settings, thrownError);
            });

            $(document).ajaxSend(function(event, xhr, settings) {
                self.registerRequest(settings.url, xhr);
            });

            $(document).ajaxComplete(function(event, xhr, settings) {
                self.unregisterRequest(settings.url);
            });
        }
    }

    async interceptedFetch(originalFetch, ...args) {
        const url = args[0];
        const options = args[1] || {};
        
        // Check if we're offline
        if (!this.isOnline) {
            return this.handleOfflineRequest(url, options);
        }

        try {
            this.registerRequest(url);
            const response = await originalFetch(...args);
            this.unregisterRequest(url);
            
            if (!response.ok) {
                return this.handleFailedResponse(response, url, options, originalFetch, ...args);
            }
            
            // Reset retry attempts on success
            this.retryAttempts.delete(url);
            return response;
            
        } catch (error) {
            this.unregisterRequest(url);
            return this.handleNetworkError(error, url, options, originalFetch, ...args);
        }
    }

    async handleFailedResponse(response, url, options, originalFetch, ...args) {
        const status = response.status;
        
        // Handle different HTTP status codes
        switch (status) {
            case 408: // Request Timeout
            case 429: // Too Many Requests
            case 500: // Internal Server Error
            case 502: // Bad Gateway
            case 503: // Service Unavailable
            case 504: // Gateway Timeout
                return this.retryRequest(url, options, originalFetch, ...args);
            
            case 401: // Unauthorized
                this.handleAuthenticationError();
                break;
            
            case 403: // Forbidden
                this.handleAuthorizationError();
                break;
            
            case 404: // Not Found
                this.handleNotFoundError(url);
                break;
            
            case 422: // Unprocessable Entity
                this.handleValidationError(response);
                break;
        }
        
        return response;
    }

    async handleNetworkError(error, url, options, originalFetch, ...args) {
        // Check if it's a network connectivity issue
        if (error.name === 'TypeError' && error.message.includes('fetch')) {
            // Likely a network connectivity issue
            this.setOfflineStatus();
            return this.handleOfflineRequest(url, options);
        }
        
        // Try to retry the request
        return this.retryRequest(url, options, originalFetch, ...args);
    }

    async retryRequest(url, options, originalFetch, ...args) {
        const attempts = this.retryAttempts.get(url) || 0;
        
        if (attempts >= this.maxRetryAttempts) {
            this.retryAttempts.delete(url);
            throw new Error(`Max retry attempts reached for ${url}`);
        }
        
        // Calculate exponential backoff delay
        const delay = Math.min(this.retryDelay * Math.pow(2, attempts), this.maxRetryDelay);
        
        // Show retry notification
        this.showRetryNotification(url, attempts + 1, delay);
        
        this.retryAttempts.set(url, attempts + 1);
        
        // Wait before retrying
        await this.sleep(delay);
        
        // Check connection before retrying
        const isConnected = await this.checkConnection();
        if (!isConnected) {
            return this.handleOfflineRequest(url, options);
        }
        
        // Retry the request
        return originalFetch(...args);
    }

    handleOfflineRequest(url, options) {
        // Queue the request for when connection is restored
        this.queueOfflineRequest(url, options);
        
        // Show offline notification
        this.showOfflineNotification();
        
        // Return a rejected promise with offline error
        return Promise.reject(new Error('No internet connection'));
    }

    queueOfflineRequest(url, options) {
        this.offlineQueue.push({
            url: url,
            options: options,
            timestamp: Date.now()
        });
        
        // Limit queue size
        if (this.offlineQueue.length > 50) {
            this.offlineQueue = this.offlineQueue.slice(-50);
        }
    }

    async processOfflineQueue() {
        if (this.offlineQueue.length === 0) return;
        
        this.showProcessingQueueNotification(this.offlineQueue.length);
        
        const requests = [...this.offlineQueue];
        this.offlineQueue = [];
        
        for (const request of requests) {
            try {
                await fetch(request.url, request.options);
            } catch (error) {
                console.error('Failed to process queued request:', error);
                // Re-queue failed requests
                this.offlineQueue.push(request);
            }
        }
        
        if (this.offlineQueue.length === 0) {
            this.showQueueProcessedNotification();
        }
    }

    registerRequest(url, xhr = null) {
        this.pendingRequests.set(url, {
            xhr: xhr,
            timestamp: Date.now()
        });
    }

    unregisterRequest(url) {
        this.pendingRequests.delete(url);
    }

    async checkConnection() {
        try {
            // Try to fetch a small resource from the same origin
            const response = await fetch('/api/health-check', {
                method: 'HEAD',
                cache: 'no-cache',
                timeout: 5000
            });
            
            const isOnline = response.ok;
            this.updateConnectionStatus(isOnline);
            return isOnline;
            
        } catch (error) {
            this.updateConnectionStatus(false);
            return false;
        }
    }

    updateConnectionStatus(isOnline) {
        const wasOnline = this.isOnline;
        this.isOnline = isOnline;
        
        if (!wasOnline && isOnline) {
            this.handleOnlineEvent();
        } else if (wasOnline && !isOnline) {
            this.handleOfflineEvent();
        }
    }

    handleOnlineEvent() {
        this.isOnline = true;
        this.showOnlineNotification();
        this.notifyConnectionListeners(true);
        
        // Process offline queue
        setTimeout(() => {
            this.processOfflineQueue();
        }, 1000);
        
        // Reset retry attempts
        this.retryAttempts.clear();
    }

    handleOfflineEvent() {
        this.isOnline = false;
        this.setOfflineStatus();
        this.showOfflineNotification();
        this.notifyConnectionListeners(false);
        
        // Cancel pending requests
        this.cancelPendingRequests();
    }

    setOfflineStatus() {
        this.isOnline = false;
        
        // Add visual indicator
        this.showOfflineIndicator();
    }

    cancelPendingRequests() {
        for (const [url, request] of this.pendingRequests) {
            if (request.xhr && request.xhr.abort) {
                request.xhr.abort();
            }
        }
        this.pendingRequests.clear();
    }

    handleAjaxError(xhr, settings, thrownError) {
        const url = settings.url;
        const status = xhr.status;
        
        if (status === 0) {
            // Network error
            this.setOfflineStatus();
            this.handleOfflineRequest(url, settings);
        } else {
            // HTTP error
            this.handleHttpError(status, url, xhr);
        }
    }

    handleHttpError(status, url, xhr) {
        switch (status) {
            case 401:
                this.handleAuthenticationError();
                break;
            case 403:
                this.handleAuthorizationError();
                break;
            case 404:
                this.handleNotFoundError(url);
                break;
            case 422:
                this.handleValidationError(xhr);
                break;
            case 500:
            case 502:
            case 503:
            case 504:
                this.handleServerError(status, url);
                break;
        }
    }

    handleAuthenticationError() {
        if (window.errorDisplaySystem) {
            window.errorDisplaySystem.showError({
                category: 'security',
                code: 'authentication_required',
                message: 'Необхідна повторна авторизація',
                details: {
                    action: 'redirect_to_login'
                }
            });
        }
        
        // Redirect to login after delay
        setTimeout(() => {
            window.location.href = '/login/';
        }, 3000);
    }

    handleAuthorizationError() {
        if (window.errorDisplaySystem) {
            window.errorDisplaySystem.showError({
                category: 'permission',
                code: 'access_denied',
                message: 'Недостатньо прав для виконання операції'
            });
        }
    }

    handleNotFoundError(url) {
        if (window.errorDisplaySystem) {
            window.errorDisplaySystem.showError({
                category: 'network',
                code: 'resource_not_found',
                message: `Ресурс не знайдено: ${url}`
            });
        }
    }

    handleValidationError(xhr) {
        try {
            const response = JSON.parse(xhr.responseText);
            if (response.errors && window.errorDisplaySystem) {
                window.errorDisplaySystem.showValidationErrors(response.errors);
            }
        } catch (e) {
            if (window.errorDisplaySystem) {
                window.errorDisplaySystem.showError({
                    category: 'validation',
                    code: 'validation_error',
                    message: 'Помилка валідації даних'
                });
            }
        }
    }

    handleServerError(status, url) {
        if (window.errorDisplaySystem) {
            window.errorDisplaySystem.showError({
                category: 'system',
                code: 'server_error',
                message: `Помилка сервера (${status})`,
                details: {
                    status: status,
                    url: url
                }
            });
        }
    }

    showRetryNotification(url, attempt, delay) {
        if (window.errorDisplaySystem) {
            window.errorDisplaySystem.showError({
                category: 'network',
                code: 'retrying_request',
                message: `Повторна спроба ${attempt}/${this.maxRetryAttempts} через ${Math.round(delay/1000)} сек`,
                severity: 'warning'
            });
        }
    }

    showOfflineNotification() {
        if (window.errorDisplaySystem) {
            window.errorDisplaySystem.showError({
                category: 'network',
                code: 'offline',
                message: 'Відсутнє з\'єднання з інтернетом. Запити будуть виконані після відновлення з\'єднання.',
                severity: 'warning'
            });
        }
    }

    showOnlineNotification() {
        if (window.errorDisplaySystem) {
            window.errorDisplaySystem.showSuccess('З\'єднання з інтернетом відновлено');
        }
    }

    showProcessingQueueNotification(count) {
        if (window.errorDisplaySystem) {
            window.errorDisplaySystem.showError({
                category: 'network',
                code: 'processing_queue',
                message: `Обробка ${count} відкладених запитів...`,
                severity: 'info'
            });
        }
    }

    showQueueProcessedNotification() {
        if (window.errorDisplaySystem) {
            window.errorDisplaySystem.showSuccess('Всі відкладені запити оброблено');
        }
    }

    showOfflineIndicator() {
        let indicator = document.getElementById('offline-indicator');
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.id = 'offline-indicator';
            indicator.className = 'offline-indicator';
            indicator.innerHTML = `
                <i class="fas fa-wifi-slash me-2"></i>
                Немає з'єднання
            `;
            document.body.appendChild(indicator);
        }
        indicator.style.display = 'block';
    }

    hideOfflineIndicator() {
        const indicator = document.getElementById('offline-indicator');
        if (indicator) {
            indicator.style.display = 'none';
        }
    }

    addConnectionListener(callback) {
        this.connectionListeners.push(callback);
    }

    removeConnectionListener(callback) {
        const index = this.connectionListeners.indexOf(callback);
        if (index > -1) {
            this.connectionListeners.splice(index, 1);
        }
    }

    notifyConnectionListeners(isOnline) {
        this.connectionListeners.forEach(callback => {
            try {
                callback(isOnline);
            } catch (error) {
                console.error('Error in connection listener:', error);
            }
        });
    }

    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    // Public API methods
    isConnected() {
        return this.isOnline;
    }

    getRetryAttempts(url) {
        return this.retryAttempts.get(url) || 0;
    }

    getOfflineQueueSize() {
        return this.offlineQueue.length;
    }

    clearOfflineQueue() {
        this.offlineQueue = [];
    }

    forceConnectionCheck() {
        return this.checkConnection();
    }

    // Cleanup
    destroy() {
        if (this.connectionCheckInterval) {
            clearInterval(this.connectionCheckInterval);
        }
        
        this.connectionListeners = [];
        this.pendingRequests.clear();
        this.retryAttempts.clear();
        this.offlineQueue = [];
    }
}

// CSS for offline indicator
const offlineIndicatorCSS = `
.offline-indicator {
    position: fixed;
    top: 0;
    left: 50%;
    transform: translateX(-50%);
    background-color: #dc3545;
    color: white;
    padding: 8px 16px;
    border-radius: 0 0 8px 8px;
    font-size: 14px;
    font-weight: 500;
    z-index: 10000;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    display: none;
    animation: slideDown 0.3s ease-out;
}

@keyframes slideDown {
    from {
        transform: translateX(-50%) translateY(-100%);
    }
    to {
        transform: translateX(-50%) translateY(0);
    }
}

.offline-indicator i {
    animation: pulse 2s infinite;
}

@keyframes pulse {
    0% { opacity: 1; }
    50% { opacity: 0.5; }
    100% { opacity: 1; }
}
`;

// Add CSS to page
const styleSheet = document.createElement('style');
styleSheet.textContent = offlineIndicatorCSS;
document.head.appendChild(styleSheet);

// Initialize network error handler
const networkErrorHandler = new NetworkErrorHandler();

// Make it globally available
window.networkErrorHandler = networkErrorHandler;

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = NetworkErrorHandler;
} 