"""Audit-Test für Phase 33.4 – Stagnations-Analyse pause-aware.

Reproduziert das Fehlverhalten (Vergleich über eine dokumentierte Pause hinweg)
und sichert den Fix ab: `_get_stagnation_empfehlung` darf Vor-Pause-Trainings
nicht mit Post-Pause-Trainings zu einer „Stagnations"-Kette verketten.

Kern-Szenario: 4 Trainings mit konstantem Gewicht VOR einer mehrwöchigen Pause
würden allein als Stagnation gelten. Nach der Pause liegen erst 2 Comeback-
Trainings – zu wenig für ein Stagnations-Urteil. Ohne den Fix würde die 6er-Kette
(4 vor + 2 nach) fälschlich als „kein Fortschritt in 6 Trainings" gelabelt.
"""

from datetime import datetime, timedelta

from django.utils import timezone

import pytest

from core.models import Satz, Trainingseinheit
from core.tests.factories import (
    SatzFactory,
    TrainingseinheitFactory,
    TrainingsPauseFactory,
    UebungFactory,
    UserFactory,
)
from core.views import ai_recommendations as ai_views


def _training_am(user, tage_vor_heute, uebung, gewicht, rpe="8.0"):
    when = timezone.localdate() - timedelta(days=tage_vor_heute)
    aware = timezone.make_aware(datetime(when.year, when.month, when.day, 12, 0))
    einheit = TrainingseinheitFactory(user=user, plan=None, ist_deload=False)
    Trainingseinheit.objects.filter(pk=einheit.pk).update(datum=aware)
    SatzFactory(
        einheit=einheit,
        uebung=uebung,
        gewicht=gewicht,
        rpe=rpe,
        wiederholungen=8,
        ist_aufwaermsatz=False,
    )


def _saetze(user):
    return Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False)


@pytest.mark.django_db
class TestPausenCutoff:
    def test_juengste_qualifizierende_grenze(self):
        user = UserFactory()
        heute = timezone.localdate()
        # Qualifizierende Pause (11 Tage) endet vor 10 Tagen.
        TrainingsPauseFactory(
            user=user, start_datum=heute - timedelta(days=20), end_datum=heute - timedelta(days=10)
        )
        # Kurze Pause (3 Tage, < Schwelle) endet später → darf NICHT die Grenze setzen.
        TrainingsPauseFactory(
            user=user, start_datum=heute - timedelta(days=3), end_datum=heute - timedelta(days=1)
        )
        cutoff = ai_views._pausen_cutoff_datum(user)
        assert cutoff == heute - timedelta(days=10)

    def test_offene_pause_setzt_keine_grenze(self):
        user = UserFactory()
        heute = timezone.localdate()
        TrainingsPauseFactory(user=user, start_datum=heute - timedelta(days=20), end_datum=None)
        assert ai_views._pausen_cutoff_datum(user) is None

    def test_ohne_pause_keine_grenze(self):
        user = UserFactory()
        assert ai_views._pausen_cutoff_datum(user) is None


@pytest.mark.django_db
class TestStagnationPauseAware:
    def test_kette_ueberquert_pause_nicht(self):
        """Der eigentliche Bug: 4 Vor-Pause + 2 Post-Pause dürfen nicht flaggen."""
        user = UserFactory()
        bank = UebungFactory(muskelgruppe="BRUST", bezeichnung="Bankdrücken")
        # 4 konstante Trainings VOR der Pause (würden allein Stagnation ergeben).
        for tage in (40, 35, 30, 25):
            _training_am(user, tage, bank, 100)
        # Dokumentierte Pause (11 Tage) dazwischen.
        heute = timezone.localdate()
        TrainingsPauseFactory(
            user=user, start_datum=heute - timedelta(days=20), end_datum=heute - timedelta(days=10)
        )
        # Nur 2 Comeback-Trainings NACH der Pause.
        for tage in (8, 5):
            _training_am(user, tage, bank, 100)

        result = ai_views._get_stagnation_empfehlung(_saetze(user), user)
        assert result == []  # Post-Pause-Segment hat < 4 Trainings → keine Stagnation

    def test_post_pause_segment_flaggt_weiterhin(self):
        """Fix unterdrückt nicht zu viel: 4 konstante Post-Pause-Trainings flaggen."""
        user = UserFactory()
        bank = UebungFactory(muskelgruppe="BRUST", bezeichnung="Bankdrücken")
        for tage in (40, 35):  # Vor-Pause (werden ausgeschlossen)
            _training_am(user, tage, bank, 100)
        heute = timezone.localdate()
        TrainingsPauseFactory(
            user=user, start_datum=heute - timedelta(days=20), end_datum=heute - timedelta(days=10)
        )
        for tage in (8, 6, 4, 2):  # 4 konstante Post-Pause-Trainings
            _training_am(user, tage, bank, 100)

        result = ai_views._get_stagnation_empfehlung(_saetze(user), user)
        assert any(r["typ"] == "stagnation" for r in result)
        # Der Zählertext bezieht sich nur auf die 4 Post-Pause-Trainings.
        eintrag = next(r for r in result if r["typ"] == "stagnation")
        assert "4 Trainings" in eintrag["beschreibung"]

    def test_ohne_pause_unveraendert(self):
        """Regression: ohne Pause flaggen 4 konstante Trainings wie bisher."""
        user = UserFactory()
        bank = UebungFactory(muskelgruppe="BRUST", bezeichnung="Bankdrücken")
        for tage in (40, 30, 20, 10):
            _training_am(user, tage, bank, 100)

        result = ai_views._get_stagnation_empfehlung(_saetze(user), user)
        assert any(r["typ"] == "stagnation" for r in result)
