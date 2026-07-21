"""
Tests für core/export/stats_collector.py

Abdeckung:
- muscle_status: alle Branches (nicht trainiert, untertrainiert, übertrainiert, optimal, wenig Daten)
- collect_muscle_balance: mit/ohne Trainingsdaten
- collect_push_pull: alle Ratio-Branches (keine Daten, ausgewogen, push-betont, einseitig → nicht bewertbar, pull-betont)
- collect_strength_progression: plan_start_date, fallback_session_count, backwards-compat
- collect_intensity_data: mit/ohne RPE-Daten
- collect_weight_trend: mit Daten, zu wenig Daten
- calc_trainings_per_week: normal, leer, eine Session
- build_top_uebungen: mit/ohne active_uebung_ids
- sum_volume: einfacher Aufruf
- calc_volume_trend_weekly: alle Branches
- calc_vormonats_delta: mit/ohne None-Werte
- collect_training_heatmap_data: mit/ohne RPE
- collect_exercise_detail_data: mit Verlauf, zu wenig Daten

Phase 24.1c: ``build_weekly_volume_overview`` (vorher
``collect_weekly_volume_pdf``) und ``select_comparable_weeks`` sind in
``core/utils/week_classification.py`` umgezogen – ihre Tests liegen in
``core/tests/test_week_classification.py``.
"""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

import pytest

from core.export.stats_collector import (
    build_top_uebungen,
    calc_trainings_per_week,
    calc_volume_trend_weekly,
    calc_vormonats_delta,
    collect_exercise_detail_data,
    collect_intensity_data,
    collect_muscle_balance,
    collect_push_pull,
    collect_strength_progression,
    collect_training_heatmap_data,
    collect_weight_trend,
    muscle_status,
    sum_volume,
)
from core.tests.factories import (
    KoerperWerteFactory,
    SatzFactory,
    TrainingseinheitFactory,
    UebungFactory,
    UserFactory,
)

# ─────────────────────────────────────────────────────────────────────────────
# muscle_status
# ─────────────────────────────────────────────────────────────────────────────


class TestMuscleStatus:
    def test_nicht_trainiert_wenig_daten(self):
        key, label, expl = muscle_status(0, 10, 20, wenig_daten=True)
        assert key == "nicht_trainiert"
        assert "Noch keine" in expl

    def test_nicht_trainiert_genug_daten(self):
        key, label, expl = muscle_status(0, 10, 20, wenig_daten=False)
        assert key == "nicht_trainiert"
        assert "nicht trainiert" in expl.lower()

    def test_untertrainiert_wenig_daten(self):
        key, label, expl = muscle_status(5, 10, 20, wenig_daten=True)
        assert key == "untertrainiert"
        assert label == "Wenig trainiert"

    def test_untertrainiert_genug_daten(self):
        key, label, expl = muscle_status(5, 10, 20, wenig_daten=False)
        assert key == "untertrainiert"
        assert label == "Untertrainiert"

    def test_uebertrainiert_wenig_daten(self):
        key, label, expl = muscle_status(25, 10, 20, wenig_daten=True)
        assert key == "uebertrainiert"
        assert label == "Viel trainiert"

    def test_uebertrainiert_genug_daten(self):
        key, label, expl = muscle_status(25, 10, 20, wenig_daten=False)
        assert key == "uebertrainiert"
        assert "Übertraining" in label or "bertraining" in label

    def test_optimal(self):
        key, label, expl = muscle_status(15, 10, 20, wenig_daten=False)
        assert key == "optimal"
        assert label == "Optimal"
        assert "15" in expl


# ─────────────────────────────────────────────────────────────────────────────
# collect_push_pull
# ─────────────────────────────────────────────────────────────────────────────


