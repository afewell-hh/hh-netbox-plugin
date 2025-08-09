/**
 * Responsive Enhancements for Hedgehog NetBox Plugin
 * Mobile-first interactive improvements while preserving desktop functionality
 */

(function() {
    'use strict';

    // Device detection and responsive utilities
    const ResponsiveEnhancer = {
        // Breakpoints matching our CSS
        breakpoints: {
            mobile: 767,
            tablet: 1199
        },

        // Get current viewport type
        getViewportType() {
            const width = window.innerWidth;
            if (width <= this.breakpoints.mobile) return 'mobile';
            if (width <= this.breakpoints.tablet) return 'tablet';
            return 'desktop';
        },

        // Check if device is mobile
        isMobile() {
            return this.getViewportType() === 'mobile';
        },

        // Check if device is tablet
        isTablet() {
            return this.getViewportType() === 'tablet';
        },

        // Check if touch device
        isTouchDevice() {
            return 'ontouchstart' in window || navigator.maxTouchPoints > 0;
        },

        // Initialize responsive enhancements
        init() {
            this.enhanceTouchInteractions();
            this.improveTableReadability();
            this.optimizeModals();
            this.enhanceProgressiveDisclosure();
            this.addSwipeGestures();
            this.setupOrientationHandling();
            this.optimizePerformance();
            
            // Re-run enhancements on resize
            window.addEventListener('resize', this.debounce(() => {
                this.handleViewportChange();
            }, 250));
        },

        // Enhance touch interactions for mobile
        enhanceTouchInteractions() {
            if (!this.isTouchDevice()) return;

            // Add touch feedback to buttons and interactive elements
            const touchElements = document.querySelectorAll('.btn, .quick-action-btn, .drift-action-btn, .section-toggle, .card[data-toggle]');
            
            touchElements.forEach(element => {
                // Add touch start feedback
                element.addEventListener('touchstart', () => {
                    element.classList.add('touch-active');
                }, { passive: true });

                // Remove feedback on touch end
                element.addEventListener('touchend', () => {
                    setTimeout(() => {
                        element.classList.remove('touch-active');
                    }, 150);
                }, { passive: true });

                // Handle touch cancel
                element.addEventListener('touchcancel', () => {
                    element.classList.remove('touch-active');
                }, { passive: true });
            });

            // Add touch-specific CSS
            if (!document.querySelector('#responsive-touch-styles')) {
                const touchStyles = document.createElement('style');
                touchStyles.id = 'responsive-touch-styles';
                touchStyles.textContent = `
                    .touch-active {
                        transform: scale(0.95) !important;
                        opacity: 0.8 !important;
                        transition: all 0.1s ease !important;
                    }
                    
                    /* Enhanced touch targets */
                    @media (max-width: 767px) {
                        .btn, .quick-action-btn, .drift-action-btn {
                            min-height: 48px !important;
                            min-width: 48px !important;
                            font-size: 16px !important; /* Prevent zoom on iOS */
                        }
                        
                        input, select, textarea {
                            font-size: 16px !important; /* Prevent zoom on iOS */
                        }
                    }
                `;
                document.head.appendChild(touchStyles);
            }
        },

        // Improve table readability on mobile
        improveTableReadability() {
            if (!this.isMobile()) return;

            const tables = document.querySelectorAll('.table');
            tables.forEach(table => {
                // Add mobile-friendly wrapper if not already present
                if (!table.closest('.table-responsive')) {
                    const wrapper = document.createElement('div');
                    wrapper.className = 'table-responsive';
                    table.parentNode.insertBefore(wrapper, table);
                    wrapper.appendChild(table);
                }

                // Add swipe hint for horizontal scroll
                this.addScrollHint(table.closest('.table-responsive'));
            });
        },

        // Add scroll hint for mobile tables
        addScrollHint(tableContainer) {
            if (!tableContainer || tableContainer.querySelector('.scroll-hint')) return;

            const hint = document.createElement('div');
            hint.className = 'scroll-hint';
            hint.innerHTML = '<i class="mdi mdi-gesture-swipe-horizontal"></i> Swipe to scroll';
            hint.style.cssText = `
                position: absolute;
                top: 10px;
                right: 10px;
                background: rgba(0,0,0,0.7);
                color: white;
                padding: 5px 10px;
                border-radius: 15px;
                font-size: 12px;
                z-index: 10;
                opacity: 0.8;
                transition: opacity 0.3s ease;
            `;

            tableContainer.style.position = 'relative';
            tableContainer.appendChild(hint);

            // Hide hint after first interaction
            let hasScrolled = false;
            tableContainer.addEventListener('scroll', () => {
                if (!hasScrolled) {
                    hasScrolled = true;
                    hint.style.opacity = '0';
                    setTimeout(() => hint.remove(), 300);
                }
            }, { passive: true });

            // Auto-hide hint after 3 seconds
            setTimeout(() => {
                if (hint.parentNode) {
                    hint.style.opacity = '0';
                    setTimeout(() => {
                        if (hint.parentNode) hint.remove();
                    }, 300);
                }
            }, 3000);
        },

        // Optimize modals for mobile
        optimizeModals() {
            const modals = document.querySelectorAll('.modal');
            modals.forEach(modal => {
                if (this.isMobile()) {
                    // Make modals full-screen on mobile
                    const modalDialog = modal.querySelector('.modal-dialog');
                    if (modalDialog && !modalDialog.classList.contains('modal-fullscreen-sm-down')) {
                        modalDialog.classList.add('modal-fullscreen-sm-down');
                    }
                }

                // Add swipe-to-dismiss on mobile
                if (this.isTouchDevice()) {
                    this.addSwipeToDismiss(modal);
                }
            });
        },

        // Add swipe to dismiss for modals
        addSwipeToDismiss(modal) {
            let startY = 0;
            let currentY = 0;
            let isDragging = false;

            const modalContent = modal.querySelector('.modal-content');
            if (!modalContent) return;

            modalContent.addEventListener('touchstart', (e) => {
                startY = e.touches[0].clientY;
                isDragging = true;
            }, { passive: true });

            modalContent.addEventListener('touchmove', (e) => {
                if (!isDragging) return;
                currentY = e.touches[0].clientY;
                const deltaY = currentY - startY;

                if (deltaY > 0) { // Only allow downward swipe
                    modalContent.style.transform = `translateY(${Math.min(deltaY, 200)}px)`;
                    modalContent.style.opacity = Math.max(1 - (deltaY / 300), 0.5);
                }
            }, { passive: true });

            modalContent.addEventListener('touchend', () => {
                if (!isDragging) return;
                isDragging = false;

                const deltaY = currentY - startY;
                if (deltaY > 100) { // Dismiss threshold
                    // Trigger modal dismiss
                    const bootstrapModal = bootstrap.Modal.getInstance(modal);
                    if (bootstrapModal) {
                        bootstrapModal.hide();
                    }
                } else {
                    // Reset position
                    modalContent.style.transform = '';
                    modalContent.style.opacity = '';
                }
            }, { passive: true });
        },

        // Enhance progressive disclosure for mobile
        enhanceProgressiveDisclosure() {
            const toggles = document.querySelectorAll('.section-toggle');
            toggles.forEach(toggle => {
                // Add keyboard support
                if (!toggle.hasAttribute('tabindex')) {
                    toggle.setAttribute('tabindex', '0');
                }

                // Add keyboard event listener
                toggle.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        toggle.click();
                    }
                });

                // Enhanced mobile interaction
                if (this.isMobile()) {
                    toggle.style.minHeight = '48px';
                    toggle.style.fontSize = '16px'; // Prevent iOS zoom
                }
            });
        },

        // Add swipe gestures for mobile navigation
        addSwipeGestures() {
            if (!this.isTouchDevice()) return;

            let startX = 0;
            let startY = 0;

            document.addEventListener('touchstart', (e) => {
                startX = e.touches[0].clientX;
                startY = e.touches[0].clientY;
            }, { passive: true });

            document.addEventListener('touchend', (e) => {
                const endX = e.changedTouches[0].clientX;
                const endY = e.changedTouches[0].clientY;
                const deltaX = endX - startX;
                const deltaY = endY - startY;

                // Only process horizontal swipes
                if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > 50) {
                    if (deltaX > 0) {
                        // Right swipe - could go back to fabric list
                        this.handleRightSwipe();
                    } else {
                        // Left swipe - could show additional options
                        this.handleLeftSwipe();
                    }
                }
            }, { passive: true });
        },

        // Handle right swipe (back navigation)
        handleRightSwipe() {
            const backButton = document.querySelector('a[href*="fabric_list"]');
            if (backButton && this.isMobile()) {
                // Add visual feedback
                backButton.classList.add('swipe-highlighted');
                setTimeout(() => {
                    backButton.classList.remove('swipe-highlighted');
                }, 300);
            }
        },

        // Handle left swipe (show options)
        handleLeftSwipe() {
            // Could implement a slide-out menu or quick actions panel
            console.log('Left swipe detected - implement additional mobile features');
        },

        // Setup orientation change handling
        setupOrientationHandling() {
            window.addEventListener('orientationchange', () => {
                // Delay to allow viewport to adjust
                setTimeout(() => {
                    this.handleViewportChange();
                }, 100);
            });
        },

        // Handle viewport changes
        handleViewportChange() {
            const currentType = this.getViewportType();
            
            // Re-initialize mobile-specific features
            if (currentType === 'mobile') {
                this.improveTableReadability();
            }
            
            // Dispatch custom event for other components
            window.dispatchEvent(new CustomEvent('responsiveViewportChange', {
                detail: { viewportType: currentType }
            }));
        },

        // Optimize performance for mobile
        optimizePerformance() {
            if (this.isMobile()) {
                // Reduce animation complexity on mobile
                const style = document.createElement('style');
                style.textContent = `
                    @media (max-width: 767px) {
                        * {
                            -webkit-transform: translateZ(0);
                            transform: translateZ(0);
                            -webkit-backface-visibility: hidden;
                            backface-visibility: hidden;
                        }
                        
                        .status-card, .drift-summary-card, .dashboard-section {
                            transition: transform 0.2s ease !important;
                        }
                    }
                `;
                document.head.appendChild(style);
            }
        },

        // Utility: Debounce function
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
        },

        // Add responsive utility classes dynamically
        addResponsiveClasses() {
            document.body.classList.add('responsive-enhanced');
            document.body.classList.add(`viewport-${this.getViewportType()}`);
            
            if (this.isTouchDevice()) {
                document.body.classList.add('touch-device');
            }
        }
    };

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            ResponsiveEnhancer.init();
            ResponsiveEnhancer.addResponsiveClasses();
        });
    } else {
        ResponsiveEnhancer.init();
        ResponsiveEnhancer.addResponsiveClasses();
    }

    // Make ResponsiveEnhancer globally available for debugging
    window.ResponsiveEnhancer = ResponsiveEnhancer;

    // Add swipe highlight style
    const swipeStyle = document.createElement('style');
    swipeStyle.textContent = `
        .swipe-highlighted {
            background-color: rgba(13, 110, 253, 0.1) !important;
            transform: scale(1.05) !important;
            transition: all 0.3s ease !important;
        }
    `;
    document.head.appendChild(swipeStyle);

})();