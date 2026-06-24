// Risk Report Permissions Fix
// This file contains fixes for JavaScript errors when elements are hidden due to permissions

document.addEventListener('DOMContentLoaded', function() {
    // Create userPermissions object if it doesn't exist
    if (typeof window.userPermissions === 'undefined') {
        window.userPermissions = {
            can_add_report: typeof canAddReport !== 'undefined' ? canAddReport : false,
            can_edit_report: typeof canEditReport !== 'undefined' ? canEditReport : false,
            can_delete_report: typeof canDeleteReport !== 'undefined' ? canDeleteReport : false,
            has_access_report: typeof hasAccessReport !== 'undefined' ? hasAccessReport : false
        };
        console.log('Created userPermissions object:', window.userPermissions);
    }
    
    // Fix for missing createProfileBtn
    const createProfileBtn = document.getElementById('createProfileBtn');
    if (!createProfileBtn) {
        console.log('createProfileBtn not found - user may not have can_add_report permission');
    }
    
    // Fix for missing createScheduleBtn
    const createScheduleBtn = document.getElementById('createScheduleBtn');
    if (!createScheduleBtn) {
        console.log('createScheduleBtn not found - user may not have can_add_report permission');
    }
    
    // Override initScheduledReports to handle missing elements
    if (window.initScheduledReports) {
        const originalInitScheduledReports = window.initScheduledReports;
        window.initScheduledReports = function() {
            try {
                originalInitScheduledReports();
            } catch (error) {
                console.log('initScheduledReports error handled:', error.message);
            }
        };
    }
    
    // Override initReportProfiles to handle missing elements
    if (window.initReportProfiles) {
        const originalInitReportProfiles = window.initReportProfiles;
        window.initReportProfiles = function() {
            try {
                originalInitReportProfiles();
            } catch (error) {
                console.log('initReportProfiles error handled:', error.message);
            }
        };
    }
    
    // Add safe event listener helper
    window.safeAddEventListener = function(elementId, event, handler) {
        const element = document.getElementById(elementId);
        if (element) {
            element.addEventListener(event, handler);
            return true;
        } else {
            console.log(`Element ${elementId} not found - skipping event listener`);
            return false;
        }
    };
}); 