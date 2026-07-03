"""Tests für Phase 33.2 – Wiedereinstiegs-Kernlogik (core/utils/reentry.py).

Deckt ab (Konzept §33.2):
- Detraining-Faktor an allen Dauer-Grenzen (inklusiv gezählt) + Medizin-Abschlag,
- Rundung auf 2.5-kg-Schritte,
- Rampe monoton steigend bis 100 %, RPE-Deckel steigend,
- Auslöser: offene Pause / zu kurze Pause / zu alte Pause → keine Empfehlung,
- letztes Arbeitsgewicht = Top-Working-Set der jüngsten Vor-Pause-Einheit
  (Aufwärmsätze, Deload-Trainings, Übungen außerhalb des Lookbacks ausgeschlossen),
- reine Anzeige: kein Schreibpfad verändert Sätze.
"""

from datetime import date, datetime
from decimal import Decimal

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
from core.utils import reentry


def _session(user, when: date, uebung, gewicht, *, warmup=False, deload=False, rpe="8.0"):
    """Eine Trainingseinheit am Tag `when` mit einem Satz (datum via update forcieren)."""
    aware = timezone.make_aware(datetime(when.year, when.month, when.day, 12, 0))
    einheit = TrainingseinheitFactory(user=user, plan=None, ist_deload=deload)
    Trainingseinheit.objects.filter(pk=einheit.pk).update(datum=aware)
    einheit.refresh_from_db()
    SatzFactory(
        einheit=einheit,
        uebung=uebung,
        gewicht=Decimal(str(gewicht)),
        wiederholungen=8,
        rpe=Decimal(rpe),
        ist_aufwaermsatz=warmup,
    )
    return einheit


# ─────────────────────────────────────────────────────────────────────────────
# Reine Faktor-/Rampen-Logik (ohne DB)
# ─────────────────────────────────────────────────────────────────────────────


class TestDetrainingProfil:
    @pytest.mark.parametrize(
        "dauer,erwartet_faktor,erwartet_wochen",
        [
            (6, 0.95, 1),  # unter der ersten Grenze → wie 7–13
            (7, 0.95, 1),
            (13, 0.95, 1),
            (14, 0.90, 2),
            (27, 0.90, 2),
            (28, 0.85, 3),
            (41, 0.85, 3),
            (42, 0.80, 4),
            (90, 0.80, 4),
        ],
    )
    def test_faktor_an_grenzen(self, dauer, erwartet_faktor, erwartet_wochen):
        faktor, wochen, rpe = reentry._detraining_profil(dauer, medizinisch=False)
        assert faktor == pytest.approx(erwartet_faktor)
        assert wochen == erwartet_wochen
        assert rpe == reentry.RPE_CAP_START

    def test_medizinisch_ist_konservativer(self):
        faktor, wochen, rpe = reentry._detraining_profil(14, medizinisch=True)
        # 0.90 − 0.05 = 0.85, Rampe 2 + 1 = 3, RPE-Deckel niedriger
        assert faktor == pytest.approx(0.85)
        assert wochen == 3
        assert rpe == reentry.RPE_CAP_START_MEDIZINISCH

    def test_medizinisch_faktor_floor(self):
        faktor, _, _ = reentry._detraining_profil(42, medizinisch=True)
        assert faktor == pytest.approx(0.75)  # 0.80 − 0.05, über dem Floor 0.70


class TestRoundToStep:
    @pytest.mark.parametrize(
        "roh,erwartet",
        [(90.0, 90.0), (91.0, 90.0), (91.9, 92.5), (93.7, 92.5), (94.0, 95.0), (0.0, 0.0)],
    )
    def test_rundung(self, roh, erwartet):
        assert reentry.round_to_step(roh) == erwartet


class TestBaueRampe:
    def test_monoton_steigend_bis_100(self):
        rampe = reentry._baue_rampe(0.80, 4, reentry.RPE_CAP_START)
        faktoren = [r["faktor"] for r in rampe]
        assert faktoren[0] == pytest.approx(0.80)  # Woche 1 = Start-Faktor
        assert faktoren == sorted(faktoren)  # steigend
        assert all(f < 1.0 for f in faktoren)  # 100 % erst NACH der Rampe
        rpe_caps = [r["rpe_cap"] for r in rampe]
        assert rpe_caps == sorted(rpe_caps)  # RPE-Deckel steigt mit

    def test_einwoechige_rampe(self):
        rampe = reentry._baue_rampe(0.95, 1, reentry.RPE_CAP_START)
        assert len(rampe) == 1
        assert rampe[0]["faktor"] == pytest.approx(0.95)


# ─────────────────────────────────────────────────────────────────────────────
# Auslöser: get_active_reentry_pause
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestActiveReentryPause:
    def test_offene_pause_zaehlt_nicht(self):
        user = UserFactory()
        today = date(2026, 6, 1)
        TrainingsPauseFactory(user=user, start_datum=date(2026, 5, 1), end_datum=None)
        assert reentry.get_active_reentry_pause(user, today=today) is None

    def test_zu_kurze_pause_zaehlt_nicht(self):
        user = UserFactory()
        today = date(2026, 6, 1)
        # 5 Tage (< REENTRY_MIN_DAYS)
        TrainingsPauseFactory(user=user, start_datum=date(2026, 5, 25), end_datum=date(2026, 5, 29))
        assert reentry.get_active_reentry_pause(user, today=today) is None

    def test_frische_qualifizierende_pause(self):
        user = UserFactory()
        today = date(2026, 6, 1)
        pause = TrainingsPauseFactory(
            user=user, start_datum=date(2026, 4, 20), end_datum=date(2026, 5, 31)
        )  # 42 Tage, Ende gestern
        assert reentry.get_active_reentry_pause(user, today=today) == pause

    def test_zu_alte_pause_ausserhalb_rampe(self):
        user = UserFactory()
        today = date(2026, 6, 1)
        # 42 Tage → Rampe 4 Wochen (28 Tage); Ende vor 30 Tagen → Rampe vorbei
        TrainingsPauseFactory(user=user, start_datum=date(2026, 3, 22), end_datum=date(2026, 5, 2))
        assert reentry.get_active_reentry_pause(user, today=today) is None


