from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Count, Max, Sum, Avg
from django.http import JsonResponse
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from .models import Trainingseinheit, KoerperWerte, Uebung, Satz, Plan, PlanUebung, MUSKELGRUPPEN
import re
import json
import random


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
    
    # Trainingsfrequenz diese Woche
    heute = timezone.now()
    start_woche = heute - timedelta(days=heute.weekday())  # Montag dieser Woche
    trainings_diese_woche = Trainingseinheit.objects.filter(user=request.user, datum__gte=start_woche).count()
    
    # Streak berechnen (aufeinanderfolgende Wochen mit mindestens 1 Training)
    streak = 0
    check_date = heute
    while True:
        week_start = check_date - timedelta(days=check_date.weekday())
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
        week_start = heute - timedelta(days=heute.weekday() + (i * 7))
        week_end = week_start + timedelta(days=7)
        
        week_saetze = Satz.objects.filter(
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
            
            # Wir erstellen so viele Platzhalter-Sätze, wie im Plan stehen
            for i in range(1, anzahl_saetze + 1):
                Satz.objects.create(
                    einheit=training,
                    uebung=uebung,
                    satz_nr=i,
                    gewicht=start_gewicht,
                    wiederholungen=start_wdh,
                    ist_aufwaermsatz=False
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
            rpe=rpe if rpe else None
        )
        
        # PR-Check (nur für Arbeitssätze)
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
                    messages.success(
                        request, 
                        f'🎉 NEUER REKORD! {uebung.bezeichnung}: {round(current_1rm, 1)} kg (1RM) - +{verbesserung} kg!'
                    )
            else:
                # Erster Satz für diese Übung = automatisch PR
                messages.success(
                    request,
                    f'🏆 Erster Rekord gesetzt! {uebung.bezeichnung}: {round(current_1rm, 1)} kg (1RM)'
                )
        
        # AJAX Request? Sende JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'satz_id': neuer_satz.id})
        
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
        volumen = sum(float(s.gewicht) * s.wiederholungen for s in arbeitssaetze)
        volumen_labels.append(training.datum.strftime('%d.%m'))
        volumen_data.append(round(volumen, 1))
    
    # Wöchentliches Volumen (letzte 12 Wochen)
    from collections import defaultdict
    weekly_volume = defaultdict(float)
    
    for training in trainings:
        week_key = training.datum.strftime('%Y-W%W')
        arbeitssaetze = training.saetze.filter(ist_aufwaermsatz=False)
        volumen = sum(float(s.gewicht) * s.wiederholungen for s in arbeitssaetze)
        weekly_volume[week_key] += volumen
    
    # Letzte 12 Wochen
    weekly_labels = sorted(weekly_volume.keys())[-12:]
    weekly_data = [round(weekly_volume[k], 1) for k in weekly_labels]
    
    # Muskelgruppen-Balance
    muskelgruppen_stats = {}
    muskelgruppen_stats_code = {}  # Für SVG-Mapping
    for training in trainings:
        for satz in training.saetze.filter(ist_aufwaermsatz=False):
            mg_display = satz.uebung.get_muskelgruppe_display()
            mg_code = satz.uebung.muskelgruppe
            volumen = float(satz.gewicht) * satz.wiederholungen
            
            if mg_display not in muskelgruppen_stats:
                muskelgruppen_stats[mg_display] = {'saetze': 0, 'volumen': 0}
            muskelgruppen_stats[mg_display]['saetze'] += 1
            muskelgruppen_stats[mg_display]['volumen'] += volumen
            
            # Für SVG-Mapping
            if mg_code not in muskelgruppen_stats_code:
                muskelgruppen_stats_code[mg_code] = 0
            muskelgruppen_stats_code[mg_code] += volumen
    
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
            for hm in uebung.hilfsmuskeln:
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
            
            PlanUebung.objects.create(
                plan=plan,
                uebung=uebung,
                reihenfolge=idx,
                saetze_ziel=saetze,
                wiederholungen_ziel=wdh
            )
        
        messages.success(request, f'Trainingsplan "{plan.name}" erfolgreich aktualisiert!')
        return redirect('plan_details', plan_id=plan.id)
    
    uebungen = Uebung.objects.all().order_by('muskelgruppe', 'bezeichnung')
    plan_uebung_ids = list(plan.uebungen.values_list('uebung_id', flat=True))
    
    # Gruppiere Übungen nach Muskelgruppen
    uebungen_nach_gruppe = {}
    for uebung in uebungen:
        mg_label = dict(MUSKELGRUPPEN).get(uebung.muskelgruppe, uebung.muskelgruppe)
        if mg_label not in uebungen_nach_gruppe:
            uebungen_nach_gruppe[mg_label] = []
        
        # Hilfsmuskelgruppen-Labels abrufen
        hilfs_labels = []
        if uebung.hilfsmuskeln:
            for hm in uebung.hilfsmuskeln:
                hilfs_labels.append(dict(MUSKELGRUPPEN).get(hm, hm))
        
        uebungen_nach_gruppe[mg_label].append({
            'id': uebung.id,
            'bezeichnung': uebung.bezeichnung,
            'muskelgruppe': uebung.muskelgruppe,
            'muskelgruppe_label': mg_label,
            'hilfsmuskeln': hilfs_labels,
            'gewichts_typ': uebung.get_gewichts_typ_display(),
            'bewegungstyp': uebung.bewegungstyp,  # Für Empfehlungslogik
            'in_plan': uebung.id in plan_uebung_ids,
        })
    
    context = {
        'plan': plan,
        'uebungen_nach_gruppe': uebungen_nach_gruppe,
        'muskelgruppen': MUSKELGRUPPEN,
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
    uebungen = Uebung.objects.all().order_by('muskelgruppe', 'bezeichnung')
    
    # Gruppiere nach Muskelgruppen
    uebungen_nach_gruppe = {}
    for uebung in uebungen:
        mg_label = dict(MUSKELGRUPPEN).get(uebung.muskelgruppe, uebung.muskelgruppe)
        if mg_label not in uebungen_nach_gruppe:
            uebungen_nach_gruppe[mg_label] = []
        
        # Hilfsmuskelgruppen-Labels abrufen
        hilfs_labels = []
        if uebung.hilfsmuskeln:
            for hm in uebung.hilfsmuskeln:
                hilfs_labels.append(dict(MUSKELGRUPPEN).get(hm, hm))
        
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
        # Wenn hilfsmuskeln ein String ist, splitten wir ihn
        if isinstance(uebung.hilfsmuskeln, str):
            hilfs_texte = [h.strip() for h in uebung.hilfsmuskeln.split(',')]
        else:
            hilfs_texte = uebung.hilfsmuskeln
        
        for hilfs_text in hilfs_texte:
            # Text bereinigen (z.B. "(Stabilisierung)" entfernen)
            hilfs_text_clean = re.sub(r'\([^)]*\)', '', hilfs_text).strip()
            # Code nachschlagen
            code = text_to_code.get(hilfs_text_clean)
            if code:
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