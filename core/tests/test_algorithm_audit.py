"""
Tests für Phase 5.0 – Algorithm Audit & Correction.

Testet explizit die korrigierten Algorithmen:
1. Plateau-Detection: muss Rep-PRs als Fortschritt erkennen (1RM-Basis)
2. Junk-Volume: Aufwärmsätze dürfen nicht gewertet werden
3. Push/Pull: mehr Pull als Push darf KEINE Warnung auslösen
4. 1RM-Skalierung: allometrisch, nicht linear
"""

from decimal import Decimal
from datetime import timedelta

from django.urls import reverse

import pytest

from core.utils.advanced_stats import calculate_plateau_analysis, calculate_rpe_quality_analysis

from .factories import SatzFactory, TrainingseinheitFactory, UebungFactory, UserFactory


@pytest.mark.django_db
class TestPlateauDetectionUsesOneRM:
    """Plateau-Detection muss Fortschritt durch Wiederholungssteigerung erkennen."""

    def _satz_qs(self, saetze):
        """Hilfsmethode: QuerySet aus einer Liste von IDs."""
        from core.models import Satz

        return Satz.objects.filter(id__in=[s.id for s in saetze])

    def test_rep_increase_counts_as_progression(self):
        """
        Szenario: User macht Fortschritt durch Wdh.-Steigerung, nicht Gewichtssteigerung.
        Vor 30 Tagen: 100kg × 1 (1RM ≈ 103kg) → das war der Roh-Gewicht-PR.
        Heute:        80kg × 12 (1RM ≈ 112kg)  → echter Fortschritt im 1RM.

        Alter Code (Roh-Gewicht): PR = 100kg, tage_seit_pr = 30 → falsches "Plateau".
        Neuer Code (1RM-Basis): PR = 112kg (heute) → kein Plateau.
        """
        from datetime import timedelta

        from django.utils import timezone

        from core.models import Satz, Trainingseinheit

        user = UserFactory()
        uebung = UebungFactory()

        # 30 Tage alt: 100kg × 1 (1RM ≈ 103kg)
        einheit_alt = TrainingseinheitFactory(user=user)
        Trainingseinheit.objects.filter(id=einheit_alt.id).update(
            datum=timezone.now() - timedelta(days=30)
        )
        einheit_alt.refresh_from_db()
        satz_alt = SatzFactory(
            einheit=einheit_alt, uebung=uebung, gewicht=Decimal("100"), wiederholungen=1
        )

        # Heute: 80kg × 12 (1RM ≈ 112kg) – besser im 1RM, aber schlechteres Roh-Gewicht
        einheit_neu = TrainingseinheitFactory(user=user)
        satz_neu = SatzFactory(
            einheit=einheit_neu, uebung=uebung, gewicht=Decimal("80"), wiederholungen=12
        )

        alle_saetze = Satz.objects.filter(id__in=[satz_alt.id, satz_neu.id])
        top_uebungen = [{"uebung__bezeichnung": uebung.bezeichnung, "muskelgruppe_display": ""}]

        ergebnisse = calculate_plateau_analysis(alle_saetze, top_uebungen)
        assert len(ergebnisse) == 1
        result = ergebnisse[0]

        # Neuer Code: PR = heute (1RM 112 > 103), tage_seit_pr = 0 → kein Plateau
        assert result["tage_seit_pr"] <= 1, (
            f"1RM-Fortschritt (80×12 > 100×1 im 1RM) wurde nicht als PR erkannt. "
            f"tage_seit_pr={result['tage_seit_pr']} (erwartet: 0)"
        )
        assert (
            "plateau" not in result["status"]
        ), f"Falsches Plateau bei echtem 1RM-Fortschritt. Status: {result['status']}"

    def test_weight_decrease_with_more_reps_correctly_classified(self):
        """
        Wenn Gewicht und 1RM beide sinken → PR liegt in der Vergangenheit.
        Hinweis: datum ist auto_now_add → nach Erstellung per update() setzen.
        """
        from datetime import timedelta

        from django.utils import timezone

        from core.models import Satz, Trainingseinheit

        user = UserFactory()
        uebung = UebungFactory()

        # PR vor 30 Tagen – Datum nach Erstellung setzen (auto_now_add umgehen)
        einheit_alt = TrainingseinheitFactory(user=user)
        Trainingseinheit.objects.filter(id=einheit_alt.id).update(
            datum=timezone.now() - timedelta(days=30)
        )
        einheit_alt.refresh_from_db()
        satz_alt = SatzFactory(
            einheit=einheit_alt, uebung=uebung, gewicht=Decimal("100"), wiederholungen=5
        )

        # Heute: 70kg × 5 – klar schlechterer 1RM
        einheit_neu = TrainingseinheitFactory(user=user)
        satz_neu = SatzFactory(
            einheit=einheit_neu, uebung=uebung, gewicht=Decimal("70"), wiederholungen=5
        )

        alle_saetze = Satz.objects.filter(id__in=[satz_alt.id, satz_neu.id])
        top_uebungen = [{"uebung__bezeichnung": uebung.bezeichnung, "muskelgruppe_display": ""}]

        ergebnisse = calculate_plateau_analysis(alle_saetze, top_uebungen)
        assert len(ergebnisse) == 1
        # PR (100kg × 5 = 1RM ~117kg) liegt vor 30 Tagen → tage_seit_pr ~30
        assert (
            ergebnisse[0]["tage_seit_pr"] >= 25
        ), f"Erwartet PR aus der Vergangenheit, aber tage_seit_pr={ergebnisse[0]['tage_seit_pr']}"


