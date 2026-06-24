// Threat Impact Assessment JavaScript
// Handles the new impact assessment functionality in the threat modal

class ThreatImpactAssessment {
    constructor() {
        this.impactLevels = null;
        this.currentLanguage = this.getCurrentLanguage();
        if (window.DEBUG_MODE) {
            console.log('ThreatImpactAssessment: Initialized with language:', this.currentLanguage);
        }
        this.init();
    }

    async init() {
        try {
            await this.loadImpactLevels();
            this.setupEventListeners();
            this.populateImpactDropdowns();
        } catch (error) {
            console.error('ThreatImpactAssessment: Error during initialization:', error);
        }
    }

    getCurrentLanguage() {
        // First priority: Use language from Django template variable
        if (typeof window.currentLanguage !== 'undefined' && window.currentLanguage) {
            if (window.DEBUG_MODE) {
                console.log('ThreatImpactAssessment: Using language from Django template:', window.currentLanguage);
            }
            return window.currentLanguage.substring(0, 2);
        }
        
        // Second priority: Use language from modal template
        if (typeof window.currentLanguageShort !== 'undefined' && window.currentLanguageShort) {
            if (window.DEBUG_MODE) {
                console.log('ThreatImpactAssessment: Using language from modal template:', window.currentLanguageShort);
            }
            return window.currentLanguageShort;
        }
        
        // Third priority: Try to get from HTML lang attribute
        const htmlLang = document.documentElement.lang;
        if (htmlLang) {
            if (window.DEBUG_MODE) {
                console.log('ThreatImpactAssessment: Using language from HTML lang attribute:', htmlLang);
            }
            return htmlLang.substring(0, 2);
        }
        
        // Fourth priority: Try to get from URL path
        const path = window.location.pathname;
        const langMatch = path.match(/^\/([a-z]{2})\//);
        if (langMatch) {
            if (window.DEBUG_MODE) {
                console.log('ThreatImpactAssessment: Using language from URL path:', langMatch[1]);
            }
            return langMatch[1];
        }
        
        // Default to Ukrainian
        if (window.DEBUG_MODE) {
            console.log('ThreatImpactAssessment: Using default language: uk');
        }
        return 'uk';
    }

    async loadImpactLevels() {
        try {
            // Get current language for API request
            const currentLanguage = this.getCurrentLanguage();
            if (window.DEBUG_MODE) {
                console.log('ThreatImpactAssessment: Loading impact levels for language:', currentLanguage);
            }
            
            // Use the correct URL with language prefix and explicit language param for backend
            const apiUrl = `/${currentLanguage}/app_risk/get_impact_levels/?language=${currentLanguage}`;
            if (window.DEBUG_MODE) {
                console.log('ThreatImpactAssessment: API URL:', apiUrl);
            }
            
            const response = await fetch(apiUrl);
            if (window.DEBUG_MODE) {
                console.log('ThreatImpactAssessment: API response status:', response.status);
            }
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            this.impactLevels = await response.json();
            if (window.DEBUG_MODE) {
                console.log('ThreatImpactAssessment: Impact levels loaded:', this.impactLevels);
                
                // Log the structure of loaded data
                if (this.impactLevels) {
                    console.log('ThreatImpactAssessment: Financial impacts count:', this.impactLevels.financial_impacts?.length || 0);
                    console.log('ThreatImpactAssessment: Operational impacts count:', this.impactLevels.operational_impacts?.length || 0);
                    console.log('ThreatImpactAssessment: Reputational impacts count:', this.impactLevels.reputational_impacts?.length || 0);
                }
            }
        } catch (error) {
            console.error('ThreatImpactAssessment: Error loading impact levels:', error);
            throw error;
        }
    }

    populateImpactDropdowns() {
        console.log('ThreatImpactAssessment: Populating impact dropdowns...');
        
        // Get current language
        const currentLanguage = this.getCurrentLanguage();
        console.log('ThreatImpactAssessment: Current language for dropdowns:', currentLanguage);
        
        // Populate Financial Impact dropdown
        this.populateDropdown('financial', this.impactLevels.financial_impacts, currentLanguage);
        
        // Populate Operational Impact dropdown
        this.populateDropdown('operational', this.impactLevels.operational_impacts, currentLanguage);
        
        // Populate Reputational Impact dropdown
        this.populateDropdown('reputational', this.impactLevels.reputational_impacts, currentLanguage);
    }

    populateDropdown(type, impacts, language) {
        const selectElement = document.getElementById(`threat-${type}-impact`);
        if (!selectElement) {
            console.warn(`ThreatImpactAssessment: Select element for ${type} impact not found`);
            return;
        }

        console.log(`ThreatImpactAssessment: Populating ${type} impact dropdown for language: ${language}`);
        console.log(`ThreatImpactAssessment: ${type} impacts data:`, impacts);
        
        // Clear existing options except the first one
        while (selectElement.options.length > 1) {
            selectElement.remove(1);
        }

        if (!impacts || impacts.length === 0) {
            console.warn(`ThreatImpactAssessment: No ${type} impacts data available`);
            return;
        }

        console.log(`ThreatImpactAssessment: Adding ${impacts.length} options to ${type} dropdown`);

        impacts.forEach(impact => {
            const option = document.createElement('option');
            option.value = impact.id;
            
            // Use localized name from API response
            let displayName = impact.name;
            console.log(`ThreatImpactAssessment: ${type} impact ${impact.id} name:`, displayName);
            
            // Add impact value to display name for better UX
            option.textContent = `${displayName} (${impact.impact_value})`;
            option.dataset.impactValue = impact.impact_value;
            option.dataset.description = impact.description || '';
            option.dataset.criteria = impact.criteria || '';
            option.dataset.examples = impact.examples || '';
            option.dataset.color = impact.color || '#000000';
            
            selectElement.appendChild(option);
        });

        console.log(`ThreatImpactAssessment: ${type} dropdown populated with ${impacts.length} options`);
        console.log(`ThreatImpactAssessment: ${type} dropdown options:`, Array.from(selectElement.options).map(opt => ({value: opt.value, text: opt.textContent})));
    }

    setupEventListeners() {
        console.log('ThreatImpactAssessment: Setting up event listeners...');
        
        // Financial Impact change
        const financialSelect = document.getElementById('threat-financial-impact');
        if (financialSelect) {
            financialSelect.addEventListener('change', (e) => {
                this.handleImpactChange('financial', e.target.value);
            });
        }
        
        // Operational Impact change
        const operationalSelect = document.getElementById('threat-operational-impact');
        if (operationalSelect) {
            operationalSelect.addEventListener('change', (e) => {
                this.handleImpactChange('operational', e.target.value);
            });
        }
        
        // Reputational Impact change
        const reputationalSelect = document.getElementById('threat-reputational-impact');
        if (reputationalSelect) {
            reputationalSelect.addEventListener('change', (e) => {
                this.handleImpactChange('reputational', e.target.value);
            });
        }
        
        // Probability field change
        const probabilityField = document.getElementById('threat-probability');
        if (probabilityField) {
            console.log('ThreatImpactAssessment: Found probability field');
            probabilityField.addEventListener('input', (e) => {
                this.updateOverallImpact();
            });
        } else {
            console.warn('ThreatImpactAssessment: Probability field not found');
        }
    }

    handleImpactChange(type, selectedId) {
        console.log(`ThreatImpactAssessment: ${type} impact changed to:`, selectedId);
        
        const detailsElement = document.getElementById(`${type}-impact-details`);
        const descriptionElement = document.getElementById(`${type}-impact-description`);
        
        if (!detailsElement || !descriptionElement) {
            console.warn(`ThreatImpactAssessment: Details elements for ${type} impact not found`);
            return;
        }

        if (!selectedId) {
            console.log(`ThreatImpactAssessment: No ${type} impact selected, hiding details`);
            detailsElement.style.display = 'none';
            return;
        }

        const impacts = this.impactLevels[`${type}_impacts`];
        console.log(`ThreatImpactAssessment: Available ${type} impacts:`, impacts);
        
        const selectedImpact = impacts.find(impact => impact.id == selectedId);
        console.log(`ThreatImpactAssessment: Selected ${type} impact:`, selectedImpact);
        
        if (!selectedImpact) {
            console.warn(`ThreatImpactAssessment: Selected ${type} impact not found for ID:`, selectedId);
            return;
        }

        // Get current language
        const currentLanguage = this.getCurrentLanguage();
        console.log(`ThreatImpactAssessment: Displaying ${type} impact details for language:`, currentLanguage);
        
        // Get localized labels based on language
        const labels = this.getLocalizedLabels(currentLanguage);
        
        // Get localized description from API response
        let description = selectedImpact.description;
        let criteria = selectedImpact.criteria;
        let examples = selectedImpact.examples;

        console.log(`ThreatImpactAssessment: ${type} impact details:`, {
            description: description,
            criteria: criteria,
            examples: examples
        });

        // Create detailed description with all information
        let fullDescription = '';
        if (description) {
            fullDescription += `<strong>${labels.description}:</strong> ${description}<br><br>`;
        }
        if (criteria) {
            fullDescription += `<strong>${labels.criteria}:</strong> ${criteria}<br><br>`;
        }
        if (examples) {
            fullDescription += `<strong>${labels.examples}:</strong> ${examples}`;
        }

        descriptionElement.innerHTML = fullDescription;
        detailsElement.style.display = 'block';
        
        // Apply color styling
        if (selectedImpact.color) {
            detailsElement.style.backgroundColor = this.getLightColor(selectedImpact.color);
            detailsElement.style.borderLeft = `4px solid ${selectedImpact.color}`;
        }

        // Update overall impact calculation
        this.updateOverallImpact();
    }

    updateOverallImpact() {
        console.log('ThreatImpactAssessment: Updating overall impact...');
        
        const impacts = [];
        
        // Get Financial Impact
        const financialSelect = document.getElementById('threat-financial-impact');
        if (financialSelect && financialSelect.value) {
            const financialImpact = this.impactLevels.financial_impacts.find(impact => impact.id == financialSelect.value);
            if (financialImpact) {
                impacts.push(financialImpact.impact_value);
            }
        }
        
        // Get Operational Impact
        const operationalSelect = document.getElementById('threat-operational-impact');
        if (operationalSelect && operationalSelect.value) {
            const operationalImpact = this.impactLevels.operational_impacts.find(impact => impact.id == operationalSelect.value);
            if (operationalImpact) {
                impacts.push(operationalImpact.impact_value);
            }
        }
        
        // Get Reputational Impact
        const reputationalSelect = document.getElementById('threat-reputational-impact');
        if (reputationalSelect && reputationalSelect.value) {
            const reputationalImpact = this.impactLevels.reputational_impacts.find(impact => impact.id == reputationalSelect.value);
            if (reputationalImpact) {
                impacts.push(reputationalImpact.impact_value);
            }
        }
        
        // Calculate overall impact
        let overallImpact = 0;
        if (impacts.length > 0) {
            // Загальний вплив (E) = (Фінансовий вплив + Операційний вплив + Репутаційний вплив) / 3
            overallImpact = impacts.reduce((sum, impact) => sum + impact, 0) / impacts.length;
        }
        
        // Update overall impact display
        const overallImpactElement = document.getElementById('overall-impact-value');
        if (overallImpactElement) {
            overallImpactElement.textContent = overallImpact.toFixed(3);
        }
        
        // Update progress bar
        const progressBar = document.getElementById('overall-impact-bar');
        if (progressBar) {
            const percentage = Math.min(overallImpact * 100, 100);
            progressBar.style.width = `${percentage}%`;
            progressBar.style.backgroundColor = this.getImpactColor(overallImpact);
        }
        
        // Update impact level badge
        const impactLevelElement = document.getElementById('overall-impact-level');
        if (impactLevelElement) {
            const levelName = this.getImpactLevelName(overallImpact);
            const badgeClass = this.getImpactBadgeClass(overallImpact);
            impactLevelElement.textContent = levelName;
            impactLevelElement.className = `badge ${badgeClass} ms-2`;
        }
        
        // Update threat impact field
        const originalImpactField = document.getElementById('threat-impact');
        if (originalImpactField) {
            // Вплив загрози = Ймовірність (L) × Загальний вплив (E) × 100 для відсоткового формату
            const probabilityField = document.getElementById('threat-probability');
            let probability = 0;
            if (probabilityField && probabilityField.value) {
                probability = parseFloat(probabilityField.value);
            }
            
            // Розраховуємо вплив загрози: Вплив загрози = Ймовірність (L) × Загальний вплив (E) × 100
            const threatImpact = probability * overallImpact * 100;
            originalImpactField.value = threatImpact.toFixed(2);
            
            console.log('ThreatImpactAssessment: Threat impact calculated:', threatImpact, '(Probability:', probability, '× Overall Impact:', overallImpact, '× 100)');
        }
    }

    getImpactColor(impactValue) {
        if (impactValue <= 0.2) return '#28a745'; // Green
        if (impactValue <= 0.5) return '#ffc107'; // Yellow
        if (impactValue <= 0.8) return '#fd7e14'; // Orange
        return '#dc3545'; // Red
    }

    getLightColor(hexColor) {
        // Convert hex to RGB and make it lighter
        const r = parseInt(hexColor.slice(1, 3), 16);
        const g = parseInt(hexColor.slice(3, 5), 16);
        const b = parseInt(hexColor.slice(5, 7), 16);
        
        const lightR = Math.min(255, r + 100);
        const lightG = Math.min(255, g + 100);
        const lightB = Math.min(255, b + 100);
        
        return `rgb(${lightR}, ${lightG}, ${lightB})`;
    }

    getImpactLevelName(impactValue) {
        const currentLanguage = this.getCurrentLanguage();
        console.log('ThreatImpactAssessment: Getting impact level name for language:', currentLanguage);
        
        if (impactValue <= 0.2) {
            return this.getLocalizedText('Низький', 'Low', 'Низкий', currentLanguage);
        } else if (impactValue <= 0.5) {
            return this.getLocalizedText('Середній', 'Medium', 'Средний', currentLanguage);
        } else if (impactValue <= 0.8) {
            return this.getLocalizedText('Високий', 'High', 'Высокий', currentLanguage);
        } else {
            return this.getLocalizedText('Критичний', 'Critical', 'Критический', currentLanguage);
        }
    }

    getLocalizedText(ukText, enText, ruText, language) {
        switch (language) {
            case 'uk':
                return ukText;
            case 'en':
                return enText;
            case 'ru':
                return ruText;
            default:
                return ukText;
        }
    }

    getLocalizedLabels(language) {
        const labels = {
            uk: {
                description: 'Опис',
                criteria: 'Критерії',
                examples: 'Приклади'
            },
            en: {
                description: 'Description',
                criteria: 'Criteria',
                examples: 'Examples'
            },
            ru: {
                description: 'Описание',
                criteria: 'Критерии',
                examples: 'Примеры'
            }
        };
        
        return labels[language] || labels.uk;
    }

    getImpactBadgeClass(impactValue) {
        if (impactValue <= 0.2) {
            return 'bg-success'; // Зелений для низького
        } else if (impactValue <= 0.5) {
            return 'bg-warning'; // Жовтий для середнього
        } else if (impactValue <= 0.8) {
            return 'bg-danger'; // Червоний для високого
        } else {
            return 'bg-dark'; // Темний для критичного
        }
    }

    setImpactValues(threatData) {
        console.log('ThreatImpactAssessment: Setting impact values:', threatData);
        
        // Get current language
        const currentLanguage = this.getCurrentLanguage();
        console.log('ThreatImpactAssessment: Current language:', currentLanguage);
        
        // Set Financial Impact
        if (threatData.financial_impact) {
            const financialSelect = document.getElementById('threat-financial-impact');
            if (financialSelect) {
                financialSelect.value = threatData.financial_impact;
                this.handleImpactChange('financial', threatData.financial_impact);
            }
        }
        
        // Set Operational Impact
        if (threatData.operational_impact) {
            const operationalSelect = document.getElementById('threat-operational-impact');
            if (operationalSelect) {
                operationalSelect.value = threatData.operational_impact;
                this.handleImpactChange('operational', threatData.operational_impact);
            }
        }
        
        // Set Reputational Impact
        if (threatData.reputational_impact) {
            const reputationalSelect = document.getElementById('threat-reputational-impact');
            if (reputationalSelect) {
                reputationalSelect.value = threatData.reputational_impact;
                this.handleImpactChange('reputational', threatData.reputational_impact);
            }
        }
        
        // Update overall impact calculation
        this.updateOverallImpact();
    }

    async reloadImpactLevelsForCurrentLanguage() {
        /** Reload impact levels with current site language (uses Country-based translations e.g. Germany DE). */
        await this.loadImpactLevels();
        this.populateImpactDropdowns();
    }

    clearImpactValues() {
        console.log('ThreatImpactAssessment: Clearing impact values');
        
        // Clear Financial Impact
        const financialSelect = document.getElementById('threat-financial-impact');
        if (financialSelect) {
            financialSelect.value = '';
            this.handleImpactChange('financial', '');
        }
        
        // Clear Operational Impact
        const operationalSelect = document.getElementById('threat-operational-impact');
        if (operationalSelect) {
            operationalSelect.value = '';
            this.handleImpactChange('operational', '');
        }
        
        // Clear Reputational Impact
        const reputationalSelect = document.getElementById('threat-reputational-impact');
        if (reputationalSelect) {
            reputationalSelect.value = '';
            this.handleImpactChange('reputational', '');
        }
        
        // Update overall impact calculation
        this.updateOverallImpact();
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('ThreatImpactAssessment: DOM ready, initializing...');
    console.log('ThreatImpactAssessment: Available language variables:', {
        currentLanguage: window.currentLanguage,
        currentLanguageShort: window.currentLanguageShort,
        htmlLang: document.documentElement.lang,
        urlPath: window.location.pathname
    });
    window.threatImpactAssessment = new ThreatImpactAssessment();
});
