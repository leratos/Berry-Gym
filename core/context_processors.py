"""
Custom context processors for HomeGym templates.
"""
from datetime import datetime


def global_context(request):
    """
    Adds global context variables available in all templates.
    """
    return {
        'current_year': datetime.now().year,
    }
