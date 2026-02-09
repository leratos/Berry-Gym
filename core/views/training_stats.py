"""
Training Analytics and Statistics Module

This module handles training analytics, statistics, and the main dashboard view.
It provides comprehensive performance analysis, progress tracking, and workout history management.

Functions:
- dashboard: Main dashboard with performance metrics and analytics
- training_list: List of all past training sessions
- delete_training: Remove a training session from history
- training_stats: Detailed training statistics with volume progression
- exercise_stats: Performance analysis for individual exercises
"""

from datetime import datetime, timedelta, date
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Count, Max, Sum, Avg, F, Q, DecimalField
from django.http import JsonResponse
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from collections import defaultdict
import json
import os
import logging
import random

from ..models import (
    Trainingseinheit, KoerperWerte, Uebung, Satz,
    MUSKELGRUPPEN, CardioEinheit, Plan, UserProfile
)
logger = logging.getLogger(__name__)


@login_required
def dashboard(request):
    letztes_training = Trainingseinheit.objects.filter(user=request.user).first()
    letzter_koerperwert = KoerperWerte.objects.filter(user=request.user).first()

    # Trainingsfrequenz diese Woche (Montag bis Sonntag)
    heute = timezone.now()
    # ISO-Woche: Montag = 1, Sonntag = 7
    iso_weekday = heute.isoweekday()
    # Start der Woche ist Montag
    start_woche = heute - timedelta(days=iso_weekday - 1)
    # Setze auf Mitternacht
    start_woche = start_woche.replace(hour=0, minute=0, second=0, microsecond=0)
    trainings_diese_woche = Trainingseinheit.objects.filter(user=request.user, datum__gte=start_woche).count()

    # Streak berechnen (aufeinanderfolgende Wochen mit mindestens 1 Training)
    streak = 0
    check_date = heute
    while True:
        # ISO-Woche: Montag = 1
        iso_weekday = check_date.isoweekday()
        week_start = check_date - timedelta(days=iso_weekday - 1)
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7)
        trainings_in_week = Trainingseinheit.objects.filter(
            user=request.user,
            datum__gte=week_start,
            datum__lt=week_end
        ).count()
        if trainings_in_week > 0:
            streak += 1
            check_date = week_start - timedelta(days=1)  # Vorwoche prüfen
        else:
            break
        if streak > 52:  # Sicherheitslimit
            break

    # Favoriten-Übungen (Top 3 meist trainierte)
    favoriten = (Satz.objects
                 .filter(einheit__user=request.user, ist_aufwaermsatz=False)
                 .values('uebung__bezeichnung', 'uebung__id')
                 .annotate(anzahl=Count('id'))
                 .order_by('-anzahl')[:3])

    # Gesamtstatistiken
    gesamt_trainings = Trainingseinheit.objects.filter(user=request.user).count()
    gesamt_saetze = Satz.objects.filter(einheit__user=request.user, ist_aufwaermsatz=False).count()

    # Performance Form-Index berechnen (0-100 Score)
    form_index = 0
    form_factors = []

    if gesamt_trainings >= 4:  # Mindestens 4 Trainings für aussagekräftige Analyse
        # Faktor 1: Trainingsfrequenz (0-30 Punkte)
        # Optimal: 3-5x pro Woche
        freq_score = min(trainings_diese_woche * 7.5, 30)  # 4 Trainings = 30 Punkte
        form_factors.append(('Trainingsfrequenz', round(freq_score, 1)))

        # Faktor 2: Streak-Konsistenz (0-25 Punkte)
        # Bis zu 10 Wochen = 25 Punkte
        streak_score = min(streak * 2.5, 25)
        form_factors.append(('Konsistenz', round(streak_score, 1)))

        # Faktor 3: RPE-Durchschnitt letzte 2 Wochen (0-25 Punkte)
        two_weeks_ago = heute - timedelta(days=14)
        recent_saetze = Satz.objects.filter(
            einheit__datum__gte=two_weeks_ago,
            ist_aufwaermsatz=False,
            rpe__isnull=False
        )

        if recent_saetze.exists():
            avg_rpe = recent_saetze.aggregate(Avg('rpe'))['rpe__avg']
            # Optimal RPE: 7-8 (nicht zu leicht, nicht zu hart)
            # 7-8 = 25 Punkte, <5 oder >9 = weniger Punkte
            if 7 <= avg_rpe <= 8:
                rpe_score = 25
            elif 6 <= avg_rpe <= 9:
                rpe_score = 20
            elif 5 <= avg_rpe <= 9.5:
                rpe_score = 15
            else:
                rpe_score = 10
            form_factors.append(('Trainingsintensität (RPE)', rpe_score))
        else:
            rpe_score = 0

        # Faktor 4: Volumen-Trend (0-20 Punkte)
        # Letzte 4 Wochen: steigend = gut, fallend = schlecht
        last_4_weeks = []
        for i in range(4):
            week_start = heute - timedelta(days=heute.weekday() + (i * 7))
            week_end = week_start + timedelta(days=7)
            week_volume = Satz.objects.filter(
                einheit__datum__gte=week_start,
                einheit__datum__lt=week_end,

                ist_aufwaermsatz=False,
                einheit__user=request.user

            ).aggregate(
                total=Sum(F('gewicht') * F('wiederholungen'), output_field=DecimalField())
            )
            if week_volume['total']:
                last_4_weeks.append(float(week_volume['total'] or 0))

        if len(last_4_weeks) >= 2:
            # Trend: positive Steigung = gut
            if last_4_weeks[0] >= last_4_weeks[1]:  # Diese Woche >= letzte Woche
                volume_score = 20
            elif last_4_weeks[0] >= last_4_weeks[1] * 0.8:  # Nur leichter Rückgang
                volume_score = 15
            else:
                volume_score = 10
            form_factors.append(('Volumen-Trend', volume_score))
        else:
            volume_score = 0

        form_index = round(freq_score + streak_score + rpe_score + volume_score)

        # Bewertung
        if form_index >= 80:
            form_rating = 'Ausgezeichnet'
            form_color = 'success'
        elif form_index >= 60:
            form_rating = 'Gut'
            form_color = 'info'
        elif form_index >= 40:
            form_rating = 'Solide'
            form_color = 'warning'
        else:
            form_rating = 'Ausbaufähig'
            form_color = 'danger'
    else:
        form_rating = 'Nicht verfügbar'
        form_color = 'secondary'

    # Wöchentliches Volumen (letzte 4 Wochen für Dashboard)
    weekly_volumes = []
    for i in range(4):
        # ISO-Woche: Montag = 1, Sonntag = 7
        iso_weekday = heute.isoweekday()
        # Berechne Wochenstart (Montag) für Woche i
        week_start = heute - timedelta(days=iso_weekday - 1 + (i * 7))
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7)

        week_saetze = Satz.objects.filter(
            einheit__user=request.user,
            einheit__datum__gte=week_start,
            einheit__datum__lt=week_end,
            ist_aufwaermsatz=False
        )

        week_total = sum([
            float(s.gewicht) * int(s.wiederholungen)
            for s in week_saetze if s.gewicht and s.wiederholungen
        ])

        # Woche benennen
        if i == 0:
            week_label = 'Diese Woche'
        elif i == 1:
            week_label = 'Letzte Woche'
        else:
            week_label = f'Vor {i} Wochen'

        weekly_volumes.append({
            'label': week_label,
            'volume': round(week_total, 0),
            'week_num': i
        })

    # Ermüdungs-Index berechnen (0-100, höher = mehr Ermüdung)
    fatigue_index = 0
    fatigue_warnings = []

    if gesamt_trainings >= 4:
        # Faktor 1: Volumen-Spike (40% Gewicht)
        if len(weekly_volumes) >= 2:
            current_vol = weekly_volumes[0]['volume']
            last_vol = weekly_volumes[1]['volume']
            if last_vol > 0:
                vol_change = ((current_vol - last_vol) / last_vol) * 100
                if vol_change > 30:  # Sehr starker Anstieg
                    fatigue_index += 40
                    fatigue_warnings.append('Sehr starker Volumen-Anstieg')
                elif vol_change > 20:
                    fatigue_index += 30
                    fatigue_warnings.append('Starker Volumen-Anstieg')
                elif vol_change > 10:
                    fatigue_index += 15

        # Faktor 2: Hoher RPE-Durchschnitt (30% Gewicht)
        if recent_saetze.exists():
            avg_rpe = recent_saetze.aggregate(Avg('rpe'))['rpe__avg']
            if avg_rpe and avg_rpe > 8.5:
                fatigue_index += 30
                fatigue_warnings.append('Sehr hohe Trainingsintensität')
            elif avg_rpe and avg_rpe > 8:
                fatigue_index += 20
                fatigue_warnings.append('Hohe Trainingsintensität')

        # Faktor 3: Hohe Frequenz ohne Ruhetag (30% Gewicht)
        last_7_days = Trainingseinheit.objects.filter(
            user=request.user,
            datum__gte=heute - timedelta(days=7)
        ).count()

        if last_7_days >= 6:
            fatigue_index += 30
            fatigue_warnings.append('Sehr hohe Trainingsfrequenz')
        elif last_7_days >= 5:
            fatigue_index += 15

    # NEU: Faktor 4: Cardio-Ermüdung (zusätzliche Punkte)
    cardio_letzte_7_tage = CardioEinheit.objects.filter(
        user=request.user,
        datum__gte=heute - timedelta(days=7)
    )
    cardio_fatigue_total = sum(c.ermuedungs_punkte for c in cardio_letzte_7_tage)

    # Cardio-Ermüdung: max 20 Punkte (bei 120+ Ermüdungspunkten aus Cardio)
    if cardio_fatigue_total >= 120:
        fatigue_index += 20
        fatigue_warnings.append(f'Hohes Cardio-Volumen ({cardio_fatigue_total:.0f} Punkte)')
    elif cardio_fatigue_total >= 60:
        fatigue_index += 10
        fatigue_warnings.append(f'Moderates Cardio-Volumen ({cardio_fatigue_total:.0f} Punkte)')
    elif cardio_fatigue_total >= 30:
        fatigue_index += 5

    # Cardio-Statistik für Dashboard
    cardio_diese_woche = cardio_letzte_7_tage.count()
    cardio_minuten_diese_woche = sum(c.dauer_minuten for c in cardio_letzte_7_tage)

    # Ermüdungs-Bewertung
    if fatigue_index >= 60:
        fatigue_rating = 'Hoch'
        fatigue_color = 'danger'
        fatigue_message = 'Deload-Woche empfohlen! Reduziere Volumen um 40-50%.'
    elif fatigue_index >= 40:
        fatigue_rating = 'Moderat'
        fatigue_color = 'warning'
        fatigue_message = 'Achte auf ausreichend Regeneration.'
    elif fatigue_index >= 20:
        fatigue_rating = 'Niedrig'
        fatigue_color = 'info'
        fatigue_message = 'Gute Balance zwischen Training und Erholung.'
    else:
        fatigue_rating = 'Sehr niedrig'
        fatigue_color = 'success'
        fatigue_message = 'Du kannst noch mehr trainieren!'

    # Motivations-Quote basierend auf Performance
    motivational_quotes = {
        'high_performance': [
            '💪 Du bist auf Feuer! Weiter so!',
            '🔥 Unglaubliche Leistung! Dein Fortschritt ist beeindruckend.',
            '⚡ Du zerlegst deine Ziele! Keep crushing it!',
            '🏆 Champion-Mindset! Deine Konsistenz zahlt sich aus.',
        ],
        'good_performance': [
            '✨ Solide Arbeit! Du bist auf dem richtigen Weg.',
            '📈 Guter Progress! Bleib dran und die Ergebnisse kommen.',
            '💯 Starke Performance! Dein Training zeigt Wirkung.',
            '🎯 Du machst es richtig! Konsistenz ist der Schlüssel.',
        ],
        'need_motivation': [
            '🌟 Jeder Tag ist eine neue Chance! Du schaffst das.',
            '💪 Klein anfangen ist besser als gar nicht! Los geht\'s.',
            '🔋 Lade deine Batterien auf und komm stärker zurück!',
            '🎯 Ein Training nach dem anderen. Du bist stärker als du denkst!',
        ],
        'high_fatigue': [
            '🛌 Dein Körper braucht Erholung! Gönne dir eine Pause.',
            '⚠️ Regeneration ist Training! Nimm dir Zeit zum Erholen.',
            '🧘 Recovery ist Progress! Dein Körper braucht Zeit.',
            '💤 Qualität über Quantität! Weniger kann mehr sein.',
        ]
    }

    # Quote-Auswahl basierend auf Status
    if fatigue_index >= 60:
        motivation_quote = random.choice(motivational_quotes['high_fatigue'])
    elif form_index >= 70:
        motivation_quote = random.choice(motivational_quotes['high_performance'])
    elif form_index >= 40:
        motivation_quote = random.choice(motivational_quotes['good_performance'])
    else:
        motivation_quote = random.choice(motivational_quotes['need_motivation'])

    # Trainings-Kalender Heatmap (365 Tage)
    training_heatmap = {}
    start_date = heute - timedelta(days=364)

    # Alle Trainings der letzten 365 Tage gruppiert nach Datum
    trainings_by_date = Trainingseinheit.objects.filter(
        user=request.user,
        datum__gte=start_date
    ).values('datum__date').annotate(count=Count('id'))

    # Dictionary mit Datum -> Anzahl Trainings erstellen
    for entry in trainings_by_date:
        date_str = entry['datum__date'].strftime('%Y-%m-%d')
        training_heatmap[date_str] = entry['count']

    # JSON für Frontend vorbereiten
    training_heatmap_json = json.dumps(training_heatmap)

    # OpenRouter Flag für AI Plan Generator
    # Auf dem Server (DEBUG=False) immer OpenRouter verwenden (keine lokale GPU)
    use_openrouter = not settings.DEBUG or os.getenv('USE_OPENROUTER', 'False').lower() == 'true'

    # AI Auto-Suggest: Performance-Warnungen analysieren
    performance_warnings = []

    if gesamt_trainings >= 4:
        # 1. PLATEAU-Erkennung: Keine Progression bei Top-Übungen (letzte 4 Wochen)
        four_weeks_ago = heute - timedelta(days=28)

        two_weeks_ago = heute - timedelta(days=14)

        for fav in favoriten[:3]:  # Top 3 Übungen prüfen
            uebung_id = fav['uebung__id']
            uebung_name = fav['uebung__bezeichnung']

            # Max-Gewicht der letzten 2 Wochen vs. Wochen 2-4
            recent_max_qs = Satz.objects.filter(
                einheit__user=request.user,
                uebung_id=uebung_id,
                ist_aufwaermsatz=False,
                einheit__datum__gte=two_weeks_ago
            ).aggregate(max_gewicht=Max('gewicht'))

            older_max_qs = Satz.objects.filter(
                einheit__user=request.user,
                uebung_id=uebung_id,
                ist_aufwaermsatz=False,
                einheit__datum__gte=four_weeks_ago,
                einheit__datum__lt=two_weeks_ago
            ).aggregate(max_gewicht=Max('gewicht'))

            recent_max = float(recent_max_qs['max_gewicht'] or 0)
            older_max = float(older_max_qs['max_gewicht'] or 0)

            # Plateau nur wenn beide Zeiträume Daten haben und kein Anstieg
            if older_max > 0 and recent_max > 0 and recent_max <= older_max:
                performance_warnings.append({
                    'type': 'plateau',
                    'severity': 'warning',
                    'exercise': uebung_name,
                    'message': f'Kein Progress seit 4 Wochen',
                    'suggestion': 'Versuche Intensitätstechniken wie Drop-Sets oder erhöhe das Volumen um 10-15%',
                    'icon': 'bi-graph-down',
                    'color': 'warning'
                })

        # 2. RÜCKSCHRITT-Erkennung: Leistungsabfall bei Übungen
        two_weeks_ago = heute - timedelta(days=14)

        # Prüfe alle Übungen die in den letzten 2 Wochen trainiert wurden
        recent_exercises = Satz.objects.filter(
            einheit__user=request.user,
            einheit__datum__gte=two_weeks_ago,
            ist_aufwaermsatz=False
        ).values('uebung__bezeichnung', 'uebung_id').annotate(
            avg_gewicht=Avg('gewicht')
        ).filter(avg_gewicht__isnull=False)

        for ex in recent_exercises:
            ex_id = ex['uebung_id']
            ex_name = ex['uebung__bezeichnung']
            current_avg = float(ex['avg_gewicht'])

            # Vergleiche mit 2-4 Wochen davor
            comparison_sets = Satz.objects.filter(
                einheit__user=request.user,
                uebung_id=ex_id,
                ist_aufwaermsatz=False,
                einheit__datum__gte=heute - timedelta(days=28),
                einheit__datum__lt=two_weeks_ago
            ).aggregate(Avg('gewicht'))

            previous_avg = float(comparison_sets['gewicht__avg'] or 0)

            # Rückschritt wenn >15% Leistungsabfall
            if previous_avg > 0 and current_avg < previous_avg * 0.85:
                drop_percent = round(((previous_avg - current_avg) / previous_avg) * 100)
                performance_warnings.append({
                    'type': 'regression',
                    'severity': 'danger',
                    'exercise': ex_name,
                    'message': f'Leistungsabfall von {drop_percent}%',
                    'suggestion': 'Prüfe Regeneration, Ernährung und Schlaf. Erwäge eine Deload-Woche.',
                    'icon': 'bi-arrow-down-circle',
                    'color': 'danger'
                })

        # 3. STAGNATION-Erkennung: Lange Pause bei Muskelgruppen
        # Prüfe welche Muskelgruppen lange nicht trainiert wurden
        all_muscle_groups = dict(MUSKELGRUPPEN)
        trained_recently = set(
            Satz.objects.filter(
                einheit__user=request.user,
                einheit__datum__gte=heute - timedelta(days=14),
                ist_aufwaermsatz=False
            ).values_list('uebung__muskelgruppe', flat=True)
        )

        # Muskelgruppen die User Equipment hat aber nicht trainiert
        # set() statt .distinct() weil Meta ordering=['bezeichnung'] das DISTINCT verfälscht
        user_muscle_groups = set(
            Uebung.objects.filter(
                Q(is_custom=False) | Q(created_by=request.user)
            ).values_list('muskelgruppe', flat=True)
        )

        for mg in user_muscle_groups:
            if mg not in trained_recently:
                # Prüfe wann zuletzt trainiert
                last_training = Satz.objects.filter(
                    einheit__user=request.user,
                    uebung__muskelgruppe=mg,
                    ist_aufwaermsatz=False
                ).order_by('-einheit__datum').first()

                if last_training:
                    days_ago = (heute.date() - last_training.einheit.datum.date()).days
                    if days_ago >= 14:  # 2 Wochen keine Aktivität
                        mg_label = all_muscle_groups.get(mg, mg)
                        performance_warnings.append({
                            'type': 'stagnation',
                            'severity': 'info',
                            'exercise': mg_label,
                            'message': f'Seit {days_ago} Tagen nicht trainiert',
                            'suggestion': 'Integriere diese Muskelgruppe wieder in deinen Trainingsplan',
                            'icon': 'bi-pause-circle',
                            'color': 'info'
                        })

        # Limitiere auf Top 3 wichtigste Warnungen (Priorität: Rückschritt > Plateau > Stagnation)
        warnings_sorted = sorted(
            performance_warnings,
            key=lambda x: {'regression': 0, 'plateau': 1, 'stagnation': 2}[x['type']]
        )
        performance_warnings = warnings_sorted[:3]

    context = {
        'letztes_training': letztes_training,
        'letzter_koerperwert': letzter_koerperwert,
        'trainings_diese_woche': trainings_diese_woche,
        'use_openrouter': use_openrouter,
        'streak': streak,
        'favoriten': favoriten,
        'gesamt_trainings': gesamt_trainings,
        'gesamt_saetze': gesamt_saetze,
        'form_index': form_index,
        'form_rating': form_rating,
        'form_color': form_color,
        'form_factors': form_factors,
        'weekly_volumes': weekly_volumes,
        'fatigue_index': fatigue_index,
        'fatigue_rating': fatigue_rating,
        'fatigue_color': fatigue_color,
        'fatigue_message': fatigue_message,
        'fatigue_warnings': fatigue_warnings,
        'motivation_quote': motivation_quote,
        'training_heatmap_json': training_heatmap_json,
        # Cardio-Statistiken
        'cardio_diese_woche': cardio_diese_woche,
        'cardio_minuten_diese_woche': cardio_minuten_diese_woche,
        # AI Auto-Suggest
        'performance_warnings': performance_warnings,
    }

    # Aktiver Plan-Gruppen-Info für Dashboard-Widget
    try:
        profile = request.user.profile
        if profile.active_plan_group:
            group_plans = list(
                Plan.objects.filter(
                    user=request.user, gruppe_id=profile.active_plan_group
                ).order_by('gruppe_reihenfolge', 'name')
            )
            if group_plans:
                context['active_plan_group_name'] = group_plans[0].gruppe_name or 'Unbenannte Gruppe'
                context['active_plan_group_id'] = str(profile.active_plan_group)

                # Nächsten Plan ermitteln (Rotation: 1->2->3->1)
                last_training = Trainingseinheit.objects.filter(
                    user=request.user,
                    plan__in=group_plans
                ).select_related('plan').order_by('-datum').first()

                if last_training and last_training.plan:
                    # Finde Index des zuletzt trainierten Plans
                    plan_ids = [p.id for p in group_plans]
                    try:
                        last_idx = plan_ids.index(last_training.plan.id)
                        next_idx = (last_idx + 1) % len(group_plans)
                    except ValueError:
                        next_idx = 0
                else:
                    next_idx = 0

                next_plan = group_plans[next_idx]
                context['next_plan'] = next_plan
                context['next_plan_index'] = next_idx + 1
                context['group_plan_count'] = len(group_plans)

                # Zyklus-Woche berechnen
                current_week = profile.get_current_cycle_week()
                if current_week:
                    context['cycle_week'] = current_week
                    context['cycle_length'] = profile.cycle_length
                    context['is_deload'] = profile.is_deload_week()
                    context['deload_volume_pct'] = int((1 - profile.deload_volume_factor) * 100)
                    context['deload_weight_pct'] = int((1 - profile.deload_weight_factor) * 100)
                    context['deload_rpe_target'] = profile.deload_rpe_target
            else:
                # Gruppe existiert nicht mehr
                context['active_plan_group_stale'] = True
    except UserProfile.DoesNotExist:
        pass

    return render(request, 'core/dashboard.html', context)


