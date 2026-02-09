"""
Advanced Training Statistics - Helper Functions
Provides comprehensive analysis for training progression, consistency, and performance.
"""

from datetime import timedelta
from django.db.models import Count, Max, Avg
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
    acht_wochen = heute - timedelta(days=56)
    
    plateau_analysis = []
    
    for uebung in top_uebungen[:5]:
        uebung_name = uebung['uebung__bezeichnung']
        muskelgruppe = uebung.get('muskelgruppe_display', '')
        
        # Alle Sätze dieser Übung chronologisch
        uebung_saetze = alle_saetze.filter(
            uebung__bezeichnung=uebung_name
        ).order_by('einheit__datum')
        
        if uebung_saetze.count() < 2:
            continue
            
        # Finde letzten PR (höchstes Gewicht)
        max_gewicht_satz = uebung_saetze.filter(
            gewicht__isnull=False
        ).order_by('-gewicht', '-einheit__datum').first()
        
        if not max_gewicht_satz:
            continue
            
        letzter_pr = float(max_gewicht_satz.gewicht)
        pr_datum = max_gewicht_satz.einheit.datum
        tage_seit_pr = (heute.date() - pr_datum.date()).days
        
        # Berechne durchschnittliche Progression pro Monat
        erster_satz = uebung_saetze.filter(gewicht__isnull=False).first()
        if erster_satz and erster_satz.gewicht:
            erstes_gewicht = float(erster_satz.gewicht)
            tage_gesamt = (pr_datum.date() - erster_satz.einheit.datum.date()).days
            
            if tage_gesamt > 0:
                gewichtsdiff = letzter_pr - erstes_gewicht
                progression_pro_monat = round((gewichtsdiff / tage_gesamt) * 30, 2)
            else:
                progression_pro_monat = 0
        else:
            progression_pro_monat = 0
        
        # Status bestimmen
        if tage_seit_pr <= 7:
            # Weniger als 1 Woche - noch zu früh für Bewertung
            if progression_pro_monat > 0:
                status = 'progression'
                status_label = '✅ Aktive Progression'
                status_farbe = 'success'
            else:
                status = 'zu_frueh'
                status_label = '⏳ Zu früh zu bewerten'
                status_farbe = 'info'
        elif tage_seit_pr <= 14:
            # 1-2 Wochen
            if progression_pro_monat > 0:
                status = 'progression'
                status_label = '✅ Aktive Progression'
                status_farbe = 'success'
            else:
                status = 'beobachten'
                status_label = '👀 Beobachten'
                status_farbe = 'info'
        elif tage_seit_pr <= 42:  # 2-6 Wochen
            status = 'plateau_leicht'
            status_label = '⚠️ Leichtes Plateau'
            status_farbe = 'warning'
        elif tage_seit_pr <= 84:  # 6-12 Wochen
            status = 'plateau'
            status_label = '🔴 Plateau'
            status_farbe = 'danger'
        else:
            status = 'plateau_lang'
            status_label = '❌ Langzeit-Plateau'
            status_farbe = 'danger'
        
        # Prüfe auf Regression (aktuelle Leistung < letzter PR)
        letzte_4_wochen = uebung_saetze.filter(
            einheit__datum__gte=vier_wochen,
            gewicht__isnull=False
        )
        
        if letzte_4_wochen.exists():
            aktuelles_max = max((float(s.gewicht) for s in letzte_4_wochen))
            if aktuelles_max < letzter_pr * 0.9:  # >10% Rückgang
                status = 'regression'
                status_label = '⚠️ Rückschritt'
                status_farbe = 'danger'
        
        plateau_analysis.append({
            'uebung': uebung_name,
            'muskelgruppe': muskelgruppe,
            'letzter_pr': letzter_pr,
            'pr_datum': pr_datum.strftime('%d.%m.%Y'),
            'tage_seit_pr': tage_seit_pr,
            'progression_pro_monat': progression_pro_monat,
            'status': status,
            'status_label': status_label,
            'status_farbe': status_farbe,
        })
    
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
        
        trainings_in_week = alle_trainings.filter(
            datum__gte=week_start,
            datum__lt=week_end
        ).count()
        
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
    erste_training = alle_trainings.order_by('datum').first()
    if erste_training:
        wochen_gesamt = max(1, ((heute - erste_training.datum).days // 7))
        wochen_mit_training = alle_trainings.dates('datum', 'week').count()
        adherence_rate = round((wochen_mit_training / wochen_gesamt) * 100, 1)
    else:
        adherence_rate = 0
    
    # Durchschnittliche Pause zwischen Trainings
    trainings_sorted = list(alle_trainings.order_by('datum').values_list('datum', flat=True))
    if len(trainings_sorted) > 1:
        pausen = []
        for i in range(1, len(trainings_sorted)):
            pause_tage = (trainings_sorted[i].date() - trainings_sorted[i-1].date()).days
            pausen.append(pause_tage)
        avg_pause_tage = round(sum(pausen) / len(pausen), 1)
    else:
        avg_pause_tage = 0
    
    # Bewertung
    if aktueller_streak >= 12 and adherence_rate >= 85:
        bewertung = '🏆 Exzellent'
        bewertung_farbe = 'success'
    elif aktueller_streak >= 8 and adherence_rate >= 70:
        bewertung = '✅ Sehr gut'
        bewertung_farbe = 'success'
    elif aktueller_streak >= 4 and adherence_rate >= 60:
        bewertung = '👍 Gut'
        bewertung_farbe = 'info'
    elif adherence_rate >= 40:
        bewertung = '⚠️ Ausbaufähig'
        bewertung_farbe = 'warning'
    else:
        bewertung = '🔴 Inkonsistent'
        bewertung_farbe = 'danger'
    
    return {
        'aktueller_streak': aktueller_streak,
        'laengster_streak': laengster_streak,
        'adherence_rate': adherence_rate,
        'avg_pause_tage': avg_pause_tage,
        'bewertung': bewertung,
        'bewertung_farbe': bewertung_farbe,
    }


def calculate_fatigue_index(weekly_volume_data, rpe_saetze, alle_trainings):
    """
    Calculates fatigue index and deload recommendations.
    
    Returns dict with:
    - fatigue_index: Score 0-100 (higher = more fatigue)
    - volumen_spike: Boolean if volume increased >20%
    - rpe_steigend: Boolean if RPE trending up
    - deload_empfohlen: Boolean if deload recommended
    - naechste_deload: Suggested date for next deload
    - warnungen: List of warning messages
    """
    heute = timezone.now()
    vier_wochen = heute - timedelta(days=28)
    
    fatigue_index = 0
    warnungen = []
    
    # 1. Volumen-Spike Detection (40% Gewichtung)
    volumen_spike = False
    if len(weekly_volume_data) >= 2:
        letzte_woche = weekly_volume_data[-1]['volumen']
        vorletzte_woche = weekly_volume_data[-2]['volumen']
        
        if vorletzte_woche > 0:
            volumen_change = ((letzte_woche - vorletzte_woche) / vorletzte_woche) * 100
            
            if volumen_change > 30:
                fatigue_index += 40
                volumen_spike = True
                warnungen.append(f'Sehr starker Volumen-Anstieg: +{round(volumen_change)}%')
            elif volumen_change > 20:
                fatigue_index += 30
                volumen_spike = True
                warnungen.append(f'Starker Volumen-Anstieg: +{round(volumen_change)}%')
            elif volumen_change > 10:
                fatigue_index += 15
    
    # 2. RPE-Trend (30% Gewichtung)
    rpe_steigend = False
    if rpe_saetze.exists() and rpe_saetze.count() >= 10:
        # Vergleiche letzte 2 Wochen mit 2-4 Wochen davor
        zwei_wochen = heute - timedelta(days=14)
        
        recent_rpe = rpe_saetze.filter(
            einheit__datum__gte=zwei_wochen
        ).aggregate(Avg('rpe'))['rpe__avg']
        
        older_rpe = rpe_saetze.filter(
            einheit__datum__gte=vier_wochen,
            einheit__datum__lt=zwei_wochen
        ).aggregate(Avg('rpe'))['rpe__avg']
        
        if recent_rpe and older_rpe:
            if recent_rpe > 8.5:
                fatigue_index += 30
                rpe_steigend = True
                warnungen.append(f'Sehr hohe Trainingsintensität (RPE {round(recent_rpe, 1)})')
            elif recent_rpe > 8.0:
                fatigue_index += 20
                rpe_steigend = True
                warnungen.append(f'Hohe Trainingsintensität (RPE {round(recent_rpe, 1)})')
            
            # Prüfe ob RPE steigt bei gleichem/sinkendem Gewicht
            rpe_change = recent_rpe - older_rpe
            if rpe_change > 0.5:
                fatigue_index += 10
                warnungen.append('RPE steigt trotz Training (mögliche Ermüdung)')
    
    # 3. Trainingsfrequenz ohne Ruhetag (30% Gewichtung)
    letzte_7_tage = alle_trainings.filter(
        datum__gte=heute - timedelta(days=7)
    ).count()
    
    if letzte_7_tage >= 7:
        fatigue_index += 30
        warnungen.append('Jeden Tag trainiert - KEIN Ruhetag!')
    elif letzte_7_tage >= 6:
        fatigue_index += 20
        warnungen.append('Fast täglich trainiert - mehr Ruhe empfohlen')
    elif letzte_7_tage >= 5:
        fatigue_index += 10
    
    # Deload-Empfehlung
    deload_empfohlen = fatigue_index >= 50
    
    # Nächste Deload berechnen (alle 6-8 Wochen empfohlen)
    letzte_deload = None  # TODO: Aus User-Settings/Historie holen
    if not letzte_deload:
        # Annahme: Sollte alle 6 Wochen sein
        naechste_deload = heute + timedelta(weeks=6)
    else:
        naechste_deload = letzte_deload + timedelta(weeks=6)
    
    # Bewertung
    if fatigue_index >= 70:
        bewertung = '🚨 Kritisch'
        bewertung_farbe = 'danger'
        empfehlung = 'SOFORT Deload-Woche! Reduziere Volumen um 40-50% für 1 Woche.'
    elif fatigue_index >= 50:
        bewertung = '⚠️ Hoch'
        bewertung_farbe = 'danger'
        empfehlung = 'Deload-Woche dringend empfohlen. Reduziere Volumen um 40%.'
    elif fatigue_index >= 30:
        bewertung = '⚠️ Moderat'
        bewertung_farbe = 'warning'
        empfehlung = 'Achte auf Regeneration. Erwäge Deload in 1-2 Wochen.'
    else:
        bewertung = '✅ Niedrig'
        bewertung_farbe = 'success'
        empfehlung = 'Gute Erholung. Weiter so!'
    
    return {
        'fatigue_index': fatigue_index,
        'volumen_spike': volumen_spike,
        'rpe_steigend': rpe_steigend,
        'deload_empfohlen': deload_empfohlen,
        'naechste_deload': naechste_deload.strftime('%d.%m.%Y'),
        'warnungen': warnungen,
        'bewertung': bewertung,
        'bewertung_farbe': bewertung_farbe,
        'empfehlung': empfehlung,
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
    sechs_monate = heute - timedelta(days=180)

    ergebnisse = []

    for uebung in top_uebungen[:5]:
        uebung_name = uebung['uebung__bezeichnung']

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
        entwicklung_liste = []
        for i in range(6):
            monat_start = heute - timedelta(days=30 * (5 - i))
            monat_ende = monat_start + timedelta(days=30)
            monat_saetze = uebung_saetze.filter(
                einheit__datum__gte=monat_start,
                einheit__datum__lt=monat_ende
            )

            monat_best_1rm = 0
            for satz in monat_saetze:
                if satz.wiederholungen and satz.wiederholungen > 0:
                    gewicht = float(satz.gewicht or 0)
                    estimated_1rm = gewicht * (1 + satz.wiederholungen / 30.0)
                    if estimated_1rm > monat_best_1rm:
                        monat_best_1rm = estimated_1rm

            monat_name = monat_start.strftime('%b')
            entwicklung_liste.append({
                'monat': monat_name,
                '1rm': round(monat_best_1rm, 1) if monat_best_1rm > 0 else None
            })

        # Standards aus DB holen und skalieren
        gewicht_float = float(user_gewicht) if user_gewicht else 80.0
        scaling_factor = gewicht_float / 80.0

        standards = {
            'beginner': round(float(uebung_obj.standard_beginner) * scaling_factor, 1),
            'intermediate': round(float(uebung_obj.standard_intermediate) * scaling_factor, 1),
            'advanced': round(float(uebung_obj.standard_advanced) * scaling_factor, 1),
            'elite': round(float(uebung_obj.standard_elite) * scaling_factor, 1),
        }

        # Level bestimmen
        standard_level = 'untrainiert'
        naechstes_level = None
        prozent_bis_naechstes = 0

        if beste_1rm < standards['beginner']:
            standard_level = 'untrainiert'
            naechstes_level = 'beginner'
            naechstes_gewicht = standards['beginner']
            prozent_bis_naechstes = round((beste_1rm / naechstes_gewicht) * 100, 1)
        else:
            levels_order = ['beginner', 'intermediate', 'advanced', 'elite']
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
            'untrainiert': 'Untrainiert',
            'beginner': 'Anfänger',
            'intermediate': 'Fortgeschritten',
            'advanced': 'Erfahren',
            'elite': 'Elite'
        }

        if standard_level == 'untrainiert':
            erreicht = []
        else:
            erreicht = [level_labels[lv] for lv in levels_order[:levels_order.index(standard_level)+1]]

        standard_info = {
            'level': standard_level,
            'level_label': level_labels[standard_level],
            'naechstes_level': level_labels.get(naechstes_level, 'Elite'),
            'naechstes_gewicht': standards.get(naechstes_level, 0) if naechstes_level in standards else standards.get('beginner', 0),
            'prozent_bis_naechstes': prozent_bis_naechstes if naechstes_level else 100,
            'alle_levels': {
                level_labels[k]: v
                for k, v in standards.items()
            },
            'erreicht': erreicht
        }

        # Muskelgruppe
        muskelgruppe_name = uebung.get('muskelgruppe_display', '')

        ergebnisse.append({
            'uebung': uebung_name,
            'muskelgruppe': muskelgruppe_name,
            'geschaetzter_1rm': round(beste_1rm, 1),
            '1rm_entwicklung': entwicklung_liste,
            'standard_info': standard_info,
        })

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
    rpe_saetze = alle_saetze.filter(rpe__isnull=False)
    gesamt = rpe_saetze.count()
    
    if gesamt == 0:
        return None
    
    # Verteilung berechnen
    rpe_sehr_leicht = rpe_saetze.filter(rpe__lt=5).count()  # RPE <5
    rpe_leicht = rpe_saetze.filter(rpe__gte=5, rpe__lt=6).count()  # RPE 5-6
    rpe_moderat = rpe_saetze.filter(rpe__gte=6, rpe__lte=7).count()  # RPE 6-7
    rpe_schwer = rpe_saetze.filter(rpe__gt=7, rpe__lt=9).count()  # RPE 7-9
    rpe_sehr_schwer = rpe_saetze.filter(rpe__gte=9, rpe__lt=10).count()  # RPE 9-10
    rpe_versagen = rpe_saetze.filter(rpe=10).count()  # RPE 10
    
    # Prozente
    junk_volume_rate = round(((rpe_sehr_leicht + rpe_leicht) / gesamt) * 100, 1)
    optimal_intensity_rate = round(((rpe_schwer + rpe_sehr_schwer) / gesamt) * 100, 1)
    failure_rate = round((rpe_versagen / gesamt) * 100, 1)
    
    rpe_verteilung_prozent = {
        'sehr_leicht': round((rpe_sehr_leicht / gesamt) * 100, 1),
        'leicht': round((rpe_leicht / gesamt) * 100, 1),
        'moderat': round((rpe_moderat / gesamt) * 100, 1),
        'schwer': round((rpe_schwer / gesamt) * 100, 1),
        'sehr_schwer': round((rpe_sehr_schwer / gesamt) * 100, 1),
        'versagen': round((rpe_versagen / gesamt) * 100, 1),
    }
    
    # Empfehlungen generieren
    empfehlungen = []
    
    if junk_volume_rate > 20:
        empfehlungen.append(f'⚠️ Zu viel "Junk Volume" ({junk_volume_rate}%) - Reduziere Aufwärmsätze oder erhöhe Intensität')
    
    if optimal_intensity_rate < 50:
        empfehlungen.append(f'⚠️ Zu wenig intensive Sätze ({optimal_intensity_rate}%) - Trainiere näher ans Versagen (RPE 7-9)')
    
    if failure_rate > 10:
        empfehlungen.append(f'⚠️ Zu oft bis zum Versagen ({failure_rate}%) - Risiko für Übertraining. Ziel: <5%')
    
    if optimal_intensity_rate >= 60 and failure_rate <= 5 and junk_volume_rate <= 15:
        empfehlungen.append('✅ Optimale Trainingsintensität! Weiter so.')
    
    # Bewertung
    if optimal_intensity_rate >= 70 and junk_volume_rate <= 10 and failure_rate <= 5:
        bewertung = '🏆 Exzellent'
        bewertung_farbe = 'success'
    elif optimal_intensity_rate >= 60 and junk_volume_rate <= 20 and failure_rate <= 10:
        bewertung = '✅ Gut'
        bewertung_farbe = 'success'
    elif optimal_intensity_rate >= 40:
        bewertung = '⚠️ Ausbaufähig'
        bewertung_farbe = 'warning'
    else:
        bewertung = '🔴 Verbesserung nötig'
        bewertung_farbe = 'danger'
    
    return {
        'optimal_intensity_rate': optimal_intensity_rate,
        'junk_volume_rate': junk_volume_rate,
        'failure_rate': failure_rate,
        'rpe_verteilung_prozent': rpe_verteilung_prozent,
        'bewertung': bewertung,
        'bewertung_farbe': bewertung_farbe,
        'empfehlungen': empfehlungen,
        'gesamt_saetze': gesamt,
    }