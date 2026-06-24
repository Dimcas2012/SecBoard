/**
 * SecBoard Risk Reports - Interactive Components
 * Enhanced UI/UX with animations, transitions, and modern interactions
 */

class InteractiveComponents {
    constructor() {
        this.init();
        this.setupEventListeners();
        this.loadPreferences();
    }

    init() {
        this.setupThemeToggle();
        this.setupAnimatedCounters();
        this.setupProgressBars();
        this.setupTooltips();
        this.setupModals();
        this.setupDropdowns();
        this.setupTabs();
        this.setupAccordions();
        this.setupLoadingStates();
        this.setupNotifications();
    }

    // ===== THEME MANAGEMENT =====
    setupThemeToggle() {
        const themeToggle = document.getElementById('themeToggle');
        if (!themeToggle) return;

        themeToggle.addEventListener('click', () => {
            this.toggleTheme();
        });

        // Update toggle state based on current theme
        this.updateThemeToggle();
    }

    toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        
        // Add transition class
        document.documentElement.classList.add('theme-transition');
        
        // Change theme
        document.documentElement.setAttribute('data-theme', newTheme);
        
        // Save preference
        localStorage.setItem('theme', newTheme);
        
        // Update toggle
        this.updateThemeToggle();
        
        // Remove transition class after animation
        setTimeout(() => {
            document.documentElement.classList.remove('theme-transition');
        }, 300);