@pytest.mark.django_db
class TestJunkVolumeExcludesWarmup:
    """Aufwärmsätze dürfen nicht als Junk Volume gezählt werden."""

    def test_warmup_sets_excluded_from_rpe_analysis(self):
        """
        Wenn alle RPE-Sätze Aufwärmsätze sind, soll rpe_quality_analysis None zurückgeben
        (kein Material für Analyse), statt sie als Junk Volume zu werten.
        """
        from core.models import Satz

        user = UserFactory()
        uebung = UebungFactory()
        einheit = TrainingseinheitFactory(user=user)

        # Nur Aufwärmsätze mit niedrigem RPE
        saetze = []
        for _ in range(5):
            s = SatzFactory(
                einheit=einheit,
                uebung=uebung,
                rpe=5.0,
                wiederholungen=10,
                ist_aufwaermsatz=True,  # explizit Aufwärmen
            )
            saetze.append(s)

        alle_saetze = Satz.objects.filter(id__in=[s.id for s in saetze])
        result = calculate_rpe_quality_analysis(alle_saetze)

        # Wenn nur Aufwärmsätze → keine Arbeitssätze mit RPE → None
        assert result is None, (
            "Aufwärmsätze wurden fälschlicherweise als Arbeitssätze gewertet. "
            f"Ergebnis: {result}"
        )

    def test_mixed_warmup_and_working_sets_only_counts_working(self):
        """
        Mischung aus Aufwärm- und Arbeitssätzen: nur Arbeitssätze fließen ein.
        """
        from core.models import Satz

        user = UserFactory()
        uebung = UebungFactory()
        einheit = TrainingseinheitFactory(user=user)

        # 3 Aufwärmsätze RPE 5 (würden Junk-Quote erhöhen)
        warmup_saetze = [
            SatzFactory(
                einheit=einheit, uebung=uebung, rpe=5.0, wiederholungen=10, ist_aufwaermsatz=True
            )
            for _ in range(3)
        ]

        # 5 Arbeitssätze RPE 8 (optimal)
        arbeits_saetze = [
            SatzFactory(
                einheit=einheit, uebung=uebung, rpe=8.0, wiederholungen=8, ist_aufwaermsatz=False
            )
            for _ in range(5)
        ]

        alle_ids = [s.id for s in warmup_saetze + arbeits_saetze]
        alle_saetze = Satz.objects.filter(id__in=alle_ids)
        result = calculate_rpe_quality_analysis(alle_saetze)

        assert result is not None
        # Nur die 5 Arbeitssätze (RPE 8) → optimal_intensity_rate sollte 100% sein
        assert (
            result["gesamt_saetze"] == 5
        ), f"Aufwärmsätze wurden mitgezählt. gesamt_saetze={result['gesamt_saetze']} (erwartet: 5)"
        assert (
            result["junk_volume_rate"] == 0.0
        ), f"Aufwärmsätze fälschlicherweise als Junk Volume gezählt: {result['junk_volume_rate']}%"


