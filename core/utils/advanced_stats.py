"""
Advanced Training Statistics - Helper Functions
Provides comprehensive analysis for training progression, consistency, and performance.
"""

from datetime import timedelta

from django.utils import timezone


def calculate_plateau_analysis(alle_saetze, top_uebungen):
    """
    Analyzes progression for top exercises to detect plateaus.

    Returns list with:
    - uebung: Exercise name
    - letzter_pr: Last personal record weight
    - pr_datum: Date of last PR
    - tage_seit_pr: Days since last PR
    - progression_pro_monat: Average weight increase per month
    - status: 'progression' / 'plateau' / 'regression'
    - muskelgruppe: Muscle group
    """
    heute = timezone.now()
    vier_wochen = heute - timedelta(days=28)

    plateau_analysis = []

    for uebung in top_uebungen[:5]:
        uebung_name = uebung["uebung__bezeichnung"]
        muskelgruppe = uebung.get("muskelgruppe_display", "")

        # Alle Sätze dieser Übung chronologisch
        uebung_saetze = alle_saetze.filter(uebung__bezeichnung=uebung_name).order_by(
            "einheit__datum"
        )

        if uebung_saetze.count() < 2:
            continue

        # PR auf Basis des geschätzten 1RM (Epley-Formel: Gewicht × (1 + Wdh/30))
        # Korrekte Methode: Roh-Gewicht allein ignoriert Rep-Steigerungen als Fortschritt.
        # Wer 80kg × 8 → 80kg × 12 steigert (1RM: 101 → 112 kg) hat echten Fortschritt.
        bester_1rm = 0.0
        bester_1rm_satz = None

        for satz in uebung_saetze.filter(gewicht__isnull=False):
            wdh = satz.wiederholungen or 1
            einzel_1rm = float(satz.gewicht) * (1 + wdh / 30.0)
            if einzel_1rm > bester_1rm:
                bester_1rm = einzel_1rm
                bester_1rm_satz = satz

        if not bester_1rm_satz:
            continue

        letzter_pr = round(bester_1rm, 1)
        pr_datum = bester_1rm_satz.einheit.datum
        tage_seit_pr = (heute.date() - pr_datum.date()).days

        # Berechne durchschnittliche Progression pro Monat (auf 1RM-Basis)
        erster_satz = uebung_saetze.filter(gewicht__isnull=False).order_by("einheit__datum").first()
        if erster_satz and erster_satz.gewicht:
            erstes_1rm = float(erster_satz.gewicht) * (1 + (erster_satz.wiederholungen or 1) / 30.0)
            tage_gesamt = (pr_datum.date() - erster_satz.einheit.datum.date()).days

            if tage_gesamt > 0:
                gewichtsdiff = letzter_pr - erstes_1rm
                progression_pro_monat = round((gewichtsdiff / tage_gesamt) * 30, 2)
            else:
                progression_pro_monat = 0
        else:
            progression_pro_monat = 0

        # RPE-Trend prüfen: sinkender RPE bei gleichem Gewicht = Konsolidierung (kein Plateau)
        # Vergleiche Durchschnitts-RPE der ersten vs. letzten Hälfte der letzten 4 Wochen
        rpe_trend_sinkend = False
        letzte_4w_saetze = uebung_saetze.filter(
            einheit__datum__gte=vier_wochen, gewicht__isnull=False, rpe__isnull=False
        ).order_by("einheit__datum")

        if letzte_4w_saetze.count() >= 4:
            rpe_werte = [float(s.rpe) for s in letzte_4w_saetze]
            mitte = len(rpe_werte) // 2
            avg_rpe_frueh = sum(rpe_werte[:mitte]) / mitte
            avg_rpe_spaet = sum(rpe_werte[mitte:]) / len(rpe_werte[mitte:])
            # RPE sinkt um mindestens 0.5 → Konsolidierung
            if avg_rpe_frueh - avg_rpe_spaet >= 0.5:
                rpe_trend_sinkend = True

        # Status bestimmen
        if tage_seit_pr <= 7:
            # Weniger als 1 Woche - noch zu früh für Bewertung
            if progression_pro_monat > 0:
                status = "progression"
                status_label = "✅ Aktive Progression"
                status_farbe = "success"
            else:
                status = "zu_frueh"
                status_label = "⏳ Zu früh zu bewerten"
                status_farbe = "info"
        elif tage_seit_pr <= 14:
            # 1-2 Wochen
            if progression_pro_monat > 0:
                status = "progression"
                status_label = "✅ Aktive Progression"
                status_farbe = "success"
            else:
                status = "beobachten"
                status_label = "👀 Beobachten"
                status_farbe = "info"
        elif rpe_trend_sinkend:
            # Gewicht stagniert, aber RPE sinkt → User wird stärker
            status = "konsolidierung"
            status_label = "💪 Konsolidierung (RPE sinkt)"
            status_farbe = "info"
        elif tage_seit_pr <= 42:  # 2-6 Wochen
            status = "plateau_leicht"
            status_label = "⚠️ Leichtes Plateau"
            status_farbe = "warning"
        elif tage_seit_pr <= 84:  # 6-12 Wochen
            status = "plateau"
            status_label = "🔴 Plateau"
            status_farbe = "danger"
        else:
            status = "plateau_lang"
            status_label = "❌ Langzeit-Plateau"
            status_farbe = "danger"

        # Prüfe auf Regression: aktueller 1RM (letzte 4 Wochen) vs. bester je 1RM
        letzte_4_wochen = uebung_saetze.filter(
            einheit__datum__gte=vier_wochen, gewicht__isnull=False
        )

        if letzte_4_wochen.exists():
            aktueller_1rm = max(
                float(s.gewicht) * (1 + (s.wiederholungen or 1) / 30.0) for s in letzte_4_wochen
            )
            if aktueller_1rm < letzter_pr * 0.9:  # >10% Rückgang im 1RM
                status = "regression"
                status_label = "⚠️ Rückschritt"
                status_farbe = "danger"

        plateau_analysis.append(
            {
                "uebung": uebung_name,
                "muskelgruppe": muskelgruppe,
                "letzter_pr": letzter_pr,
                "pr_datum": pr_datum.strftime("%d.%m.%Y"),
                "tage_seit_pr": tage_seit_pr,
                "progression_pro_monat": progression_pro_monat,
                "status": status,
                "status_label": status_label,
                "status_farbe": status_farbe,
            }
        )

    return plateau_analysis


