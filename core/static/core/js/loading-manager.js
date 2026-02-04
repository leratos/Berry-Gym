/**
 * Loading State Manager
 * Zeigt/versteckt Spinner und deaktiviert Buttons während API-Calls
 */

class LoadingManager {
    constructor() {
        this.activeRequests = new Set();
        this.injectCSS();
    }

    /**
     * Injiziert CSS-Styles für Spinner
     */
    injectCSS() {
        if (document.getElementById('loading-manager-styles')) return;
        
        const style = document.createElement('style');
        style.id = 'loading-manager-styles';
        style.textContent = `
            .loading-spinner {
                display: inline-block;
                width: 20px;
                height: 20px;
                border: 3px solid rgba(255, 255, 255, 0.3);
                border-radius: 50%;
                border-top-color: #fff;
                animation: spin 1s ease-in-out infinite;
            }
            
            .loading-spinner-sm {
                width: 16px;
                height: 16px;
                border-width: 2px;
            }
            
            .loading-spinner-lg {
                width: 32px;
                height: 32px;
                border-width: 4px;
            }
            
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
            
            .loading-overlay {
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.5);
                display: flex;
                align-items: center;
                justify-content: center;
                border-radius: inherit;
                z-index: 1000;
            }
            
            .loading-overlay-spinner {
                width: 40px;
                height: 40px;
                border: 4px solid rgba(255, 255, 255, 0.3);
                border-radius: 50%;
                border-top-color: #0dcaf0;
                animation: spin 1s ease-in-out infinite;
            }
            
            .btn-loading {
                position: relative;
                pointer-events: none;
                opacity: 0.7;
            }
            
            .btn-loading .btn-text {
                visibility: hidden;
            }
            
            .btn-loading::after {
                content: "";
                position: absolute;
                width: 16px;
                height: 16px;
                top: 50%;
                left: 50%;
                margin-left: -8px;
                margin-top: -8px;
                border: 2px solid rgba(255, 255, 255, 0.3);
                border-radius: 50%;
                border-top-color: #fff;
                animation: spin 1s ease-in-out infinite;
            }
        `;
        document.head.appendChild(style);
    }

    /**
     * Startet Loading State für Button
     * @param {HTMLElement} button - Button Element
     * @param {string} requestId - Eindeutige ID für diesen Request
     */
    startButton(button, requestId = Date.now().toString()) {
        if (!button) return;
        
        this.activeRequests.add(requestId);
        button.disabled = true;
        button.classList.add('btn-loading');
        
        // Original-Text speichern
        if (!button.dataset.originalText) {
            button.dataset.originalText = button.innerHTML;
        }
        
        return requestId;
    }

    /**
     * Stoppt Loading State für Button
     * @param {HTMLElement} button - Button Element
     * @param {string} requestId - Request ID
     */
    stopButton(button, requestId) {
        if (!button) return;
        
        this.activeRequests.delete(requestId);
        button.disabled = false;
        button.classList.remove('btn-loading');
        
        // Original-Text wiederherstellen
        if (button.dataset.originalText) {
            button.innerHTML = button.dataset.originalText;
        }
    }

    /**
     * Zeigt Overlay-Spinner über Element
     * @param {HTMLElement} element - Container Element
     * @param {string} requestId - Eindeutige ID
     * @returns {string} requestId
     */
    startOverlay(element, requestId = Date.now().toString()) {
        if (!element) return requestId;
        
        this.activeRequests.add(requestId);
        
        // Relative Positionierung für Overlay
        const originalPosition = window.getComputedStyle(element).position;
        if (originalPosition === 'static') {
            element.style.position = 'relative';
            element.dataset.originalPosition = 'static';
        }
        
        // Overlay erstellen
        const overlay = document.createElement('div');
        overlay.className = 'loading-overlay';
        overlay.dataset.requestId = requestId;
        overlay.innerHTML = '<div class="loading-overlay-spinner"></div>';
        element.appendChild(overlay);
        
        return requestId;
    }

    /**
     * Entfernt Overlay-Spinner
     * @param {HTMLElement} element - Container Element
     * @param {string} requestId - Request ID
     */
    stopOverlay(element, requestId) {
        if (!element) return;
        
        this.activeRequests.delete(requestId);
        
        const overlay = element.querySelector(`[data-request-id="${requestId}"]`);
        if (overlay) {
            overlay.remove();
        }
        
        // Original Position wiederherstellen
        if (element.dataset.originalPosition === 'static') {
            element.style.position = 'static';
            delete element.dataset.originalPosition;
        }
    }

    /**
     * Ändert Button-Text während Loading
     * @param {HTMLElement} button - Button Element
     * @param {string} loadingText - Text während Loading (z.B. "Laden...")
     * @param {string} requestId - Eindeutige ID
     * @returns {string} requestId
     */
    startButtonWithText(button, loadingText = 'Laden...', requestId = Date.now().toString()) {
        if (!button) return requestId;
        
        this.activeRequests.add(requestId);
        button.disabled = true;
        
        // Original-Text speichern
        if (!button.dataset.originalText) {
            button.dataset.originalText = button.innerHTML;
        }
        
        button.innerHTML = `
            <span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
            ${loadingText}
        `;
        
        return requestId;
    }

    /**
     * Wrapper für fetch mit automatischem Loading State
     * @param {string} url - URL
     * @param {object} options - Fetch options
     * @param {HTMLElement} button - Optional: Button für Loading State
     * @param {string} loadingText - Optional: Loading Text
     * @returns {Promise}
     */
    async fetch(url, options = {}, button = null, loadingText = null) {
        const requestId = Date.now().toString();
        
        try {
            // Button Loading State
            if (button) {
                if (loadingText) {
                    this.startButtonWithText(button, loadingText, requestId);
                } else {
                    this.startButton(button, requestId);
                }
            }
            
            const response = await fetch(url, options);
            
            // Button zurücksetzen
            if (button) {
                this.stopButton(button, requestId);
            }
            
            return response;
        } catch (error) {
            // Button zurücksetzen bei Fehler
            if (button) {
                this.stopButton(button, requestId);
            }
            throw error;
        }
    }

    /**
     * Prüft ob aktuell Requests aktiv sind
     * @returns {boolean}
     */
    isLoading() {
        return this.activeRequests.size > 0;
    }

    /**
     * Stoppt alle aktiven Loading States (Notfall-Reset)
     */
    resetAll() {
        // Alle Overlays entfernen
        document.querySelectorAll('.loading-overlay').forEach(overlay => overlay.remove());
        
        // Alle Buttons zurücksetzen
        document.querySelectorAll('.btn-loading').forEach(button => {
            button.disabled = false;
            button.classList.remove('btn-loading');
            if (button.dataset.originalText) {
                button.innerHTML = button.dataset.originalText;
            }
        });
        
        this.activeRequests.clear();
    }
}

// Globale Instanz
window.loadingManager = new LoadingManager();

// Export für ES6 Module
if (typeof module !== 'undefined' && module.exports) {
    module.exports = LoadingManager;
}