class TestCollectPushPull:
    def _mg_stats(self, **group_sets):
        """Hilfsmethode: erstellt muskelgruppen_stats-Liste mit status='optimal'."""
        return [
            {"key": k, "saetze": v, "status": "optimal", "name": k} for k, v in group_sets.items()
        ]

    def _with_status(self, key: str, saetze: int, status: str) -> dict:
        return {"key": key, "saetze": saetze, "status": status, "name": key}

    def test_keine_daten(self):
        result = collect_push_pull([])
        assert result["bewertung"] == "Keine Daten"
        assert result["ratio"] == 0
        assert result["context_override"] is False

    def test_ausgewogen(self):
        stats = self._mg_stats(BRUST=10, RUECKEN_LAT=10)
        result = collect_push_pull(stats)
        assert result["bewertung"] == "Ausgewogen"
        assert result["ratio"] == 1.0
        assert result["context_override"] is False

    def test_push_betont_leicht(self):
        # Ratio 1.3:1 → leicht push-betont
        stats = self._mg_stats(BRUST=13, RUECKEN_LAT=10)
        result = collect_push_pull(stats)
        assert "Leicht Push" in result["bewertung"]

    def test_zu_viel_push(self):
        # Ratio > 2.0
        stats = self._mg_stats(BRUST=21, RUECKEN_LAT=10)
        result = collect_push_pull(stats)
        assert "Push" in result["bewertung"]

    def test_pull_betont(self):
        # ratio < 0.8
        stats = self._mg_stats(BRUST=7, RUECKEN_LAT=10)
        result = collect_push_pull(stats)
        assert "Pull" in result["bewertung"]

    def test_nur_push_kein_pull_nicht_bewertbar(self):
        """Phase 35.2 (#1059 c): eine Seite ohne Sätze → keine Balance-Bewertung."""
        stats = self._mg_stats(BRUST=10)
        result = collect_push_pull(stats)
        assert result["bewertung"] == "Nicht bewertbar"
        assert result["ratio"] == 0
        assert "nicht bewertbar" in result["empfehlung"]

    def test_nur_pull_kein_push_nicht_bewertbar(self):
        """Kernbug #1059 (c): push=0/pull=18 erzeugte 'Pull-betont (gut)' mit
        'überwiegt leicht'-Gesundheitsaussage bei Ratio 0,00:1."""
        stats = self._mg_stats(RUECKEN_LAT=18)
        result = collect_push_pull(stats)
        assert result["bewertung"] == "Nicht bewertbar"
        assert result["ratio"] == 0
        assert "nicht bewertbar" in result["empfehlung"]
        assert "überwiegt" not in result["empfehlung"]
        assert "positiv" not in result["empfehlung"]


# ─────────────────────────────────────────────────────────────────────────────
# Phase 24.2: collect_push_pull – kontextabhängige Empfehlung
# ─────────────────────────────────────────────────────────────────────────────


