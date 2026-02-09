/**
 * Autocomplete / Typeahead für Übungssuche
 * Fuzzy matching, Tastatur-Navigation, schnelle Suche
 */

class ExerciseAutocomplete {
    constructor(inputElement, exercises, options = {}) {
        this.input = inputElement;
        this.exercises = exercises;
        this.options = {
            minChars: 2,
            maxResults: 8,
            onSelect: options.onSelect || null,
            fuzzyMatch: options.fuzzyMatch !== false,
            highlightMatch: options.highlightMatch !== false
        };

        this.selectedIndex = -1;
        this.results = [];
        this.dropdown = null;

        this.init();
    }

    init() {
        // Dropdown erstellen
        this.dropdown = document.createElement('div');
        this.dropdown.className = 'autocomplete-dropdown';
        this.dropdown.style.display = 'none';
        this.input.parentElement.style.position = 'relative';
        this.input.parentElement.appendChild(this.dropdown);

        // Event Listeners
        this.input.addEventListener('input', this.handleInput.bind(this));
        this.input.addEventListener('keydown', this.handleKeydown.bind(this));
        this.input.addEventListener('blur', () => {
            // Verzögert schließen damit Click-Events noch funktionieren
            setTimeout(() => this.hide(), 200);
        });

        // CSS injizieren
        this.injectCSS();
    }

    handleInput(e) {
        const query = e.target.value.trim();

        if (query.length < this.options.minChars) {
            this.hide();
            return;
        }

        this.search(query);
    }

    search(query) {
        const lowerQuery = query.toLowerCase();

        // Filtere und score Übungen
        this.results = this.exercises
            .map(exercise => {
                const name = exercise.name.toLowerCase();
                const muscle = (exercise.muscle || '').toLowerCase();

                let score = 0;
                let matchType = null;

                // Exakter Match (höchste Priorität)
                if (name === lowerQuery) {
                    score = 1000;
                    matchType = 'exact';
                }
                // Starts with
                else if (name.startsWith(lowerQuery)) {
                    score = 500;
                    matchType = 'starts';
                }
                // Contains
                else if (name.includes(lowerQuery)) {
                    score = 250;
                    matchType = 'contains';
                }
                // Fuzzy match
                else if (this.options.fuzzyMatch && this.fuzzyMatch(lowerQuery, name)) {
                    score = 100;
                    matchType = 'fuzzy';
                }
                // Muskelgruppe match
                else if (muscle.includes(lowerQuery)) {
                    score = 50;
                    matchType = 'muscle';
                }

                if (score > 0) {
                    return { ...exercise, score, matchType };
                }
                return null;
            })
            .filter(Boolean)
            .sort((a, b) => b.score - a.score)
            .slice(0, this.options.maxResults);

        if (this.results.length > 0) {
            this.show(query);
        } else {
            this.hide();
        }
    }

    fuzzyMatch(pattern, text) {
        let patternIdx = 0;
        let textIdx = 0;

        while (patternIdx < pattern.length && textIdx < text.length) {
            if (pattern[patternIdx] === text[textIdx]) {
                patternIdx++;
            }
            textIdx++;
        }

        return patternIdx === pattern.length;
    }

    show(query) {
        this.selectedIndex = -1;
        const lowerQuery = query.toLowerCase();

        let html = '';
        this.results.forEach((result, index) => {
            const highlightedName = this.options.highlightMatch
                ? this.highlightText(result.name, lowerQuery)
                : result.name;

            const muscleTag = result.muscle ? `<small class="text-muted ms-2">${result.muscle}</small>` : '';

            html += `
                <div class="autocomplete-item" data-index="${index}">
                    <div class="d-flex align-items-center">
                        <i class="bi bi-search me-2 text-secondary"></i>
                        <div class="flex-grow-1">
                            ${highlightedName}
                            ${muscleTag}
                        </div>
                        ${result.matchType === 'muscle' ? '<span class="badge bg-secondary">Muskelgruppe</span>' : ''}
                    </div>
                </div>
            `;
        });

        if (this.results.length === 0) {
            html = '<div class="autocomplete-item text-muted">Keine Übungen gefunden</div>';
        }

        this.dropdown.innerHTML = html;
        this.dropdown.style.display = 'block';

        // Click Events
        this.dropdown.querySelectorAll('.autocomplete-item').forEach((item, index) => {
            item.addEventListener('click', () => this.select(index));
        });
    }

