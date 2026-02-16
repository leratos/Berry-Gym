"""
Template-Tags für wissenschaftliche Quellen.

Verwendung:
    {% load source_tags %}
    {% source_tooltip "fatigue_index" %}
    {% source_tooltip "1rm_standards" label="Quelle" %}
"""

from django import template
from django.utils.html import format_html

from core.models import TrainingSource

register = template.Library()

# Cache: pro Request einmal laden, nicht pro Tag-Aufruf
_SOURCE_CACHE: dict = {}


def _get_sources_for_key(applies_to_key: str) -> list:
    """Holt aktive Quellen für einen applies_to-Schlüssel (in-memory gecacht).

    Filtert in Python statt per ORM, da SQLite JSONField__contains
    nicht unterstützt. Bei ~10-50 Quellen kein Performance-Problem.
    """
    if applies_to_key not in _SOURCE_CACHE:
        all_active = TrainingSource.objects.filter(is_active=True)
        _SOURCE_CACHE[applies_to_key] = [
            {
                "citation_short": s.citation_short,
                "doi_url": s.doi_url,
            }
            for s in all_active
            if applies_to_key in (s.applies_to or [])
        ][:3]
    return _SOURCE_CACHE[applies_to_key]


@register.simple_tag
def source_tooltip(applies_to_key: str, label: str = "") -> str:
    """
    Rendert ein ℹ-Icon mit Hover-Tooltip und Link zur Quellen-Seite.

    Args:
        applies_to_key: z.B. "fatigue_index", "1rm_standards", "rpe_quality"
        label: Optionaler Text neben dem Icon (Standard: leer)

    Beispiel:
        {% source_tooltip "fatigue_index" %}
        {% source_tooltip "1rm_standards" label="Quelle" %}
    """
    sources = _get_sources_for_key(applies_to_key)

    if not sources:
        return ""

    # Tooltip-Text aufbauen
    citations = " | ".join(s.get("citation_short", "") for s in sources if s.get("citation_short"))
    tooltip_text = f"Quellen: {citations}"

    icon_html = format_html(
        '<a href="/quellen/?category=" '
        '   class="source-tooltip-link" '
        '   title="{tooltip}" '
        '   aria-label="Wissenschaftliche Quellen ansehen" '
        '   data-bs-toggle="tooltip" '
        '   data-bs-placement="top">'
        '  {label}<span class="source-tooltip-icon">ℹ️</span>'
        "</a>",
        tooltip=tooltip_text,
        label=f"{label} " if label else "",
    )
    return icon_html


@register.simple_tag
def sources_count() -> int:
    """Gibt die Anzahl aktiver Quellen zurück."""
    return TrainingSource.objects.filter(is_active=True).count()
