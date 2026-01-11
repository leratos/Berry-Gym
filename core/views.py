from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Count, Max, Sum, Avg, F
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from .models import (
    Trainingseinheit, KoerperWerte, Uebung, Satz, Plan, PlanUebung, 
    ProgressPhoto, Equipment, MUSKELGRUPPEN, BEWEGUNGS_TYP, GEWICHTS_TYP
)
from django.db import models
import re
import json
import random
import os


def register(request):
    """Registrierung neuer Benutzer."""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=password)
            login(request, user)
            messages.success(request, f'Account erfolgreich erstellt! Willkommen, {username}!')
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'registration/register.html', {'form': form})


@login_required
def dashboard(request):
    letztes_training = Trainingseinheit.objects.filter(user=request.user).first()
    letzter_koerperwert = KoerperWerte.objects.first()
    
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
                ist_aufwaermsatz=False
            ).aggregate(
                total=Sum('gewicht') * Sum('wiederholungen')
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
            datum__gte=heute - timedelta(days=7)
        ).count()
        
        if last_7_days >= 6:
            fatigue_index += 30
            fatigue_warnings.append('Sehr hohe Trainingsfrequenz')
        elif last_7_days >= 5:
            fatigue_index += 15
    
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
    import random
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
    import json
    training_heatmap_json = json.dumps(training_heatmap)
    
    context = {
        'letztes_training': letztes_training,
        'letzter_koerperwert': letzter_koerperwert,
        'trainings_diese_woche': trainings_diese_woche,
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
    }
    return render(request, 'core/dashboard.html', context)

def training_select_plan(request):
    """Zeigt alle verfügbaren Pläne zur Auswahl an."""
    plaene = Plan.objects.all()
    return render(request, 'core/training_select_plan.html', {'plaene': plaene})

def plan_details(request, plan_id):
    """Zeigt Details eines Trainingsplans mit allen Übungen."""
    plan = get_object_or_404(Plan, id=plan_id)
    plan_uebungen = plan.uebungen.all().order_by('reihenfolge')
    
    # Für jede Übung das letzte verwendete Gewicht holen (für Vorschau)
    uebungen_mit_historie = []
    for plan_uebung in plan_uebungen:
        letzter_satz = Satz.objects.filter(
            uebung=plan_uebung.uebung,
            ist_aufwaermsatz=False
        ).order_by('-einheit__datum').first()
        
        uebungen_mit_historie.append({
            'plan_uebung': plan_uebung,
            'letztes_gewicht': letzter_satz.gewicht if letzter_satz else None,
            'letzte_wdh': letzter_satz.wiederholungen if letzter_satz else None,
        })
    
    context = {
        'plan': plan,
        'uebungen_mit_historie': uebungen_mit_historie,
    }
    return render(request, 'core/plan_details.html', context)

def training_start(request, plan_id=None):
    """Startet Training. Wenn plan_id da ist, werden Übungen vor-angelegt."""
    training = Trainingseinheit.objects.create(user=request.user)
    
    if plan_id:
        plan = get_object_or_404(Plan, id=plan_id, user=request.user)
        training.plan = plan
        training.save()
        # Wir gehen alle Übungen im Plan durch
        for plan_uebung in plan.uebungen.all().order_by('reihenfolge'):
            uebung = plan_uebung.uebung
            
            # SMART GHOSTING: Wir schauen, was du letztes Mal gemacht hast
            letzter_satz = Satz.objects.filter(einheit__user=request.user, uebung=uebung, ist_aufwaermsatz=False).order_by('-einheit__datum', '-satz_nr').first()
            
            # Gewicht: Historie gewinnt (Ghosting), da im Plan oft kein kg steht
            start_gewicht = letzter_satz.gewicht if letzter_satz else 0
            
            # Wiederholungen: PLAN gewinnt vor Historie!
            start_wdh = 0
            
            # Versuch 1: Wir lesen die Zahl aus dem Plan (z.B. "12" oder "8-12")
            ziel_text = plan_uebung.wiederholungen_ziel
            # re.search sucht die erste Zahl im Text
            match = re.search(r'\d+', str(ziel_text)) if ziel_text else None
            
            if match:
                start_wdh = int(match.group())
            # Versuch 2: Wenn im Plan nix steht, nehmen wir die Historie
            elif letzter_satz:
                start_wdh = letzter_satz.wiederholungen
            
            # Anzahl der Sätze aus dem Plan holen
            anzahl_saetze = plan_uebung.saetze_ziel
            
            # Superset-Gruppe aus dem Plan übernehmen
            superset_gruppe = plan_uebung.superset_gruppe
            
            # Wir erstellen so viele Platzhalter-Sätze, wie im Plan stehen
            for i in range(1, anzahl_saetze + 1):
                Satz.objects.create(
                    einheit=training,
                    uebung=uebung,
                    satz_nr=i,
                    gewicht=start_gewicht,
                    wiederholungen=start_wdh,
                    ist_aufwaermsatz=False,
                    superset_gruppe=superset_gruppe
                )
            
    return redirect('training_session', training_id=training.id)

@login_required
def training_session(request, training_id):
    training = get_object_or_404(Trainingseinheit, id=training_id, user=request.user)
    
    # Sortieren für Gruppierung: Erst Muskelgruppe, dann Übungsname
    uebungen = Uebung.objects.all().order_by('muskelgruppe', 'bezeichnung')
    
    # Sortierung nach Plan-Reihenfolge wenn Training aus Plan gestartet wurde
    if training.plan:
        # Erstelle eine Map von uebung_id zu reihenfolge aus dem Plan
        plan_reihenfolge = {pu.uebung_id: pu.reihenfolge for pu in training.plan.uebungen.all()}
        # Hole alle Sätze und sortiere nach Plan-Reihenfolge, dann Satz-Nummer
        saetze = sorted(
            training.saetze.all(),
            key=lambda s: (plan_reihenfolge.get(s.uebung_id, 999), s.satz_nr)
        )
    else:
        # Fallback: alphabetisch nach Übungsname
        saetze = training.saetze.all().order_by('uebung__bezeichnung', 'satz_nr')

    # Volumen berechnen (nur Arbeitssätze, keine Warmups)
    total_volume = 0
    arbeitssaetze = training.saetze.filter(ist_aufwaermsatz=False)
    for satz in arbeitssaetze:
        total_volume += float(satz.gewicht) * satz.wiederholungen

    context = {
        'training': training,
        'uebungen': uebungen,
        'saetze': saetze,
        'total_volume': round(total_volume, 1),
        'arbeitssaetze_count': arbeitssaetze.count(),
    }
    return render(request, 'core/training_session.html', context)

@login_required
def add_set(request, training_id):
    training = get_object_or_404(Trainingseinheit, id=training_id, user=request.user)
    
    if request.method == 'POST':
        uebung_id = request.POST.get('uebung')
        gewicht = request.POST.get('gewicht')
        wdh = request.POST.get('wiederholungen')
        rpe = request.POST.get('rpe')
        is_warmup = request.POST.get('ist_aufwaermsatz') == 'on'
        notiz = request.POST.get('notiz', '').strip()
        superset_gruppe = request.POST.get('superset_gruppe', 0)
        
        uebung = get_object_or_404(Uebung, id=uebung_id)
        
        # Automatische Satz-Nummerierung
        max_satz = training.saetze.filter(uebung=uebung).aggregate(Max('satz_nr'))['satz_nr__max']
        neue_nr = (max_satz or 0) + 1
        
        # Neuen Satz erstellen
        neuer_satz = Satz.objects.create(
            einheit=training,
            uebung=uebung,
            satz_nr=neue_nr,
            gewicht=gewicht,
            wiederholungen=wdh,
            ist_aufwaermsatz=is_warmup,
            rpe=rpe if rpe else None,
            notiz=notiz if notiz else None,
            superset_gruppe=int(superset_gruppe)
        )
        
        # PR-Check (nur für Arbeitssätze)
        pr_message = None
        if not is_warmup and gewicht and wdh:
            # Berechne 1RM für diesen Satz (Epley-Formel)
            gewicht_float = float(gewicht)
            wdh_int = int(wdh)
            current_1rm = gewicht_float * (1 + wdh_int / 30)
            
            # Hole bisheriges Maximum für diese Übung
            alte_saetze = Satz.objects.filter(
                uebung=uebung,
                ist_aufwaermsatz=False
            ).exclude(id=neuer_satz.id)
            
            if alte_saetze.exists():
                max_alter_satz = max(
                    [float(s.gewicht) * (1 + int(s.wiederholungen) / 30) for s in alte_saetze]
                )
                
                # Neuer PR?
                if current_1rm > max_alter_satz:
                    verbesserung = round(current_1rm - max_alter_satz, 1)
                    pr_message = f'🎉 NEUER REKORD! {uebung.bezeichnung}: {round(current_1rm, 1)} kg (1RM) - +{verbesserung} kg!'
                    messages.success(request, pr_message)
            else:
                # Erster Satz für diese Übung = automatisch PR
                pr_message = f'🏆 Erster Rekord gesetzt! {uebung.bezeichnung}: {round(current_1rm, 1)} kg (1RM)'
                messages.success(request, pr_message)
        
        # AJAX Request? Sende JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True, 
                'satz_id': neuer_satz.id,
                'pr_message': pr_message  # Neu: PR-Message für Toast
            })
        
        return redirect('training_session', training_id=training_id)
    
    return redirect('training_session', training_id=training_id)

def delete_set(request, set_id):
    """Löscht einen Satz und kehrt zur Liste zurück"""
    # Wir holen den Satz. Wenn er nicht existiert, gibt's nen 404 Fehler.
    satz = get_object_or_404(Satz, id=set_id)
    
    # Wir merken uns die Training-ID, bevor wir löschen, damit wir zurückspringen können
    training_id = satz.einheit.id
    
    satz.delete()
    
    return redirect('training_session', training_id=training_id)

def update_set(request, set_id):
    """Speichert Änderungen an einem existierenden Satz."""
    satz = get_object_or_404(Satz, id=set_id)
    training_id = satz.einheit.id
    
    if request.method == 'POST':
        satz.gewicht = request.POST.get('gewicht')
        satz.wiederholungen = request.POST.get('wiederholungen')
        satz.rpe = request.POST.get('rpe') if request.POST.get('rpe') else None
        satz.ist_aufwaermsatz = request.POST.get('ist_aufwaermsatz') == 'on'
        notiz = request.POST.get('notiz', '').strip()
        satz.notiz = notiz if notiz else None
        superset_gruppe = request.POST.get('superset_gruppe', 0)
        satz.superset_gruppe = int(superset_gruppe)
        satz.save()
        
        # AJAX Request? Sende JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
    
    return redirect('training_session', training_id=training_id)

