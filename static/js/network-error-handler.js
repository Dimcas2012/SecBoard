/**
 * Network Error Handler
 * Provides automatic retry, offline support, and connection monitoring
 */

class NetworkErrorHandler {
    constructor() {
        this.isOnline = navigator.onLine;
        this.retryQueue = [];
        this.maxRetries = 3;
        this.baseDelay = 1000; // 1 second
        this.maxDelay = 30000; // 30 seconds
        this.requestQueue = [];
        this.connectionIndicator = null;
        this.retryCallbacks = new Map();
        this.init();
    }

    init() {
        this.setupConnectionMonitoring();
        this.createConnectionIndicator();
        this.setupEventListeners();
        this.loadLanguageStrings();
        this.interceptFetch();
    }

    setupConnectionMonitoring() {
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

    createConnectionIndicator() {
        // Create connection status indicator
        this.connectionIndicator = document.createElement('div');
        this.connectionIndicator.id = 'connection-indicator';
        this.connectionIndicator.className = 'connection-indicator position-fixed';
        this.connectionIndicator.style.cssText = `
            top: 10px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 10000;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: 500;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            transition: all 0.3s ease;
            display: none;
        `;
        
        document.body.appendChild(this.connectionIndicator);
        this.updateConnectionIndicator();
    }

    setupEventListeners() {
        // Listen for custom network events
        document.addEventListener('networkRequest', (event) => {
            const { request, options } = event.detail;
            this.handleNetworkRequest(request, options);
        });

        // Listen for retry requests
        document.addEventListener('retryRequest', (event) => {
            const { requestId } = event.detail;
            this.retryRequest(requestId);
        });
    }

    handleConnectionChange(online) {
        const wasOnline = this.isOnline;
        this.isOnline = online;
        
        console.log(`Connection status changed: ${online ? 'online' : 'offline'}`);
        
        this.updateConnectionIndicator();
        
        if (online && !wasOnline) {
            // Connection restored - don't show message
            // this.showConnectionMessage('connection_restored', 'success');
            this.processQueuedRequests();
        } else if (!online && wasOnline) {
            // Connection lost - don't show message
            // this.showConnectionMessage('connection_lost', 'danger');
        }
    }

    updateConnectionIndicator() {
        if (!this.connectionIndicator) return;

        const strings = this.getLanguageStrings();
        
        if (this.isOnline) {
            this.connectionIndicator.style.display = 'none';
        } else {
            this.connectionIndicator.className = 'connection-indicator position-fixed bg-danger text-white';
            this.connectionIndicator.innerHTML = `
                <i class="fas fa-wifi me-2"></i>
                ${strings.offline}
                <span class="ms-2">
                    <i class="fas fa-spinner fa-spin"></i>
                </span>
            `;
            this.connectionIndicator.style.display = 'block';
        }
    }

    showConnectionMessage(messageKey, type) {
        const strings = this.getLanguageStrings();
        const message = strings[messageKey] || messageKey;
        
        if (window.errorDisplaySystem) {
            if (type === 'success') {
                window.errorDisplaySystem.showSuccess(message);
            } else {
                window.errorDisplaySystem.showNetworkError(message);
            }
        } else {
            // Fallback notification
            this.showFallbackNotification(message, type);
        }
    }

    showFallbackNotification(message, type) {
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} position-fixed`;
        notification.style.cssText = `
            top: 60px;
            right: 20px;
            z-index: 9999;
            max-width: 300px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        `;
        notification.innerHTML = `
            <div class="d-flex align-items-center">
                <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-triangle'} me-2"></i>
                ${message}
            </div>
        `;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 5000);
    }

    async checkConnection() {
        try {
            // Try to fetch a small resource to check connectivity
            const response = await fetch('/static/robots.txt', {
                method: 'HEAD',
                cache: 'no-cache',
                timeout: 5000
            });
            
            const online = response.ok;
            if (online !== this.isOnline) {
                this.handleConnectionChange(online);
            }
        } catch (error) {
            if (this.isOnline) {
                this.handleConnectionChange(false);
            }
        }
    }

    interceptFetch() {
        const originalFetch = window.fetch;
        const self = this;
        
        window.fetch = async function(url, options = {}) {
            // Add default timeout if not specified
            if (!options.timeout && !options.signal) {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 seconds
                options.signal = controller.signal;
            }
            
            try {
                const response = await originalFetch(url, options);
                
                // Handle HTTP errors
                if (!response.ok) {
                    return self.handleHttpError(response, url, options);
                }
                
                return response;
            } catch (error) {
                return self.handleNetworkError(error, url, options);
            }
        };
    }

    async handleHttpError(response, url, options) {
        const status = response.status;
        const strings = this.getLanguageStrings();
        
        switch (status) {
            case 401:
                // Unauthorized - redirect to login or show auth error
                this.showAuthError();
                break;
            case 403:
                // Forbidden
                if (window.errorDisplaySystem) {
                    window.errorDisplaySystem.showPermissionError(strings.access_denied);
                }
                break;
            case 404:
                // Not found
                if (window.errorDisplaySystem) {
                    window.errorDisplaySystem.showNetworkError(strings.not_found);
                }
                break;
            case 422:
                // Validation error
                try {
                    const errorData = await response.json();
                    if (window.errorDisplaySystem) {
                        window.errorDisplaySystem.showValidationError(
                            strings.validation_error,
                            errorData
                        );
                    }
                } catch (e) {
                    // Fallback if JSON parsing fails
                    if (window.errorDisplaySystem) {
                        window.errorDisplaySystem.showValidationError(strings.validation_error);
                    }
                }
                break;
            case 500:
            case 502:
            case 503:
            case 504:
                // Server errors - offer retry
                const requestId = this.generateRequestId();
                if (window.errorDisplaySystem) {
                    window.errorDisplaySystem.showNetworkError(
                        strings.server_error,
                        { status, url },
                        () => this.retryRequest(requestId)
                    );
                }
                this.queueRequest(requestId, url, options);
                break;
            default:
                // Other HTTP errors
                if (window.errorDisplaySystem) {
                    window.errorDisplaySystem.showNetworkError(
                        `${strings.http_error} ${status}`,
                        { status, url }
                    );
                }
        }
        
        return response;
    }

    async handleNetworkError(error, url, options) {
        const strings = this.getLanguageStrings();
        
        if (error.name === 'AbortError') {
            // Request timeout - don't show to users
            const requestId = this.generateRequestId();
            // if (window.errorDisplaySystem) {
            //     window.errorDisplaySystem.showNetworkError(
            //         strings.request_timeout,
            //         { url, error: error.message },
            //         () => this.retryRequest(requestId)
            //     );
            // }
            this.queueRequest(requestId, url, options);
        } else if (error.name === 'TypeError' && error.message.includes('fetch')) {
            // Network error (likely offline)
            this.handleConnectionChange(false);
            const requestId = this.generateRequestId();
            this.queueRequest(requestId, url, options);
            
            // Don't show network errors to users
            // if (window.errorDisplaySystem) {
            //     window.errorDisplaySystem.showNetworkError(
            //         strings.network_error,
            //         { url, error: error.message },
            //         () => this.retryRequest(requestId)
            //     );
            // }
        } else {
            // Other errors - only show if not network-related
            const isNetworkError = error.message && (
                error.message.includes('fetch') || 
                error.message.includes('network') || 
                error.message.includes('NetworkError')
            );
            if (!isNetworkError && window.errorDisplaySystem) {
                window.errorDisplaySystem.showNetworkError(
                    strings.unexpected_error,
                    { url, error: error.message }
                );
            }
        }
        
        throw error;
    }

    showAuthError() {
        const strings = this.getLanguageStrings();
        
        if (window.errorDisplaySystem) {
            window.errorDisplaySystem.showSecurityError(
                strings.auth_required,
                null
            );
        }
        
        // Redirect to login page after a delay
        setTimeout(() => {
            window.location.href = '/login/';
        }, 3000);
    }

    queueRequest(requestId, url, options) {
        this.requestQueue.push({
            id: requestId,
            url,
            options,
            timestamp: Date.now(),
            retryCount: 0
        });
        
        console.log(`Request queued: ${requestId} - ${url}`);
    }

    async retryRequest(requestId) {
        const requestIndex = this.requestQueue.findIndex(req => req.id === requestId);
        if (requestIndex === -1) {
            console.warn(`Request ${requestId} not found in queue`);
            return;
        }
        
        const request = this.requestQueue[requestIndex];
        const strings = this.getLanguageStrings();
        
        if (request.retryCount >= this.maxRetries) {
            this.requestQueue.splice(requestIndex, 1);
            if (window.errorDisplaySystem) {
                window.errorDisplaySystem.showNetworkError(strings.max_retries_exceeded);
            }
            return;
        }
        
        request.retryCount++;
        
        // Calculate delay with exponential backoff
        const delay = Math.min(
            this.baseDelay * Math.pow(2, request.retryCount - 1),
            this.maxDelay
        );
        
        console.log(`Retrying request ${requestId} (attempt ${request.retryCount}) after ${delay}ms`);
        
        setTimeout(async () => {
            try {
                const response = await fetch(request.url, request.options);
                
                if (response.ok) {
                    // Success - remove from queue
                    this.requestQueue.splice(requestIndex, 1);
                    if (window.errorDisplaySystem) {
                        window.errorDisplaySystem.showSuccess(strings.request_succeeded);
                    }
                } else {
                    // Still failing - will be handled by handleHttpError
                    console.log(`Retry ${request.retryCount} failed for ${requestId}`);
                }
            } catch (error) {
                console.log(`Retry ${request.retryCount} failed for ${requestId}:`, error);
            }
        }, delay);
    }

    async processQueuedRequests() {
        const strings = this.getLanguageStrings();
        
        if (this.requestQueue.length === 0) return;
        
        console.log(`Processing ${this.requestQueue.length} queued requests`);
        
        // Process requests with a delay to avoid overwhelming the server
        for (let i = 0; i < this.requestQueue.length; i++) {
            setTimeout(() => {
                this.retryRequest(this.requestQueue[i].id);
            }, i * 500); // 500ms delay between requests
        }
        
        if (window.errorDisplaySystem) {
            window.errorDisplaySystem.showSuccess(
                `${strings.processing_queued_requests} (${this.requestQueue.length})`
            );
        }
    }

    generateRequestId() {
        return 'req_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    loadLanguageStrings() {
        const currentLang = document.documentElement.lang || 'uk';
        this.currentLanguage = currentLang;
    }

    getLanguageStrings() {
        const lang = this.currentLanguage || 'uk';
        
        const strings = {
            uk: {
                offline: 'Відсутнє з\'єднання',
                connection_lost: 'З\'єднання втрачено. Запити будуть повторені автоматично.',
                connection_restored: 'З\'єднання відновлено. Обробка відкладених запитів...',
                network_error: 'Помилка мережі. Перевірте підключення до інтернету.',
                server_error: 'Помилка сервера. Спроба повторного підключення...',
                request_timeout: 'Час очікування запиту минув. Повторна спроба...',
                auth_required: 'Потрібна авторизація. Перенаправлення на сторінку входу...',
                access_denied: 'Доступ заборонено. Недостатньо прав.',
                not_found: 'Ресурс не знайдено.',
                validation_error: 'Помилка валідації даних.',
                http_error: 'HTTP помилка',
                unexpected_error: 'Неочікувана помилка.',
                max_retries_exceeded: 'Перевищено максимальну кількість спроб повтору.',
                request_succeeded: 'Запит успішно виконано.',
                processing_queued_requests: 'Обробка відкладених запитів'
            },
            en: {
                offline: 'No connection',
                connection_lost: 'Connection lost. Requests will be retried automatically.',
                connection_restored: 'Connection restored. Processing queued requests...',
                network_error: 'Network error. Please check your internet connection.',
                server_error: 'Server error. Attempting to reconnect...',
                request_timeout: 'Request timeout. Retrying...',
                auth_required: 'Authentication required. Redirecting to login page...',
                access_denied: 'Access denied. Insufficient permissions.',
                not_found: 'Resource not found.',
                validation_error: 'Data validation error.',
                http_error: 'HTTP error',
                unexpected_error: 'Unexpected error.',
                max_retries_exceeded: 'Maximum retry attempts exceeded.',
                request_succeeded: 'Request completed successfully.',
                processing_queued_requests: 'Processing queued requests'
            },
            ru: {
                offline: 'Нет соединения',
                connection_lost: 'Соединение потеряно. Запросы будут повторены автоматически.',
                connection_restored: 'Соединение восстановлено. Обработка отложенных запросов...',
                network_error: 'Ошибка сети. Проверьте подключение к интернету.',
                server_error: 'Ошибка сервера. Попытка переподключения...',
                request_timeout: 'Время ожидания запроса истекло. Повторная попытка...',
                auth_required: 'Требуется авторизация. Перенаправление на страницу входа...',
                access_denied: 'Доступ запрещен. Недостаточно прав.',
                not_found: 'Ресурс не найден.',
                validation_error: 'Ошибка валидации данных.',
                http_error: 'HTTP ошибка',
                unexpected_error: 'Неожиданная ошибка.',
                max_retries_exceeded: 'Превышено максимальное количество попыток повтора.',
                request_succeeded: 'Запрос успешно выполнен.',
                processing_queued_requests: 'Обработка отложенных запросов'
            }
        };

        return strings[lang] || strings.uk;
    }

    // Public API methods
    isConnectionOnline() {
        return this.isOnline;
    }

    getQueuedRequestsCount() {
        return this.requestQueue.length;
    }

    clearRequestQueue() {
        this.requestQueue = [];
        console.log('Request queue cleared');
    }

    setMaxRetries(maxRetries) {
        this.maxRetries = maxRetries;
    }

    setRetryDelay(baseDelay, maxDelay) {
        this.baseDelay = baseDelay;
        this.maxDelay = maxDelay;
    }

    // Manual retry for specific requests
    retryAllQueuedRequests() {
        this.processQueuedRequests();
    }

    // Add request to queue manually
    addRequestToQueue(url, options) {
        const requestId = this.generateRequestId();
        this.queueRequest(requestId, url, options);
        return requestId;
    }
}

// Add CSS for connection indicator
        const networkErrorStyle = document.createElement('style');
        networkErrorStyle.textContent = `
    .connection-indicator {
        animation: slideDown 0.3s ease-out;
    }
    
    @keyframes slideDown {
        from {
            transform: translateX(-50%) translateY(-100%);
            opacity: 0;
        }
        to {
            transform: translateX(-50%) translateY(0);
            opacity: 1;
        }
    }
    
    .connection-indicator.bg-danger {
        background-color: #dc3545 !important;
    }
    
    .connection-indicator.bg-success {
        background-color: #28a745 !important;
    }
        `;
        document.head.appendChild(networkErrorStyle);

// Initialize the network error handler when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    window.networkErrorHandler = new NetworkErrorHandler();
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = NetworkErrorHandler;
}
