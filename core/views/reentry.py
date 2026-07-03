"""View für die Wiedereinstiegs-Empfehlung nach einer Trainingspause (Phase 33.3).

Reine Anzeige (`@login_required`, user-scoped). Die gesamte Logik liegt in
`core/utils/reentry.py`; hier wird nur gerendert. Kein Schreibpfad.
"""

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from ..utils.reentry import build_reentry_recommendation


@login_required
def reentry_detail(request: HttpRequest) -> HttpResponse:
    """Detailseite: Einstiegsgewichts-Empfehlung + Rampe pro Übung.

    `empfehlung` ist None, wenn aktuell keine frische, qualifizierende Pause
    vorliegt – das Template zeigt dann einen neutralen Hinweis.
    """
    empfehlung = build_reentry_recommendation(request.user)
    return render(request, "core/reentry.html", {"empfehlung": empfehlung})