@login_required
def training_list(request):
    """Zeigt eine Liste aller vergangenen Trainings."""
    # Wir holen NUR die Trainings des aktuellen Users, sortiert nach Datum (neu -> alt)
    # annotate(satz_count=Count('saetze')) zählt die Sätze für die Vorschau
    trainings = Trainingseinheit.objects.filter(user=request.user).annotate(satz_count=Count('saetze')).order_by('-datum')

    # Volumen für jedes Training berechnen
    trainings_mit_volumen = []
    for training in trainings:
        arbeitssaetze = training.saetze.filter(ist_aufwaermsatz=False)
        volumen = sum(float(s.gewicht) * s.wiederholungen for s in arbeitssaetze)
        trainings_mit_volumen.append({
            'training': training,
            'volumen': round(volumen, 1),
            'arbeitssaetze': arbeitssaetze.count()
        })

    context = {
        'trainings_data': trainings_mit_volumen
    }
    return render(request, 'core/training_list.html', context)


@login_required
def delete_training(request, training_id):
    """Löscht ein komplettes Training aus der Historie."""
    training = get_object_or_404(Trainingseinheit, id=training_id, user=request.user)
    training.delete()
    # Wir leiten zurück zur Liste (History)
    return redirect('training_list')


@login_required
def exercise_stats(request, uebung_id):
    """Berechnet 1RM-Verlauf und Rekorde für eine Übung."""
    uebung = get_object_or_404(
        Uebung,
        Q(is_custom=False) | Q(created_by=request.user),
        id=uebung_id,
    )

    # Alle Arbeitssätze holen (keine Warmups), chronologisch sortiert
    saetze = Satz.objects.filter(
        einheit__user=request.user,
        uebung=uebung,
        ist_aufwaermsatz=False
    ).select_related('einheit').order_by('einheit__datum')

    if not saetze.exists():
        return render(request, 'core/stats_exercise.html', {
            'uebung': uebung,
            'no_data': True
        })

    # Daten für den Graphen aufbereiten
    # Wir wollen pro Datum nur den BESTEN 1RM Wert
    history_data = {} # Key: DatumString, Value: 1RM

    personal_record = 0
    best_weight = 0
    max_volume = 0

    for satz in saetze:
        # 1. Gewicht normalisieren (für Vergleichbarkeit)
        effektives_gewicht = float(satz.gewicht)
        if uebung.gewichts_typ == 'PRO_SEITE':
            effektives_gewicht *= 2
        elif uebung.gewichts_typ == 'KOERPERGEWICHT':
            # Hier könnten wir später das Körpergewicht des Nutzers addieren
            # Für V1 nehmen wir nur das Zusatzgewicht
            pass

        # 2. 1RM nach Epley berechnen
        # Formel: Gewicht * (1 + Wdh/30)
        # Bei Zeit-Übungen macht 1RM keinen Sinn -> da nehmen wir einfach die Sekunden/Wdh als Wert
        if uebung.gewichts_typ == 'ZEIT':
            one_rep_max = float(satz.wiederholungen)
        else:
            if effektives_gewicht > 0:
                one_rep_max = effektives_gewicht * (1 + (satz.wiederholungen / 30))
            else:
                one_rep_max = 0

        # 3. Bestwert des Tages ermitteln
        datum_str = satz.einheit.datum.strftime('%d.%m.%Y')
        if datum_str not in history_data or one_rep_max > history_data[datum_str]:
            history_data[datum_str] = round(one_rep_max, 1)

        # 4. Rekorde updaten
        if one_rep_max > personal_record:
            personal_record = round(one_rep_max, 1)
        if effektives_gewicht > best_weight:
            best_weight = effektives_gewicht

    # Chart.js braucht Listen
    labels = list(history_data.keys())
    data = list(history_data.values())

    # Durchschnittliches RPE berechnen
    avg_rpe = saetze.aggregate(Avg('rpe'))['rpe__avg']
    avg_rpe_display = round(avg_rpe, 1) if avg_rpe else None

    # RPE-Trend berechnen (letzte 4 Wochen vs. davor)
    rpe_trend = None
    if avg_rpe:
        heute = timezone.now()
        vier_wochen_alt = heute - timedelta(days=28)
        acht_wochen_alt = heute - timedelta(days=56)

        recent_rpe = saetze.filter(
            einheit__datum__gte=vier_wochen_alt
        ).aggregate(Avg('rpe'))['rpe__avg']

        older_rpe = saetze.filter(
            einheit__datum__gte=acht_wochen_alt,
            einheit__datum__lt=vier_wochen_alt
        ).aggregate(Avg('rpe'))['rpe__avg']

        if recent_rpe and older_rpe:
            diff = recent_rpe - older_rpe
            if diff < -0.3:
                rpe_trend = 'improving'  # RPE sinkt = besser
            elif diff > 0.3:
                rpe_trend = 'declining'  # RPE steigt = schlechter
            else:
                rpe_trend = 'stable'

    context = {
        'uebung': uebung,
        'labels_json': json.dumps(labels),
        'data_json': json.dumps(data),
        'personal_record': personal_record,
        'best_weight': best_weight,
        'avg_rpe': avg_rpe_display,
        'rpe_trend': rpe_trend,
    }
    return render(request, 'core/stats_exercise.html', context)