@pytest.mark.django_db
class TestPushPullRatioFix:
    """Pull > Push darf keine negative Empfehlung auslösen."""

    def test_more_pull_than_push_no_warning(self, client):
        """
        Wenn Pull-Volumen deutlich größer als Push → KEINE Warnung.
        Mehr Pull als Push ist für Schultergesundheit positiv.
        """
        user = UserFactory()
        client.force_login(user)

        ruecken_uebung = UebungFactory(muskelgruppe="RUECKEN_LAT")
        einheit = TrainingseinheitFactory(user=user)

        # Viel Pull, kaum Push
        for _ in range(10):
            SatzFactory(
                einheit=einheit,
                uebung=ruecken_uebung,
                ist_aufwaermsatz=False,
                rpe=8.0,
                wiederholungen=10,
            )

        url = reverse("workout_recommendations")
        response = client.get(url)
        assert response.status_code == 200

        empfehlungen = response.context.get("empfehlungen", [])
        balance_empfehlungen = [e for e in empfehlungen if e.get("typ") == "balance"]

        # Keine Empfehlung "mehr Push trainieren"
        for emp in balance_empfehlungen:
            assert (
                "push" not in emp.get("empfehlung", "").lower()
                or "pull" in emp.get("empfehlung", "").lower()
            ), f"Falsche Empfehlung bei Pull-Dominanz: {emp.get('empfehlung')}"

    def test_more_push_than_pull_triggers_warning(self, client):
        """Wenn Push deutlich größer als Pull (ratio > 1.5) → Warnung wird ausgelöst."""
        user = UserFactory()
        client.force_login(user)

        brust_uebung = UebungFactory(muskelgruppe="BRUST")
        ruecken_uebung = UebungFactory(muskelgruppe="RUECKEN_LAT")
        einheit = TrainingseinheitFactory(user=user)

        # Viel Push
        for _ in range(10):
            SatzFactory(
                einheit=einheit,
                uebung=brust_uebung,
                ist_aufwaermsatz=False,
                rpe=8.0,
                wiederholungen=10,
            )
        # Wenig Pull
        for _ in range(2):
            SatzFactory(
                einheit=einheit,
                uebung=ruecken_uebung,
                ist_aufwaermsatz=False,
                rpe=8.0,
                wiederholungen=10,
            )

        url = reverse("workout_recommendations")
        response = client.get(url)
        assert response.status_code == 200

        empfehlungen = response.context.get("empfehlungen", [])
        typen = [e.get("typ") for e in empfehlungen]
        # Bei ratio > 1.5 (Push >> Pull) soll eine "balance"-Empfehlung erscheinen
        assert (
            "balance" in typen
        ), "Keine Balance-Warnung bei deutlichem Push-Übergewicht (10:2 Push:Pull)"


