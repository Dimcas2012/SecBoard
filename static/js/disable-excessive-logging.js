// Disable excessive DOM logging
(function() {
    'use strict';
    
    // Disable console.log for DOM mutations if not in debug mode
    if (!window.DEBUG_MODE) {
        // Override console.log to filter out excessive DOM logging
        const originalLog = console.log;
        console.log = function(...args) {
            const message = args.join(' ');
            
            // Skip logging for common DOM mutation messages
            const skipPatterns = [
                'A child node has been added or removed',
                'The class attribute was modified',
                'The style attribute was modified',
                'The tabindex attribute was modified',
                'The aria-',
                'The data-',
                'The role attribute was modified',
                'The placeholder attribute was modified',
                'The title attribute was modified',
                'The id attribute was modified',
                'The rowspan attribute was modified',
                'The colspan attribute was modified',
                'The aria-selected attribute was modified',
                'The aria-disabled attribute was modified',
                'The aria-controls attribute was modified',
                'The aria-describedby attribute was modified',
                'The aria-readonly attribute was modified',
                'The aria-labelledby attribute was modified',
                'The aria-hidden attribute was modified',
                'The aria-label attribute was modified',
                'The data-select2-id attribute was modified',
                'The data-popper-placement attribute was modified'
            ];
            
            // Check if message should be skipped
            const shouldSkip = skipPatterns.some(pattern => message.includes(pattern));
            
            if (!shouldSkip) {
                originalLog.apply(console, args);
            }
        };
    }
    
    // Disable MutationObserver logging if not in debug mode
    if (!window.DEBUG_MODE) {
        // Override console.log for MutationObserver
        const originalLog = console.log;
        console.log = function(...args) {
            const message = args.join(' ');
            
            // Skip MutationObserver related logging
            if (message.includes('MutationObserver') || 
                message.includes('DOM mutation') ||
                message.includes('attribute was modified') ||
                message.includes('child node has been')) {
                return;
            }
            
            originalLog.apply(console, args);
        };
    }
    
    // Add debug mode toggle
    window.toggleDebugMode = function() {
        window.DEBUG_MODE = !window.DEBUG_MODE;
        console.log('Debug mode:', window.DEBUG_MODE ? 'enabled' : 'disabled');
        
        if (window.DEBUG_MODE) {
            console.log('Excessive logging enabled. Use toggleDebugMode() to disable.');
        }
    };
    
    // Initialize debug mode as disabled
    window.DEBUG_MODE = false;
    
})();