class TestCollectPushPullContextAware:
    def _stats(self, *entries):
        """entries = (key, saetze, status) tuples."""
        return [{"key": k, "saetze": s, "status": st, "name": k} for k, s, st in entries]

    def test_pull_betont_ohne_uebertraining_unveraendert(self):
        """Klassischer Fall: ratio<0.8, alle Pull-Muskeln optimal → bestehender
        positiver Text bleibt (keine Inversion)."""
        stats = self._stats(("BRUST", 12, "optimal"), ("RUECKEN_LAT", 16, "optimal"))
        result = collect_push_pull(stats)
        assert result["bewertung"] == "Pull-betont (gut)"
        assert result["context_override"] is False
        assert "positiv" in result["empfehlung"]

    def test_mai_2026_pull_betont_aber_pull_uebertraining_invertiert(self):
        """Mai-Bug-Reproduktion: ratio 0.75, Rücken-Lat & Schulter-Hint im
        Übertraining-Bereich. Empfehlung muss kippen, statt 'positiv für
        Schultergesundheit' zu sagen."""
        stats = self._stats(
            ("BRUST", 12, "optimal"),
            ("TRIZEPS", 6, "optimal"),
            ("RUECKEN_LAT", 28, "uebertrainiert"),
            ("SCHULTER_HINT", 24, "uebertrainiert"),
            ("BIZEPS", 8, "optimal"),
        )
        result = collect_push_pull(stats)
        assert result["bewertung"] == "Pull-betont (gut)"
        assert result["context_override"] is True
        # Inhalt der invertierten Empfehlung
        assert "bereits hoch" in result["empfehlung"]
        assert "Push ergänzen" in result["empfehlung"]
        assert "Rücken-Lat" in result["empfehlung"]
        assert "Schulter-Hintere" in result["empfehlung"]
        # Strukturierter Status für späteres UI
        assert "Rücken-Lat" in result["pull_overtrained"]
        assert "Schulter-Hintere" in result["pull_overtrained"]
        assert result["push_overtrained"] == []

    def test_leicht_push_betont_mit_push_uebertraining_invertiert(self):
        """ratio 1.3, Brust übertrainiert → invertiert: Pull aufstocken."""
        stats = self._stats(
            ("BRUST", 26, "uebertrainiert"),
            ("TRIZEPS", 6, "optimal"),
            ("RUECKEN_LAT", 18, "optimal"),
        )
        result = collect_push_pull(stats)
        assert result["bewertung"] == "Leicht Push-betont"
        assert result["context_override"] is True
        assert "Pull aufstocken" in result["empfehlung"]
        assert "Brust" in result["empfehlung"]

    def test_leicht_push_betont_alles_optimal_unveraendert(self):
        stats = self._stats(("BRUST", 13, "optimal"), ("RUECKEN_LAT", 10, "optimal"))
        result = collect_push_pull(stats)
        assert result["bewertung"] == "Leicht Push-betont"
        assert result["context_override"] is False
        assert "tolerierbaren Bereich" in result["empfehlung"]

    def test_zu_viel_push_pull_dennoch_uebertrainiert_invertiert(self):
        """Edge-Case: ratio>2 (massiv mehr Push), aber gleichzeitig sind
        die wenigen Pull-Sätze auf einer Muskelgruppe konzentriert, die ins
        Übertraining gerät. Empfehlung muss differenzieren."""
        stats = self._stats(
            ("BRUST", 30, "optimal"),
            ("RUECKEN_LAT", 14, "uebertrainiert"),
        )
        result = collect_push_pull(stats)
        assert result["bewertung"] == "Zu viel Push"
        assert result["context_override"] is True
        assert "Push-Volumen senken" in result["empfehlung"]

    def test_ausgewogen_aber_push_uebertraining_warnt(self):
        """Mathematisch ausgewogen, aber Push-Muskel im Übertraining → Warnung."""
        stats = self._stats(
            ("BRUST", 22, "uebertrainiert"),
            ("RUECKEN_LAT", 22, "optimal"),
        )
        result = collect_push_pull(stats)
        assert result["bewertung"] == "Ausgewogen"
        assert result["context_override"] is True
        assert "Volumen pro Muskelgruppe" in result["empfehlung"]
        assert "Push" in result["empfehlung"]

    def test_ausgewogen_alle_optimal_unveraendert(self):
        stats = self._stats(("BRUST", 15, "optimal"), ("RUECKEN_LAT", 15, "optimal"))
        result = collect_push_pull(stats)
        assert result["bewertung"] == "Ausgewogen"
        assert result["context_override"] is False
        assert "Perfekt" in result["empfehlung"]

    def test_nur_push_mit_uebertraining_bleibt_nicht_bewertbar(self):
        """Phase 35.2: auch mit Übertraining-Status auf der einzigen Seite gibt
        es keine Balance-Aussage aus einseitigen Daten – der Übertraining-Status
        selbst bleibt in der Muskelgruppen-Tabelle sichtbar."""
        stats = self._stats(("BRUST", 25, "uebertrainiert"))
        result = collect_push_pull(stats)
        assert result["bewertung"] == "Nicht bewertbar"
        assert result["context_override"] is False


# ─────────────────────────────────────────────────────────────────────────────
# collect_weight_trend
# ─────────────────────────────────────────────────────────────────────────────


class TestCollectWeightTrend:
    def test_zu_wenig_daten_gibt_none(self):
        kw = [KoerperWerteFactory()]
        result = collect_weight_trend(kw)
        assert result is None

    def test_gewichtszunahme(self):
        kw1 = KoerperWerteFactory(gewicht=Decimal("85.0"))
        kw2 = KoerperWerteFactory(gewicht=Decimal("80.0"))
        result = collect_weight_trend([kw1, kw2])
        assert result is not None
        assert result["richtung"] == "zugenommen"
        assert result["diff"] == pytest.approx(5.0, abs=0.2)

    def test_gewichtsabnahme(self):
        kw1 = KoerperWerteFactory(gewicht=Decimal("78.0"))
        kw2 = KoerperWerteFactory(gewicht=Decimal("82.0"))
        result = collect_weight_trend([kw1, kw2])
        assert result is not None
        assert result["richtung"] == "abgenommen"


