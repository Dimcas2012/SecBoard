// Reduce logging in threat-impact-assessment.js
(function() {
    'use strict';
    
    // Override console.log for ThreatImpactAssessment messages
    const originalLog = console.log;
    console.log = function(...args) {
        const message = args.join(' ');
        
        // Skip ThreatImpactAssessment logging unless in debug mode
        if (message.includes('ThreatImpactAssessment:') && !window.DEBUG_MODE) {
            return;
        }
        
        // Skip other verbose logging unless in debug mode
        if ((message.includes('Loaded threats:') || 
             message.includes('DataTable initialized') ||
             message.includes('Asset filter initialized') ||
             message.includes('Risk Configuration permissions initialized')) && !window.DEBUG_MODE) {
            return;
        }
        
        originalLog.apply(console, args);
    };
    
    // Add debug mode toggle for easy testing
    if (!window.toggleDebugMode) {
        window.toggleDebugMode = function() {
            window.DEBUG_MODE = !window.DEBUG_MODE;
            console.log('Debug mode:', window.DEBUG_MODE ? 'enabled' : 'disabled');
        };
    }
    
    // Initialize debug mode as disabled
    window.DEBUG_MODE = false;
    
})();
