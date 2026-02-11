"""
Custom context processors for HomeGym templates.
"""

from datetime import datetime

from core.models_disclaimer import ScientificDisclaimer


def global_context(request):
    """
    Adds global context variables available in all templates.
    """
    return {
        "current_year": datetime.now().year,
    }


def disclaimers(request):
    """
    Adds active scientific disclaimers to template context.

    Disclaimers are shown based on:
    - is_active=True
    - URL pattern matches (show_on_pages field)
    - If show_on_pages is empty, disclaimer is shown globally

    Example:
        - Disclaimer with show_on_pages=["stats/"] shows on /stats/xyz
        - Disclaimer with show_on_pages=[] shows on all pages
    """
    # Get current URL path
    current_path = request.path

    # Get all active disclaimers
    all_disclaimers = ScientificDisclaimer.objects.filter(is_active=True)

    # Filter by URL pattern
    matching_disclaimers = []
    for disclaimer in all_disclaimers:
        # If no specific pages set, show globally
        if not disclaimer.show_on_pages:
            matching_disclaimers.append(disclaimer)
            continue

        # Check if current path matches any pattern
        for pattern in disclaimer.show_on_pages:
            if pattern in current_path:
                matching_disclaimers.append(disclaimer)
                break

    return {
        "active_disclaimers": matching_disclaimers,
    }