@login_required
def add_koerperwert(request):
    """Formular zum Eintragen der erweiterten Watch-Daten"""
    
    # Wir holen den letzten Eintrag, um die Größe vorzuschlagen
    letzter_wert = KoerperWerte.objects.first()
    standard_groesse = letzter_wert.groesse_cm if letzter_wert else 180

    if request.method == 'POST':
        # Pflichtfelder
        groesse = request.POST.get('groesse')
        gewicht = request.POST.get('gewicht')
        
        # Optionale Watch-Daten
        fett_kg = request.POST.get('fett_kg')
        kfa = request.POST.get('kfa')
        wasser = request.POST.get('wasser')
        muskel = request.POST.get('muskel')
        knochen = request.POST.get('knochen')
        notiz = request.POST.get('notiz')

        # Speichern
        KoerperWerte.objects.create(
            user=request.user,
            groesse_cm=groesse,
            gewicht=gewicht,
            fettmasse_kg=fett_kg if fett_kg else None,
            koerperfett_prozent=kfa if kfa else None,
            koerperwasser_kg=wasser if wasser else None,
            muskelmasse_kg=muskel if muskel else None,
            knochenmasse_kg=knochen if knochen else None,
            notiz=notiz
        )
        return redirect('dashboard')
    
    context = {
        'standard_groesse': standard_groesse
    }
    return render(request, 'core/add_koerperwert.html', context)

def body_stats(request):
    """Zeigt Körperwerte-Verlauf mit Graphen."""
    werte = KoerperWerte.objects.all().order_by('datum')
    
    if not werte.exists():
        return render(request, 'core/body_stats.html', {'no_data': True})
    
    # Aktueller Wert & Veränderung
    aktueller_wert = werte.last()
    erster_wert = werte.first()
    aenderung = float(aktueller_wert.gewicht) - float(erster_wert.gewicht)
    
    # Daten für Charts vorbereiten
    labels = [w.datum.strftime('%d.%m.%y') for w in werte]
    gewicht_data = [float(w.gewicht) for w in werte]
    
    # BMI & FFMI
    bmi_data = [w.bmi if w.bmi else None for w in werte]
    ffmi_data = [w.ffmi if w.ffmi else None for w in werte]
    
    # Körperfett
    kfa_data = [float(w.koerperfett_prozent) if w.koerperfett_prozent else None for w in werte]
    
    # Muskelmasse
    muskel_data = [float(w.muskelmasse_kg) if w.muskelmasse_kg else None for w in werte]
    
    context = {
        'werte': werte,
        'aktuelles_gewicht': aktueller_wert.gewicht,
        'aenderung': aenderung,
        'labels_json': json.dumps(labels),
        'gewicht_json': json.dumps(gewicht_data),
        'bmi_json': json.dumps(bmi_data),
        'ffmi_json': json.dumps(ffmi_data),
        'kfa_json': json.dumps(kfa_data),
        'muskel_json': json.dumps(muskel_data),
        'aktuelles_gewicht': werte.last().gewicht if werte else None,
        'aenderung': round(float(werte.last().gewicht - werte.first().gewicht), 1) if werte.count() > 1 else 0,
    }
    return render(request, 'core/body_stats.html', context)

@login_required
def edit_koerperwert(request, wert_id):
    """Körperwert bearbeiten."""
    wert = get_object_or_404(KoerperWerte, id=wert_id, user=request.user)
    
    if request.method == 'POST':
        # Update fields
        wert.gewicht = request.POST.get('gewicht')
        wert.groesse_cm = request.POST.get('groesse_cm') or None
        wert.koerperfett_prozent = request.POST.get('koerperfett_prozent') or None
        wert.fettmasse_kg = request.POST.get('fettmasse_kg') or None
        wert.muskelmasse_kg = request.POST.get('muskelmasse_kg') or None
        wert.save()
        messages.success(request, 'Körperwert erfolgreich aktualisiert!')
        return redirect('body_stats')
    
    context = {
        'wert': wert,
    }
    return render(request, 'core/edit_koerperwert.html', context)

@login_required
def delete_koerperwert(request, wert_id):
    """Körperwert löschen."""
    wert = get_object_or_404(KoerperWerte, id=wert_id, user=request.user)
    wert.delete()
    messages.success(request, 'Körperwert erfolgreich gelöscht!')
    return redirect('body_stats')

@login_required
def toggle_favorite(request, uebung_id):
    """Toggle Favoriten-Status einer Übung."""
    uebung = get_object_or_404(Uebung, id=uebung_id)
    
    if request.user in uebung.favoriten.all():
        uebung.favoriten.remove(request.user)
        is_favorite = False
    else:
        uebung.favoriten.add(request.user)
        is_favorite = True
    
    return JsonResponse({'is_favorite': is_favorite})

@login_required
def export_training_csv(request):
    """Export aller Trainings-Daten als CSV."""
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="training_export.csv"'
    response.write('\ufeff')  # UTF-8 BOM für Excel
    
    writer = csv.writer(response)
    writer.writerow(['Datum', 'Übung', 'Muskelgruppe', 'Satz Nr.', 'Gewicht (kg)', 'Wiederholungen', 'RPE', 'Volumen (kg)', 'Aufwärmsatz', 'Notiz'])
    
    trainings = Trainingseinheit.objects.filter(user=request.user).prefetch_related('saetze__uebung').order_by('-datum')
    
    for training in trainings:
        for satz in training.saetze.all():
            volumen = float(satz.gewicht) * satz.wiederholungen if satz.gewicht else 0
            writer.writerow([
                training.datum.strftime('%d.%m.%Y'),
                satz.uebung.bezeichnung,
                satz.uebung.get_muskelgruppe_display(),
                satz.satznummer,
                float(satz.gewicht) if satz.gewicht else '',
                satz.wiederholungen,
                satz.rpe if satz.rpe else '',
                round(volumen, 1),
                'Ja' if satz.ist_aufwaermsatz else 'Nein',
                satz.notiz or ''
            ])
    
    return response

def training_list(request):
    """Zeigt eine Liste aller vergangenen Trainings."""
    # Wir holen alle Trainings, sortiert nach Datum (neu -> alt)
    # annotate(satz_count=Count('saetze')) zählt die Sätze für die Vorschau
    trainings = Trainingseinheit.objects.annotate(satz_count=Count('saetze')).order_by('-datum')
    
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

def delete_training(request, training_id):
    """Löscht ein komplettes Training aus der Historie."""
    training = get_object_or_404(Trainingseinheit, id=training_id)
    training.delete()
    # Wir leiten zurück zur Liste (History)
    return redirect('training_list')

@login_required
def get_last_set(request, uebung_id):
    """API: Liefert die Werte des letzten 'echten' Satzes einer Übung zurück."""
    # Wir suchen den allerletzten Satz dieser Übung (trainingübergreifend)
    # Wichtig: Wir ignorieren Aufwärmsätze (ist_aufwaermsatz=False)
    letzter_satz = Satz.objects.filter(
        einheit__user=request.user,
        uebung_id=uebung_id, 
        ist_aufwaermsatz=False
    ).order_by('-einheit__datum', '-satz_nr').first()

    if letzter_satz:
        # Progressive Overload Logik
        empfohlenes_gewicht = float(letzter_satz.gewicht)
        empfohlene_wdh = letzter_satz.wiederholungen
        
        # Wenn letztes Mal RPE sehr leicht war (< 7), mehr vorschlagen
        if letzter_satz.rpe and float(letzter_satz.rpe) < 7:
            # Bei RPE < 7: +2.5kg vorschlagen
            empfohlenes_gewicht += 2.5
            progression_hint = f"Letztes Mal RPE {letzter_satz.rpe} → versuch mehr Gewicht!"
        elif letzter_satz.rpe and float(letzter_satz.rpe) >= 9:
            # Bei RPE >= 9: Gewicht halten, aber mehr Wdh anstreben
            empfohlene_wdh = min(empfohlene_wdh + 1, 15)  # Max 15 Wdh
            progression_hint = f"Letztes Mal RPE {letzter_satz.rpe} → versuch mehr Wiederholungen!"
        elif letzter_satz.wiederholungen >= 12:
            # Wenn 12+ Wdh geschafft, mehr Gewicht vorschlagen
            empfohlenes_gewicht += 2.5
            empfohlene_wdh = 8  # Zurück zu niedrigeren Wdh
            progression_hint = "12+ Wdh geschafft → Zeit für mehr Gewicht!"
        else:
            progression_hint = "Halte das Niveau oder steigere dich leicht"
        
        return JsonResponse({
            'success': True,
            'gewicht': empfohlenes_gewicht,
            'wiederholungen': empfohlene_wdh,
            'rpe': letzter_satz.rpe,
            'progression_hint': progression_hint,
            'letztes_gewicht': float(letzter_satz.gewicht),
            'letzte_wdh': letzter_satz.wiederholungen,
        })
    else:
        return JsonResponse({'success': False})
    
@login_required
def exercise_stats(request, uebung_id):
    """Berechnet 1RM-Verlauf und Rekorde für eine Übung."""
    uebung = get_object_or_404(Uebung, id=uebung_id)
    
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
    from collections import defaultdict
    weekly_volume = defaultdict(float)
    
    for training in trainings:
        week_key = training.datum.strftime('%Y-W%W')
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
    from datetime import date, timedelta
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

def finish_training(request, training_id):
    """Zeigt Zusammenfassung und ermöglicht Speichern von Dauer/Kommentar."""
    training = get_object_or_404(Trainingseinheit, id=training_id)
    
    if request.method == 'POST':
        # Dauer und Kommentar speichern
        dauer = request.POST.get('dauer_minuten')
        kommentar = request.POST.get('kommentar')
        
        if dauer:
            training.dauer_minuten = dauer
        if kommentar:
            training.kommentar = kommentar
        training.save()
        
        return redirect('dashboard')
    
    # Statistiken für die Zusammenfassung berechnen
    arbeitssaetze = training.saetze.filter(ist_aufwaermsatz=False)
    warmup_saetze = training.saetze.filter(ist_aufwaermsatz=True)
    
    # Volumen berechnen
    total_volume = sum(float(s.gewicht) * s.wiederholungen for s in arbeitssaetze)
    
    # Anzahl Übungen
    uebungen_count = training.saetze.values('uebung').distinct().count()
    
    # Trainingsdauer schätzen (falls nicht manuell eingegeben)
    if training.datum:
        from django.utils import timezone
        dauer_geschaetzt = int((timezone.now() - training.datum).total_seconds() / 60)
    else:
        dauer_geschaetzt = 60
    
    context = {
        'training': training,
        'arbeitssaetze_count': arbeitssaetze.count(),
        'warmup_saetze_count': warmup_saetze.count(),
        'total_volume': round(total_volume, 1),
        'uebungen_count': uebungen_count,
        'dauer_geschaetzt': dauer_geschaetzt,
    }
    return render(request, 'core/training_finish.html', context)