@pytest.mark.django_db
class TestAllometricScaling:
    """1RM-Standards-Skalierung muss allometrisch (2/3-Potenz) sein, nicht linear."""

    def test_scaling_is_sublinear(self):
        """
        Schwererer User bekommt NICHT proportional höhere Standards.
        80kg → 120kg (1.5×) soll Standards um < 1.5× erhöhen (typisch ~1.31× bei 2/3-Potenz).
        """
        from core.models import Satz, Uebung
        from core.utils.advanced_stats import calculate_1rm_standards

        user = UserFactory()
        uebung = UebungFactory()

        # Setze Standards am Uebungs-Objekt (direkt, ohne Fixtures)
        Uebung.objects.filter(id=uebung.id).update(
            standard_beginner=60,
            standard_intermediate=100,
            standard_advanced=140,
            standard_elite=180,
        )
        uebung.refresh_from_db()

        einheit = TrainingseinheitFactory(user=user)
        satz = SatzFactory(einheit=einheit, uebung=uebung, gewicht=Decimal("80"), wiederholungen=5)

        alle_saetze = Satz.objects.filter(id=satz.id)
        top_uebungen = [{"uebung__bezeichnung": uebung.bezeichnung, "muskelgruppe_display": ""}]

        # Bei 80kg (Baseline) → scaling_factor = 1.0 → Standards unveränder
        result_80 = calculate_1rm_standards(alle_saetze, top_uebungen, user_gewicht=80)
        # Bei 120kg → scaling_factor sollte (120/80)^(2/3) ≈ 1.31 sein, nicht 1.5
        result_120 = calculate_1rm_standards(alle_saetze, top_uebungen, user_gewicht=120)

        if not result_80 or not result_120:
            pytest.skip("Keine Standards verfügbar – Test nicht anwendbar")

        beginner_80 = result_80[0]["standard_info"]["alle_levels"]["Anfänger"]
        beginner_120 = result_120[0]["standard_info"]["alle_levels"]["Anfänger"]

        actual_ratio = beginner_120 / beginner_80
        linear_ratio = 120 / 80  # = 1.5

        # Allometrische Skalierung (2/3-Potenz): (120/80)^(2/3) ≈ 1.31
        expected_allometric = (120 / 80) ** (2 / 3)

        assert (
            actual_ratio < linear_ratio
        ), f"Skalierung ist noch linear! Ratio: {actual_ratio:.3f}, linear wäre: {linear_ratio:.3f}"
        assert abs(actual_ratio - expected_allometric) < 0.01, (
            f"Allometrischer Exponent stimmt nicht. "
            f"Erwartet: {expected_allometric:.3f}, Erhalten: {actual_ratio:.3f}"
        )


@pytest.mark.django_db
class TestAdherenceRateNeverExceedsHundred:
    """
    Regression: adherence_rate darf nie > 100% sein.

    Bug: wochen_gesamt verwendete `days // 7` (Ganzzahl-Division),
    wochen_mit_training zählte Django-Kalenderwochen (ISO-Wochen).
    Trainings die eine Wochengrenzen überbrücken erzeugten Nenner < Zähler.

    Beispiel-Szenario das den Bug auslöste:
    - Erstes Training: Donnerstag (vor 3 Tagen)
    - Zweites Training: heute (Sonntag, neue Kalenderwoche)
    - days = 3 → days // 7 = 0 → max(1, 0) = 1 Woche (Nenner)
    - Django dates("datum", "week") = 2 Kalenderwochen (Zähler)
    → Ergebnis: 2/1 * 100 = 200%
    """

    def test_adherence_never_exceeds_100_percent(self):
        """
        Trainings über Wochengrenzen dürfen nicht zu > 100% führen.
        Wir erstellen Trainings die definitiv mehr Kalenderwochen
        als die `days // 7`-Formel ergeben würde.
        """
        from django.utils import timezone

        from core.utils.advanced_stats import calculate_consistency_metrics

        user = UserFactory()

        # Trainings in 5 verschiedenen Kalenderwochen über 8 Wochen
        heute = timezone.now()
        offsets = [0, 7, 14, 21, 28]  # 5 Wochen, alle Montage
        for offset in offsets:
            datum = heute - timedelta(days=offset)
            TrainingseinheitFactory(user=user, datum=datum, abgeschlossen=True)

        from core.models import Trainingseinheit

        alle_trainings = Trainingseinheit.objects.filter(user=user)
        result = calculate_consistency_metrics(alle_trainings)

        assert result is not None
        assert (
            result["adherence_rate"] <= 100.0
        ), f"adherence_rate über 100%: {result['adherence_rate']}%"

    def test_adherence_cross_week_boundary(self):
        """
        Spezifisches Szenario: 2 Trainings, nur 3 Tage auseinander,
        aber in verschiedenen ISO-Kalenderwochen (z.B. Do → So).
        Das Ergebnis muss ≤ 100% sein.
        """
        from django.utils import timezone

        from core.utils.advanced_stats import calculate_consistency_metrics

        user = UserFactory()
        heute = timezone.now()

        # Montag der aktuellen Woche
        montag_heute = heute - timedelta(days=heute.weekday())
        # Donnerstag der Vorwoche (= 4 Tage vor diesem Montag)
        donnerstag_vorwoche = montag_heute - timedelta(days=4)

        TrainingseinheitFactory(user=user, datum=donnerstag_vorwoche, abgeschlossen=True)
        TrainingseinheitFactory(user=user, datum=heute, abgeschlossen=True)

        from core.models import Trainingseinheit

        alle_trainings = Trainingseinheit.objects.filter(user=user)
        result = calculate_consistency_metrics(alle_trainings)

        assert result is not None
        assert (
            result["adherence_rate"] <= 100.0
        ), f"Wochengrenzfall: adherence_rate = {result['adherence_rate']}% (>100% ist ein Bug)"

    def test_adherence_single_training_returns_valid_value(self):
        """Ein einziges Training darf keine Division-by-Zero oder > 100% erzeugen."""
        from django.utils import timezone

        from core.utils.advanced_stats import calculate_consistency_metrics

        user = UserFactory()
        TrainingseinheitFactory(user=user, datum=timezone.now(), abgeschlossen=True)

        from core.models import Trainingseinheit

        alle_trainings = Trainingseinheit.objects.filter(user=user)
        result = calculate_consistency_metrics(alle_trainings)

        assert result is not None
        assert 0.0 <= result["adherence_rate"] <= 100.0