# ─────────────────────────────────────────────────────────────────────────────
# calc_trainings_per_week
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCalcTrainingsPerWeek:
    def test_keine_trainings(self):
        user = UserFactory()
        from core.models import Trainingseinheit

        alle = Trainingseinheit.objects.filter(user=user)
        result = calc_trainings_per_week(alle, timezone.now())
        assert result == 0.0

    def test_trainings_vorhanden(self):
        user = UserFactory()
        heute = timezone.now()
        # Erstelle 4 Trainingseinheiten über 4 Wochen
        for i in range(4):
            TrainingseinheitFactory(user=user, datum=heute - timedelta(days=7 * i))
        from core.models import Trainingseinheit

        alle = Trainingseinheit.objects.filter(user=user)
        result = calc_trainings_per_week(alle, heute)
        assert result > 0.0


# ─────────────────────────────────────────────────────────────────────────────
# calc_volume_trend_weekly
# ─────────────────────────────────────────────────────────────────────────────


class TestCalcVolumeTrendWeekly:
    def test_zu_wenig_daten_gibt_none(self):
        assert calc_volume_trend_weekly([]) is None
        assert calc_volume_trend_weekly([{"woche": "KW01", "volumen": 1000}]) is None

    def test_vorwoche_null_gibt_none(self):
        heute = timezone.now()
        # Baue zwei abgeschlossene Wochen, Vorwoche = 0
        wochen = [
            {"woche": "KW01", "volumen": 0},
            {"woche": "KW02", "volumen": 1000},
        ]
        # Aktuelle KW ist nicht in Liste → werden beide als Kandidaten gewählt
        result = calc_volume_trend_weekly(wochen, heute)
        assert result is None  # vorletzte=0, daher None

    def test_trend_steigt(self):
        heute = timezone.now()
        # Verwende KWs die nicht der aktuellen Woche entsprechen
        wochen = [
            {"woche": "KW01", "volumen": 1000},
            {"woche": "KW02", "volumen": 1100},
        ]
        result = calc_volume_trend_weekly(wochen, heute)
        if result:
            assert result["trend"] == "steigt"

    def test_trend_faellt(self):
        heute = timezone.now()
        wochen = [
            {"woche": "KW01", "volumen": 1100},
            {"woche": "KW02", "volumen": 900},
        ]
        result = calc_volume_trend_weekly(wochen, heute)
        if result:
            assert result["trend"] == "fällt"

    def test_trend_stabil(self):
        heute = timezone.now()
        wochen = [
            {"woche": "KW01", "volumen": 1000},
            {"woche": "KW02", "volumen": 1010},
        ]
        result = calc_volume_trend_weekly(wochen, heute)
        if result:
            assert result["trend"] == "stabil"

    def test_laufende_woche_wird_ignoriert(self):
        heute = timezone.now()
        kw_aktuell = f"KW{heute.isocalendar()[1]:02d}"
        wochen = [
            {"woche": "KW01", "volumen": 1000},
            {"woche": "KW02", "volumen": 1050},
            {"woche": kw_aktuell, "volumen": 500},  # Aktuelle → ignorieren
        ]
        result = calc_volume_trend_weekly(wochen, heute)
        # Ergebnis sollte auf KW01/KW02 basieren, nicht auf laufender KW
        if result:
            assert result["diese_woche"] == pytest.approx(1050.0, abs=1.0)


# ─────────────────────────────────────────────────────────────────────────────
# calc_vormonats_delta
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCalcVormonatsDelta:
    def test_deltas_werden_berechnet(self):
        user = UserFactory()
        aktuell = KoerperWerteFactory(user=user, gewicht=Decimal("80.0"))
        vormonat = KoerperWerteFactory(user=user, gewicht=Decimal("82.0"))
        result = calc_vormonats_delta(aktuell, vormonat)
        assert result["gewicht"] == pytest.approx(-2.0, abs=0.2)

    def test_gleicher_wert_gibt_none(self):
        user = UserFactory()
        aktuell = KoerperWerteFactory(user=user, gewicht=Decimal("80.0"))
        vormonat = KoerperWerteFactory(user=user, gewicht=Decimal("80.0"))
        result = calc_vormonats_delta(aktuell, vormonat)
        assert result["gewicht"] is None


