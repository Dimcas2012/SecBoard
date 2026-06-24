/**
 * Fix for JavaScript permissions policy violations in Django admin
 * This script prevents the unload event violations that cause console errors
 */

(function() {
    'use strict';
    
    // Override window.addEventListener to prevent unload violations
    const originalAddEventListener = window.addEventListener;
    window.addEventListener = function(type, listener, options) {
        if (type === 'unload' || type === 'beforeunload') {
            // Log the attempt but don't actually add the listener
            console.debug('Prevented unload event listener to avoid permissions policy violation');
            return function() {}; // Return a dummy function
        }
        return originalAddEventListener.call(this, type, listener, options);
    };
    
    // Clear any existing unload handlers
    window.onbeforeunload = null;
    window.onunload = null;
    
    // Fix for RelatedObjectLookups.js issues
    document.addEventListener('DOMContentLoaded', function() {
        // Override problematic functions
        if (typeof window.dismissRelatedLookupPopup !== 'undefined') {
            const originalDismissRelatedLookupPopup = window.dismissRelatedLookupPopup;
            window.dismissRelatedLookupPopup = function(win, chosenId) {
                try {
                    return originalDismissRelatedLookupPopup(win, chosenId);
                } catch (e) {
                    console.warn('RelatedObjectLookups error handled:', e);
                    if (win && win.close) {
                        win.close();
                    }
                }
            };
        }
        
        // Override showRelatedObjectLookupPopup to prevent unload violations
        if (typeof window.showRelatedObjectLookupPopup !== 'undefined') {
            const originalShowRelatedObjectLookupPopup = window.showRelatedObjectLookupPopup;
            window.showRelatedObjectLookupPopup = function(triggeringLink) {
                try {
                    // Remove unload event listeners before opening popup
                    const originalOnBeforeUnload = window.onbeforeunload;
                    window.onbeforeunload = null;
                    
                    const result = originalShowRelatedObjectLookupPopup(triggeringLink);
                    
                    // Restore original handler after a delay
                    setTimeout(function() {
                        window.onbeforeunload = originalOnBeforeUnload;
                    }, 100);
                    
                    return result;
                } catch (e) {
                    console.warn('showRelatedObjectLookupPopup error handled:', e);
                    // Fallback: navigate to the URL directly
                    if (triggeringLink && triggeringLink.href) {
                        window.location.href = triggeringLink.href.replace(/[?&]_popup=1/, '');
                    }
                }
            };
        }
        
        // Handle popup links to prevent violations
        const popupLinks = document.querySelectorAll('a[onclick*="showRelatedObjectLookupPopup"]');
        popupLinks.forEach(function(link) {
            link.addEventListener('click', function(e) {
                e.preventDefault();
                const href = this.href;
                if (href) {
                    // Open in same window instead of popup to avoid violations
                    window.location.href = href.replace(/[?&]_popup=1/, '');
                }
            });
        });
        
        // Handle delete confirmations more gracefully
        const deleteLinks = document.querySelectorAll('a[href*="delete/"]');
        deleteLinks.forEach(function(link) {
            link.addEventListener('click', function(e) {
                if (!confirm('Are you sure you want to delete this item?')) {
                    e.preventDefault();
                }
            });
        });
        
        // Improve form submission handling
        const forms = document.querySelectorAll('form');
        forms.forEach(function(form) {
            form.addEventListener('submit', function(e) {
                // Allow normal form submission without unload warnings
                window.onbeforeunload = null;
            });
        });
    });
    
    // Prevent the page from showing "Are you sure you want to leave" dialogs
    window.onbeforeunload = function() {
        return null;
    };
    
})(); 