    hide() {
        this.dropdown.style.display = 'none';
        this.selectedIndex = -1;
    }

    highlightText(text, query) {
        const regex = new RegExp(`(${this.escapeRegex(query)})`, 'gi');
        return text.replace(regex, '<strong class="text-info">$1</strong>');
    }

    escapeRegex(str) {
        return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    handleKeydown(e) {
        if (this.dropdown.style.display === 'none' || this.results.length === 0) return;

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                this.selectedIndex = Math.min(this.selectedIndex + 1, this.results.length - 1);
                this.updateSelection();
                break;

            case 'ArrowUp':
                e.preventDefault();
                this.selectedIndex = Math.max(this.selectedIndex - 1, -1);
                this.updateSelection();
                break;

            case 'Enter':
                e.preventDefault();
                if (this.selectedIndex >= 0) {
                    this.select(this.selectedIndex);
                }
                break;

            case 'Escape':
                this.hide();
                break;
        }
    }

    updateSelection() {
        this.dropdown.querySelectorAll('.autocomplete-item').forEach((item, index) => {
            if (index === this.selectedIndex) {
                item.classList.add('active');
                item.scrollIntoView({ block: 'nearest' });
            } else {
                item.classList.remove('active');
            }
        });
    }

    select(index) {
        if (index < 0 || index >= this.results.length) return;

        const selected = this.results[index];
        this.input.value = selected.name;
        this.hide();

        if (this.options.onSelect) {
            this.options.onSelect(selected);
        }

        // Trigger input event für andere Listener
        this.input.dispatchEvent(new Event('input', { bubbles: true }));
    }

    injectCSS() {
        if (document.getElementById('autocomplete-styles')) return;

        const style = document.createElement('style');
        style.id = 'autocomplete-styles';
        style.textContent = `
            .autocomplete-dropdown {
                position: absolute;
                top: 100%;
                left: 0;
                right: 0;
                max-height: 300px;
                overflow-y: auto;
                background: var(--bs-body-bg);
                border: 1px solid var(--bs-border-color);
                border-radius: 0.375rem;
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                z-index: 1050;
                margin-top: 0.25rem;
            }

            [data-bs-theme="dark"] .autocomplete-dropdown {
                background: #212529;
                border-color: #495057;
            }

            [data-bs-theme="light"] .autocomplete-dropdown {
                background: #ffffff;
                border-color: #dee2e6;
            }

            .autocomplete-item {
                padding: 0.75rem 1rem;
                cursor: pointer;
                transition: background-color 0.15s;
                border-bottom: 1px solid var(--bs-border-color);
            }

            .autocomplete-item:last-child {
                border-bottom: none;
            }

            .autocomplete-item:hover,
            .autocomplete-item.active {
                background: var(--bs-secondary-bg);
            }

            [data-bs-theme="dark"] .autocomplete-item:hover,
            [data-bs-theme="dark"] .autocomplete-item.active {
                background: #343a40;
            }

            [data-bs-theme="light"] .autocomplete-item:hover,
            [data-bs-theme="light"] .autocomplete-item.active {
                background: #f8f9fa;
            }
        `;
        document.head.appendChild(style);
    }

    destroy() {
        if (this.dropdown) {
            this.dropdown.remove();
        }
    }
}

// Export für globale Nutzung
window.ExerciseAutocomplete = ExerciseAutocomplete;

// Export für ES6 Module
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ExerciseAutocomplete;
}
