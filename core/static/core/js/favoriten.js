/**
 * Favoriten-Toggle Funktionalität
 * Handhabt Hinzufügen/Entfernen von Übungen zu Favoriten
 */

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function toggleFavorit(uebungId, buttonElement) {
    const csrftoken = getCookie('csrftoken');
    const icon = buttonElement.querySelector('i');
    
    // Optimistic UI: Icon sofort aktualisieren
    const wasFavorit = icon.classList.contains('bi-star-fill');
    icon.classList.toggle('bi-star-fill');
    icon.classList.toggle('bi-star');
    
    fetch(`/uebung/${uebungId}/toggle-favorit/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrftoken,
            'Content-Type': 'application/json'
        },
        credentials: 'same-origin'
    })
    .then(response => response.json())
    .then(data => {
        // Toast-Benachrichtigung (falls vorhanden)
        if (typeof toast !== 'undefined') {
            if (data.is_favorit) {
                toast.success(data.message);
            } else {
                toast.info(data.message);
            }
        }
        
        // Sicherstellen dass Icon mit Server-Status synchron ist
        if (data.is_favorit) {
            icon.classList.remove('bi-star');
            icon.classList.add('bi-star-fill');
            buttonElement.classList.add('active');
        } else {
            icon.classList.remove('bi-star-fill');
            icon.classList.add('bi-star');
            buttonElement.classList.remove('active');
        }
        
        // Event für Filter-Update (falls Favoriten-Filter aktiv)
        const filterEvent = new CustomEvent('favoritChanged', { 
            detail: { uebungId, isFavorit: data.is_favorit }
        });
        document.dispatchEvent(filterEvent);
    })
    .catch(error => {
        console.error('Fehler beim Toggle Favorit:', error);
        // Bei Fehler Icon zurücksetzen
        icon.classList.toggle('bi-star-fill');
        icon.classList.toggle('bi-star');
        
        if (typeof toast !== 'undefined') {
            toast.error('Fehler beim Aktualisieren der Favoriten');
        }
    });
}

// Favoriten-Filter in Übungsliste
function setupFavoritenFilter() {
    const filterCheckbox = document.getElementById('favoritenFilter');
    if (!filterCheckbox) return;
    
    filterCheckbox.addEventListener('change', function() {
        const showOnlyFavorites = this.checked;
        const exerciseCards = document.querySelectorAll('.exercise-item');
        
        exerciseCards.forEach(card => {
            const favButton = card.querySelector('.favorit-btn');
            if (!favButton) return;
            
            const isFavorit = favButton.querySelector('i').classList.contains('bi-star-fill');
            
            if (showOnlyFavorites && !isFavorit) {
                card.style.display = 'none';
            } else {
                card.style.display = '';
            }
        });
        
        // Muskelgruppen-Sektionen ohne sichtbare Übungen ausblenden
        document.querySelectorAll('.muscle-group-section').forEach(section => {
            const visibleCards = section.querySelectorAll('.exercise-item:not([style*="display: none"])');
            section.style.display = visibleCards.length > 0 ? '' : 'none';
        });
    });
}

// Favorit-Status nach Filter-Update aktualisieren
document.addEventListener('favoritChanged', function(e) {
    const filterCheckbox = document.getElementById('favoritenFilter');
    if (filterCheckbox && filterCheckbox.checked) {
        // Re-apply filter wenn aktiv
        filterCheckbox.dispatchEvent(new Event('change'));
    }
});

// Setup bei Seitenladung
document.addEventListener('DOMContentLoaded', setupFavoritenFilter);