# ─────────────────────────────────────────────────────────────────────────────
# collect_intensity_data
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCollectIntensityData:
    def test_keine_rpe_daten(self):
        user = UserFactory()
        einheit = TrainingseinheitFactory(user=user)
        uebung = UebungFactory()
        # Satz ohne RPE
        SatzFactory(einheit=einheit, uebung=uebung, rpe=None)
        from core.models import Satz

        alle_saetze = Satz.objects.filter(einheit__user=user)
        letzte_30_tage = (timezone.now() - timedelta(days=30)).date()
        avg_rpe, verteilung = collect_intensity_data(alle_saetze, letzte_30_tage)
        assert avg_rpe == 0.0
        assert verteilung == {"leicht": 0, "mittel": 0, "schwer": 0}

    def test_mit_rpe_daten(self):
        user = UserFactory()
        heute = timezone.now()
        einheit = TrainingseinheitFactory(user=user, datum=heute)
        uebung = UebungFactory()
        SatzFactory(einheit=einheit, uebung=uebung, rpe=Decimal("5.0"))  # leicht
        SatzFactory(einheit=einheit, uebung=uebung, rpe=Decimal("7.0"))  # mittel
        SatzFactory(einheit=einheit, uebung=uebung, rpe=Decimal("9.0"))  # schwer
        from core.models import Satz

        alle_saetze = Satz.objects.filter(einheit__user=user)
        letzte_30_tage = (heute - timedelta(days=30)).date()
        avg_rpe, verteilung = collect_intensity_data(alle_saetze, letzte_30_tage)
        assert avg_rpe > 0.0
        assert verteilung["leicht"] == 1
        assert verteilung["mittel"] == 1
        assert verteilung["schwer"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# build_top_uebungen
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestBuildTopUebungen:
    def test_ohne_active_filter(self):
        user = UserFactory()
        uebung = UebungFactory(muskelgruppe="BRUST")
        einheit = TrainingseinheitFactory(user=user)
        for _ in range(3):
            SatzFactory(einheit=einheit, uebung=uebung)
        from core.models import Satz

        alle_saetze = Satz.objects.filter(einheit__user=user)
        result = build_top_uebungen(alle_saetze, {"BRUST": "Brust"})
        assert len(result) >= 1
        assert result[0]["uebung__bezeichnung"] == uebung.bezeichnung

    def test_mit_active_uebung_ids_filter(self):
        user = UserFactory()
        uebung1 = UebungFactory(bezeichnung="Übung Filter 1")
        uebung2 = UebungFactory(bezeichnung="Übung Filter 2")
        einheit = TrainingseinheitFactory(user=user)
        for _ in range(3):
            SatzFactory(einheit=einheit, uebung=uebung1)
            SatzFactory(einheit=einheit, uebung=uebung2)
        from core.models import Satz

        alle_saetze = Satz.objects.filter(einheit__user=user)
        # Nur uebung1 filtern
        result = build_top_uebungen(alle_saetze, {}, active_uebung_ids={uebung1.id})
        names = [r["uebung__bezeichnung"] for r in result]
        assert uebung1.bezeichnung in names
        assert uebung2.bezeichnung not in names

    def test_leere_saetze(self):
        user = UserFactory()
        from core.models import Satz

        alle_saetze = Satz.objects.filter(einheit__user=user)
        result = build_top_uebungen(alle_saetze, {})
        assert result == []


# ─────────────────────────────────────────────────────────────────────────────
# collect_strength_progression
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCollectStrengthProgression:
    def _setup_saetze(self, user, uebung, n_sessions=5, start_gewicht=100):
        """Erstellt n_sessions Trainingseinheiten mit je 3 Sätzen, steigendes Gewicht."""
        heute = timezone.now()
        for i in range(n_sessions):
            datum = heute - timedelta(days=(n_sessions - 1 - i) * 7)
            einheit = TrainingseinheitFactory(user=user, datum=datum)
            gewicht = Decimal(str(start_gewicht + i * 2.5))
            for _ in range(3):
                SatzFactory(einheit=einheit, uebung=uebung, gewicht=gewicht)

    def test_backwards_compat(self):
        user = UserFactory()
        uebung = UebungFactory(muskelgruppe="BRUST")
        self._setup_saetze(user, uebung)
        from core.models import Satz

        alle_saetze = Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False)
        top_uebungen = [
            {
                "uebung__bezeichnung": uebung.bezeichnung,
                "uebung__muskelgruppe": uebung.muskelgruppe,
            }
        ]
        result = collect_strength_progression(alle_saetze, top_uebungen, {"BRUST": "Brust"})
        assert len(result) >= 1
        assert result[0]["mode_label"] == "Gesamt"

    def test_mit_plan_start_date(self):
        user = UserFactory()
        uebung = UebungFactory(muskelgruppe="BRUST")
        self._setup_saetze(user, uebung)
        from core.models import Satz

        alle_saetze = Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False)
        top_uebungen = [
            {
                "uebung__bezeichnung": uebung.bezeichnung,
                "uebung__muskelgruppe": uebung.muskelgruppe,
            }
        ]
        plan_start = (timezone.now() - timedelta(days=60)).date()
        result = collect_strength_progression(
            alle_saetze, top_uebungen, {"BRUST": "Brust"}, plan_start_date=plan_start
        )
        if result:
            assert result[0]["mode_label"] == "im aktuellen Plan"

    def test_mit_fallback_session_count(self):
        user = UserFactory()
        uebung = UebungFactory(muskelgruppe="BRUST")
        self._setup_saetze(user, uebung, n_sessions=6)
        from core.models import Satz

        alle_saetze = Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False)
        top_uebungen = [
            {
                "uebung__bezeichnung": uebung.bezeichnung,
                "uebung__muskelgruppe": uebung.muskelgruppe,
            }
        ]
        result = collect_strength_progression(
            alle_saetze, top_uebungen, {"BRUST": "Brust"}, fallback_session_count=5
        )
        if result:
            assert "Sessions" in result[0]["mode_label"]

    def test_zu_wenige_saetze_wird_uebersprungen(self):
        user = UserFactory()
        uebung = UebungFactory()
        einheit = TrainingseinheitFactory(user=user)
        SatzFactory(einheit=einheit, uebung=uebung)  # nur 1 Satz → zu wenig
        from core.models import Satz

        alle_saetze = Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False)
        top_uebungen = [
            {
                "uebung__bezeichnung": uebung.bezeichnung,
                "uebung__muskelgruppe": uebung.muskelgruppe,
            }
        ]
        result = collect_strength_progression(alle_saetze, top_uebungen, {})
        assert result == []


