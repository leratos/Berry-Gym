"""
View für die wissenschaftliche Quellen-Seite (/quellen/).

Öffentlich zugänglich (kein Login erforderlich).
Zeigt alle aktiven Quellen, filterbar nach Kategorie.
"""

from django.shortcuts import render

from core.models import TrainingSource


def sources_list(request):
    """
    Öffentliche Literaturliste aller wissenschaftlichen Quellen.

    GET-Parameter:
        category: Filtert nach Kategorie (z.B. ?category=VOLUME)
    """
    selected_category = request.GET.get("category", "")

    quellen = TrainingSource.objects.filter(is_active=True)
    if selected_category:
        quellen = quellen.filter(category=selected_category)

    # Kategorien mit Anzahl für Tab-Navigation
    from django.db.models import Count

    kategorie_counts = (
        TrainingSource.objects.filter(is_active=True)
        .values("category")
        .annotate(count=Count("id"))
        .order_by("category")
    )

    # Category-Labels für Anzeige
    category_labels = dict(TrainingSource.CATEGORY_CHOICES)
    kategorien = [
        {
            "key": item["category"],
            "label": category_labels.get(item["category"], item["category"]),
            "count": item["count"],
            "active": item["category"] == selected_category,
        }
        for item in kategorie_counts
    ]

    context = {
        "quellen": quellen,
        "kategorien": kategorien,
        "selected_category": selected_category,
        "selected_label": category_labels.get(selected_category, "Alle Quellen"),
        "gesamt_count": TrainingSource.objects.filter(is_active=True).count(),
    }
    return render(request, "core/sources.html", context)
