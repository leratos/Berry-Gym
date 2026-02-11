/**
 * HomeGym Keyboard Shortcuts
 * Global shortcuts for improved productivity
 */

class KeyboardShortcuts {
    constructor() {
        this.init();
    }

    init() {
        document.addEventListener('keydown', (e) => {
            // ESC - Close all modals
            if (e.key === 'Escape') {
                this.closeActiveModal();
            }

            // ENTER - Submit active modal form (if no textarea focused)
            if (e.key === 'Enter' && !e.shiftKey) {
                const activeElement = document.activeElement;

                // Skip if typing in textarea
                if (activeElement.tagName === 'TEXTAREA') {
                    return;
                }

                // Check if we're in a modal
                const activeModal = document.querySelector('.modal.show');
                if (activeModal) {
                    e.preventDefault();
                    this.submitActiveModalForm(activeModal);
                }
            }

            // Shortcuts nur wenn kein Input/Textarea fokussiert ist
            const activeElement = document.activeElement;
            const isTyping = ['INPUT', 'TEXTAREA', 'SELECT'].includes(activeElement.tagName);

            if (isTyping) return;

            // S - Add Satz (nur im Training)
            if (e.key.toLowerCase() === 's' && document.querySelector('[data-context="training"]')) {
                e.preventDefault();
                this.openAddSatzModal();
            }

            // N - New Training (nur auf Dashboard)
            if (e.key.toLowerCase() === 'n' && document.querySelector('[data-context="dashboard"]')) {
                e.preventDefault();
                window.location.href = '/training/select-plan/';
            }

            // P - Show all Plans
            if (e.key.toLowerCase() === 'p' && !e.ctrlKey && !e.metaKey) {
                const planBtn = document.querySelector('a[href*="training/select-plan"]');
                if (planBtn && !isTyping) {
                    e.preventDefault();
                    planBtn.click();
                }
            }

            // ? - Show shortcut help
            if (e.key === '?' && !e.shiftKey) {
                e.preventDefault();
                this.showShortcutHelp();
            }
        });
    }

    closeActiveModal() {
        const activeModal = document.querySelector('.modal.show');
        if (activeModal) {
            const bsModal = bootstrap.Modal.getInstance(activeModal);
            if (bsModal) {
                bsModal.hide();
            }
        }
    }

    submitActiveModalForm(modal) {
        const form = modal.querySelector('form');
        if (form) {
            const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
            if (submitBtn && !submitBtn.disabled) {
                submitBtn.click();
            }
        }
    }

    openAddSatzModal() {
        const addSatzBtn = document.querySelector('[data-bs-target="#addSetModal"]');
        if (addSatzBtn) {
            addSatzBtn.click();
        }
    }

    showShortcutHelp() {
        // Check if help modal already exists
        if (document.getElementById('shortcutHelpModal')) {
            const modal = new bootstrap.Modal(document.getElementById('shortcutHelpModal'));
            modal.show();
            return;
        }

        // Create help modal
        const modalHTML = `
            <div class="modal fade" id="shortcutHelpModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header bg-dark border-secondary">
                            <h5 class="modal-title">
                                <i class="bi bi-keyboard me-2"></i>Tastatur-Shortcuts
                            </h5>
                            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body bg-dark">
                            <div class="row g-3">
                                <div class="col-12">
                                    <h6 class="text-primary mb-2">
                                        <i class="bi bi-universal-access me-2"></i>Universell
                                    </h6>
                                    <table class="table table-sm table-dark table-hover">
                                        <tbody>
                                            <tr>
                                                <td><kbd>Esc</kbd></td>
                                                <td>Modal schließen</td>
                                            </tr>
                                            <tr>
                                                <td><kbd>Enter</kbd></td>
                                                <td>Modal-Formular absenden</td>
                                            </tr>
                                            <tr>
                                                <td><kbd>?</kbd></td>
                                                <td>Diese Hilfe anzeigen</td>
                                            </tr>
                                        </tbody>
                                    </table>
                                </div>

                                <div class="col-12">
                                    <h6 class="text-success mb-2">
                                        <i class="bi bi-dumbbell me-2"></i>Training
                                    </h6>
                                    <table class="table table-sm table-dark table-hover">
                                        <tbody>
                                            <tr>
                                                <td><kbd>S</kbd></td>
                                                <td>Satz hinzufügen</td>
                                            </tr>
                                            <tr>
                                                <td><kbd>N</kbd></td>
                                                <td>Neues Training starten</td>
                                            </tr>
                                            <tr>
                                                <td><kbd>P</kbd></td>
                                                <td>Plan auswählen</td>
                                            </tr>
                                        </tbody>
                                    </table>
                                </div>
                            </div>

                            <div class="alert alert-info mt-3 mb-0">
                                <i class="bi bi-info-circle me-2"></i>
                                <small>Shortcuts funktionieren nicht während du in ein Textfeld tippst.</small>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHTML);
        const modal = new bootstrap.Modal(document.getElementById('shortcutHelpModal'));
        modal.show();
    }
}

// Initialize keyboard shortcuts globally
document.addEventListener('DOMContentLoaded', () => {
    new KeyboardShortcuts();
    console.log('⌨️ Keyboard Shortcuts aktiv - Drücke "?" für Hilfe');
});