# ─────────────────────────────────────────────────────────────────────────────
# collect_muscle_balance
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCollectMuscleBalance:
    def test_leere_saetze_ergibt_alle_gruppen_als_nicht_trainiert(self):
        """Phase 35.2 (#1059 d): 0-Satz-Gruppen erscheinen mit Status
        'nicht_trainiert' in der Liste, statt komplett zu fehlen – vorher war
        der berechnete Status toter Code und die Schwachstellen-Auswahl sah
        nur trainierte Gruppen."""
        user = UserFactory()
        from core.models import Satz

        alle_saetze = Satz.objects.filter(einheit__user=user)
        letzte_30_tage = (timezone.now() - timedelta(days=30)).date()
        result = collect_muscle_balance(alle_saetze, letzte_30_tage, 0)
        assert result, "0-Satz-Gruppen müssen emittiert werden"
        assert all(r["saetze"] == 0 for r in result)
        assert all(r["status"] == "nicht_trainiert" for r in result)
        assert all(r["volumen"] == 0.0 and r["avg_rpe"] == 0.0 for r in result)

    def test_mit_saetzen(self):
        user = UserFactory()
        heute = timezone.now()
        uebung = UebungFactory(muskelgruppe="BRUST")
        einheit = TrainingseinheitFactory(user=user, datum=heute)
        for _ in range(15):
            SatzFactory(einheit=einheit, uebung=uebung, gewicht=Decimal("80.0"), rpe=Decimal("7.0"))
        from core.models import Satz

        alle_saetze = Satz.objects.filter(einheit__user=user)
        letzte_30_tage = (heute - timedelta(days=30)).date()
        result = collect_muscle_balance(alle_saetze, letzte_30_tage, 10)
        keys = [r["key"] for r in result]
        assert "BRUST" in keys
        # Phase 30.0: BRUST ist eine "gross"-Muskelgruppe → Schwelle (12, 25),
        # NICHT der frühere kaputte Default (12, 20).
        brust_entry = next(r for r in result if r["key"] == "BRUST")
        assert brust_entry["empfehlung_min"] == 12
        assert brust_entry["empfehlung_max"] == 25
        assert brust_entry["status"] == "optimal"  # 15 ist im Bereich [12, 25]

    def test_db_constants_resolve_to_size_specific_thresholds(self):
        """Phase 30.0 (Regressions-Test): jeder Größenklasse muss ihre eigene
        Schwelle bekommen – früher matchte EMPFOHLENE_SAETZE.get(...) nie und
        alle Gruppen erbten (12, 20) als Default.
        """
        user = UserFactory()
        heute = timezone.now()
        cases = [
            # (muskelgruppe, sätze, soll_min, soll_max, erwarteter_status)
            ("BRUST", 15, 12, 25, "optimal"),  # gross
            ("TRIZEPS", 20, 10, 18, "uebertrainiert"),  # mittel – früher fälschlich "optimal"
            ("BIZEPS", 8, 8, 16, "optimal"),  # klein – früher fälschlich "untertrainiert"
            ("HUEFTBEUGER", 9, 6, 12, "optimal"),  # haltung – früher fälschlich "untertrainiert"
        ]
        for i, (mg, n_saetze, _min, _max, _status) in enumerate(cases):
            uebung = UebungFactory(bezeichnung=f"X-{mg}", muskelgruppe=mg)
            einheit = TrainingseinheitFactory(user=user, datum=heute - timedelta(hours=i))
            for _ in range(n_saetze):
                SatzFactory(
                    einheit=einheit, uebung=uebung, gewicht=Decimal("40.0"), rpe=Decimal("7.0")
                )

        from core.models import Satz

        alle_saetze = Satz.objects.filter(einheit__user=user)
        letzte_30_tage = (heute - timedelta(days=30)).date()
        result = collect_muscle_balance(alle_saetze, letzte_30_tage, 10)
        by_key = {r["key"]: r for r in result}

        for mg, _n, soll_min, soll_max, soll_status in cases:
            assert mg in by_key, f"{mg} fehlt im Ergebnis"
            assert (
                by_key[mg]["empfehlung_min"] == soll_min
            ), f"{mg}: min sollte {soll_min} sein, war {by_key[mg]['empfehlung_min']}"
            assert (
                by_key[mg]["empfehlung_max"] == soll_max
            ), f"{mg}: max sollte {soll_max} sein, war {by_key[mg]['empfehlung_max']}"
            assert (
                by_key[mg]["status"] == soll_status
            ), f"{mg}: Status sollte {soll_status!r} sein, war {by_key[mg]['status']!r}"

    def test_ganzkoerper_wird_uebersprungen(self):
        """Phase 30.0: GANZKOERPER hat keinen sinnvollen Set-Schwellenwert
        (Cardio/Spezial) und wird im Set-basierten Balance-View übersprungen.
        """
        user = UserFactory()
        heute = timezone.now()
        uebung = UebungFactory(bezeichnung="Burpees", muskelgruppe="GANZKOERPER")
        einheit = TrainingseinheitFactory(user=user, datum=heute)
        for _ in range(5):
            SatzFactory(einheit=einheit, uebung=uebung, gewicht=Decimal("0.0"), rpe=Decimal("8.0"))
        from core.models import Satz

        alle_saetze = Satz.objects.filter(einheit__user=user)
        letzte_30_tage = (heute - timedelta(days=30)).date()
        result = collect_muscle_balance(alle_saetze, letzte_30_tage, 10)
        keys = [r["key"] for r in result]
        assert "GANZKOERPER" not in keys


