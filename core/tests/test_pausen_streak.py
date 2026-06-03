"""Tests für Phase 32.5 – Streak pausiert (Dashboard + PDF) + adherence_rate.

Deckt ab (Konzept §32.5 / §9.4):
- Dokumentierte Pause ≥ Mindestdauer **bridged** den Streak (kein Reset) – in
  BEIDEN Implementierungen (`_calculate_streak` Dashboard,
  `calculate_consistency_metrics` PDF), auch bei nicht auf Mo–So ausgerichteter
  Pause (Di–So, ⑨).
- 1-Tages-Pause (< Mindestdauer) bridged NICHT (⑤).
- Un-dokumentierter Gap bricht weiterhin.
- Live/PDF-Parität (㉒-Schwester-Bug ②).
- `adherence_rate` pausenbereinigt: dokumentierte Pausenwoche ohne Training
  fällt aus dem Nenner (㉒).
"""

from datetime import datetime, time, timedelta
from decimal import Decimal

from django.utils import timezone

import pytest

from core.utils.advanced_stats import calculate_consistency_metrics
from core.views.training_stats import _calculate_streak


def _train(user, d):
    """Eine Trainingseinheit + 1 Satz am Tag ``d`` (date)."""
    from core.models import Trainingseinheit
    from core.tests.factories import SatzFactory, TrainingseinheitFactory, UebungFactory

    dt = timezone.make_aware(datetime.combine(d, time(12, 0)))
    e = TrainingseinheitFactory(user=user)
    Trainingseinheit.objects.filter(pk=e.pk).update(datum=dt)
    e.refresh_from_db()
    SatzFactory(
        einheit=e,
        uebung=UebungFactory(),
        gewicht=Decimal("100"),
        wiederholungen=10,
        rpe=Decimal("8.0"),
        ist_aufwaermsatz=False,
    )


def _monday(d):
    return d - timedelta(days=d.weekday())


def _wk_monday(base_date, k):
    """Montag der Woche, die ``k`` Wochen vor ``base_date`` liegt."""
    return _monday(base_date - timedelta(weeks=k))


def _pause(user, start, end):
    from core.tests.factories import TrainingsPauseFactory

    return TrainingsPauseFactory(user=user, start_datum=start, end_datum=end)


@pytest.mark.django_db
class TestDashboardStreakBridge:
    def test_dokumentierte_pause_bridged(self):
        from core.tests.factories import UserFactory

        user = UserFactory()
        now = timezone.now()
        heute_d = now.date()
        # Training in Wochen 0,1 (aktuell) und 4,5 (vor der Pause).
        for k in (0, 1, 4, 5):
            _train(user, _wk_monday(heute_d, k))
        # Dokumentierte 2-Wochen-Pause über Wochen 2+3 (0 Sessions, ≥ Mindestdauer).
        _pause(user, _wk_monday(heute_d, 3), _wk_monday(heute_d, 2) + timedelta(days=6))
        # Erwartung: Wochen 0,1 (2) + bridge über 2,3 + Wochen 4,5 (2) = 4.
        assert _calculate_streak(user, now) == 4

    def test_di_bis_so_pause_bridged(self):
        """⑨: Pause Di–So (nicht auf Mo–So ausgerichtet, 6 Tage) überbrückt."""
        from core.tests.factories import UserFactory

        user = UserFactory()
        now = timezone.now()
        heute_d = now.date()
        for k in (0, 1, 3, 4):
            _train(user, _wk_monday(heute_d, k))
        # Woche 2: Pause Di–So (Mo ohne Training, also Woche session-los), 6 Tage.
        woche2_mo = _wk_monday(heute_d, 2)
        _pause(user, woche2_mo + timedelta(days=1), woche2_mo + timedelta(days=6))
        # 0,1 (2) + bridge Woche2 + 3,4 (2) = 4.
        assert _calculate_streak(user, now) == 4

    def test_eintagespause_bridged_nicht(self):
        """⑤: 1-Tages-Pause (< Mindestdauer) überbrückt NICHT → Streak bricht."""
        from core.tests.factories import UserFactory

        user = UserFactory()
        now = timezone.now()
        heute_d = now.date()
        for k in (0, 1, 3, 4):
            _train(user, _wk_monday(heute_d, k))
        woche2_mi = _wk_monday(heute_d, 2) + timedelta(days=2)
        _pause(user, woche2_mi, woche2_mi)  # 1 Tag
        # Woche 2 ohne Training + nur 1-Tages-Pause → Bruch nach Wochen 0,1.
        assert _calculate_streak(user, now) == 2

    def test_undokumentierter_gap_bricht(self):
        from core.tests.factories import UserFactory

        user = UserFactory()
        now = timezone.now()
        heute_d = now.date()
        for k in (0, 1, 3, 4):
            _train(user, _wk_monday(heute_d, k))
        # Keine Pause → Woche 2 bricht den Streak.
        assert _calculate_streak(user, now) == 2


@pytest.mark.django_db
class TestPdfStreakBridgeUndParitaet:
    def test_consistency_streak_bridged_und_paritaet(self):
        from core.models import Trainingseinheit
        from core.tests.factories import UserFactory

        user = UserFactory()
        now = timezone.now()
        heute_d = now.date()
        for k in (0, 1, 4, 5):
            _train(user, _wk_monday(heute_d, k))
        _pause(user, _wk_monday(heute_d, 3), _wk_monday(heute_d, 2) + timedelta(days=6))
        alle = Trainingseinheit.objects.filter(user=user)
        metrics = calculate_consistency_metrics(alle)
        # PDF-Streak gebridged …
        assert metrics["aktueller_streak"] == 4
        # … und identisch zum Dashboard (Live/PDF-Parität, ②).
        assert metrics["aktueller_streak"] == _calculate_streak(user, now)

    def test_adherence_pausenbereinigt(self):
        """㉒: dokumentierte Pausenwoche ohne Training fällt aus dem Nenner."""
        from core.models import Trainingseinheit
        from core.tests.factories import UserFactory

        user = UserFactory()
        now = timezone.now()
        heute_d = now.date()
        # Training Wochen 0,1,2,4 (4 Wochen), Woche 3 = dokumentierte Vollpause.
        for k in (0, 1, 2, 4):
            _train(user, _wk_monday(heute_d, k))
        _pause(user, _wk_monday(heute_d, 3), _wk_monday(heute_d, 3) + timedelta(days=6))
        alle = Trainingseinheit.objects.filter(user=user)
        metrics = calculate_consistency_metrics(alle)
        # Ohne Bereinigung: 4/5 = 80 %. Mit Bereinigung (Woche 3 raus): 4/4 = 100 %.
        assert metrics["adherence_rate"] == 100.0