# ─────────────────────────────────────────────────────────────────────────────
# Vollständige Empfehlung: build_reentry_recommendation
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestBuildRecommendation:
    def test_keine_pause_gibt_none(self):
        user = UserFactory()
        assert reentry.build_reentry_recommendation(user, today=date(2026, 6, 1)) is None

    def test_faktor_und_rampe_fuer_42_tage(self):
        user = UserFactory()
        today = date(2026, 6, 1)
        TrainingsPauseFactory(user=user, start_datum=date(2026, 4, 20), end_datum=date(2026, 5, 31))
        rec = reentry.build_reentry_recommendation(user, today=today)
        assert rec is not None
        assert rec["dauer_tage"] == 42
        assert rec["medizinisch"] is False
        assert rec["start_faktor"] == pytest.approx(0.80)
        assert rec["rampen_wochen"] == 4
        assert rec["aktuelle_woche"] == 1  # Ende gestern → Woche 1

    def test_medizinisch_setzt_flag_und_ist_konservativer(self):
        user = UserFactory()
        today = date(2026, 6, 1)
        TrainingsPauseFactory(
            user=user,
            start_datum=date(2026, 4, 20),
            end_datum=date(2026, 5, 31),
            aerztliche_freigabe_noetig=True,
        )
        rec = reentry.build_reentry_recommendation(user, today=today)
        assert rec["medizinisch"] is True
        assert rec["start_faktor"] == pytest.approx(0.75)  # 0.80 − 0.05
        assert rec["rampen_wochen"] == 5  # 4 + 1

    def test_letztes_arbeitsgewicht_ist_top_set_der_juengsten_einheit(self):
        user = UserFactory()
        today = date(2026, 6, 1)
        bank = UebungFactory(bezeichnung="Bankdrücken")
        # Ältere Einheit (schwerer) darf NICHT gewinnen – die jüngste zählt.
        _session(user, date(2026, 4, 10), bank, 110)
        # Jüngste Vor-Pause-Einheit: Aufwärmsatz 120 (ignoriert), Working 85 + 90.
        einheit = _session(user, date(2026, 4, 18), bank, 90)
        SatzFactory(einheit=einheit, uebung=bank, gewicht=Decimal("85"), wiederholungen=8)
        SatzFactory(
            einheit=einheit,
            uebung=bank,
            gewicht=Decimal("120"),
            wiederholungen=3,
            ist_aufwaermsatz=True,
        )
        TrainingsPauseFactory(user=user, start_datum=date(2026, 4, 20), end_datum=date(2026, 5, 31))
        rec = reentry.build_reentry_recommendation(user, today=today)
        assert len(rec["uebungen"]) == 1
        eintrag = rec["uebungen"][0]
        assert eintrag["uebung"] == bank
        assert eintrag["letztes_gewicht"] == 90.0
        # 42 Tage → Rampe 0.80/0.85/0.90/0.95 auf 90 kg, gerundet auf 2.5-Schritte:
        # 72.0→72.5, 76.5→77.5, 81.0→80.0, 85.5→85.0
        assert [w["gewicht"] for w in eintrag["wochen"]] == [72.5, 77.5, 80.0, 85.0]

    def test_deload_und_lookback_werden_ausgeschlossen(self):
        user = UserFactory()
        today = date(2026, 6, 1)
        bank = UebungFactory(bezeichnung="Bankdrücken")
        squat = UebungFactory(bezeichnung="Kniebeuge")
        alt = UebungFactory(bezeichnung="Altlast")
        # Bank: normale jüngste Einheit → zählt.
        _session(user, date(2026, 4, 18), bank, 100)
        # Kniebeuge: nur als Deload geloggt → ausgeschlossen.
        _session(user, date(2026, 4, 18), squat, 140, deload=True)
        # Altlast: außerhalb des 60-Tage-Lookbacks vor Pausenbeginn (20.04) → raus.
        _session(user, date(2026, 1, 5), alt, 50)
        TrainingsPauseFactory(user=user, start_datum=date(2026, 4, 20), end_datum=date(2026, 5, 31))
        rec = reentry.build_reentry_recommendation(user, today=today)
        namen = {e["uebung"].bezeichnung for e in rec["uebungen"]}
        assert namen == {"Bankdrücken"}

    def test_reine_anzeige_veraendert_keine_saetze(self):
        user = UserFactory()
        today = date(2026, 6, 1)
        bank = UebungFactory(bezeichnung="Bankdrücken")
        _session(user, date(2026, 4, 18), bank, 100)
        TrainingsPauseFactory(user=user, start_datum=date(2026, 4, 20), end_datum=date(2026, 5, 31))
        vorher = list(Satz.objects.values_list("gewicht", flat=True))
        reentry.build_reentry_recommendation(user, today=today)
        nachher = list(Satz.objects.values_list("gewicht", flat=True))
        assert vorher == nachher