# ─────────────────────────────────────────────────────────────────────────────
# Phase 24.1c: ``build_weekly_volume_overview`` und ``select_comparable_weeks``
# sind in ``core/utils/week_classification.py`` umgezogen – siehe
# ``core/tests/test_week_classification.py``.
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# collect_training_heatmap_data
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCollectTrainingHeatmapData:
    def test_ohne_rpe_bekommt_0_5(self):
        user = UserFactory()
        heute = timezone.now()
        einheit = TrainingseinheitFactory(user=user, datum=heute)
        uebung = UebungFactory()
        SatzFactory(einheit=einheit, uebung=uebung, rpe=None)
        from core.models import Satz, Trainingseinheit

        alle_trainings = Trainingseinheit.objects.filter(user=user)
        alle_saetze = Satz.objects.filter(einheit__user=user)
        result = collect_training_heatmap_data(alle_trainings, alle_saetze)
        assert len(result) == 1
        assert result[0]["intensitaet"] == 0.5

    def test_mit_rpe_berechnet_intensitaet(self):
        user = UserFactory()
        heute = timezone.now()
        einheit = TrainingseinheitFactory(user=user, datum=heute)
        uebung = UebungFactory()
        SatzFactory(einheit=einheit, uebung=uebung, rpe=Decimal("8.0"))
        from core.models import Satz, Trainingseinheit

        alle_trainings = Trainingseinheit.objects.filter(user=user)
        alle_saetze = Satz.objects.filter(einheit__user=user)
        result = collect_training_heatmap_data(alle_trainings, alle_saetze)
        assert len(result) == 1
        assert result[0]["intensitaet"] == pytest.approx(0.8, abs=0.01)