        // Trigger custom event
        this.dispatchEvent('themeChanged', { theme: newTheme });
    }

    updateThemeToggle() {
        const themeToggle = document.getElementById('themeToggle');
        const themeIcon = themeToggle?.querySelector('.theme-icon');
        const currentTheme = document.documentElement.getAttribute('data-theme');
        
        if (themeIcon) {
            themeIcon.innerHTML = currentTheme === 'dark' 
                ? '<i class="fas fa-sun"></i>' 
                : '<i class="fas fa-moon"></i>';
        }
    }

    // ===== ANIMATED COUNTERS =====
    setupAnimatedCounters() {
        const counters = document.querySelectorAll('[data-counter]');
        
        const observerOptions = {
            threshold: 0.5,
            rootMargin: '0px 0px -50px 0px'
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting && !entry.target.classList.contains('counted')) {
                    this.animateCounter(entry.target);
                    entry.target.classList.add('counted');
                }
            });
        }, observerOptions);

        counters.forEach(counter => observer.observe(counter));
    }

    animateCounter(element) {
        const target = parseInt(element.getAttribute('data-counter'));
        const duration = parseInt(element.getAttribute('data-duration') || '2000');
        const increment = target / (duration / 16);
        let current = 0;

        const updateCounter = () => {
            current += increment;
            if (current < target) {
                element.textContent = Math.floor(current);
                requestAnimationFrame(updateCounter);
            } else {
                element.textContent = target;
            }
        };

        updateCounter();
    }

    // ===== PROGRESS BARS =====
    setupProgressBars() {
        const progressBars = document.querySelectorAll('.progress-bar[data-progress]');
        
        const observerOptions = {
            threshold: 0.3,
            rootMargin: '0px 0px -100px 0px'
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting && !entry.target.classList.contains('animated')) {
                    this.animateProgressBar(entry.target);
                    entry.target.classList.add('animated');
                }
            });
        }, observerOptions);

        progressBars.forEach(bar => observer.observe(bar));
    }

    animateProgressBar(element) {
        const targetProgress = parseInt(element.getAttribute('data-progress'));
        const duration = parseInt(element.getAttribute('data-duration') || '1500');
        
        element.style.width = '0%';
        
        setTimeout(() => {
            element.style.transition = `width ${duration}ms ease-out`;
            element.style.width = `${targetProgress}%`;
        }, 100);
    }

    // ===== TOOLTIPS =====
    setupTooltips() {
        const tooltipTriggers = document.querySelectorAll('[data-tooltip]');
        
        tooltipTriggers.forEach(trigger => {
            let tooltip = null;
            
            trigger.addEventListener('mouseenter', (e) => {
                tooltip = this.createTooltip(e.target);
                document.body.appendChild(tooltip);
                this.positionTooltip(tooltip, e.target);
                
                // Animate in
                requestAnimationFrame(() => {
                    tooltip.classList.add('show');
                });
            });
            
            trigger.addEventListener('mouseleave', () => {
                if (tooltip) {
                    tooltip.classList.remove('show');
                    setTimeout(() => {
                        if (tooltip && tooltip.parentNode) {
                            tooltip.parentNode.removeChild(tooltip);
                        }
                    }, 150);
                }
            });
        });
    }

    createTooltip(trigger) {
        const tooltip = document.createElement('div');
        tooltip.className = 'tooltip';
        tooltip.textContent = trigger.getAttribute('data-tooltip');
        
        const placement = trigger.getAttribute('data-tooltip-placement') || 'top';
        tooltip.classList.add(`tooltip-${placement}`);
        
        return tooltip;
    }

    positionTooltip(tooltip, trigger) {
        const triggerRect = trigger.getBoundingClientRect();
        const tooltipRect = tooltip.getBoundingClientRect();
        const placement = tooltip.classList.contains('tooltip-bottom') ? 'bottom' :
                         tooltip.classList.contains('tooltip-left') ? 'left' :
                         tooltip.classList.contains('tooltip-right') ? 'right' : 'top';
        
        let top, left;
        
        switch (placement) {
            case 'top':
                top = triggerRect.top - tooltipRect.height - 8;
                left = triggerRect.left + (triggerRect.width - tooltipRect.width) / 2;
                break;
            case 'bottom':
                top = triggerRect.bottom + 8;
                left = triggerRect.left + (triggerRect.width - tooltipRect.width) / 2;
                break;
            case 'left':
                top = triggerRect.top + (triggerRect.height - tooltipRect.height) / 2;
                left = triggerRect.left - tooltipRect.width - 8;
                break;
            case 'right':
                top = triggerRect.top + (triggerRect.height - tooltipRect.height) / 2;
                left = triggerRect.right + 8;
                break;
        }
        
        tooltip.style.top = `${top + window.scrollY}px`;
        tooltip.style.left = `${left + window.scrollX}px`;
    }

    // ===== MODALS =====
    setupModals() {
        const modalTriggers = document.querySelectorAll('[data-modal-target]');
        const modals = document.querySelectorAll('.modal');
        
        modalTriggers.forEach(trigger => {
            trigger.addEventListener('click', (e) => {
                e.preventDefault();
                const targetId = trigger.getAttribute('data-modal-target');
                const modal = document.getElementById(targetId);
                if (modal) {
                    this.openModal(modal);
                }
            });
        });
        
        modals.forEach(modal => {
            // Close button
            const closeBtn = modal.querySelector('.modal-close, [data-modal-close]');
            if (closeBtn) {
                closeBtn.addEventListener('click', () => this.closeModal(modal));
            }
            
            // Backdrop click
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.closeModal(modal);
                }
            });
        });
        
        // ESC key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                const openModal = document.querySelector('.modal.show');
                if (openModal) {
                    this.closeModal(openModal);
                }
            }
        });
    }

    openModal(modal) {
        modal.classList.add('show');
        document.body.classList.add('modal-open');
        
        // Focus management
        const focusableElements = modal.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusableElements.length > 0) {
            focusableElements[0].focus();
        }
        
        this.dispatchEvent('modalOpened', { modal });
    }

    closeModal(modal) {
        modal.classList.remove('show');
        document.body.classList.remove('modal-open');
        
        this.dispatchEvent('modalClosed', { modal });
    }

    // ===== DROPDOWNS =====
    setupDropdowns() {
        const dropdownTriggers = document.querySelectorAll('[data-dropdown-toggle]');
        
        dropdownTriggers.forEach(trigger => {
            trigger.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                
                const targetId = trigger.getAttribute('data-dropdown-toggle');
                const dropdown = document.getElementById(targetId);
                
                if (dropdown) {
                    this.toggleDropdown(dropdown);
                }
            });
        });
        
        // Close dropdowns when clicking outside
        document.addEventListener('click', () => {
            const openDropdowns = document.querySelectorAll('.dropdown.show');
            openDropdowns.forEach(dropdown => {
                dropdown.classList.remove('show');
            });
        });
    }

    toggleDropdown(dropdown) {
        const isOpen = dropdown.classList.contains('show');
        
        // Close all other dropdowns
        const allDropdowns = document.querySelectorAll('.dropdown.show');
        allDropdowns.forEach(d => d.classList.remove('show'));
        
        if (!isOpen) {
            dropdown.classList.add('show');
            this.positionDropdown(dropdown);
        }
    }

    positionDropdown(dropdown) {
        const trigger = document.querySelector(`[data-dropdown-toggle="${dropdown.id}"]`);
        if (!trigger) return;
        
        const triggerRect = trigger.getBoundingClientRect();
        const dropdownRect = dropdown.getBoundingClientRect();
        
        // Check if dropdown fits below trigger
        const spaceBelow = window.innerHeight - triggerRect.bottom;
        const spaceAbove = triggerRect.top;
        
        if (spaceBelow < dropdownRect.height && spaceAbove > dropdownRect.height) {
            dropdown.classList.add('dropdown-up');
        } else {
            dropdown.classList.remove('dropdown-up');
        }
    }

    // ===== TABS =====
    setupTabs() {
        const tabGroups = document.querySelectorAll('.tab-group');
        
        tabGroups.forEach(group => {
            const tabs = group.querySelectorAll('.tab');
            const panels = group.querySelectorAll('.tab-panel');
            
            tabs.forEach((tab, index) => {
                tab.addEventListener('click', (e) => {
                    e.preventDefault();
                    this.switchTab(tabs, panels, index);
                });
            });
        });
    }

    switchTab(tabs, panels, activeIndex) {
        // Remove active class from all tabs and panels
        tabs.forEach(tab => tab.classList.remove('active'));
        panels.forEach(panel => {
            panel.classList.remove('active');
            panel.style.opacity = '0';
        });
        
        // Add active class to selected tab
        tabs[activeIndex].classList.add('active');
        
        // Show selected panel with animation
        setTimeout(() => {
            panels[activeIndex].classList.add('active');
            panels[activeIndex].style.opacity = '1';
        }, 150);
        
        this.dispatchEvent('tabChanged', { index: activeIndex });
    }

    // ===== ACCORDIONS =====
    setupAccordions() {
        const accordionTriggers = document.querySelectorAll('.accordion-trigger');
        
        accordionTriggers.forEach(trigger => {
            trigger.addEventListener('click', () => {
                this.toggleAccordion(trigger);
            });
        });
    }

    toggleAccordion(trigger) {
        const accordion = trigger.closest('.accordion-item');
        const content = accordion.querySelector('.accordion-content');
        const isOpen = accordion.classList.contains('open');
        
        if (isOpen) {
            content.style.maxHeight = '0';
            accordion.classList.remove('open');
        } else {
            content.style.maxHeight = content.scrollHeight + 'px';
            accordion.classList.add('open');
        }
        
        // Update icon
        const icon = trigger.querySelector('.accordion-icon');
        if (icon) {
            icon.style.transform = isOpen ? 'rotate(0deg)' : 'rotate(180deg)';
        }
    }

    // ===== LOADING STATES =====
    setupLoadingStates() {
        // Auto-setup for forms
        const forms = document.querySelectorAll('form[data-loading]');
        
        forms.forEach(form => {
            form.addEventListener('submit', (e) => {
                const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
                if (submitBtn) {
                    this.setLoadingState(submitBtn, true);
                }
            });
        });
    }

    setLoadingState(element, isLoading) {
        if (isLoading) {
            element.disabled = true;
            element.classList.add('loading');
            
            // Store original content
            if (!element.hasAttribute('data-original-content')) {
                element.setAttribute('data-original-content', element.innerHTML);
            }
            
            // Add spinner
            element.innerHTML = '<i class="fas fa-spinner animate-spin"></i> Loading...';
        } else {
            element.disabled = false;
            element.classList.remove('loading');
            
            // Restore original content
            const originalContent = element.getAttribute('data-original-content');
            if (originalContent) {
                element.innerHTML = originalContent;
            }
        }
    }

    // ===== NOTIFICATIONS =====
    setupNotifications() {
        // Create notification container if it doesn't exist
        if (!document.getElementById('notification-container')) {
            const container = document.createElement('div');
            container.id = 'notification-container';
            container.className = 'notification-container';
            document.body.appendChild(container);
        }
    }

    showNotification(message, type = 'info', duration = 5000) {
        const container = document.getElementById('notification-container');
        const notification = document.createElement('div');
        
        notification.className = `notification notification-${type} animate-slideIn`;
        notification.innerHTML = `
            <div class="notification-content">
                <i class="notification-icon fas ${this.getNotificationIcon(type)}"></i>
                <span class="notification-message">${message}</span>
                <button class="notification-close" type="button">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;
        
        // Add to container
        container.appendChild(notification);
        
        // Close button
        const closeBtn = notification.querySelector('.notification-close');
        closeBtn.addEventListener('click', () => {
            this.closeNotification(notification);
        });
        
        // Auto close
        if (duration > 0) {
            setTimeout(() => {
                this.closeNotification(notification);
            }, duration);
        }
        
        return notification;
    }

    closeNotification(notification) {
        notification.style.animation = 'slideOut 0.3s ease-out forwards';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }

    getNotificationIcon(type) {
        const icons = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        };
        return icons[type] || icons.info;
    }

    // ===== UTILITY METHODS =====
    setupEventListeners() {
        // Window resize
        window.addEventListener('resize', this.debounce(() => {
            this.handleResize();
        }, 250));
        
        // Scroll events
        window.addEventListener('scroll', this.throttle(() => {
            this.handleScroll();
        }, 16));
    }

    handleResize() {
        // Reposition dropdowns and tooltips
        const openDropdowns = document.querySelectorAll('.dropdown.show');
        openDropdowns.forEach(dropdown => {
            this.positionDropdown(dropdown);
        });
        
        this.dispatchEvent('windowResized');
    }

    handleScroll() {
        // Update scroll-based animations
        this.dispatchEvent('windowScrolled');
    }

    loadPreferences() {
        // Load theme preference
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme) {
            document.documentElement.setAttribute('data-theme', savedTheme);
            this.updateThemeToggle();
        }
        
        // Load other preferences
        const preferences = JSON.parse(localStorage.getItem('ui-preferences') || '{}');
        this.applyPreferences(preferences);
    }

    savePreference(key, value) {
        const preferences = JSON.parse(localStorage.getItem('ui-preferences') || '{}');
        preferences[key] = value;
        localStorage.setItem('ui-preferences', JSON.stringify(preferences));
    }

    applyPreferences(preferences) {
        // Apply saved UI preferences
        Object.keys(preferences).forEach(key => {
            this.dispatchEvent('preferenceApplied', { key, value: preferences[key] });
        });
    }

    // ===== HELPER METHODS =====
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    throttle(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }

    dispatchEvent(eventName, detail = {}) {
        const event = new CustomEvent(`ui:${eventName}`, { detail });
        document.dispatchEvent(event);
    }

    // ===== PUBLIC API =====
    // Methods that can be called from outside
    static getInstance() {
        if (!InteractiveComponents.instance) {
            InteractiveComponents.instance = new InteractiveComponents();
        }
        return InteractiveComponents.instance;
    }
}

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.UI = InteractiveComponents.getInstance();
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = InteractiveComponents;
}