"""Tests für Phase 32.3 – Klassifikations-Awareness (Kern).

Deckt ab (Konzept §32.3 / §9.2+§9.5+§9.8):
- ``_classify_week_pause``: zwei orthogonale Achsen (Abdeckung vs. Dauer-Grenze),
  inkl. ist_ausfall⟺Vollabdeckung+0 Sessions, Voll-Overlap *mit* Session →
  teilweise_ausfall (⑯), 1-Tages-Pause → kein ist_ausfall/keine Grenze (⑤),
  Di–So (6 inkl. Tage) → Grenze ohne volle Wochenabdeckung (⑥), Grenze auch wenn
  beide berührten Wochen Sessions haben (⑭).
- ``select_comparable_weeks``: Pausen-Grenze = Epoch-break, kurze
  teilweise_ausfall-Woche = continue (Volumen erhalten, kein Anker).
- ``build_weekly_volume_overview``: leere Krankheitswoche wird als gelabelte
  Lücke emittiert; Zukunfts-Pause emittiert keine Zukunfts-Wochen (⑰); offene
  Pause = aktuelle Lücke (auf heute geclamped).
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

from django.utils import timezone

import pytest

from core.utils.week_classification import (
    _classify_week_pause,
    build_weekly_volume_overview,
    select_comparable_weeks,
)


def _key(d: date) -> str:
    iy, iw, _ = d.isocalendar()
    return f"{iy}-W{iw:02d}"


def _monday(iso_year: int, iso_week: int) -> date:
    return date.fromisocalendar(iso_year, iso_week, 1)


def _sunday(iso_year: int, iso_week: int) -> date:
    return date.fromisocalendar(iso_year, iso_week, 7)


# Feste ISO-Woche für die reinen Klassifikator-Tests.
_YEAR, _WEEK = 2026, 10
_MO = _monday(_YEAR, _WEEK)
_SO = _sunday(_YEAR, _WEEK)
_KEY = _key(_MO)


def _clamped(start: date, end: date) -> tuple[date, date, int]:
    """Baut ein (start, end, dauer_tage)-Tupel wie ``_clamp_pausen``."""
    return (start, end, (end - start).days + 1)


class TestClassifyWeekPause:
    """Reine Logik – keine DB nötig."""

    def test_vollabdeckung_ohne_sessions_ist_ausfall(self):
        pausen = [_clamped(_MO - timedelta(days=2), _SO + timedelta(days=2))]
        ausfall, teilweise, grenze = _classify_week_pause(_KEY, pausen, hat_sessions=False)
        assert ausfall is True
        assert teilweise is False
        assert grenze is True  # ist_ausfall impliziert die Grenze

    def test_vollabdeckung_mit_session_ist_teilweise(self):
        """⑯: Voll-Overlap, aber Session geloggt → teilweise_ausfall, kein ist_ausfall."""
        pausen = [_clamped(_MO, _SO)]
        ausfall, teilweise, grenze = _classify_week_pause(_KEY, pausen, hat_sessions=True)
        assert ausfall is False
        assert teilweise is True
        assert grenze is True  # 7 Tage ≥ Mindestdauer

    def test_partieller_overlap_ist_teilweise(self):
        pausen = [_clamped(_MO + timedelta(days=2), _MO + timedelta(days=4))]  # Mi–Fr, 3 Tage
        ausfall, teilweise, grenze = _classify_week_pause(_KEY, pausen, hat_sessions=False)
        assert ausfall is False
        assert teilweise is True
        assert grenze is False  # < Mindestdauer

    def test_eintagespause_kein_ausfall_keine_grenze(self):
        """⑤: 1-Tages-Pause in sessionloser Woche – verbirgt die Woche nicht."""
        pausen = [_clamped(_MO + timedelta(days=2), _MO + timedelta(days=2))]  # 1 Tag
        ausfall, teilweise, grenze = _classify_week_pause(_KEY, pausen, hat_sessions=False)
        assert ausfall is False  # keine Vollabdeckung
        assert teilweise is True
        assert grenze is False  # 1 < Mindestdauer

    def test_di_bis_so_grenze_ohne_vollabdeckung(self):
        """⑥: Di–So (6 inkl. Tage) erreicht die Grenze, deckt aber Mo nicht ab."""
        pausen = [_clamped(_MO + timedelta(days=1), _SO)]  # Di–So
        ausfall, teilweise, grenze = _classify_week_pause(_KEY, pausen, hat_sessions=False)
        assert ausfall is False
        assert teilweise is True
        assert grenze is True

    def test_kein_overlap_alles_false(self):
        # Pause eine Woche später
        pausen = [_clamped(_SO + timedelta(days=1), _SO + timedelta(days=4))]
        ausfall, teilweise, grenze = _classify_week_pause(_KEY, pausen, hat_sessions=False)
        assert (ausfall, teilweise, grenze) == (False, False, False)

    def test_grenze_auch_wenn_woche_sessions_hat(self):
        """⑭: Grenz-Flag NICHT auf 0-Sessions gaten (Do–Di-Pause, beide Wochen trainiert)."""
        # Pause Do (W10) bis Di (W11) = 6 Tage, berührt W10 partiell mit Sessions
        pausen = [_clamped(_MO + timedelta(days=3), _monday(_YEAR, _WEEK + 1) + timedelta(days=1))]
        ausfall, teilweise, grenze = _classify_week_pause(_KEY, pausen, hat_sessions=True)
        assert grenze is True
        assert teilweise is True
        assert ausfall is False


class TestSelectComparableWeeksPause:
    """Pausen-Grenze als Epoch-break, kurze teilweise_ausfall als continue."""

    def test_pausen_grenze_bricht_epoche(self):
        weeks = [
            {"woche": "KW18", "volumen": 100},  # vor der Pause
            {"woche": "KW19", "volumen": 0, "ist_ausfall": True, "ist_pausen_grenze": True},
            {"woche": "KW20", "volumen": 110},  # Comeback
        ]
        result = select_comparable_weeks(weeks)
        # Vergleich darf die Pause NICHT überqueren: nur Post-Pause-Woche bleibt.
        assert [w["woche"] for w in result] == ["KW20"]

    def test_kurze_teilweise_woche_wird_uebersprungen_nicht_gebrochen(self):
        weeks = [
            {"woche": "KW18", "volumen": 100},
            {"woche": "KW19", "volumen": 90, "teilweise_ausfall": True},  # kein Grenz-Flag
            {"woche": "KW20", "volumen": 110},
        ]
        result = select_comparable_weeks(weeks)
        # KW19 nur übersprungen (continue) – KW18 bleibt vergleichbar.
        assert [w["woche"] for w in result] == ["KW18", "KW20"]

    def test_comeback_woche_allein_ergibt_keinen_vergleich(self):
        weeks = [
            {"woche": "KW18", "volumen": 100},
            {"woche": "KW19", "volumen": 0, "ist_ausfall": True, "ist_pausen_grenze": True},
            {"woche": "KW20", "volumen": 110, "ist_laufend": True},
        ]
        result = select_comparable_weeks(weeks)
        assert result == []  # < 2 → Trend pausiert


@pytest.mark.django_db
class TestBuildOverviewEmission:
    """Integration: union-Emission + Clamping über echte Sessions/Pausen."""

    def _session(self, user, dt: datetime):
        from core.models import Trainingseinheit
        from core.tests.factories import SatzFactory, TrainingseinheitFactory, UebungFactory

        aware = timezone.make_aware(dt) if timezone.is_naive(dt) else dt
        einheit = TrainingseinheitFactory(user=user)
        Trainingseinheit.objects.filter(pk=einheit.pk).update(datum=aware)
        einheit.refresh_from_db()
        SatzFactory(
            einheit=einheit,
            uebung=UebungFactory(),
            gewicht=Decimal("100"),
            wiederholungen=10,
            rpe=Decimal("8.0"),
            ist_aufwaermsatz=False,
        )
        return einheit

    def _saetze(self, user):
        from core.models import Satz

        return Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False)

    def _trainings(self, user):
        from core.models import Trainingseinheit

        return Trainingseinheit.objects.filter(user=user)

    def test_leere_krankheitswoche_wird_emittiert(self):
        from core.tests.factories import TrainingsPauseFactory, UserFactory

        user = UserFactory()
        # Sessions in W20 + W21, heute in W23 → ohne Pause würde W22 fehlen.
        self._session(user, datetime.combine(_monday(2026, 20), datetime.min.time()))
        self._session(user, datetime.combine(_monday(2026, 21), datetime.min.time()))
        # Volle Pause über W22 (Mo–So), 0 Sessions.
        pause = TrainingsPauseFactory(
            user=user, start_datum=_monday(2026, 22), end_datum=_sunday(2026, 22)
        )
        heute = datetime.combine(_monday(2026, 23), datetime.min.time())

        weeks = build_weekly_volume_overview(
            self._saetze(user), self._trainings(user), heute=heute, pausen=[pause]
        )
        w22 = next((w for w in weeks if w["_iso_key"] == _key(_monday(2026, 22))), None)
        assert w22 is not None, "leere Krankheitswoche W22 muss als Lücke emittiert werden"
        assert w22["ist_ausfall"] is True
        assert w22["ist_pausen_grenze"] is True
        assert w22["volumen"] == 0

    def test_zukunftspause_emittiert_keine_zukunftswochen(self):
        """⑰: geschlossene Zukunfts-Range emittiert keine Zukunfts-Wochen."""
        from core.tests.factories import TrainingsPauseFactory, UserFactory

        user = UserFactory()
        self._session(user, datetime.combine(_monday(2026, 20), datetime.min.time()))
        self._session(user, datetime.combine(_monday(2026, 21), datetime.min.time()))
        heute = datetime.combine(_monday(2026, 22), datetime.min.time())
        # Pause komplett in der Zukunft (W30).
        pause = TrainingsPauseFactory(
            user=user, start_datum=_monday(2026, 30), end_datum=_sunday(2026, 30)
        )
        weeks = build_weekly_volume_overview(
            self._saetze(user), self._trainings(user), heute=heute, pausen=[pause]
        )
        keys = [w["_iso_key"] for w in weeks]
        assert _key(_monday(2026, 30)) not in keys
        # Keine Woche jenseits der aktuellen ISO-Woche (W22).
        assert all(k <= _key(_monday(2026, 22)) for k in keys)

    def test_offene_pause_ist_aktuelle_luecke(self):
        from core.tests.factories import TrainingsPauseFactory, UserFactory

        user = UserFactory()
        self._session(user, datetime.combine(_monday(2026, 20), datetime.min.time()))
        self._session(user, datetime.combine(_monday(2026, 21), datetime.min.time()))
        heute = datetime.combine(_monday(2026, 23), datetime.min.time())
        # Offene Pause ab W22 (kein Ende) → bis heute (W23) geclamped.
        pause = TrainingsPauseFactory(user=user, start_datum=_monday(2026, 22), end_datum=None)
        weeks = build_weekly_volume_overview(
            self._saetze(user), self._trainings(user), heute=heute, pausen=[pause]
        )
        keys = [w["_iso_key"] for w in weeks]
        assert _key(_monday(2026, 23)) in keys  # aktuelle Woche als Lücke emittiert
        w23 = next(w for w in weeks if w["_iso_key"] == _key(_monday(2026, 23)))
        assert w23["ist_laufend"] is True
        assert w23["teilweise_ausfall"] or w23["ist_ausfall"]


@pytest.mark.django_db
class TestDashboardGapLabel:
    """§9.2/㉔: Dashboard-Karte markiert dokumentierte Pausenwochen."""

    def test_calculate_weekly_volumes_markiert_pause(self):
        from core.tests.factories import TrainingsPauseFactory, UserFactory
        from core.views.training_stats import _calculate_weekly_volumes

        user = UserFactory()
        heute = timezone.make_aware(
            datetime.combine(_monday(2026, 23) + timedelta(days=2), datetime.min.time())
        )
        # Pause über die ganze Vorwoche W22 (Mo–So) → 7 Tage ≥ Mindestdauer = Grenze
        TrainingsPauseFactory(user=user, start_datum=_monday(2026, 22), end_datum=_sunday(2026, 22))
        weeks = _calculate_weekly_volumes(user, heute)
        w_letzte = next(w for w in weeks if w["week_num"] == 1)  # W22
        w_diese = next(w for w in weeks if w["week_num"] == 0)  # W23
        assert w_letzte["ist_pause"] is True
        assert w_diese["ist_pause"] is False


def test_generate_volume_chart_mit_pause_smoke():
    """generate_volume_chart verträgt Pausen-Flags (gelabelte Lücke)."""
    from core.chart_generator import generate_volume_chart

    wochen = [
        {"woche": "KW20", "volumen": 2000, "effektives_volumen": 1500},
        {"woche": "KW21", "volumen": 0, "ist_ausfall": True},
        {"woche": "KW22", "volumen": 0, "ist_ausfall": True},
        {"woche": "KW23", "volumen": 2500, "effektives_volumen": 2000},
    ]
    img = generate_volume_chart(wochen)
    assert isinstance(img, str) and len(img) > 0