def calculate_consistency_metrics(alle_trainings):
    """
    Calculates training consistency metrics including streaks and adherence.

    Returns dict with:
    - aktueller_streak: Current weeks with training
    - laengster_streak: Longest streak ever
    - adherence_rate: % of weeks with training
    - avg_pause_tage: Average days between sessions
    - bewertung: Overall consistency rating
    """
    if not alle_trainings.exists():
        return None

    heute = timezone.now()

    # Streak berechnen (aufeinanderfolgende Wochen mit mindestens 1 Training)
    aktueller_streak = 0
    laengster_streak = 0
    temp_streak = 0
    aktueller_streak_aktiv = True  # Flag ob wir noch im aktuellen Streak sind

    check_date = heute
    wochen_geprueft = 0

    while wochen_geprueft < 104:  # Max 2 Jahre zurück
        iso_weekday = check_date.isoweekday()
        week_start = check_date - timedelta(days=iso_weekday - 1)
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7)

        trainings_in_week = alle_trainings.filter(datum__gte=week_start, datum__lt=week_end).count()

        if trainings_in_week > 0:
            temp_streak += 1
            if temp_streak > laengster_streak:
                laengster_streak = temp_streak
            # Aktueller Streak: Nur Wochen die direkt zusammenhängen bis heute
            if aktueller_streak_aktiv:
                aktueller_streak = temp_streak
        else:
            # Streak unterbrochen
            if aktueller_streak_aktiv:
                # Erste Lücke = aktueller Streak endet hier
                aktueller_streak_aktiv = False
            temp_streak = 0

        # Gehe 1 Woche zurück
        check_date = week_start - timedelta(days=1)
        wochen_geprueft += 1

    # Adherence Rate: % der Wochen mit Training
    # WICHTIG: Zähler (wochen_mit_training) und Nenner (wochen_gesamt) müssen
    # dieselbe Einheit verwenden – beide basieren auf ISO-Kalenderwochen.
    # Vorher: wochen_gesamt = days // 7 (Ganzzahl-Division) vs. Django-Kalenderwochen
    # → führte zu Adherence > 100% wenn Trainings Wochengrenzen überbrücken.
    erste_training = alle_trainings.order_by("datum").first()
    if erste_training:
        erste_datum = erste_training.datum.date()
        heute_datum = heute.date()
        # Montag der Startwoche und Montag der aktuellen Woche
        erste_woche_montag = erste_datum - timedelta(days=erste_datum.weekday())
        heute_woche_montag = heute_datum - timedelta(days=heute_datum.weekday())
        # Anzahl Kalenderwochen inklusiv Start- und Endwoche
        wochen_gesamt = max(1, ((heute_woche_montag - erste_woche_montag).days // 7) + 1)
        wochen_mit_training = alle_trainings.dates("datum", "week").count()
        # min(100.0) als Sicherheitsnetz (darf nie über 100% liegen)
        adherence_rate = min(100.0, round((wochen_mit_training / wochen_gesamt) * 100, 1))
    else:
        adherence_rate = 0

    # Durchschnittliche Pause zwischen Trainings
    trainings_sorted = list(alle_trainings.order_by("datum").values_list("datum", flat=True))
    if len(trainings_sorted) > 1:
        pausen = []
        for i in range(1, len(trainings_sorted)):
            pause_tage = (trainings_sorted[i].date() - trainings_sorted[i - 1].date()).days
            pausen.append(pause_tage)
        avg_pause_tage = round(sum(pausen) / len(pausen), 1)
    else:
        avg_pause_tage = 0

    # Bewertung
    if aktueller_streak >= 12 and adherence_rate >= 85:
        bewertung = "🏆 Exzellent"
        bewertung_farbe = "success"
    elif aktueller_streak >= 8 and adherence_rate >= 70:
        bewertung = "✅ Sehr gut"
        bewertung_farbe = "success"
    elif aktueller_streak >= 4 and adherence_rate >= 60:
        bewertung = "👍 Gut"
        bewertung_farbe = "info"
    elif adherence_rate >= 40:
        bewertung = "⚠️ Ausbaufähig"
        bewertung_farbe = "warning"
    else:
        bewertung = "🔴 Inkonsistent"
        bewertung_farbe = "danger"

    return {
        "aktueller_streak": aktueller_streak,
        "laengster_streak": laengster_streak,
        "adherence_rate": adherence_rate,
        "avg_pause_tage": avg_pause_tage,
        "bewertung": bewertung,
        "bewertung_farbe": bewertung_farbe,
    }


def calculate_fatigue_index(weekly_volume_data, rpe_saetze, alle_trainings):
    """
    Calculates fatigue index and deload recommendations.

    Delegiert an die Dashboard-Helfer in training_stats.py (Phase 14 Konsolidierung),
    damit Dashboard und PDF-Export identische Fatigue-Berechnung verwenden.

    Die Dashboard-Version (Phase 9.4+) nutzt RPE-10-Verteilung statt einfachem
    RPE-Durchschnitt, berücksichtigt Cardio, und hat Block-Age-Awareness.

    Returns dict with:
    - fatigue_index, bewertung, bewertung_farbe, empfehlung
    - volumen_spike, rpe_steigend, deload_empfohlen
    - naechste_deload, warnungen
    """
    from core.views.training_stats import (
        _get_cardio_fatigue,
        _get_frequency_fatigue,
        _get_rpe_fatigue,
        _get_volume_spike_fatigue,
    )

    heute = timezone.now()

    # User aus QuerySet ableiten (alle_trainings ist user-gefiltert)
    user = None
    first_training = alle_trainings.first()
    if first_training:
        user = first_training.user

    fatigue_index = 0
    warnungen = []

    # Volumen-Spike: weekly_volume_data in Dashboard-Format konvertieren
    if len(weekly_volume_data) >= 2:
        dashboard_volumes = [{"volume": w.get("volumen", 0)} for w in reversed(weekly_volume_data)]
        pts, warns = _get_volume_spike_fatigue(dashboard_volumes)
        fatigue_index += pts
        warnungen.extend(warns)

    volumen_spike = fatigue_index > 0

    # RPE + Frequenz + Cardio: nutzen User-Objekt
    rpe_steigend = False
    if user and alle_trainings.count() >= 4:
        rpe_pts, rpe_warns = _get_rpe_fatigue(user, heute)
        fatigue_index += rpe_pts
        warnungen.extend(rpe_warns)
        rpe_steigend = rpe_pts > 0

        freq_pts, freq_warns = _get_frequency_fatigue(user, heute)
        fatigue_index += freq_pts
        warnungen.extend(freq_warns)

    if user:
        cardio_pts, cardio_warns, _, _ = _get_cardio_fatigue(user, heute)
        fatigue_index += cardio_pts
        warnungen.extend(cardio_warns)

    # Deload-Empfehlung + Bewertung (identisch mit Dashboard)
    deload_empfohlen = fatigue_index >= 50
    naechste_deload = heute + timedelta(weeks=6)

    if fatigue_index >= 60:
        bewertung = "🚨 Hoch"
        bewertung_farbe = "danger"
        empfehlung = "Deload-Woche empfohlen! Reduziere Volumen um 40-50%."
    elif fatigue_index >= 40:
        bewertung = "⚠️ Moderat"
        bewertung_farbe = "warning"
        empfehlung = "Achte auf ausreichend Regeneration."
    elif fatigue_index >= 20:
        bewertung = "ℹ️ Niedrig"
        bewertung_farbe = "info"
        empfehlung = "Gute Balance zwischen Training und Erholung."
    else:
        bewertung = "✅ Sehr niedrig"
        bewertung_farbe = "success"
        empfehlung = "Du kannst noch mehr trainieren!"

    return {
        "fatigue_index": fatigue_index,
        "volumen_spike": volumen_spike,
        "rpe_steigend": rpe_steigend,
        "deload_empfohlen": deload_empfohlen,
        "naechste_deload": naechste_deload.strftime("%d.%m.%Y"),
        "warnungen": warnungen,
        "bewertung": bewertung,
        "bewertung_farbe": bewertung_farbe,
        "empfehlung": empfehlung,
    }


def calculate_1rm_standards(alle_saetze, top_uebungen, user_gewicht=None):
    """
    Calculates 1RM estimates and compares against strength standards from database.
    Standards are now stored per-exercise in the Uebung model.

    Uses Epley Formula: 1RM = Gewicht × (1 + Wiederholungen/30)

    Returns list with:
    - uebung: Exercise name
    - muskelgruppe: Muscle group
    - geschaetzter_1rm: Estimated 1RM in kg
    - 1rm_entwicklung: List of dicts with 'monat' and '1rm' keys for 6-month progression
    - standard_info: Dict with level, progress, and standards
    """
    from core.models import Uebung

    if not alle_saetze.exists() or not top_uebungen:
        return []

    heute = timezone.now()

    ergebnisse = []

    for uebung in top_uebungen[:5]:
        uebung_name = uebung["uebung__bezeichnung"]

        # Hole Übung aus DB
        try:
            uebung_obj = Uebung.objects.get(bezeichnung=uebung_name)
        except Uebung.DoesNotExist:
            continue

        # Prüfe ob diese Übung Standards hat
        if not uebung_obj.standard_beginner:
            # Keine Standards definiert - überspringe
            continue

        # Hole alle Sätze für diese Übung
        uebung_saetze = alle_saetze.filter(uebung__bezeichnung=uebung_name)

        # 1RM berechnen für jeden Satz
        beste_1rm = 0
        for satz in uebung_saetze:
            if satz.wiederholungen and satz.wiederholungen > 0:
                gewicht = float(satz.gewicht or 0)
                # Epley Formel
                estimated_1rm = gewicht * (1 + satz.wiederholungen / 30.0)
                if estimated_1rm > beste_1rm:
                    beste_1rm = estimated_1rm

        if beste_1rm == 0:
            continue

        # 6-Monats-Entwicklung (Format für Template: Liste von Dicts)
        # Bugfix: Formel war `30 * (5 - i)`, so dass der letzte Slot (i=5)
        # monat_start = heute, monat_ende = heute + 30 ergab → Zukunft, keine Daten.
        # Fix: `30 * (6 - i)` → letzter Slot = heute-30 bis heute (aktueller Monat korrekt befüllt).
        # Monatslabel vom Ende-Datum (nicht Start), damit der aktuelle Monat korrekt beschriftet wird.
        entwicklung_liste = []
        for i in range(6):
            monat_start = heute - timedelta(days=30 * (6 - i))
            monat_ende = monat_start + timedelta(days=30)
            monat_saetze = uebung_saetze.filter(
                einheit__datum__gte=monat_start, einheit__datum__lte=monat_ende
            )

            monat_best_1rm = 0
            for satz in monat_saetze:
                if satz.wiederholungen and satz.wiederholungen > 0:
                    gewicht = float(satz.gewicht or 0)
                    estimated_1rm = gewicht * (1 + satz.wiederholungen / 30.0)
                    if estimated_1rm > monat_best_1rm:
                        monat_best_1rm = estimated_1rm

            # Label vom Ende-Datum, damit der aktuelle Monat korrekt angezeigt wird
            monat_name = monat_ende.strftime("%b")
            entwicklung_liste.append(
                {
                    "monat": monat_name,
                    "1rm": round(monat_best_1rm, 1) if monat_best_1rm > 0 else None,
                }
            )

        # Allometrische Skalierung (Jaric, 2002; Batterham & George, 1997)
        # Kraft skaliert NICHT linear mit Körpergewicht (lineares Modell ist ein bekannter Fehler).
        # Exponent 2/3 (≈ 0.667) ist der wissenschaftlich belegte Standard für
        # absolute Kraftleistung relativ zur Körpermasse.
        # Formel: skalierter_standard = basis_standard × (user_kg / 80.0) ^ (2/3)
        gewicht_float = float(user_gewicht) if user_gewicht else 80.0
        scaling_factor = (gewicht_float / 80.0) ** (2 / 3)

        standards = {
            "beginner": round(float(uebung_obj.standard_beginner) * scaling_factor, 1),
            "intermediate": round(float(uebung_obj.standard_intermediate) * scaling_factor, 1),
            "advanced": round(float(uebung_obj.standard_advanced) * scaling_factor, 1),
            "elite": round(float(uebung_obj.standard_elite) * scaling_factor, 1),
        }

        # Level bestimmen
        standard_level = "untrainiert"
        naechstes_level = None
        prozent_bis_naechstes = 0

        if beste_1rm < standards["beginner"]:
            standard_level = "untrainiert"
            naechstes_level = "beginner"
            naechstes_gewicht = standards["beginner"]
            prozent_bis_naechstes = round((beste_1rm / naechstes_gewicht) * 100, 1)
        else:
            levels_order = ["beginner", "intermediate", "advanced", "elite"]
            for level in levels_order:
                if beste_1rm >= standards[level]:
                    standard_level = level
                else:
                    naechstes_level = level
                    naechstes_gewicht = standards[level]
                    aktuelles_gewicht = standards[standard_level]
                    diff = naechstes_gewicht - aktuelles_gewicht
                    progress = beste_1rm - aktuelles_gewicht
                    prozent_bis_naechstes = round((progress / diff) * 100, 1) if diff > 0 else 0
                    break

        level_labels = {
            "untrainiert": "Untrainiert",
            "beginner": "Anfänger",
            "intermediate": "Fortgeschritten",
            "advanced": "Erfahren",
            "elite": "Elite",
        }

        if standard_level == "untrainiert":
            erreicht = []
        else:
            erreicht = [
                level_labels[lv] for lv in levels_order[: levels_order.index(standard_level) + 1]
            ]

        # Differenz zum nächsten Level berechnen (nicht absolutes Gewicht)
        if naechstes_level and naechstes_level in standards:
            diff_bis_naechstes = round(standards[naechstes_level] - beste_1rm, 1)
        else:
            diff_bis_naechstes = 0

        standard_info = {
            "level": standard_level,
            "level_label": level_labels[standard_level],
            "naechstes_level": level_labels.get(naechstes_level, "Elite"),
            "naechstes_gewicht": diff_bis_naechstes,
            "prozent_bis_naechstes": prozent_bis_naechstes if naechstes_level else 100,
            "alle_levels": {level_labels[k]: v for k, v in standards.items()},
            "erreicht": erreicht,
        }

        # Muskelgruppe
        muskelgruppe_name = uebung.get("muskelgruppe_display", "")

        ergebnisse.append(
            {
                "uebung": uebung_name,
                "muskelgruppe": muskelgruppe_name,
                "geschaetzter_1rm": round(beste_1rm, 1),
                "1rm_entwicklung": entwicklung_liste,
                "standard_info": standard_info,
            }
        )

    return ergebnisse


def calculate_rpe_quality_analysis(alle_saetze):
    """
    Analyzes RPE distribution to detect junk volume and optimal intensity.

    Returns dict with:
    - optimal_intensity_rate: % of sets at RPE 7-9
    - junk_volume_rate: % of sets at RPE <6
    - failure_rate: % of sets at RPE 10
    - rpe_verteilung_prozent: Distribution across RPE ranges
    - bewertung: Overall training quality rating
    - empfehlungen: List of recommendations
    """
    # Aufwärmsätze explizit ausschließen: niedrige RPE ist beim Aufwärmen intentional,
    # nicht Junk Volume. Warmup-Sätze würden die Analyse systematisch verfälschen.
    rpe_saetze = alle_saetze.filter(rpe__isnull=False, ist_aufwaermsatz=False)
    gesamt = rpe_saetze.count()

    if gesamt == 0:
        return None

    # Verteilung berechnen (Detail-Kategorien für Aufschlüsselung)
    rpe_sehr_leicht = rpe_saetze.filter(rpe__lt=5).count()  # RPE <5
    rpe_leicht = rpe_saetze.filter(rpe__gte=5, rpe__lt=7).count()  # RPE 5-6.9
    rpe_moderat = rpe_saetze.filter(rpe__gte=7, rpe__lte=8).count()  # RPE 7-8
    rpe_schwer = rpe_saetze.filter(rpe__gt=8, rpe__lte=9).count()  # RPE 8.1-9
    rpe_sehr_schwer = rpe_saetze.filter(rpe__gt=9, rpe__lt=10).count()  # RPE 9.1-9.9
    rpe_versagen = rpe_saetze.filter(rpe=10).count()  # RPE 10

    # Top-3 Metriken: Lückenlos (Summe = 100%)
    # Junk Volume: RPE < 7 (zu leicht für echten Muskelreiz)
    junk_count = rpe_saetze.filter(rpe__lt=7).count()
    # Optimal: RPE 7-9 (idealer Trainingsbereich)
    optimal_count = rpe_saetze.filter(rpe__gte=7, rpe__lt=10).count()
    # Versagen: RPE 10
    failure_count = rpe_versagen

    junk_volume_rate = round((junk_count / gesamt) * 100, 1)
    optimal_intensity_rate = round((optimal_count / gesamt) * 100, 1)
    failure_rate = round((failure_count / gesamt) * 100, 1)

    rpe_verteilung_prozent = {
        "sehr_leicht": round((rpe_sehr_leicht / gesamt) * 100, 1),
        "leicht": round((rpe_leicht / gesamt) * 100, 1),
        "moderat": round((rpe_moderat / gesamt) * 100, 1),
        "schwer": round((rpe_schwer / gesamt) * 100, 1),
        "sehr_schwer": round((rpe_sehr_schwer / gesamt) * 100, 1),
        "versagen": round((rpe_versagen / gesamt) * 100, 1),
    }

    # Empfehlungen generieren
    empfehlungen = []

    if junk_volume_rate > 20:
        empfehlungen.append(
            f'⚠️ Zu viel "Junk Volume" ({junk_volume_rate}%) - Reduziere Aufwärmsätze oder erhöhe Intensität'
        )

    if optimal_intensity_rate < 50:
        empfehlungen.append(
            f"⚠️ Zu wenig intensive Sätze ({optimal_intensity_rate}%) - Trainiere näher ans Versagen (RPE 7-9)"
        )

    if failure_rate > 10:
        empfehlungen.append(
            f"⚠️ Zu oft bis zum Versagen ({failure_rate}%) - Risiko für Übertraining. Ziel: <5%"
        )

    if optimal_intensity_rate >= 60 and failure_rate <= 5 and junk_volume_rate <= 15:
        empfehlungen.append("✅ Optimale Trainingsintensität! Weiter so.")

    # Bewertung
    if optimal_intensity_rate >= 70 and junk_volume_rate <= 10 and failure_rate <= 5:
        bewertung = "🏆 Exzellent"
        bewertung_farbe = "success"
    elif optimal_intensity_rate >= 60 and junk_volume_rate <= 20 and failure_rate <= 10:
        bewertung = "✅ Gut"
        bewertung_farbe = "success"
    elif optimal_intensity_rate >= 40:
        bewertung = "⚠️ Ausbaufähig"
        bewertung_farbe = "warning"
    else:
        bewertung = "🔴 Verbesserung nötig"
        bewertung_farbe = "danger"

    return {
        "optimal_intensity_rate": optimal_intensity_rate,
        "junk_volume_rate": junk_volume_rate,
        "failure_rate": failure_rate,
        "rpe_verteilung_prozent": rpe_verteilung_prozent,
        "bewertung": bewertung,
        "bewertung_farbe": bewertung_farbe,
        "empfehlungen": empfehlungen,
        "gesamt_saetze": gesamt,
    }