@login_required
def training_stats(request):
    """Erweiterte Trainingsstatistiken mit Volumen-Progression und Analyse."""
    # Alle Trainings mit Volumen
    trainings = Trainingseinheit.objects.filter(user=request.user).order_by('datum')

    if not trainings.exists():
        return render(request, 'core/training_stats.html', {'no_data': True})

    # Volumen-Daten pro Training
    volumen_labels = []
    volumen_data = []

    for training in trainings:
        arbeitssaetze = training.saetze.filter(ist_aufwaermsatz=False)
        volumen = sum(
            float(s.gewicht) * s.wiederholungen
            for s in arbeitssaetze
            if s.gewicht and s.wiederholungen
        )
        volumen_labels.append(training.datum.strftime('%d.%m'))
        volumen_data.append(round(volumen, 1))

    # Wöchentliches Volumen (letzte 12 Wochen)
    weekly_volume = defaultdict(float)

    for training in trainings:
        # ISO-Kalenderwoche verwenden (konsistent mit PDF Export)
        iso_year, iso_week, _ = training.datum.isocalendar()
        week_key = f"{iso_year}-W{iso_week:02d}"
        arbeitssaetze = training.saetze.filter(ist_aufwaermsatz=False)
        volumen = sum(
            float(s.gewicht) * s.wiederholungen
            for s in arbeitssaetze
            if s.gewicht and s.wiederholungen
        )
        weekly_volume[week_key] += volumen

    # Letzte 12 Wochen
    weekly_labels = sorted(weekly_volume.keys())[-12:]
    weekly_data = [round(weekly_volume[k], 1) for k in weekly_labels]

    # Muskelgruppen-Balance (RPE-gewichtet)
    muskelgruppen_stats = {}
    muskelgruppen_stats_code = {}  # Für SVG-Mapping
    for training in trainings:
        for satz in training.saetze.filter(ist_aufwaermsatz=False):
            # Überspringe Sätze ohne Wiederholungen/RPE
            if not satz.wiederholungen or not satz.rpe:
                continue

            mg_display = satz.uebung.get_muskelgruppe_display()
            mg_code = satz.uebung.muskelgruppe

            # Effektive Wiederholungen: Wiederholungen × (RPE/10)
            effektive_wdh = satz.wiederholungen * (float(satz.rpe) / 10.0)

            if mg_display not in muskelgruppen_stats:
                muskelgruppen_stats[mg_display] = {'saetze': 0, 'volumen': 0}
            muskelgruppen_stats[mg_display]['saetze'] += 1
            muskelgruppen_stats[mg_display]['volumen'] += effektive_wdh

            # Für SVG-Mapping
            if mg_code not in muskelgruppen_stats_code:
                muskelgruppen_stats_code[mg_code] = 0
            muskelgruppen_stats_code[mg_code] += effektive_wdh

    # Sortieren nach Volumen
    muskelgruppen_sorted = sorted(
        muskelgruppen_stats.items(),
        key=lambda x: x[1]['volumen'],
        reverse=True
    )

    mg_labels = [mg[0] for mg in muskelgruppen_sorted]
    mg_data = [round(mg[1]['volumen'], 1) for mg in muskelgruppen_sorted]

    # SVG-Mapping: MUSKELGRUPPEN Code → Volumen
    # Normalisiere Volumen für Farb-Intensität (0-1)
    max_volumen = max(muskelgruppen_stats_code.values()) if muskelgruppen_stats_code else 1
    muscle_intensity = {}
    for code, volumen in muskelgruppen_stats_code.items():
        muscle_intensity[code] = round(volumen / max_volumen, 2)

    # Muscle mapping für SVG (gleich wie in muscle_map view)
    muscle_mapping = {
        'BRUST': ['front_chest_left', 'front_chest_right'],
        'TRIZEPS': ['back_triceps_left', 'back_triceps_right'],
        'BIZEPS': ['front_biceps_left', 'front_biceps_right'],
        'SCHULTER_VORN': ['front_delt_left', 'front_delt_right'],
        'SCHULTER_SEIT': ['front_delt_left', 'front_delt_right'],  # Approximation
        'SCHULTER_HINT': ['back_delt_left', 'back_delt_right'],
        'RUECKEN_LAT': ['back_lat_left', 'back_lat_right'],
        'RUECKEN_TRAPEZ': ['back_trap_left', 'back_trap_right'],
        'RUECKEN_UNTEN': ['back_lower_back'],
        'BEINE_QUAD': ['front_quad_left', 'front_quad_right'],
        'BEINE_HAM': ['back_ham_left', 'back_ham_right'],
        'WADEN': ['back_calves_left', 'back_calves_right'],
        'PO': ['back_glutes_left', 'back_glutes_right'],
        'BAUCH': ['front_abs'],
        'UNTERARME': ['front_forearm_left', 'front_forearm_right'],
        'ADDUKTOREN': ['front_quad_left', 'front_quad_right'],  # Approximation
        'ABDUKTOREN': ['back_glutes_left', 'back_glutes_right'],  # Approximation
    }

    # Erstelle JSON-Daten für SVG-Färbung
    svg_muscle_data = {}
    for code, intensity in muscle_intensity.items():
        svg_ids = muscle_mapping.get(code, [])
        for svg_id in svg_ids:
            # Intensität akkumulieren falls mehrere Codes auf gleiche SVG-IDs mappen
            if svg_id in svg_muscle_data:
                svg_muscle_data[svg_id] = min(1.0, svg_muscle_data[svg_id] + intensity)
            else:
                svg_muscle_data[svg_id] = intensity

    # Gesamtstatistiken
    gesamt_volumen = sum(volumen_data)
    durchschnitt_pro_training = round(gesamt_volumen / len(trainings), 1) if trainings else 0

    # Deload-Erkennung: Volumen-Spikes zwischen Wochen
    deload_warnings = []
    if len(weekly_data) >= 2:
        for i in range(1, len(weekly_data)):
            current_volume = weekly_data[i]
            previous_volume = weekly_data[i-1]

            if previous_volume > 0:  # Vermeide Division durch 0
                change_percent = ((current_volume - previous_volume) / previous_volume) * 100

                # Warnung bei >20% Anstieg
                if change_percent > 20:
                    deload_warnings.append({
                        'week': weekly_labels[i],
                        'increase': round(change_percent, 1),
                        'volume': round(current_volume, 1),
                        'type': 'spike'
                    })
                # Warnung bei >30% Rückgang (mögliches Plateau/Burnout)
                elif change_percent < -30:
                    deload_warnings.append({
                        'week': weekly_labels[i],
                        'decrease': abs(round(change_percent, 1)),
                        'volume': round(current_volume, 1),
                        'type': 'drop'
                    })

    # Heatmap-Daten (letzte 90 Tage)
    heute = timezone.now().date()
    start_date = heute - timedelta(days=89)  # 90 Tage

    # Dictionary für schnelle Lookups
    training_dates = {}
    for training in trainings.filter(datum__gte=start_date):
        date_key = training.datum.date().isoformat()
        if date_key not in training_dates:
            training_dates[date_key] = 0
        training_dates[date_key] += 1

    # Heatmap-Array erstellen
    heatmap_data = []
    current_date = start_date
    while current_date <= heute:
        date_key = current_date.isoformat()
        heatmap_data.append({
            'date': date_key,
            'count': training_dates.get(date_key, 0)
        })
        current_date += timedelta(days=1)

    context = {
        'trainings_count': trainings.count(),
        'gesamt_volumen': round(gesamt_volumen, 1),
        'durchschnitt_volumen': durchschnitt_pro_training,
        'volumen_labels_json': json.dumps(volumen_labels),
        'volumen_data_json': json.dumps(volumen_data),
        'weekly_labels_json': json.dumps(weekly_labels),
        'weekly_data_json': json.dumps(weekly_data),
        'mg_labels_json': json.dumps(mg_labels),
        'mg_data_json': json.dumps(mg_data),
        'muskelgruppen_stats': muskelgruppen_sorted,
        'heatmap_data_json': json.dumps(heatmap_data),
        'deload_warnings': deload_warnings,
        'svg_muscle_data_json': json.dumps(svg_muscle_data),
    }
    return render(request, 'core/training_stats.html', context)