@pytest.mark.django_db
class TestOneRMMonthWindowFix:
    """Regression: 1RM-Monatsentwicklung darf aktuellen Monat nicht als leer zeigen.

    Bug: Formel `30 * (5 - i)` ergab für den letzten Slot i=5:
         monat_start = heute, monat_ende = heute + 30 → Zukunft, keine Daten.
    Fix: `30 * (6 - i)` → letzter Slot = heute-30 bis heute.
    """

    def test_current_month_pr_shows_in_last_slot(self):
        """Ein PR von heute muss im letzten 1RM-Entwicklungs-Eintrag erscheinen."""
        from datetime import date

        from core.models import Satz
        from core.utils.advanced_stats import calculate_1rm_standards

        user = UserFactory()
        uebung = UebungFactory(
            bezeichnung="Bugfix-Testübung",
            standard_beginner=Decimal("60.0"),
            standard_intermediate=Decimal("100.0"),
            standard_advanced=Decimal("140.0"),
            standard_elite=Decimal("180.0"),
        )
        einheit = TrainingseinheitFactory(user=user, datum=date.today(), abgeschlossen=True)
        SatzFactory(
            einheit=einheit,
            uebung=uebung,
            gewicht=Decimal("80.0"),
            wiederholungen=5,
            ist_aufwaermsatz=False,
        )

        alle_saetze = Satz.objects.filter(einheit__user=user)
        top_uebungen = [{"uebung__bezeichnung": uebung.bezeichnung}]

        result = calculate_1rm_standards(alle_saetze, top_uebungen, user_gewicht=None)

        assert len(result) == 1, "Kein Ergebnis für Übung mit Standards"
        entwicklung = result[0]["1rm_entwicklung"]
        assert len(entwicklung) == 6, "Entwicklungsliste muss 6 Einträge haben"

        # Letzter Slot muss den heutigen PR enthalten (nicht None)
        letzter_slot = entwicklung[-1]
        assert letzter_slot["1rm"] is not None, (
            f"Letzter Slot '{letzter_slot['monat']}' sollte heutigen PR enthalten, ist aber None. "
            f"Bug: Monats-Fenster schaut in die Zukunft statt in die letzten 30 Tage."
        )
        # Letzter Slot sollte aktuellen Monatsnamen tragen
        import calendar

        erwarteter_monat = calendar.month_abbr[date.today().month]
        assert (
            letzter_slot["monat"] == erwarteter_monat
        ), f"Letzter Slot zeigt '{letzter_slot['monat']}', erwartet '{erwarteter_monat}'"