# ─────────────────────────────────────────────────────────────────────────────
# collect_exercise_detail_data
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCollectExerciseDetailData:
    def test_zu_wenig_verlauf_wird_uebersprungen(self):
        user = UserFactory()
        uebung = UebungFactory()
        einheit = TrainingseinheitFactory(user=user)
        SatzFactory(einheit=einheit, uebung=uebung, gewicht=Decimal("80.0"))
        from core.models import Satz

        alle_saetze = Satz.objects.filter(einheit__user=user)
        top = [
            {
                "uebung__bezeichnung": uebung.bezeichnung,
                "muskelgruppe_display": "Brust",
            }
        ]
        result = collect_exercise_detail_data(alle_saetze, top)
        # Nur 1 Datum → < 2 Verlaufs-Einträge → wird übersprungen
        assert result == []

    def test_mit_verlauf(self):
        user = UserFactory()
        uebung = UebungFactory()
        heute = timezone.now()
        for i in range(3):
            datum = heute - timedelta(days=i * 7)
            einheit = TrainingseinheitFactory(user=user, datum=datum)
            SatzFactory(
                einheit=einheit, uebung=uebung, gewicht=Decimal(str(80 + i * 5)), wiederholungen=8
            )
        from core.models import Satz

        alle_saetze = Satz.objects.filter(einheit__user=user)
        top = [
            {
                "uebung__bezeichnung": uebung.bezeichnung,
                "muskelgruppe_display": "Brust",
            }
        ]
        result = collect_exercise_detail_data(alle_saetze, top)
        assert len(result) == 1
        assert result[0]["uebung"] == uebung.bezeichnung
        assert len(result[0]["verlauf"]) >= 2


# ─────────────────────────────────────────────────────────────────────────────
# sum_volume
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSumVolume:
    def test_volumen_wird_berechnet(self):
        user = UserFactory()
        uebung = UebungFactory(gewichts_typ="GESAMT")
        einheit = TrainingseinheitFactory(user=user)
        SatzFactory(einheit=einheit, uebung=uebung, gewicht=Decimal("100.0"), wiederholungen=10)
        from core.models import Satz

        alle_saetze = Satz.objects.filter(einheit__user=user)
        vol = sum_volume(alle_saetze)
        assert vol > 0

    def test_leere_saetze_gibt_null(self):
        user = UserFactory()
        from core.models import Satz

        alle_saetze = Satz.objects.filter(einheit__user=user)
        vol = sum_volume(alle_saetze)
        assert vol == 0.0
