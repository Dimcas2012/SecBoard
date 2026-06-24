/**
 * Risk Configuration Permissions Fix
 * Ensures safe operation with permission-controlled elements
 */

// Create global permissions object if not exists
if (typeof window.userPermissions === 'undefined') {
    window.userPermissions = {
        has_access_config: typeof has_access_config !== 'undefined' ? has_access_config : false,
        can_add_config: typeof can_add_config !== 'undefined' ? can_add_config : false,
        can_edit_config: typeof can_edit_config !== 'undefined' ? can_edit_config : false,
        can_delete_config: typeof can_delete_config !== 'undefined' ? can_delete_config : false
    };
}

// Safe element selector with permission check
function safeAddEventListener(selector, event, handler, permission = null) {
    try {
        const element = document.querySelector(selector);
        if (element) {
            // Check permission if provided
            if (permission && !window.userPermissions[permission]) {
                console.log(`Permission ${permission} not granted for element ${selector}`);
                return;
            }
            element.addEventListener(event, handler);
        } else {
            console.log(`Element ${selector} not found (may be hidden due to permissions)`);
        }
    } catch (error) {
        console.error(`Error adding event listener to ${selector}:`, error);
    }
}

// Safe multiple elements selector with permission check
function safeAddEventListenerAll(selector, event, handler, permission = null) {
    try {
        const elements = document.querySelectorAll(selector);
        elements.forEach(element => {
            // Check permission if provided
            if (permission && !window.userPermissions[permission]) {
                console.log(`Permission ${permission} not granted for elements ${selector}`);
                return;
            }
            element.addEventListener(event, handler);
        });
    } catch (error) {
        console.error(`Error adding event listeners to ${selector}:`, error);
    }
}

// Initialize permission-controlled elements safely
function initializeRiskConfigPermissions() {
    try {
        // Threats section
        safeAddEventListener('#addThreatBtn', 'click', function() {
            // Add threat functionality
            console.log('Add threat clicked');
        }, 'can_add_config');

        safeAddEventListenerAll('.edit-threat', 'click', function() {
            // Edit threat functionality
            console.log('Edit threat clicked');
        }, 'can_edit_config');

        safeAddEventListenerAll('.delete-threat', 'click', function() {
            // Delete threat functionality
            console.log('Delete threat clicked');
        }, 'can_delete_config');

        // Vulnerabilities section
        safeAddEventListener('#addVulnerabilityBtn', 'click', function() {
            // Add vulnerability functionality
            console.log('Add vulnerability clicked');
        }, 'can_add_config');

        safeAddEventListener('#deleteSelectedVulnerabilities', 'click', function() {
            // Delete selected vulnerabilities functionality
            console.log('Delete selected vulnerabilities clicked');
        }, 'can_delete_config');

        // AI Tools
        safeAddEventListener('#addVulnerabilityAIBtn', 'click', function() {
            // Add vulnerability AI functionality
            console.log('Add vulnerability AI clicked');
        }, 'can_add_config');

        safeAddEventListener('#descriptionSelectedAiBtn', 'click', function() {
            // Description AI functionality
            console.log('Description AI clicked');
        }, 'can_edit_config');

        safeAddEventListener('#analyzeSelectedVulnerabilities', 'click', function() {
            // Analyze vulnerabilities functionality
            console.log('Analyze vulnerabilities clicked');
        }, 'can_edit_config');

        safeAddEventListener('#riskMitigationSelectedAiBtn', 'click', function() {
            // Risk mitigation AI functionality
            console.log('Risk mitigation AI clicked');
        }, 'can_edit_config');

        safeAddEventListener('#pciDssSelectedAiBtn', 'click', function() {
            // PCI DSS AI functionality
            console.log('PCI DSS AI clicked');
        }, 'can_edit_config');

        safeAddEventListener('#iso27002SelectedAiBtn', 'click', function() {
            // ISO27002 AI functionality
            console.log('ISO27002 AI clicked');
        }, 'can_edit_config');

        safeAddEventListener('#noteSelectedAiBtn', 'click', function() {
            // Note AI functionality
            console.log('Note AI clicked');
        }, 'can_edit_config');

        safeAddEventListener('#translateSelectedAiBtn', 'click', function() {
            // Translate AI functionality
            console.log('Translate AI clicked');
        }, 'can_edit_config');

        // Data Management
        safeAddEventListener('#translateSelectedVulnerabilities', 'click', function() {
            // Translate vulnerabilities functionality
            console.log('Translate vulnerabilities clicked');
        }, 'can_edit_config');

        safeAddEventListener('#exportVulnerabilitiesXlsx', 'click', function() {
            // Export vulnerabilities functionality
            console.log('Export vulnerabilities clicked');
        }, 'has_access_config');

        safeAddEventListener('#importVulnerabilitiesBtn', 'click', function() {
            // Import vulnerabilities functionality
            console.log('Import vulnerabilities clicked');
        }, 'can_add_config');

        console.log('Risk Configuration permissions initialized successfully');
    } catch (error) {
        console.error('Error initializing Risk Configuration permissions:', error);
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    initializeRiskConfigPermissions();
});

// Also initialize when page is fully loaded (for dynamic content)
window.addEventListener('load', function() {
    initializeRiskConfigPermissions();
}); 