# Trainingsplan ohne Admin erstellen
@login_required
def create_plan(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        beschreibung = request.POST.get('beschreibung', '')
        uebungen_ids = request.POST.getlist('uebungen')  # Liste von Übungs-IDs
        
        if name and uebungen_ids:
            plan = Plan.objects.create(user=request.user, name=name, beschreibung=beschreibung)
            
            # Übungen zum Plan hinzufügen
            for idx, uebung_id in enumerate(uebungen_ids, start=1):
                uebung = get_object_or_404(Uebung, id=uebung_id)
                saetze = request.POST.get(f'saetze_{uebung_id}', 3)
                wdh = request.POST.get(f'wdh_{uebung_id}', '8-12')
                
                PlanUebung.objects.create(
                    plan=plan,
                    uebung=uebung,
                    reihenfolge=idx,
                    saetze_ziel=saetze,
                    wiederholungen_ziel=wdh
                )
            
            messages.success(request, f'Trainingsplan "{name}" erfolgreich erstellt!')
            return redirect('plan_details', plan_id=plan.id)
    
    uebungen = Uebung.objects.all().order_by('muskelgruppe', 'bezeichnung')
    
    # Gruppiere Übungen nach Muskelgruppen für bessere Darstellung
    uebungen_nach_gruppe = {}
    for uebung in uebungen:
        mg_label = dict(MUSKELGRUPPEN).get(uebung.muskelgruppe, uebung.muskelgruppe)
        if mg_label not in uebungen_nach_gruppe:
            uebungen_nach_gruppe[mg_label] = []
        
        # Hilfsmuskelgruppen-Labels abrufen
        hilfs_labels = []
        if uebung.hilfsmuskeln:
            # Sicherstellen dass hilfsmuskeln eine Liste ist
            hilfsmuskeln = uebung.hilfsmuskeln if isinstance(uebung.hilfsmuskeln, list) else []
            for hm in hilfsmuskeln:
                hilfs_labels.append(dict(MUSKELGRUPPEN).get(hm, hm))
        
        uebungen_nach_gruppe[mg_label].append({
            'id': uebung.id,
            'bezeichnung': uebung.bezeichnung,
            'muskelgruppe': uebung.muskelgruppe,
            'muskelgruppe_label': mg_label,
            'hilfsmuskeln': hilfs_labels,
            'gewichts_typ': uebung.get_gewichts_typ_display(),
            'bewegungstyp': uebung.bewegungstyp,  # Für Empfehlungslogik
        })
    
    context = {
        'uebungen_nach_gruppe': uebungen_nach_gruppe,
        'muskelgruppen': MUSKELGRUPPEN,
    }
    return render(request, 'core/create_plan.html', context)


@login_required
def edit_plan(request, plan_id):
    plan = get_object_or_404(Plan, id=plan_id, user=request.user)
    
    if request.method == 'POST':
        plan.name = request.POST.get('name', plan.name)
        plan.beschreibung = request.POST.get('beschreibung', plan.beschreibung)
        plan.save()
        
        # Lösche alte PlanUebung-Zuordnungen
        PlanUebung.objects.filter(plan=plan).delete()
        
        # Neue Zuordnungen erstellen
        uebungen_ids = request.POST.getlist('uebungen')
        for idx, uebung_id in enumerate(uebungen_ids, start=1):
            uebung = get_object_or_404(Uebung, id=uebung_id)
            saetze = request.POST.get(f'saetze_{uebung_id}', 3)
            wdh = request.POST.get(f'wdh_{uebung_id}', '8-12')
            superset_gruppe = request.POST.get(f'superset_gruppe_{uebung_id}', 0)
            
            PlanUebung.objects.create(
                plan=plan,
                uebung=uebung,
                reihenfolge=idx,
                saetze_ziel=saetze,
                wiederholungen_ziel=wdh,
                superset_gruppe=int(superset_gruppe)
            )
        
        messages.success(request, f'Trainingsplan "{plan.name}" erfolgreich aktualisiert!')
        return redirect('plan_details', plan_id=plan.id)
    
    uebungen = Uebung.objects.all().order_by('muskelgruppe', 'bezeichnung')
    
    # Hole Plan-Übungen mit Details (Reihenfolge, Sets, Reps, Superset)
    plan_uebungen_details = {}
    for pu in plan.uebungen.all():
        plan_uebungen_details[pu.uebung_id] = {
            'reihenfolge': pu.reihenfolge,
            'saetze': pu.saetze_ziel,
            'wdh': pu.wiederholungen_ziel,
            'superset_gruppe': pu.superset_gruppe
        }
    
    plan_uebung_ids = list(plan_uebungen_details.keys())
    
    # Gruppiere Übungen nach Muskelgruppen
    uebungen_nach_gruppe = {}
    for uebung in uebungen:
        mg_label = dict(MUSKELGRUPPEN).get(uebung.muskelgruppe, uebung.muskelgruppe)
        if mg_label not in uebungen_nach_gruppe:
            uebungen_nach_gruppe[mg_label] = []
        
        # Hilfsmuskelgruppen-Labels abrufen
        hilfs_labels = []
        if uebung.hilfsmuskeln:
            # Sicherstellen dass hilfsmuskeln eine Liste ist
            hilfsmuskeln = uebung.hilfsmuskeln if isinstance(uebung.hilfsmuskeln, list) else []
            for hm in hilfsmuskeln:
                hilfs_labels.append(dict(MUSKELGRUPPEN).get(hm, hm))
        
        uebung_data = {
            'id': uebung.id,
            'bezeichnung': uebung.bezeichnung,
            'muskelgruppe': uebung.muskelgruppe,
            'muskelgruppe_label': mg_label,
            'hilfsmuskeln': hilfs_labels,
            'gewichts_typ': uebung.get_gewichts_typ_display(),
            'bewegungstyp': uebung.bewegungstyp,  # Für Empfehlungslogik
            'in_plan': uebung.id in plan_uebung_ids,
        }
        
        # Füge Plan-Details hinzu wenn in Plan
        if uebung.id in plan_uebungen_details:
            uebung_data.update(plan_uebungen_details[uebung.id])
        
        uebungen_nach_gruppe[mg_label].append(uebung_data)
    
    context = {
        'plan': plan,
        'uebungen_nach_gruppe': uebungen_nach_gruppe,
        'muskelgruppen': MUSKELGRUPPEN,
        'plan_uebungen_details': plan_uebungen_details,  # Für JavaScript
    }
    return render(request, 'core/edit_plan.html', context)


@login_required
def delete_plan(request, plan_id):
    plan = get_object_or_404(Plan, id=plan_id, user=request.user)
    
    if request.method == 'POST':
        name = plan.name
        plan.delete()
        messages.success(request, f'Trainingsplan "{name}" wurde gelöscht.')
        return redirect('training_select_plan')
    
    return redirect('plan_details', plan_id=plan_id)


@login_required
def uebungen_auswahl(request):
    """Übersicht aller Übungen mit grafischer Muskelgruppen-Darstellung"""
    # Equipment-Filter: Nur Übungen mit verfügbarem Equipment
    user_equipment_ids = request.user.verfuegbares_equipment.values_list('id', flat=True)
    
    if user_equipment_ids:
        # Filter: Übungen die ALLE ihre benötigten Equipment haben ODER keine Equipment-Anforderungen
        uebungen = []
        for uebung in Uebung.objects.prefetch_related('equipment').order_by('muskelgruppe', 'bezeichnung'):
            required_eq_ids = set(uebung.equipment.values_list('id', flat=True))
            # Verfügbar wenn: keine Equipment nötig ODER alle benötigten Equipment verfügbar
            if not required_eq_ids or required_eq_ids.issubset(set(user_equipment_ids)):
                uebungen.append(uebung)
    else:
        # Keine Equipment ausgewählt: Nur Übungen ohne Equipment-Anforderung
        uebungen = Uebung.objects.filter(equipment__isnull=True).distinct().order_by('muskelgruppe', 'bezeichnung')
    
    # Gruppiere nach Muskelgruppen
    uebungen_nach_gruppe = {}
    for uebung in uebungen:
        mg_label = dict(MUSKELGRUPPEN).get(uebung.muskelgruppe, uebung.muskelgruppe)
        if mg_label not in uebungen_nach_gruppe:
            uebungen_nach_gruppe[mg_label] = []
        
        # Hilfsmuskelgruppen-Labels abrufen
        hilfs_labels = []
        if uebung.hilfsmuskeln:
            # Handle string format (comma-separated)
            if isinstance(uebung.hilfsmuskeln, str):
                hilfs_texte = [h.strip() for h in uebung.hilfsmuskeln.split(',')]
            else:
                hilfs_texte = uebung.hilfsmuskeln
            
            # Text-to-Code mapping (same as in uebung_detail)
            text_to_code = {
                'Trizeps': 'TRIZEPS',
                'Bizeps': 'BIZEPS',
                'Brust': 'BRUST',
                'Schulter - Vordere': 'SCHULTER_VORN',
                'Schulter - Seitliche': 'SCHULTER_SEIT',
                'Schulter - Hintere': 'SCHULTER_HINT',
                'Bauch': 'BAUCH',
                'Po': 'PO',
                'Unterarme': 'UNTERARME',
                'Rücken - Nacken/Trapez': 'RUECKEN_TRAPEZ',
                'Rücken - Breiter Muskel': 'RUECKEN_LAT',
                'Rücken - Latissimus': 'RUECKEN_LAT',
                'Unterer Rücken': 'RUECKEN_UNTEN',
                'Beine - Quadrizeps': 'BEINE_QUAD',
                'Beine - Hamstrings': 'BEINE_HAM',
                'Waden': 'WADEN',
                'Adduktoren': 'ADDUKTOREN',
            }
            
            import re
            for hilfs_text in hilfs_texte:
                # Clean text (remove parentheses content)
                hilfs_text_clean = re.sub(r'\([^)]*\)', '', hilfs_text).strip()
                # Try to get code
                code = text_to_code.get(hilfs_text_clean)
                if code:
                    # Get display label for the code
                    label = dict(MUSKELGRUPPEN).get(code, hilfs_text_clean)
                    hilfs_labels.append(label)
                else:
                    # Fallback: use text as-is
                    hilfs_labels.append(hilfs_text_clean)
        
        uebungen_nach_gruppe[mg_label].append({
            'id': uebung.id,
            'bezeichnung': uebung.bezeichnung,
            'muskelgruppe': uebung.muskelgruppe,
            'muskelgruppe_label': mg_label,
            'hilfsmuskeln': hilfs_labels,
            'hilfsmuskeln_count': len(hilfs_labels),
            'bewegungstyp': uebung.get_bewegungstyp_display(),
            'gewichts_typ': uebung.get_gewichts_typ_display(),
        })
    
    context = {
        'uebungen_nach_gruppe': uebungen_nach_gruppe,
    }
    return render(request, 'core/uebungen_auswahl.html', context)


@login_required
def muscle_map(request):
    """Interaktive Muscle-Map mit klickbaren Muskelgruppen"""
    # Filter nach Muskelgruppe (optional)
    selected_group = request.GET.get('muskelgruppe', None)
    
    if selected_group:
        uebungen = Uebung.objects.filter(muskelgruppe=selected_group).order_by('bezeichnung')
        group_label = dict(MUSKELGRUPPEN).get(selected_group, selected_group)
    else:
        uebungen = None
        group_label = None
    
    # Mapping: SVG-ID -> Muskelgruppe
    muscle_mapping = {
        'BRUST': ['front_chest_left', 'front_chest_right'],
        'SCHULTER_VORN': ['front_delt_left', 'front_delt_right'],
        'SCHULTER_SEIT': ['front_delt_left', 'front_delt_right'],  # Approximation
        'SCHULTER_HINT': ['back_delt_left', 'back_delt_right'],
        'BIZEPS': ['front_biceps_left', 'front_biceps_right'],
        'TRIZEPS': ['back_triceps_left', 'back_triceps_right'],
        'UNTERARME': ['front_forearm_left', 'front_forearm_right', 'back_forearm_left', 'back_forearm_right'],
        'RUECKEN_LAT': ['back_lat_left', 'back_lat_right'],
        'RUECKEN_TRAPEZ': ['back_traps_left', 'back_traps_right', 'front_traps_left', 'front_traps_right'],
        'RUECKEN_OBERER': ['back_midback'],
        'RUECKEN_UNTEN': ['back_erectors_left', 'back_erectors_right'],
        'BAUCH': ['front_abs_upper', 'front_abs_mid', 'front_abs_lower', 'front_oblique_left', 'front_oblique_right'],
        'BEINE_QUAD': ['front_quad_left', 'front_quad_right'],
        'BEINE_HAM': ['back_hamstring_left', 'back_hamstring_right'],
        'PO': ['back_glute_left', 'back_glute_right'],
        'WADEN': ['front_calf_left', 'front_calf_right', 'back_calf_left', 'back_calf_right'],
        'ADDUKTOREN': ['front_adductor_left', 'front_adductor_right'],
        'ABDUKTOREN': [],  # Nicht direkt in SVG dargestellt
        'GANZKOERPER': [],
    }
    
    context = {
        'uebungen': uebungen,
        'selected_group': selected_group,
        'group_label': group_label,
        'muscle_mapping': json.dumps(muscle_mapping),
        'muskelgruppen': MUSKELGRUPPEN,
    }
    return render(request, 'core/muscle_map.html', context)


@login_required
def uebung_detail(request, uebung_id):
    """Detail-Ansicht einer Übung mit anatomischer Visualisierung"""
    uebung = get_object_or_404(Uebung, id=uebung_id)
    
    # Mapping: Muskelgruppe -> SVG-IDs
    muscle_mapping = {
        'BRUST': ['front_chest_left', 'front_chest_right'],
        'SCHULTER_VORN': ['front_delt_left', 'front_delt_right'],
        'SCHULTER_SEIT': ['front_delt_left', 'front_delt_right'],
        'SCHULTER_HINT': ['back_delt_left', 'back_delt_right'],
        'BIZEPS': ['front_biceps_left', 'front_biceps_right'],
        'TRIZEPS': ['back_triceps_left', 'back_triceps_right'],
        'UNTERARME': ['front_forearm_left', 'front_forearm_right', 'back_forearm_left', 'back_forearm_right'],
        'RUECKEN_LAT': ['back_lat_left', 'back_lat_right'],
        'RUECKEN_TRAPEZ': ['back_traps_left', 'back_traps_right', 'front_traps_left', 'front_traps_right'],
        'RUECKEN_OBERER': ['back_midback'],
        'RUECKEN_UNTEN': ['back_erectors_left', 'back_erectors_right'],
        'BAUCH': ['front_abs_upper', 'front_abs_mid', 'front_abs_lower', 'front_oblique_left', 'front_oblique_right'],
        'BEINE_QUAD': ['front_quad_left', 'front_quad_right'],
        'BEINE_HAM': ['back_hamstring_left', 'back_hamstring_right'],
        'PO': ['back_glute_left', 'back_glute_right'],
        'WADEN': ['front_calf_left', 'front_calf_right', 'back_calf_left', 'back_calf_right'],
        'ADDUKTOREN': ['front_adductor_left', 'front_adductor_right'],
        'ABDUKTOREN': [],
        'GANZKOERPER': [],
    }
    
    # Mapping: Text-Bezeichnung -> Muskelgruppen-Code
    text_to_code = {
        'Trizeps': 'TRIZEPS',
        'Bizeps': 'BIZEPS',
        'Brust': 'BRUST',
        'Schulter - Vordere': 'SCHULTER_VORN',
        'Schulter - Seitliche': 'SCHULTER_SEIT',
        'Schulter - Hintere': 'SCHULTER_HINT',
        'Bauch': 'BAUCH',
        'Po': 'PO',
        'Unterarme': 'UNTERARME',
        'Rücken - Nacken/Trapez': 'RUECKEN_TRAPEZ',
        'Rücken - Breiter Muskel': 'RUECKEN_LAT',
        'Rücken - Latissimus': 'RUECKEN_LAT',
        'Unterer Rücken': 'RUECKEN_UNTEN',
        'Beine - Quadrizeps': 'BEINE_QUAD',
        'Beine - Hamstrings': 'BEINE_HAM',
        'Waden': 'WADEN',
        'Adduktoren': 'ADDUKTOREN',
    }
    
    # SVG-IDs für Hauptmuskel (rot)
    main_muscle_ids = muscle_mapping.get(uebung.muskelgruppe, [])
    
    # SVG-IDs für Hilfsmuskeln (blau)
    helper_muscle_ids = []
    if uebung.hilfsmuskeln:
        # hilfsmuskeln ist ein JSON-Array mit Muskelgruppen-Codes
        if isinstance(uebung.hilfsmuskeln, str):
            hilfs_codes = [h.strip() for h in uebung.hilfsmuskeln.split(',')]
        else:
            hilfs_codes = uebung.hilfsmuskeln
        
        for code in hilfs_codes:
            # Code ist bereits im Format 'BIZEPS', 'BAUCH' etc.
            # Direkt im muscle_mapping nachschlagen
            if code in muscle_mapping:
                helper_muscle_ids.extend(muscle_mapping.get(code, []))
    
    # Statistiken zur Übung
    alle_saetze = Satz.objects.filter(einheit__user=request.user, uebung=uebung, ist_aufwaermsatz=False)
    max_gewicht = alle_saetze.aggregate(Max('gewicht'))['gewicht__max'] or 0
    total_volumen = sum(float(s.gewicht) * s.wiederholungen for s in alle_saetze)
    
    context = {
        'uebung': uebung,
        'main_muscle_ids': json.dumps(main_muscle_ids),
        'helper_muscle_ids': json.dumps(helper_muscle_ids),
        'max_gewicht': max_gewicht,
        'total_volumen': round(total_volumen, 1),
        'anzahl_saetze': alle_saetze.count(),
    }
    return render(request, 'core/uebung_detail.html', context)


@login_required
def progress_photos(request):
    """Zeigt alle Fortschrittsfotos des Users in einer Timeline."""
    photos = ProgressPhoto.objects.filter(user=request.user).order_by('-datum')
    
    # Gewichtsverlauf für Timeline
    koerperwerte = KoerperWerte.objects.filter(user=request.user).order_by('-datum')[:30]
    
    context = {
        'photos': photos,
        'koerperwerte': koerperwerte,
    }
    return render(request, 'core/progress_photos.html', context)


@login_required
def upload_progress_photo(request):
    """Upload eines neuen Fortschrittsfotos."""
    if request.method == 'POST':
        foto = request.FILES.get('foto')
        gewicht_kg = request.POST.get('gewicht_kg', '').strip()
        notiz = request.POST.get('notiz', '').strip()
        
        if not foto:
            messages.error(request, 'Bitte wähle ein Foto aus.')
            return redirect('progress_photos')
        
        # Foto speichern
        photo = ProgressPhoto.objects.create(
            user=request.user,
            foto=foto,
            gewicht_kg=gewicht_kg if gewicht_kg else None,
            notiz=notiz if notiz else None
        )
        
        messages.success(request, 'Foto erfolgreich hochgeladen!')
        return redirect('progress_photos')
    
    return redirect('progress_photos')


@login_required
def delete_progress_photo(request, photo_id):
    """Löscht ein Fortschrittsfoto."""
    photo = get_object_or_404(ProgressPhoto, id=photo_id, user=request.user)
    
    if request.method == 'POST':
        # Datei löschen
        if photo.foto:
            photo.foto.delete()
        
        photo.delete()
        messages.success(request, 'Foto gelöscht.')
        return redirect('progress_photos')
    
    return redirect('progress_photos')


@login_required
def export_training_pdf(request):
    """Exportiert Trainingsstatistiken als PDF (xhtml2pdf als primärer Renderer)."""
    from io import BytesIO
    import logging
    from core.chart_generator import generate_muscle_heatmap, generate_volume_chart, generate_push_pull_pie
    
    logger = logging.getLogger(__name__)
    
    # Helper-Funktion: Muskelgruppe Key zu Display Name
    muskelgruppen_dict = dict(MUSKELGRUPPEN)
    
    # Nutze xhtml2pdf als primären Renderer (zuverlässiger)
    try:
        from xhtml2pdf import pisa
    except ImportError:
        messages.error(request, 'PDF Export nicht verfügbar - xhtml2pdf fehlt')
        logger.error('xhtml2pdf import failed')
        return redirect('training_stats')
    
    # Daten sammeln
    heute = timezone.now()
    letzte_30_tage = heute - timedelta(days=30)
    letzte_90_tage = heute - timedelta(days=90)
    
    # Trainings
    trainings = Trainingseinheit.objects.filter(
        user=request.user,
        datum__gte=letzte_30_tage
    ).order_by('-datum')[:20]
    
    # Statistiken
    alle_trainings = Trainingseinheit.objects.filter(user=request.user)
    gesamt_trainings = alle_trainings.count()
    trainings_30_tage = alle_trainings.filter(datum__gte=letzte_30_tage).count()
    
    alle_saetze = Satz.objects.filter(
        einheit__user=request.user,
        ist_aufwaermsatz=False
    )
    gesamt_saetze = alle_saetze.count()
    saetze_30_tage = alle_saetze.filter(einheit__datum__gte=letzte_30_tage).count()
    
    # Volumen
    gesamt_volumen = sum(
        float(s.gewicht) * s.wiederholungen 
        for s in alle_saetze if s.gewicht and s.wiederholungen
    )
    volumen_30_tage = sum(
        float(s.gewicht) * s.wiederholungen 
        for s in alle_saetze.filter(einheit__datum__gte=letzte_30_tage)
        if s.gewicht and s.wiederholungen
    )
    
    # Durchschnittliche Trainingsfrequenz
    if gesamt_trainings > 0:
        erste_training = alle_trainings.order_by('datum').first()
        if erste_training:
            tage_aktiv = max(1, (heute - erste_training.datum).days)
            trainings_pro_woche = round((gesamt_trainings / tage_aktiv) * 7, 1)
        else:
            trainings_pro_woche = 0
    else:
        trainings_pro_woche = 0
    
    # Top Übungen mit mehr Details
    top_uebungen_raw = alle_saetze.values(
        'uebung__bezeichnung',
        'uebung__muskelgruppe'
    ).annotate(
        anzahl=Count('id'),
        max_gewicht=Max('gewicht'),
        avg_gewicht=Avg('gewicht'),
        total_volumen=Sum(
            F('gewicht') * F('wiederholungen'),
            output_field=models.FloatField()
        )
    ).order_by('-anzahl')[:10]
    
    # Konvertiere Muskelgruppe Keys zu Display Names
    top_uebungen = []
    for uebung in top_uebungen_raw:
        uebung_dict = dict(uebung)
        uebung_dict['muskelgruppe_display'] = muskelgruppen_dict.get(
            uebung['uebung__muskelgruppe'], 
            uebung['uebung__muskelgruppe']
        )
        top_uebungen.append(uebung_dict)
    
    # Kraftentwicklung: Top 5 Übungen mit messbarer Progression
    kraft_progression = []
    for uebung in top_uebungen[:5]:
        uebung_name = uebung['uebung__bezeichnung']
        uebung_saetze = alle_saetze.filter(
            uebung__bezeichnung=uebung_name
        ).order_by('einheit__datum')
        
        if uebung_saetze.count() >= 3:
            # Vergleiche erste 3 Sätze mit letzten 3 Sätzen
            erste_saetze = uebung_saetze[:3]
            # Hole die letzten 3 Sätze durch negative Indexierung
            letzte_saetze = list(uebung_saetze)[-3:]
            
            erstes_max = max((s.gewicht or 0) for s in erste_saetze)
            letztes_max = max((s.gewicht or 0) for s in letzte_saetze)
            
            if erstes_max > 0:
                progression_prozent = round(((letztes_max - erstes_max) / erstes_max) * 100, 1)
                kraft_progression.append({
                    'uebung': uebung_name,
                    'start_gewicht': erstes_max,
                    'aktuell_gewicht': letztes_max,
                    'progression': progression_prozent,
                    'muskelgruppe': muskelgruppen_dict.get(uebung['uebung__muskelgruppe'], uebung['uebung__muskelgruppe'])
                })
    
    kraft_progression = sorted(kraft_progression, key=lambda x: x['progression'], reverse=True)[:5]
    
    # Muskelgruppen-Balance mit intelligenter Bewertung
    muskelgruppen_stats = []
    
    # Empfohlene Sätze pro Muskelgruppe pro Monat (evidenzbasiert)
    empfohlene_saetze = {
        'brust': (12, 20),
        'ruecken_breiter': (15, 25),
        'ruecken_unterer': (10, 18),
        'schulter_vordere': (8, 15),
        'schulter_seitliche': (12, 20),
        'schulter_hintere': (12, 20),
        'bizeps': (10, 18),
        'trizeps': (10, 18),
        'quadrizeps': (15, 25),
        'hamstrings': (12, 20),
        'glutaeus': (10, 18),
        'waden': (12, 20),
        'bauch': (12, 25),
        'unterer_ruecken': (8, 15),
    }
    
    for gruppe_key, gruppe_name in MUSKELGRUPPEN:
        gruppe_saetze = alle_saetze.filter(
            uebung__muskelgruppe=gruppe_key,
            einheit__datum__gte=letzte_30_tage
        )
        anzahl = gruppe_saetze.count()
        
        # Berechne Empfehlung und Status
        empfehlung = empfohlene_saetze.get(gruppe_key, (12, 20))
        min_saetze, max_saetze = empfehlung
        
        if anzahl == 0:
            status = 'nicht_trainiert'
            status_label = 'Nicht trainiert'
            erklaerung = f'Diese Muskelgruppe wurde nicht trainiert. Empfehlung: {min_saetze}-{max_saetze} Sätze/Monat'
        elif anzahl < min_saetze:
            status = 'untertrainiert'
            status_label = 'Untertrainiert'
            erklaerung = f'Nur {anzahl} Sätze in 30 Tagen. Empfehlung: {min_saetze}-{max_saetze} Sätze für optimales Wachstum'
        elif anzahl > max_saetze:
            status = 'uebertrainiert'
            status_label = 'Mögl. Übertraining'
            erklaerung = f'{anzahl} Sätze könnten zu viel sein. Empfehlung: {min_saetze}-{max_saetze} Sätze. Regeneration prüfen!'
        else:
            status = 'optimal'
            status_label = 'Optimal'
            erklaerung = f'{anzahl} Sätze liegen im optimalen Bereich ({min_saetze}-{max_saetze})'
        
        if anzahl > 0:
            volumen = sum(
                float(s.gewicht) * s.wiederholungen
                for s in gruppe_saetze
                if s.gewicht and s.wiederholungen
            )
            avg_rpe = gruppe_saetze.aggregate(Avg('rpe'))['rpe__avg'] or 0
            muskelgruppen_stats.append({
                'key': gruppe_key,
                'name': gruppe_name,
                'saetze': anzahl,
                'volumen': round(volumen, 0),
                'avg_rpe': round(avg_rpe, 1),
                'status': status,
                'status_label': status_label,
                'erklaerung': erklaerung,
                'empfehlung_min': min_saetze,
                'empfehlung_max': max_saetze,
                'prozent_von_optimal': round((anzahl / ((min_saetze + max_saetze) / 2)) * 100, 0)
            })
    
    muskelgruppen_stats = sorted(muskelgruppen_stats, key=lambda x: x['saetze'], reverse=True)
    
    # Push/Pull-Balance Analyse
    push_groups = ['brust', 'schulter_vordere', 'schulter_seitliche', 'trizeps']
    pull_groups = ['ruecken_breiter', 'ruecken_unterer', 'schulter_hintere', 'bizeps']
    
    push_saetze = sum(mg['saetze'] for mg in muskelgruppen_stats if mg['key'] in push_groups)
    pull_saetze = sum(mg['saetze'] for mg in muskelgruppen_stats if mg['key'] in pull_groups)
    
    if pull_saetze > 0:
        push_pull_ratio = round(push_saetze / pull_saetze, 2)
    else:
        push_pull_ratio = 0
    
    # Bewertung der Balance
    if 0.9 <= push_pull_ratio <= 1.1:
        push_pull_bewertung = 'Ausgewogen'
        push_pull_empfehlung = 'Perfekt! Push/Pull-Verhältnis ist ausgeglichen.'
    elif push_pull_ratio > 1.1:
        push_pull_bewertung = 'Zu viel Push'
        push_pull_empfehlung = f'Ratio {push_pull_ratio}:1 - Mehr Pull-Training (Rücken, Bizeps) für Schultergesundheit!'
    else:
        push_pull_bewertung = 'Zu viel Pull'
        push_pull_empfehlung = f'Ratio {push_pull_ratio}:1 - Mehr Push-Training (Brust, Schultern) für Balance!'
    
    push_pull_balance = {
        'push_saetze': push_saetze,
        'pull_saetze': pull_saetze,
        'ratio': push_pull_ratio,
        'bewertung': push_pull_bewertung,
        'empfehlung': push_pull_empfehlung
    }
    
    # Schwachstellen identifizieren (untertrainierte Muskelgruppen)
    schwachstellen = [mg for mg in muskelgruppen_stats if mg['status'] in ['untertrainiert', 'nicht_trainiert']]
    schwachstellen = sorted(schwachstellen, key=lambda x: x['saetze'])[:5]
    
    # Intensitäts-Analyse (RPE-basiert)
    rpe_saetze = alle_saetze.filter(
        rpe__isnull=False,
        einheit__datum__gte=letzte_30_tage
    )
    if rpe_saetze.exists():
        avg_rpe = round(rpe_saetze.aggregate(Avg('rpe'))['rpe__avg'], 1)
        rpe_verteilung = {
            'leicht': rpe_saetze.filter(rpe__lte=6).count(),
            'mittel': rpe_saetze.filter(rpe__gt=6, rpe__lte=8).count(),
            'schwer': rpe_saetze.filter(rpe__gt=8).count()
        }
    else:
        avg_rpe = 0
        rpe_verteilung = {'leicht': 0, 'mittel': 0, 'schwer': 0}
    
    # Volumen-Progression über letzte 12 Wochen
    volumen_wochen = []
    for woche in range(12, 0, -1):
        start = heute - timedelta(weeks=woche)
        ende = heute - timedelta(weeks=woche-1)
        woche_saetze = alle_saetze.filter(
            einheit__datum__gte=start,
            einheit__datum__lt=ende
        )
        woche_volumen = sum(
            float(s.gewicht) * s.wiederholungen
            for s in woche_saetze
            if s.gewicht and s.wiederholungen
        )
        if woche_volumen > 0:
            volumen_wochen.append({
                'woche': f"KW{start.isocalendar()[1]}",
                'volumen': round(woche_volumen, 0)
            })
    
    # Körperwerte mit Trend
    koerperwerte_qs = KoerperWerte.objects.filter(
        user=request.user
    ).order_by('-datum')
    
    koerperwerte = list(koerperwerte_qs[:5])  # Letzte 5 Messungen als Liste
    
    letzter_koerperwert = koerperwerte[0] if koerperwerte else None
    
    # Gewichts-Trend berechnen
    gewichts_trend = None
    if len(koerperwerte) >= 2:
        neueste = koerperwerte[0]
        aelteste = koerperwerte[-1]
        gewichts_diff = neueste.gewicht - aelteste.gewicht
        gewichts_trend = {
            'diff': round(gewichts_diff, 1),
            'richtung': 'zugenommen' if gewichts_diff > 0 else 'abgenommen'
        }
    
    # Push/Pull Balance-Daten für Template
    push_saetze = push_pull_balance.get('push_saetze', 0)
    pull_saetze = push_pull_balance.get('pull_saetze', 0)
    push_pull_ratio = push_pull_balance.get('ratio', 0)
    push_pull_bewertung = push_pull_balance.get('bewertung', '')
    push_pull_empfehlung = push_pull_balance.get('empfehlung', '')
    
    # Stärken identifizieren (optimale Muskelgruppen)
    staerken = [mg for mg in muskelgruppen_stats if mg['status'] == 'optimal']
    
    # Charts generieren (matplotlib)
    try:
        muscle_heatmap = generate_muscle_heatmap(muskelgruppen_stats)
        volume_chart = generate_volume_chart(volumen_wochen[-8:])
        push_pull_chart = generate_push_pull_pie(push_saetze, pull_saetze)
        logger.info('Charts successfully generated')
    except Exception as e:
        logger.warning(f'Chart generation failed: {str(e)}')
        muscle_heatmap = None
        volume_chart = None
        push_pull_chart = None
    
    context = {
        'user': request.user,
        'datum': heute,
        'current_date': heute,
        'start_datum': letzte_30_tage,
        'end_datum': heute,
        'trainings': trainings,
        'gesamt_trainings': gesamt_trainings,
        'gesamt_saetze': gesamt_saetze,
        'gesamt_volumen': round(gesamt_volumen, 0),
        'trainings_30_tage': trainings_30_tage,
        'saetze_30_tage': saetze_30_tage,
        'volumen_30_tage': round(volumen_30_tage, 0),
        'trainings_pro_woche': trainings_pro_woche,
        'top_uebungen': top_uebungen,
        'kraft_progression': kraft_progression,
        'kraftentwicklung': kraft_progression,  # Alias für Template
        'muskelgruppen_stats': muskelgruppen_stats,
        'push_pull_balance': push_pull_balance,
        'push_saetze': push_saetze,
        'pull_saetze': pull_saetze,
        'push_pull_ratio': push_pull_ratio,
        'push_pull_bewertung': push_pull_bewertung,
        'push_pull_empfehlung': push_pull_empfehlung,
        'schwachstellen': schwachstellen,
        'staerken': staerken,
        'total_einheiten': gesamt_trainings,
        'total_saetze': gesamt_saetze,
        'total_volumen': round(gesamt_volumen, 0),
        'avg_rpe': avg_rpe,
        'rpe_verteilung': rpe_verteilung,
        'volumen_wochen': volumen_wochen[-8:],  # Letzte 8 Wochen für Übersichtlichkeit
        # Charts
        'muscle_heatmap': muscle_heatmap,
        'volume_chart': volume_chart,
        'push_pull_chart': push_pull_chart,
        'koerperwerte': koerperwerte,
        'letzter_koerperwert': letzter_koerperwert,
        'gewichts_trend': gewichts_trend,
    }
    
    # HTML rendern (vereinfachtes Template für xhtml2pdf-Kompatibilität)
    try:
        html_string = render_to_string('core/training_pdf_simple.html', context)
    except Exception as e:
        logger.error(f'Template rendering failed: {str(e)}', exc_info=True)
        messages.error(request, f'Template-Fehler: {str(e)}')
        return redirect('training_stats')
    
    # PDF generieren mit xhtml2pdf
    try:
        result = BytesIO()
        pdf = pisa.pisaDocument(BytesIO(html_string.encode("UTF-8")), result)
        
        if pdf.err:
            logger.error(f'PDF generation failed with {pdf.err} errors')
            messages.error(request, 'Fehler beim PDF-Export (pisaDocument failed)')
            return redirect('training_stats')
        
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="homegym_report_{heute.strftime("%Y%m%d")}.pdf"'
        return response
        
    except Exception as e:
        logger.error(f'PDF export failed: {str(e)}', exc_info=True)
        messages.error(request, f'PDF-Generierung fehlgeschlagen: {str(e)}')
        return redirect('training_stats')


@login_required
def workout_recommendations(request):
    """Intelligente Trainingsempfehlungen basierend auf Datenanalyse."""
    heute = timezone.now()
    letzte_30_tage = heute - timedelta(days=30)
    letzte_60_tage = heute - timedelta(days=60)
    
    # Alle Trainings des Users
    alle_saetze = Satz.objects.filter(
        einheit__user=request.user,
        ist_aufwaermsatz=False
    )
    
    letzte_30_tage_saetze = alle_saetze.filter(
        einheit__datum__gte=letzte_30_tage
    )
    
    letzte_60_tage_saetze = alle_saetze.filter(
        einheit__datum__gte=letzte_60_tage
    )
    
    empfehlungen = []
    
    # === 1. MUSKELGRUPPEN-BALANCE ANALYSE (RPE-gewichtet) ===
    muskelgruppen_stats = {}
    for gruppe_key, gruppe_name in MUSKELGRUPPEN:
        # Berechne effektive Wiederholungen: Sätze × Wiederholungen × (RPE/10)
        effektive_wdh = sum(
            s.wiederholungen * (float(s.rpe) / 10.0)
            for s in letzte_30_tage_saetze.filter(uebung__muskelgruppe=gruppe_key)
            if s.wiederholungen and s.rpe
        )
        
        saetze_anzahl = letzte_30_tage_saetze.filter(uebung__muskelgruppe=gruppe_key).count()
        
        if effektive_wdh > 0:
            muskelgruppen_stats[gruppe_key] = {
                'name': gruppe_name,
                'effektive_wdh': effektive_wdh,
                'saetze': saetze_anzahl
            }
    
    if muskelgruppen_stats:
        # Finde untertrainierte Muskelgruppen (basierend auf effektiven Wiederholungen)
        avg_effektive_wdh = sum(m['effektive_wdh'] for m in muskelgruppen_stats.values()) / len(muskelgruppen_stats)
        
        for gruppe_key, data in muskelgruppen_stats.items():
            if data['effektive_wdh'] < avg_effektive_wdh * 0.5:  # Weniger als 50% des Durchschnitts
                # Finde passende Übungen
                passende_uebungen = Uebung.objects.filter(muskelgruppe=gruppe_key)[:3]
                
                empfehlungen.append({
                    'typ': 'muskelgruppe',
                    'prioritaet': 'hoch',
                    'titel': f'{data["name"]} untertrainiert',
                    'beschreibung': f'Diese Muskelgruppe wurde in den letzten 30 Tagen unterdurchschnittlich trainiert (nur {int(data["effektive_wdh"])} effektive Wiederholungen vs. {int(avg_effektive_wdh)} Durchschnitt).',
                    'empfehlung': f'Füge mehr Übungen für {data["name"]} hinzu',
                    'uebungen': [{'id': u.id, 'name': u.bezeichnung} for u in passende_uebungen]
                })
    
    # === 2. PUSH/PULL BALANCE (RPE-gewichtet) ===
    push_gruppen = ['BRUST', 'SCHULTER_VORN', 'SCHULTER_SEIT', 'TRIZEPS']
    pull_gruppen = ['RUECKEN_LAT', 'RUECKEN_TRAPEZ', 'BIZEPS']
    
    push_effektiv = sum(
        s.wiederholungen * (float(s.rpe) / 10.0)
        for s in letzte_30_tage_saetze.filter(uebung__muskelgruppe__in=push_gruppen)
        if s.wiederholungen and s.rpe
    )
    
    pull_effektiv = sum(
        s.wiederholungen * (float(s.rpe) / 10.0)
        for s in letzte_30_tage_saetze.filter(uebung__muskelgruppe__in=pull_gruppen)
        if s.wiederholungen and s.rpe
    )
    
    if push_effektiv > 0 and pull_effektiv > 0:
        ratio = push_effektiv / pull_effektiv if pull_effektiv > 0 else 999
        
        if ratio > 1.5:  # Zu viel Push
            empfehlungen.append({
                'typ': 'balance',
                'prioritaet': 'mittel',
                'titel': 'Push/Pull Unbalance',
                'beschreibung': f'Dein Push-Training ({int(push_effektiv)} eff. Wdh) ist {ratio:.1f}x intensiver als dein Pull-Training ({int(pull_effektiv)} eff. Wdh). Dies kann zu Haltungsschäden führen.',
                'empfehlung': 'Mehr Zugübungen (Rücken, Bizeps) trainieren',
                'uebungen': [{'id': u.id, 'name': u.bezeichnung} for u in Uebung.objects.filter(muskelgruppe__in=pull_gruppen)[:3]]
            })
        elif ratio < 0.67:  # Zu viel Pull
            empfehlungen.append({
                'typ': 'balance',
                'prioritaet': 'mittel',
                'titel': 'Push/Pull Unbalance',
                'beschreibung': f'Dein Pull-Training ({int(pull_effektiv)} eff. Wdh) ist intensiver als dein Push-Training ({int(push_effektiv)} eff. Wdh).',
                'empfehlung': 'Mehr Druckübungen (Brust, Schultern, Trizeps) einbauen',
                'uebungen': [{'id': u.id, 'name': u.bezeichnung} for u in Uebung.objects.filter(muskelgruppe__in=push_gruppen)[:3]]
            })
    
    # === 3. STAGNIERENDE ÜBUNGEN ===
    haeufige_uebungen = letzte_60_tage_saetze.values('uebung').annotate(
        anzahl=Count('id')
    ).filter(anzahl__gte=5).values_list('uebung', flat=True)
    
    for uebung_id in haeufige_uebungen:
        uebung = Uebung.objects.get(id=uebung_id)
        
        # Letzte 5 Trainings mit dieser Übung
        letzte_saetze = alle_saetze.filter(uebung=uebung).order_by('-einheit__datum')[:10]
        
        if len(letzte_saetze) >= 5:
            gewichte = [float(s.gewicht) for s in letzte_saetze[:5] if s.gewicht]
            
            if gewichte and max(gewichte) == min(gewichte):  # Kein Fortschritt
                empfehlungen.append({
                    'typ': 'stagnation',
                    'prioritaet': 'niedrig',
                    'titel': f'{uebung.bezeichnung}: Stagnation',
                    'beschreibung': f'Bei dieser Übung gab es in den letzten 5 Trainings keinen Fortschritt (konstant {gewichte[0]} kg).',
                    'empfehlung': 'Versuche: (1) Deload-Woche, (2) Wiederholungsbereich ändern, (3) Tempo variieren',
                    'uebungen': []
                })
    
    # === 4. TRAININGSFREQUENZ ===
    trainings_letzte_woche = Trainingseinheit.objects.filter(
        user=request.user,
        datum__gte=heute - timedelta(days=7)
    ).count()
    
    trainings_vorige_woche = Trainingseinheit.objects.filter(
        user=request.user,
        datum__gte=heute - timedelta(days=14),
        datum__lt=heute - timedelta(days=7)
    ).count()
    
    if trainings_letzte_woche == 0:
        empfehlungen.append({
            'typ': 'frequenz',
            'prioritaet': 'hoch',
            'titel': 'Keine Trainings diese Woche',
            'beschreibung': 'Du hast diese Woche noch nicht trainiert!',
            'empfehlung': 'Starte heute ein Training - Konsistenz ist der Schlüssel zum Erfolg!',
            'uebungen': []
        })
    elif trainings_letzte_woche < trainings_vorige_woche - 1:
        empfehlungen.append({
            'typ': 'frequenz',
            'prioritaet': 'mittel',
            'titel': 'Trainingsfrequenz gesunken',
            'beschreibung': f'Diese Woche: {trainings_letzte_woche} Trainings, letzte Woche: {trainings_vorige_woche} Trainings.',
            'empfehlung': 'Versuche deine Konsistenz beizubehalten!',
            'uebungen': []
        })
    
    # === 5. RPE-BASIERTE EMPFEHLUNGEN ===
    avg_rpe = letzte_30_tage_saetze.filter(rpe__isnull=False).aggregate(Avg('rpe'))['rpe__avg']
    
    if avg_rpe:
        if avg_rpe < 6:
            empfehlungen.append({
                'typ': 'intensitaet',
                'prioritaet': 'mittel',
                'titel': 'Zu niedrige Trainingsintensität',
                'beschreibung': f'Dein durchschnittlicher RPE liegt bei {avg_rpe:.1f}. Das Training könnte intensiver sein.',
                'empfehlung': 'Steigere das Gewicht, bis du bei RPE 7-9 trainierst für optimalen Muskelaufbau',
                'uebungen': []
            })
        elif avg_rpe > 9:
            empfehlungen.append({
                'typ': 'intensitaet',
                'prioritaet': 'hoch',
                'titel': 'Zu hohe Trainingsintensität',
                'beschreibung': f'Dein durchschnittlicher RPE liegt bei {avg_rpe:.1f}. Du trainierst möglicherweise zu nah am Muskelversagen.',
                'empfehlung': 'Reduziere das Gewicht leicht - Deload-Woche empfohlen!',
                'uebungen': []
            })
    
    # Keine Empfehlungen? Lob!
    if not empfehlungen:
        empfehlungen.append({
            'typ': 'erfolg',
            'prioritaet': 'info',
            'titel': '✌️ Perfekt ausgewogenes Training!',
            'beschreibung': 'Dein Training ist optimal ausbalanciert. Alle Muskelgruppen werden gleichmäßig trainiert!',
            'empfehlung': 'Weiter so! Bleib konsistent und die Erfolge kommen.',
            'uebungen': []
        })
    
    # Sortiere nach Priorität
    prioritaet_order = {'hoch': 0, 'mittel': 1, 'niedrig': 2, 'info': 3}
    empfehlungen.sort(key=lambda x: prioritaet_order.get(x['prioritaet'], 99))
    
    context = {
        'empfehlungen': empfehlungen,
        'analysiert_tage': 30,
    }
    
    return render(request, 'core/workout_recommendations.html', context)


@login_required
def equipment_management(request):
    """
    Equipment/Ausrüstungs-Verwaltung
    User kann seine verfügbare Ausrüstung auswählen
    """
    # Alle verfügbaren Equipment-Typen laden (oder erstellen falls leer)
    from .models import EQUIPMENT_CHOICES
    
    # Equipment initial erstellen falls nicht vorhanden
    for eq_code, eq_name in EQUIPMENT_CHOICES:
        Equipment.objects.get_or_create(name=eq_code)
    
    all_equipment = Equipment.objects.all().order_by('name')
    user_equipment_ids = request.user.verfuegbares_equipment.values_list('id', flat=True)
    
    # Kategorien für bessere Darstellung
    equipment_categories = {
        'Freie Gewichte': ['LANGHANTEL', 'KURZHANTEL', 'KETTLEBELL'],
        'Racks & Stangen': ['KLIMMZUG', 'DIP', 'SMITHMASCHINE'],
        'Bänke': ['BANK', 'SCHRAEGBANK'],
        'Maschinen': ['KABELZUG', 'BEINPRESSE', 'LEG_CURL', 'LEG_EXT', 'HACKENSCHMIDT', 'RUDERMASCHINE'],
        'Sonstiges': ['WIDERSTANDSBAND', 'SUSPENSION', 'MEDIZINBALL', 'BOXEN', 'MATTE', 'KOERPER'],
    }
    
    categorized_equipment = {}
    for category, eq_codes in equipment_categories.items():
        categorized_equipment[category] = all_equipment.filter(name__in=eq_codes)
    
    # Statistik: Übungen mit verfügbarem Equipment
    total_uebungen = Uebung.objects.count()
    if user_equipment_ids:
        # Übungen die ALLE ihre benötigten Equipment-Teile beim User verfügbar haben
        available_uebungen = 0
        for uebung in Uebung.objects.prefetch_related('equipment'):
            required_eq = set(uebung.equipment.values_list('id', flat=True))
            if not required_eq or required_eq.issubset(set(user_equipment_ids)):
                available_uebungen += 1
    else:
        # Nur Übungen ohne Equipment-Anforderung
        available_uebungen = Uebung.objects.filter(equipment__isnull=True).count()
    
    context = {
        'categorized_equipment': categorized_equipment,
        'user_equipment_ids': list(user_equipment_ids),
        'total_uebungen': total_uebungen,
        'available_uebungen': available_uebungen,
        'unavailable_uebungen': total_uebungen - available_uebungen,
    }
    
    return render(request, 'core/equipment_management.html', context)


@login_required
def toggle_equipment(request, equipment_id):
    """
    Toggle Equipment für User (An/Aus)
    """
    equipment = get_object_or_404(Equipment, id=equipment_id)
    
    if request.user in equipment.users.all():
        equipment.users.remove(request.user)
        status = 'removed'
    else:
        equipment.users.add(request.user)
        status = 'added'
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': status, 'equipment_name': str(equipment)})
    
    return redirect('equipment_management')


@login_required
def exercise_api_detail(request, exercise_id):
    """
    API Endpoint für Übungsdetails (für Modal)
    Gibt JSON mit allen Übungsinformationen zurück
    """
    try:
        uebung = get_object_or_404(Uebung, id=exercise_id)
        
        # Muskelgruppen Dict für Display-Namen
        muskelgruppen_dict = dict(MUSKELGRUPPEN)
        
        # Bewegungstyp Display Namen (aus models.py)
        bewegungstyp_dict = dict(BEWEGUNGS_TYP)
        
        # Gewichtstyp Display Namen (aus models.py)
        gewichts_typ_dict = dict(GEWICHTS_TYP)
        
        # Hilfsmuskeln Display Namen
        hilfsmuskeln_display = []
        if uebung.hilfsmuskeln:
            hilfsmuskeln_display = [muskelgruppen_dict.get(m, m) for m in uebung.hilfsmuskeln]
        
        # Equipment Liste
        equipment_list = [eq.get_name_display() for eq in uebung.equipment.all()]
        
        data = {
            'id': uebung.id,
            'bezeichnung': uebung.bezeichnung,
            'beschreibung': uebung.beschreibung or 'Keine Beschreibung verfügbar',
            'bild': uebung.bild.url if uebung.bild else None,
            'muskelgruppe': uebung.muskelgruppe or '',
            'muskelgruppe_display': muskelgruppen_dict.get(uebung.muskelgruppe, uebung.muskelgruppe) if uebung.muskelgruppe else '-',
            'bewegungstyp': uebung.bewegungstyp or '',
            'bewegungstyp_display': bewegungstyp_dict.get(uebung.bewegungstyp, '') if uebung.bewegungstyp else '',
            'gewichts_typ': uebung.gewichts_typ or '',
            'gewichts_typ_display': gewichts_typ_dict.get(uebung.gewichts_typ, '') if uebung.gewichts_typ else '-',
            'hilfsmuskeln': uebung.hilfsmuskeln or [],
            'hilfsmuskeln_display': hilfsmuskeln_display,
            'equipment': equipment_list,
        }
        
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def live_guidance_api(request):
    """
    API Endpoint für Live-Guidance während Training
    POST: { session_id, question, exercise_id?, set_number? }
    Returns: { answer, cost, model }
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        
        session_id = data.get('session_id')
        question = data.get('question', '').strip()
        exercise_id = data.get('exercise_id')
        set_number = data.get('set_number')
        
        if not session_id or not question:
            return JsonResponse({'error': 'session_id und question erforderlich'}, status=400)
        
        # Prüfe ob Session dem User gehört
        session = get_object_or_404(Trainingseinheit, id=session_id, user=request.user)
        
        # Live Guidance importieren (korrekter Package-Import)
        from ai_coach.live_guidance import LiveGuidance
        
        # Use OpenRouter auf Server, Ollama lokal
        use_openrouter = os.getenv('USE_OPENROUTER', 'False').lower() == 'true'
        
        guidance = LiveGuidance(use_openrouter=use_openrouter)
        result = guidance.get_guidance(
            trainingseinheit_id=session_id,
            user_question=question,
            current_uebung_id=exercise_id,
            current_satz_number=set_number
        )
        
        return JsonResponse({
            'answer': result['answer'],
            'cost': result['cost'],
            'model': result['model']
        })
    
    except Trainingseinheit.DoesNotExist:
        return JsonResponse({'error': 'Trainingseinheit nicht gefunden'}, status=404)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def generate_plan_api(request):
    """
    API Endpoint für KI-Plan-Generierung über Web-Interface
    POST: { plan_type, sets_per_session, analysis_days? }
    Returns: { success, plan_ids, cost, message }
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        
        plan_type = data.get('plan_type', '3er-split')
        sets_per_session = int(data.get('sets_per_session', 18))
        analysis_days = int(data.get('analysis_days', 30))
        
        # Validierung
        valid_plan_types = ['2er-split', '3er-split', '4er-split', 'ganzkörper', 'push-pull-legs']
        if plan_type not in valid_plan_types:
            return JsonResponse({'error': f'Ungültiger Plan-Typ. Erlaubt: {", ".join(valid_plan_types)}'}, status=400)
        
        if sets_per_session < 10 or sets_per_session > 30:
            return JsonResponse({'error': 'Sätze pro Session muss zwischen 10-30 liegen'}, status=400)
        
        # Plan Generator importieren (korrekter Package-Import)
        from ai_coach.plan_generator import PlanGenerator
        
        # Use OpenRouter auf Server, Ollama lokal
        use_openrouter = os.getenv('USE_OPENROUTER', 'False').lower() == 'true'
        
        generator = PlanGenerator(
            user_id=request.user.id,
            plan_type=plan_type,
            analysis_days=analysis_days,
            sets_per_session=sets_per_session,
            use_openrouter=use_openrouter,
            fallback_to_openrouter=True
        )
        
        # Generiere Plan
        result = generator.generate(save_to_db=True)
        
        return JsonResponse({
            'success': True,
            'plan_ids': result.get('plan_ids', []),
            'plan_name': result.get('plan_data', {}).get('plan_name', ''),
            'sessions': len(result.get('plan_data', {}).get('sessions', [])),
            'cost': 0.003 if use_openrouter else 0.0,  # Geschätzte Kosten
            'model': 'OpenRouter 70B' if use_openrouter else 'Ollama 8B',
            'message': f"Plan '{result.get('plan_data', {}).get('plan_name', '')}' erfolgreich erstellt!"
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'error': str(e),
            'success': False
        }, status=500)


@login_required
def analyze_plan_api(request):
    """
    Regelbasierte Plan-Analyse (kostenlos)
    GET /api/analyze-plan/<plan_id>/
    
    Returns:
        {
            'warnings': [...],
            'suggestions': [...],
            'metrics': {...}
        }
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'GET request required'}, status=405)
    
    try:
        from ai_coach.plan_adapter import PlanAdapter
        
        plan_id = request.GET.get('plan_id')
        days = int(request.GET.get('days', 30))
        
        if not plan_id:
            return JsonResponse({'error': 'plan_id required'}, status=400)
        
        # Validierung: User darf nur eigene Pläne analysieren
        plan = get_object_or_404(Plan, id=plan_id, user=request.user)
        
        adapter = PlanAdapter(plan_id=plan.id, user_id=request.user.id)
        result = adapter.analyze_plan_performance(days=days)
        
        return JsonResponse({
            'success': True,
            'plan_id': plan.id,
            'plan_name': plan.name,
            **result
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'error': str(e),
            'success': False
        }, status=500)


@login_required
def optimize_plan_api(request):
    """
    KI-gestützte Plan-Optimierung (~0.003€)
    POST /api/optimize-plan/
    
    Body:
        {
            'plan_id': 1,
            'days': 30
        }
    
    Returns:
        {
            'optimizations': [...],
            'cost': 0.003,
            'model': 'llama-3.1-70b'
        }
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST request required'}, status=405)
    
    try:
        from ai_coach.plan_adapter import PlanAdapter
        
        data = json.loads(request.body)
        plan_id = data.get('plan_id')
        days = int(data.get('days', 30))
        
        if not plan_id:
            return JsonResponse({'error': 'plan_id required'}, status=400)
        
        # Validierung: User darf nur eigene Pläne optimieren
        plan = get_object_or_404(Plan, id=plan_id, user=request.user)
        
        adapter = PlanAdapter(plan_id=plan.id, user_id=request.user.id)
        result = adapter.suggest_optimizations(days=days)
        
        return JsonResponse({
            'success': True,
            'plan_id': plan.id,
            'plan_name': plan.name,
            **result
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'error': str(e),
            'success': False
        }, status=500)


@login_required
def apply_optimizations_api(request):
    """
    Wendet ausgewählte Optimierungen auf den Plan an
    POST /api/apply-optimizations/
    
    Body:
        {
            'plan_id': 1,
            'optimizations': [
                {
                    'type': 'replace_exercise',
                    'exercise_id': 15,
                    'old_exercise': 'Bankdrücken',
                    'new_exercise': 'Schrägbankdrücken'
                },
                ...
            ]
        }
    
    Returns:
        {
            'success': True,
            'applied_count': 3,
            'message': '3 Optimierungen erfolgreich angewendet'
        }
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST request required'}, status=405)
    
    try:
        data = json.loads(request.body)
        plan_id = data.get('plan_id')
        optimizations = data.get('optimizations', [])
        
        if not plan_id:
            return JsonResponse({'error': 'plan_id required'}, status=400)
        
        # Validierung: User darf nur eigene Pläne bearbeiten
        plan = get_object_or_404(Plan, id=plan_id, user=request.user)
        
        applied_count = 0
        errors = []
        
        for opt in optimizations:
            try:
                opt_type = opt.get('type')
                
                if opt_type == 'replace_exercise':
                    # Finde die zu ersetzende Übung
                    old_exercise_name = opt.get('old_exercise')
                    new_exercise_name = opt.get('new_exercise')
                    
                    # Hole alte PlanUebung
                    old_plan_uebung = PlanUebung.objects.filter(
                        plan=plan,
                        uebung__bezeichnung__icontains=old_exercise_name.split('(')[0].strip()
                    ).first()
                    
                    if not old_plan_uebung:
                        errors.append(f"Übung '{old_exercise_name}' nicht im Plan gefunden")
                        continue
                    
                    # Finde neue Übung
                    new_uebung = Uebung.objects.filter(
                        bezeichnung__icontains=new_exercise_name.split('(')[0].strip()
                    ).first()
                    
                    if not new_uebung:
                        errors.append(f"Übung '{new_exercise_name}' nicht gefunden")
                        continue
                    
                    # Ersetze Übung (behalte Sets/Reps/Reihenfolge)
                    old_plan_uebung.uebung = new_uebung
                    old_plan_uebung.save()
                    applied_count += 1
                
                elif opt_type == 'adjust_volume':
                    # Finde Übung und ändere Sets/Reps
                    exercise_name = opt.get('exercise')
                    new_sets = opt.get('new_sets')
                    new_reps = opt.get('new_reps')
                    
                    plan_uebung = PlanUebung.objects.filter(
                        plan=plan,
                        uebung__bezeichnung__icontains=exercise_name.split('(')[0].strip()
                    ).first()
                    
                    if not plan_uebung:
                        errors.append(f"Übung '{exercise_name}' nicht im Plan gefunden")
                        continue
                    
                    if new_sets:
                        plan_uebung.saetze_ziel = new_sets
                    if new_reps:
                        plan_uebung.wiederholungen_ziel = new_reps
                    plan_uebung.save()
                    applied_count += 1
                
                elif opt_type == 'add_exercise':
                    # Füge neue Übung hinzu
                    exercise_name = opt.get('exercise')
                    sets = opt.get('sets', 3)
                    reps = opt.get('reps', '8-12')
                    
                    # Finde Übung
                    uebung = Uebung.objects.filter(
                        bezeichnung__icontains=exercise_name.split('(')[0].strip()
                    ).first()
                    
                    if not uebung:
                        errors.append(f"Übung '{exercise_name}' nicht gefunden")
                        continue
                    
                    # Füge am Ende des Plans hinzu
                    max_reihenfolge = PlanUebung.objects.filter(plan=plan).aggregate(
                        Max('reihenfolge')
                    )['reihenfolge__max'] or 0
                    
                    PlanUebung.objects.create(
                        plan=plan,
                        uebung=uebung,
                        reihenfolge=max_reihenfolge + 1,
                        saetze_ziel=sets,
                        wiederholungen_ziel=reps
                    )
                    applied_count += 1
                
                elif opt_type == 'deload_recommended':
                    # Keine direkte Aktion - nur Info
                    pass
                
            except Exception as e:
                errors.append(f"{opt_type}: {str(e)}")
        
        return JsonResponse({
            'success': True,
            'applied_count': applied_count,
            'errors': errors,
            'message': f"{applied_count} Optimierung(en) erfolgreich angewendet"
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'error': str(e),
            'success': False
        }, status=500)


from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from datetime import datetime
import csv


@staff_member_required
def export_uebungen(request):
    """
    Exportiert alle Übungen als JSON-Datei
    Nur für Admin-User (staff_member_required)
    """
    from django.core.serializers import serialize
    
    # Format-Parameter (json oder csv)
    export_format = request.GET.get('format', 'json')
    
    if export_format == 'json':
        # JSON Export mit allen Feldern
        uebungen = Uebung.objects.all().prefetch_related('equipment')
        
        exercises_data = []
        for uebung in uebungen:
            exercises_data.append({
                'id': uebung.id,
                'bezeichnung': uebung.bezeichnung,
                'muskelgruppe': uebung.muskelgruppe,
                'hilfsmuskeln': uebung.hilfsmuskeln if uebung.hilfsmuskeln else [],
                'bewegungstyp': uebung.bewegungstyp,
                'gewichts_typ': uebung.gewichts_typ,
                'equipment': [eq.get_name_display() for eq in uebung.equipment.all()],
                'beschreibung': uebung.beschreibung if hasattr(uebung, 'beschreibung') else '',
            })
        
        # Response als downloadbare JSON-Datei
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        response = HttpResponse(
            json.dumps({'exercises': exercises_data}, indent=2, ensure_ascii=False),
            content_type='application/json'
        )
        response['Content-Disposition'] = f'attachment; filename="uebungen_export_{timestamp}.json"'
        return response
    
    elif export_format == 'csv':
        # CSV Export
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="uebungen_export_{timestamp}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['ID', 'Bezeichnung', 'Muskelgruppe', 'Hilfsmuskeln', 'Bewegungstyp', 'Gewichtstyp', 'Equipment'])
        
        uebungen = Uebung.objects.all().prefetch_related('equipment')
        for uebung in uebungen:
            writer.writerow([
                uebung.id,
                uebung.bezeichnung,
                uebung.muskelgruppe,
                ', '.join(uebung.hilfsmuskeln) if uebung.hilfsmuskeln else '',
                uebung.bewegungstyp,
                uebung.gewichts_typ,
                ', '.join([eq.get_name_display() for eq in uebung.equipment.all()]),
            ])
        
        return response
    
    return JsonResponse({'error': 'Invalid format'}, status=400)


@staff_member_required
def import_uebungen(request):
    """
    Importiert Übungen aus JSON-Datei
    Nur für Admin-User (staff_member_required)
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        import_file = request.FILES.get('import_file')
        if not import_file:
            messages.error(request, 'Keine Datei ausgewählt')
            return redirect('uebungen_auswahl')
        
        # Parse JSON
        try:
            data = json.load(import_file)
        except json.JSONDecodeError as e:
            messages.error(request, f'Ungültiges JSON-Format: {e}')
            return redirect('uebungen_auswahl')
        
        # Extract exercises array
        if isinstance(data, list):
            exercises = data
        elif isinstance(data, dict) and 'exercises' in data:
            exercises = data['exercises']
        else:
            messages.error(request, 'JSON muss Array oder Object mit "exercises" Key sein')
            return redirect('uebungen_auswahl')
        
        # Options
        update_existing = request.POST.get('update_existing') == 'on'
        dry_run = request.POST.get('dry_run') == 'on'
        
        # Import-Statistiken
        created_count = 0
        updated_count = 0
        skipped_count = 0
        errors = []
        
        for ex_data in exercises:
            try:
                bezeichnung = ex_data.get('bezeichnung')
                if not bezeichnung:
                    skipped_count += 1
                    continue
                
                # Equipment-Objekte finden
                equipment_names = ex_data.get('equipment', [])
                equipment_objs = []
                for eq_name in equipment_names:
                    try:
                        # Suche nach name (Display-Name aus Choices)
                        eq = Equipment.objects.get(name=eq_name)
                        equipment_objs.append(eq)
                    except Equipment.DoesNotExist:
                        # Fallback: Suche in EQUIPMENT_CHOICES by display name
                        found = False
                        from core.models import EQUIPMENT_CHOICES
                        for choice_value, choice_display in EQUIPMENT_CHOICES:
                            if choice_display == eq_name:
                                try:
                                    eq = Equipment.objects.get(name=choice_value)
                                    equipment_objs.append(eq)
                                    found = True
                                    break
                                except Equipment.DoesNotExist:
                                    pass
                        if not found:
                            errors.append(f'Equipment "{eq_name}" nicht gefunden für Übung "{bezeichnung}"')
                
                # Übung erstellen oder aktualisieren
                ex_id = ex_data.get('id')
                
                if not dry_run:
                    if ex_id and update_existing:
                        # Update existing
                        uebung, created = Uebung.objects.update_or_create(
                            id=ex_id,
                            defaults={
                                'bezeichnung': bezeichnung,
                                'muskelgruppe': ex_data.get('muskelgruppe', 'SONSTIGES'),
                                'hilfsmuskeln': ex_data.get('hilfsmuskeln', []),
                                'bewegungstyp': ex_data.get('bewegungstyp', 'COMPOUND'),
                                'gewichts_typ': ex_data.get('gewichts_typ', 'FREI'),
                            }
                        )
                        
                        # Equipment zuweisen
                        uebung.equipment.set(equipment_objs)
                        
                        if created:
                            created_count += 1
                        else:
                            updated_count += 1
                    else:
                        # Create new (ohne ID-Angabe)
                        uebung = Uebung.objects.create(
                            bezeichnung=bezeichnung,
                            muskelgruppe=ex_data.get('muskelgruppe', 'SONSTIGES'),
                            hilfsmuskeln=ex_data.get('hilfsmuskeln', []),
                            bewegungstyp=ex_data.get('bewegungstyp', 'COMPOUND'),
                            gewichts_typ=ex_data.get('gewichts_typ', 'FREI'),
                        )
                        uebung.equipment.set(equipment_objs)
                        created_count += 1
                else:
                    # Dry-Run: nur zählen
                    if ex_id and Uebung.objects.filter(id=ex_id).exists():
                        updated_count += 1
                    else:
                        created_count += 1
                
            except Exception as e:
                errors.append(f'Fehler bei "{ex_data.get("bezeichnung", "?")}": {str(e)}')
        
        # Feedback
        if dry_run:
            messages.info(
                request,
                f'Dry-Run abgeschlossen: {created_count} würden erstellt, {updated_count} würden aktualisiert, {skipped_count} übersprungen'
            )
        else:
            messages.success(
                request,
                f'Import erfolgreich: {created_count} erstellt, {updated_count} aktualisiert, {skipped_count} übersprungen'
            )
        
        if errors:
            messages.warning(request, f'{len(errors)} Fehler: ' + '; '.join(errors[:5]))
        
    except Exception as e:
        messages.error(request, f'Import fehlgeschlagen: {str(e)}')
    
    return redirect('uebungen_auswahl')