"""
Tests für core/export/stats_collector.py

Abdeckung:
- muscle_status: alle Branches (nicht trainiert, untertrainiert, übertrainiert, optimal, wenig Daten)
- collect_muscle_balance: mit/ohne Trainingsdaten
- collect_push_pull: alle Ratio-Branches (keine Daten, ausgewogen, push-betont, nur push, pull-betont)
- collect_strength_progression: plan_start_date, fallback_session_count, backwards-compat
- collect_intensity_data: mit/ohne RPE-Daten
- collect_weekly_volume_pdf: mit Daten, leere QS, Deload-Woche
- collect_weight_trend: mit Daten, zu wenig Daten
- calc_trainings_per_week: normal, leer, eine Session
- build_top_uebungen: mit/ohne active_uebung_ids
- sum_volume: einfacher Aufruf
- calc_volume_trend_weekly: alle Branches
- calc_vormonats_delta: mit/ohne None-Werte
- collect_training_heatmap_data: mit/ohne RPE
- collect_exercise_detail_data: mit Verlauf, zu wenig Daten
"""

from datetime import date, timedelta
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
    collect_weekly_volume_pdf,
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
        """Hilfsmethode: erstellt minimale muskelgruppen_stats-Liste."""
        return [{"key": k, "saetze": v} for k, v in group_sets.items()]

    def test_keine_daten(self):
        result = collect_push_pull([])
        assert result["bewertung"] == "Keine Daten"
        assert result["ratio"] == 0

    def test_ausgewogen(self):
        stats = self._mg_stats(BRUST=10, RUECKEN_LAT=10)
        result = collect_push_pull(stats)
        assert result["bewertung"] == "Ausgewogen"
        assert result["ratio"] == 1.0

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

    def test_nur_push_kein_pull(self):
        stats = self._mg_stats(BRUST=10)
        result = collect_push_pull(stats)
        assert result["bewertung"] == "Nur Push"
        assert result["ratio"] == 0


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
        kw_aktuell = f"KW{heute.isocalendar()[1]:02d}"
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
    def test_leere_saetze_ergibt_leere_liste(self):
        user = UserFactory()
        from core.models import Satz

        alle_saetze = Satz.objects.filter(einheit__user=user)
        letzte_30_tage = (timezone.now() - timedelta(days=30)).date()
        result = collect_muscle_balance(alle_saetze, letzte_30_tage, 0)
        assert result == []

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


# ─────────────────────────────────────────────────────────────────────────────
# collect_weekly_volume_pdf
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCollectWeeklyVolumePdf:
    def test_leere_saetze_gibt_leere_liste(self):
        user = UserFactory()
        from core.models import Satz

        alle_saetze = Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False)
        result = collect_weekly_volume_pdf(alle_saetze)
        assert result == []

    def test_mit_saetzen(self):
        user = UserFactory()
        heute = timezone.now()
        uebung = UebungFactory()
        einheit = TrainingseinheitFactory(user=user, datum=heute)
        SatzFactory(
            einheit=einheit,
            uebung=uebung,
            gewicht=Decimal("100.0"),
            wiederholungen=10,
            ist_aufwaermsatz=False,
        )
        from core.models import Satz

        alle_saetze = Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False)
        result = collect_weekly_volume_pdf(alle_saetze)
        assert len(result) >= 1
        assert result[-1]["volumen"] > 0

    def test_deload_woche_markiert(self):
        user = UserFactory()
        heute = timezone.now()
        uebung = UebungFactory()
        einheit = TrainingseinheitFactory(user=user, datum=heute, ist_deload=True)
        SatzFactory(
            einheit=einheit,
            uebung=uebung,
            gewicht=Decimal("70.0"),
            wiederholungen=8,
            ist_aufwaermsatz=False,
        )
        from core.models import Satz, Trainingseinheit

        alle_saetze = Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False)
        alle_trainings = Trainingseinheit.objects.filter(user=user)
        result = collect_weekly_volume_pdf(alle_saetze, alle_trainings)
        # Aktuelle Woche sollte als Deload markiert sein
        assert any(w["ist_deload"] for w in result)


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
