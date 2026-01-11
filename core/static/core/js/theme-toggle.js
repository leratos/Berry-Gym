// Global Theme Toggle System for HomeGym App
// Lädt Theme vor Render, verhindert Flash

// Theme VOR dem Render laden (FOUC vermeiden)
(function() {
    const theme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-bs-theme', theme);
})();

// Theme Toggle Funktion
function toggleTheme() {
    const html = document.documentElement;
    const currentTheme = html.getAttribute('data-bs-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    html.setAttribute('data-bs-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeIcon(newTheme);
}

// Theme Icon Update
function updateThemeIcon(theme) {
    const icon = document.getElementById('themeIcon');
    if (!icon) return; // Kein Icon vorhanden
    
    if (theme === 'dark') {
        icon.className = 'bi bi-moon-fill';
    } else {
        icon.className = 'bi bi-sun-fill';
    }
}

// Theme Icon beim Laden setzen
document.addEventListener('DOMContentLoaded', function() {
    const currentTheme = localStorage.getItem('theme') || 'dark';
    updateThemeIcon(currentTheme);
});
