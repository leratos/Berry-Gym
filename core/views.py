from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Count, Max, Sum, Avg, F, Q
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import cache_control
from django.conf import settings
from django.core.mail import send_mail
from decimal import Decimal
from .models import (
    Trainingseinheit, KoerperWerte, Uebung, Satz, Plan, PlanUebung, 
    ProgressPhoto, Equipment, MUSKELGRUPPEN, BEWEGUNGS_TYP, GEWICHTS_TYP,
    InviteCode, WaitlistEntry
)
from django.db import models
import re
import json
import random
import os
import logging

logger = logging.getLogger(__name__)


def send_welcome_email(user):
    """Sendet Willkommens-E-Mail nach erfolgreicher Registrierung"""
    subject = "🏋️ Willkommen bei HomeGym!"
    
    message = f"""Hallo {user.username}!

Herzlich willkommen bei HomeGym - deiner persönlichen Fitness-App! 🎉

Dein Account wurde erfolgreich erstellt und du kannst jetzt loslegen.

🚀 Erste Schritte:
1. Richte dein Equipment ein (welche Geräte hast du?)
2. Erstelle deinen ersten Trainingsplan mit KI-Unterstützung
3. Starte dein erstes Training und tracke deine Fortschritte

💡 Tipps für Einsteiger:
• Nutze den KI-Coach während des Trainings für Tipps
• Trage regelmäßig deine Körperwerte ein
• Mache Fortschrittsfotos für visuellen Vergleich

📱 PWA-Installation:
Du kannst HomeGym als App auf deinem Smartphone installieren!
Öffne {settings.SITE_URL} im Browser und wähle "Zum Startbildschirm hinzufügen".

Bei Fragen stehen wir dir gerne zur Verfügung.

Viel Erfolg beim Training! 💪

Dein HomeGym Team
{settings.SITE_URL}

---
Diese E-Mail wurde automatisch generiert.
Kontakt: marcus.kohtz@signz-vision.com
"""
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,  # Nicht blocken wenn E-Mail fehlschlägt
        )
        logger.info(f"Welcome email sent to {user.email}")
    except Exception as e:
        logger.error(f"Failed to send welcome email to {user.email}: {e}")


# === BETA-ZUGANG & REGISTRIERUNG ===

def apply_beta(request):
    """Bewerbungsseite für Beta-Zugang"""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        reason = request.POST.get('reason', '').strip()
        experience = request.POST.get('experience')
        interests = request.POST.getlist('interests')
        github_username = request.POST.get('github_username', '').strip()
        
        if not email or not reason or not experience:
            messages.error(request, 'Bitte fülle alle Pflichtfelder aus.')
            return render(request, 'registration/apply_beta.html')
        
        if WaitlistEntry.objects.filter(email=email).exists():
            messages.info(request, 'Diese E-Mail ist bereits auf der Warteliste.')
            return redirect('apply_beta')
        
        from django.contrib.auth.models import User
        if User.objects.filter(email=email).exists():
            messages.info(request, 'Mit dieser E-Mail existiert bereits ein Account.')
            return redirect('login')
        
        WaitlistEntry.objects.create(
            email=email, reason=reason, experience=experience,
            interests=interests, github_username=github_username or None
        )
        
        messages.success(request, '✅ Bewerbung eingereicht! Du erhältst in 48h eine E-Mail.')
        return redirect('login')
    
    return render(request, 'registration/apply_beta.html')


def register(request):
    """Registrierung mit Einladungscode"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        code_str = request.POST.get('invite_code', '').strip().upper()
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip().lower()
        pass1 = request.POST.get('password1')
        pass2 = request.POST.get('password2')
        
        errors = []
        if not code_str:
            errors.append('Einladungscode fehlt.')
        elif not InviteCode.objects.filter(code=code_str, used_count__lt=F('max_uses')).exists():
            errors.append('Ungültiger oder aufgebrauchter Code.')
        
        from django.contrib.auth.models import User
        if not username:
            errors.append('Benutzername fehlt.')
        elif User.objects.filter(username=username).exists():
            errors.append('Benutzername vergeben.')
        
        if not email:
            errors.append('E-Mail fehlt.')
        elif User.objects.filter(email=email).exists():
            errors.append('E-Mail bereits registriert.')
        
        if not pass1 or pass1 != pass2:
            errors.append('Passwörter ungültig oder nicht identisch.')
        elif len(pass1) < 8:
            errors.append('Passwort zu kurz (min. 8 Zeichen).')
        
        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'registration/register_new.html', {'invite_code': code_str})
        
        user = User.objects.create_user(username=username, email=email, password=pass1)
        invite = InviteCode.objects.get(code=code_str)
        invite.use()
        
        entry = WaitlistEntry.objects.filter(email=email, invite_code=invite).first()
        if entry:
            entry.status = 'registered'
            entry.save()
        
        # Willkommens-E-Mail senden
        send_welcome_email(user)
        
        user = authenticate(username=username, password=pass1)
        login(request, user)
        messages.success(request, f'🎉 Willkommen {username}!')
        return redirect('dashboard')
    
    code_param = request.GET.get('code', '').strip().upper()
    return render(request, 'registration/register_new.html', {'invite_code': code_param})


def impressum(request):
    """Impressum-Seite"""
    return render(request, 'core/impressum.html')


def datenschutz(request):
    """Datenschutzerklärung-Seite"""
    return render(request, 'core/datenschutz.html')


@login_required
def feedback_list(request):
    """Liste aller eigenen Feedbacks"""
    from .models import Feedback
    feedbacks = Feedback.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'core/feedback_list.html', {'feedbacks': feedbacks})


@login_required
def feedback_create(request):
    """Neues Feedback (Bug/Feature) erstellen"""
    from .models import Feedback
    
    if request.method == 'POST':
        feedback_type = request.POST.get('feedback_type', 'FEATURE')
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        
        if not title or not description:
            return render(request, 'core/feedback_create.html', {
                'error': 'Bitte fülle alle Felder aus.',
                'feedback_type': feedback_type,
                'title': title,
                'description': description,
            })
        
        Feedback.objects.create(
            user=request.user,
            feedback_type=feedback_type,
            title=title,
            description=description,
        )
        
        from django.contrib import messages
        messages.success(request, '✅ Danke für dein Feedback! Wir werden es prüfen.')
        return redirect('feedback_list')
    
    # GET - Formular anzeigen
    feedback_type = request.GET.get('type', 'FEATURE')
    return render(request, 'core/feedback_create.html', {'feedback_type': feedback_type})


@login_required
def feedback_detail(request, feedback_id):
    """Feedback-Details anzeigen"""
    from .models import Feedback
    feedback = get_object_or_404(Feedback, id=feedback_id, user=request.user)
    return render(request, 'core/feedback_detail.html', {'feedback': feedback})


@login_required
def profile(request):
    """Profil-Seite zum Bearbeiten von Benutzerdaten"""
    from django.contrib.auth.hashers import check_password
    
    if request.method == 'POST':
        action = request.POST.get('action')
        user = request.user
        
        if action == 'update_profile':
            new_username = request.POST.get('username', '').strip()
            new_email = request.POST.get('email', '').strip().lower()
            
            errors = []
            
            # Username validieren
            if new_username and new_username != user.username:
                from django.contrib.auth.models import User
                if User.objects.filter(username=new_username).exists():
                    errors.append('Dieser Benutzername ist bereits vergeben.')
                elif len(new_username) < 3:
                    errors.append('Benutzername muss mindestens 3 Zeichen haben.')
                else:
                    user.username = new_username
            
            # E-Mail validieren
            if new_email and new_email != user.email:
                from django.contrib.auth.models import User
                if User.objects.filter(email=new_email).exists():
                    errors.append('Diese E-Mail ist bereits registriert.')
                else:
                    user.email = new_email
            
            if errors:
                for error in errors:
                    messages.error(request, error)
            else:
                user.save()
                messages.success(request, '✅ Profil erfolgreich aktualisiert!')
            
        elif action == 'change_password':
            current_password = request.POST.get('current_password')
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')
            
            if not check_password(current_password, user.password):
                messages.error(request, 'Aktuelles Passwort ist falsch.')
            elif len(new_password) < 8:
                messages.error(request, 'Neues Passwort muss mindestens 8 Zeichen haben.')
            elif new_password != confirm_password:
                messages.error(request, 'Passwörter stimmen nicht überein.')
            else:
                user.set_password(new_password)
                user.save()
                # Nach Passwortänderung neu einloggen
                login(request, user)
                messages.success(request, '✅ Passwort erfolgreich geändert!')
        
        return redirect('profile')
    
    return render(request, 'core/profile.html')


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
    
    # NEU: Faktor 4: Cardio-Ermüdung (zusätzliche Punkte)
    from .models import CardioEinheit
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
    
    # OpenRouter Flag für AI Plan Generator
    # Auf dem Server (DEBUG=False) immer OpenRouter verwenden (keine lokale GPU)
    from django.conf import settings
    use_openrouter = not settings.DEBUG or os.getenv('USE_OPENROUTER', 'False').lower() == 'true'
    
    # AI Auto-Suggest: Performance-Warnungen analysieren
    performance_warnings = []
    
    if gesamt_trainings >= 4:
        # 1. PLATEAU-Erkennung: Keine Progression bei Top-Übungen (letzte 4 Wochen)
        four_weeks_ago = heute - timedelta(days=28)
        
        for fav in favoriten[:3]:  # Top 3 Übungen prüfen
            uebung_id = fav['uebung__id']
            uebung_name = fav['uebung__bezeichnung']
            
            # Letzte 8 Sätze dieser Übung
            recent_sets = Satz.objects.filter(
                einheit__user=request.user,
                uebung_id=uebung_id,
                ist_aufwaermsatz=False,
                datum__gte=four_weeks_ago
            ).order_by('-datum')[:8]
            
            if recent_sets.count() >= 4:
                # Berechne max Gewicht der letzten 4 vs. vorherige 4 Sätze
                latest_4 = list(recent_sets[:4])
                previous_4 = list(recent_sets[4:8])
                
                if len(previous_4) >= 2:
                    latest_max = max([float(s.gewicht or 0) for s in latest_4])
                    previous_max = max([float(s.gewicht or 0) for s in previous_4])
                    
                    # Plateau wenn kein Anstieg in 4 Wochen
                    if latest_max <= previous_max and latest_max > 0:
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
            datum__gte=two_weeks_ago,
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
                datum__gte=heute - timedelta(days=28),
                datum__lt=two_weeks_ago
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
                datum__gte=heute - timedelta(days=14),
                ist_aufwaermsatz=False
            ).values_list('uebung__muskelgruppe', flat=True)
        )
        
        # Muskelgruppen die User Equipment hat aber nicht trainiert
        user_exercises = Uebung.objects.filter(
            Q(is_custom=False) | Q(created_by=request.user)
        ).values_list('muskelgruppe', flat=True).distinct()
        
        for mg in user_exercises:
            if mg not in trained_recently:
                # Prüfe wann zuletzt trainiert
                last_training = Satz.objects.filter(
                    einheit__user=request.user,
                    uebung__muskelgruppe=mg,
                    ist_aufwaermsatz=False
                ).order_by('-datum').first()
                
                if last_training:
                    days_ago = (heute.date() - last_training.datum.date()).days
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
    return render(request, 'core/dashboard.html', context)

def training_select_plan(request):
    """Zeigt alle verfügbaren Pläne zur Auswahl an."""
    from collections import OrderedDict
    
    # Filter-Parameter (eigene, public oder shared)
    filter_type = request.GET.get('filter', 'eigene')
    
    if filter_type == 'public':
        # Öffentliche Pläne von allen Usern (außer eigene)
        plaene = Plan.objects.filter(is_public=True).exclude(user=request.user).order_by('gruppe_name', 'gruppe_reihenfolge', 'name')
    elif filter_type == 'shared':
        # Mit mir geteilte Pläne (von Trainingspartnern)
        plaene = request.user.shared_plans.all().order_by('gruppe_name', 'gruppe_reihenfolge', 'name')
    else:
        # Eigene Pläne (Standard) - sortiert nach Reihenfolge innerhalb Gruppe
        plaene = Plan.objects.filter(user=request.user).order_by('gruppe_name', 'gruppe_reihenfolge', 'name')
    
    # Gruppiere Pläne nach gruppe_id (echte Datenbankbeziehung)
    plan_gruppen = OrderedDict()
    einzelne_plaene = []
    
    for plan in plaene:
        if plan.gruppe_id:
            # Plan gehört zu einer Gruppe
            gruppe_key = str(plan.gruppe_id)
            if gruppe_key not in plan_gruppen:
                plan_gruppen[gruppe_key] = {
                    'name': plan.gruppe_name or 'Unbenannte Gruppe',
                    'plaene': []
                }
            plan_gruppen[gruppe_key]['plaene'].append(plan)
        else:
            # Einzelner Plan ohne Gruppe
            einzelne_plaene.append(plan)
    
    # Zähle geteilte Pläne für Badge
    shared_count = request.user.shared_plans.count()
    
    context = {
        'plaene': plaene,  # Für Fallback
        'plan_gruppen': plan_gruppen,  # Gruppierte Pläne (dict mit 'name' und 'plaene')
        'einzelne_plaene': einzelne_plaene,  # Nicht gruppierte Pläne
        'filter_type': filter_type,
        'shared_count': shared_count
    }
    return render(request, 'core/training_select_plan.html', context)

def plan_details(request, plan_id):
    """Zeigt Details eines Trainingsplans mit allen Übungen."""
    # Zugriff auf: eigene Pläne, öffentliche Pläne, oder mit mir geteilte Pläne
    from django.db.models import Q
    plan = get_object_or_404(
        Plan, 
        Q(user=request.user) | Q(is_public=True) | Q(shared_with=request.user), 
        id=plan_id
    )
    
    # Prüfe ob User der Owner ist
    is_owner = plan.user == request.user
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
        'is_owner': is_owner,
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
            # re.search sucht die erste Zahl im Text (bounded for safety)
            match = re.search(r'\d{1,4}', str(ziel_text)) if ziel_text else None
            
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

    # Zielwerte aus dem Plan laden (wenn vorhanden)
    plan_ziele = {}
    if training.plan:
        for pu in training.plan.uebungen.all():
            plan_ziele[pu.uebung_id] = {
                'saetze_ziel': pu.saetze_ziel,
                'wiederholungen_ziel': pu.wiederholungen_ziel
            }

    # Gewichtsempfehlungen für alle Übungen im Plan berechnen
    gewichts_empfehlungen = {}
    if training.plan:
        for pu in training.plan.uebungen.all():
            uebung_id = pu.uebung_id
            # Letzten echten Satz dieser Übung finden (aus vorherigen Trainings)
            letzter_satz = Satz.objects.filter(
                einheit__user=request.user,
                uebung_id=uebung_id,
                ist_aufwaermsatz=False
            ).exclude(einheit=training).order_by('-einheit__datum', '-satz_nr').first()
            
            if letzter_satz:
                empfohlenes_gewicht = float(letzter_satz.gewicht)
                empfohlene_wdh = letzter_satz.wiederholungen
                
                # Ziel-Wiederholungen aus dem Plan extrahieren (z.B. "8-10" → max 10)
                ziel_wdh_str = pu.wiederholungen_ziel or "8-12"
                try:
                    if '-' in ziel_wdh_str:
                        ziel_wdh_max = int(ziel_wdh_str.split('-')[1])
                        ziel_wdh_min = int(ziel_wdh_str.split('-')[0])
                    else:
                        ziel_wdh_max = int(ziel_wdh_str)
                        ziel_wdh_min = int(ziel_wdh_str)
                except ValueError:
                    ziel_wdh_max = 12
                    ziel_wdh_min = 8
                
                # Progressive Overload Logik - berücksichtigt Planziel
                if letzter_satz.rpe and float(letzter_satz.rpe) < 7:
                    # RPE zu leicht → mehr Gewicht
                    empfohlenes_gewicht += 2.5
                    hint = f"RPE {letzter_satz.rpe} → +2.5kg"
                elif letzter_satz.wiederholungen >= ziel_wdh_max:
                    # Obere Grenze erreicht → mehr Gewicht, Wdh zurück auf Minimum
                    empfohlenes_gewicht += 2.5
                    empfohlene_wdh = ziel_wdh_min
                    hint = f"{ziel_wdh_max}+ Wdh → +2.5kg"
                elif letzter_satz.rpe and float(letzter_satz.rpe) >= 9:
                    # RPE hoch aber noch im Wdh-Bereich → Wdh erhöhen (max bis Ziel)
                    empfohlene_wdh = min(empfohlene_wdh + 1, ziel_wdh_max)
                    hint = f"RPE {letzter_satz.rpe} → mehr Wdh"
                else:
                    hint = "Niveau halten"
                
                # Pausenempfehlung: Aus Plan nehmen falls vorhanden, sonst berechnen
                plan_pausenzeit = pu.pausenzeit if hasattr(pu, 'pausenzeit') and pu.pausenzeit else None
                
                if plan_pausenzeit:
                    # Plan hat Pausenzeit definiert → nutze diese
                    empfohlene_pause = plan_pausenzeit
                elif '+2.5kg' in hint:
                    empfohlene_pause = 180  # 3 Min für Kraftsteigerung
                elif 'mehr Wdh' in hint:
                    empfohlene_pause = 90   # 90s für Volumen/Ausdauer
                else:
                    empfohlene_pause = 120  # 2 Min Standard
                
                gewichts_empfehlungen[uebung_id] = {
                    'gewicht': empfohlenes_gewicht,
                    'wdh': empfohlene_wdh,
                    'letztes_gewicht': float(letzter_satz.gewicht),
                    'letzte_wdh': letzter_satz.wiederholungen,
                    'hint': hint,
                    'pause': empfohlene_pause,
                    'pause_from_plan': bool(plan_pausenzeit),
                }

    context = {
        'training': training,
        'uebungen': uebungen,
        'saetze': saetze,
        'total_volume': round(total_volume, 1),
        'arbeitssaetze_count': arbeitssaetze.count(),
        'plan_ziele': plan_ziele,
        'gewichts_empfehlungen': gewichts_empfehlungen,
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

def delete_training(request, training_id):
    """Löscht ein komplettes Training aus der Historie."""
    training = get_object_or_404(Trainingseinheit, id=training_id, user=request.user)
    training.delete()
    # Wir leiten zurück zur Liste (History)
    return redirect('training_list')

@login_required
def get_last_set(request, uebung_id):
    """API: Liefert die Werte des letzten 'echten' Satzes einer Übung zurück."""
    # Optionales Wiederholungsziel aus Query-Parameter (z.B. ?ziel=8-10)
    ziel_wdh_str = request.GET.get('ziel', '8-12')
    try:
        if '-' in ziel_wdh_str:
            ziel_wdh_max = int(ziel_wdh_str.split('-')[1])
            ziel_wdh_min = int(ziel_wdh_str.split('-')[0])
        else:
            ziel_wdh_max = int(ziel_wdh_str)
            ziel_wdh_min = int(ziel_wdh_str)
    except ValueError:
        ziel_wdh_max = 12
        ziel_wdh_min = 8
    
    # Wir suchen den allerletzten Satz dieser Übung (trainingübergreifend)
    # Wichtig: Wir ignorieren Aufwärmsätze (ist_aufwaermsatz=False)
    letzter_satz = Satz.objects.filter(
        einheit__user=request.user,
        uebung_id=uebung_id, 
        ist_aufwaermsatz=False
    ).order_by('-einheit__datum', '-satz_nr').first()

    if letzter_satz:
        # Progressive Overload Logik - berücksichtigt Planziel
        empfohlenes_gewicht = float(letzter_satz.gewicht)
        empfohlene_wdh = letzter_satz.wiederholungen
        
        if letzter_satz.rpe and float(letzter_satz.rpe) < 7:
            # RPE zu leicht → mehr Gewicht
            empfohlenes_gewicht += 2.5
            progression_hint = f"RPE {letzter_satz.rpe} war leicht → versuch +2.5kg!"
        elif letzter_satz.wiederholungen >= ziel_wdh_max:
            # Obere Zielgrenze erreicht → mehr Gewicht, Wdh zurück auf Minimum
            empfohlenes_gewicht += 2.5
            empfohlene_wdh = ziel_wdh_min
            progression_hint = f"{ziel_wdh_max}+ Wdh geschafft → Zeit für +2.5kg!"
        elif letzter_satz.rpe and float(letzter_satz.rpe) >= 9:
            # RPE hoch aber noch im Wdh-Bereich → Wdh erhöhen (max bis Ziel)
            empfohlene_wdh = min(empfohlene_wdh + 1, ziel_wdh_max)
            progression_hint = f"RPE {letzter_satz.rpe} → versuch mehr Wiederholungen!"
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
    
    # AI Auto-Suggest: Optimierungsvorschlag nach jedem 3. Training
    ai_suggestion = None
    training_count = Trainingseinheit.objects.filter(user=request.user).count()
    
    if training_count > 0 and training_count % 3 == 0:
        # Analysiere die letzten 3 Trainings
        recent_trainings = Trainingseinheit.objects.filter(
            user=request.user
        ).order_by('-datum')[:3]
        
        # Berechne durchschnittlichen RPE der letzten 3 Trainings
        recent_sets = Satz.objects.filter(
            einheit__in=recent_trainings,
            ist_aufwaermsatz=False,
            rpe__isnull=False
        )
        
        if recent_sets.exists():
            avg_rpe = recent_sets.aggregate(Avg('rpe'))['rpe__avg']
            
            # Volumen-Analyse der letzten 3 vs. vorherige 3 Trainings
            previous_trainings = Trainingseinheit.objects.filter(
                user=request.user
            ).order_by('-datum')[3:6]
            
            recent_volume = sum(
                float(s.gewicht or 0) * int(s.wiederholungen or 0)
                for t in recent_trainings
                for s in t.saetze.filter(ist_aufwaermsatz=False)
            )
            
            previous_volume = sum(
                float(s.gewicht or 0) * int(s.wiederholungen or 0)
                for t in previous_trainings
                for s in t.saetze.filter(ist_aufwaermsatz=False)
            ) if previous_trainings.exists() else 0
            
            # Generiere intelligente Vorschläge basierend auf Daten
            suggestions = []
            
            # Vorschlag 1: Intensität anpassen
            if avg_rpe < 6.5:
                suggestions.append({
                    'type': 'intensity',
                    'title': 'Intensität erhöhen',
                    'message': f'Dein durchschnittlicher RPE liegt bei {avg_rpe:.1f}/10',
                    'action': 'Steigere das Gewicht um 5-10% oder reduziere die Pausenzeit',
                    'icon': 'bi-arrow-up-circle',
                    'color': 'info'
                })
            elif avg_rpe > 8.5:
                suggestions.append({
                    'type': 'intensity',
                    'title': 'Regeneration priorisieren',
                    'message': f'Dein durchschnittlicher RPE liegt bei {avg_rpe:.1f}/10',
                    'action': 'Reduziere die Intensität oder plane einen Deload',
                    'icon': 'bi-shield-check',
                    'color': 'warning'
                })
            
            # Vorschlag 2: Volumen anpassen
            if previous_volume > 0:
                volume_change = ((recent_volume - previous_volume) / previous_volume) * 100
                
                if volume_change < -15:
                    suggestions.append({
                        'type': 'volume',
                        'title': 'Volumen gesunken',
                        'message': f'Dein Volumen ist um {abs(volume_change):.0f}% gefallen',
                        'action': 'Füge 1-2 Sätze pro Übung hinzu oder trainiere häufiger',
                        'icon': 'bi-graph-down',
                        'color': 'danger'
                    })
                elif volume_change > 30:
                    suggestions.append({
                        'type': 'volume',
                        'title': 'Volumen stark gestiegen',
                        'message': f'Dein Volumen ist um {volume_change:.0f}% gestiegen',
                        'action': 'Achte auf ausreichend Regeneration zwischen Trainings',
                        'icon': 'bi-graph-up',
                        'color': 'warning'
                    })
            
            # Vorschlag 3: Übungsvariation
            trained_exercises = set(
                recent_sets.values_list('uebung_id', flat=True).distinct()
            )
            
            if len(trained_exercises) < 5:
                suggestions.append({
                    'type': 'variety',
                    'title': 'Mehr Übungsvielfalt',
                    'message': f'Du hast nur {len(trained_exercises)} verschiedene Übungen gemacht',
                    'action': 'Integriere neue Übungen für besseres Muskelwachstum',
                    'icon': 'bi-shuffle',
                    'color': 'info'
                })
            
            # Wähle den wichtigsten Vorschlag (höchste Priorität)
            priority_order = {'danger': 0, 'warning': 1, 'info': 2}
            if suggestions:
                ai_suggestion = sorted(suggestions, key=lambda x: priority_order[x['color']])[0]
    
    context = {
        'training': training,
        'arbeitssaetze_count': arbeitssaetze.count(),
        'warmup_saetze_count': warmup_saetze.count(),
        'total_volume': round(total_volume, 1),
        'uebungen_count': uebungen_count,
        'dauer_geschaetzt': dauer_geschaetzt,
        'training_count': training_count,
        'ai_suggestion': ai_suggestion,
    }
    return render(request, 'core/training_finish.html', context)


# Trainingsplan ohne Admin erstellen
@login_required
def create_plan(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        beschreibung = request.POST.get('beschreibung', '')
        is_public = request.POST.get('is_public') == 'on'  # Checkbox-Wert
        uebungen_ids = request.POST.getlist('uebungen')  # Liste von Übungs-IDs
        
        if name and uebungen_ids:
            plan = Plan.objects.create(
                user=request.user, 
                name=name, 
                beschreibung=beschreibung,
                is_public=is_public
            )
            
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
        plan.is_public = request.POST.get('is_public') == 'on'  # Checkbox-Wert
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
def copy_plan(request, plan_id):
    """Kopiert einen öffentlichen Plan in die eigenen Pläne."""
    from django.db.models import Q
    
    # Plan muss öffentlich sein oder dem User gehören
    original_plan = get_object_or_404(Plan, Q(is_public=True) | Q(user=request.user), id=plan_id)
    
    # Erstelle Kopie
    new_plan = Plan.objects.create(
        user=request.user,
        name=f"{original_plan.name} (Kopie)",
        beschreibung=original_plan.beschreibung,
        is_public=False  # Kopien sind standardmäßig privat
    )
    
    # Kopiere alle Übungen
    for plan_uebung in original_plan.uebungen.all():
        PlanUebung.objects.create(
            plan=new_plan,
            uebung=plan_uebung.uebung,
            reihenfolge=plan_uebung.reihenfolge,
            trainingstag=plan_uebung.trainingstag,
            saetze_ziel=plan_uebung.saetze_ziel,
            wiederholungen_ziel=plan_uebung.wiederholungen_ziel,
            superset_gruppe=plan_uebung.superset_gruppe
        )
    
    messages.success(request, f'Plan "{original_plan.name}" wurde in deine Pläne kopiert!')
    return redirect('plan_details', plan_id=new_plan.id)


@login_required
def duplicate_plan(request, plan_id):
    """Dupliziert einen eigenen Plan."""
    original_plan = get_object_or_404(Plan, id=plan_id, user=request.user)
    
    # Erstelle Kopie
    new_plan = Plan.objects.create(
        user=request.user,
        name=f"{original_plan.name} (Kopie)",
        beschreibung=original_plan.beschreibung,
        is_public=False  # Duplikate sind standardmäßig privat
    )
    
    # Kopiere alle Übungen
    for plan_uebung in original_plan.uebungen.all().order_by('reihenfolge'):
        PlanUebung.objects.create(
            plan=new_plan,
            uebung=plan_uebung.uebung,
            reihenfolge=plan_uebung.reihenfolge,
            trainingstag=plan_uebung.trainingstag,
            saetze_ziel=plan_uebung.saetze_ziel,
            wiederholungen_ziel=plan_uebung.wiederholungen_ziel,
            pausenzeit=plan_uebung.pausenzeit,
            superset_gruppe=plan_uebung.superset_gruppe
        )
    
    messages.success(request, f'Plan "{original_plan.name}" wurde dupliziert!')
    return redirect('plan_details', plan_id=new_plan.id)


@login_required
def duplicate_group(request, gruppe_id):
    """Dupliziert eine komplette Plan-Gruppe."""
    import uuid
    
    # Alle Pläne dieser Gruppe finden
    original_plans = Plan.objects.filter(
        user=request.user, 
        gruppe_id=gruppe_id
    ).order_by('gruppe_reihenfolge', 'name')
    
    if not original_plans.exists():
        messages.error(request, 'Gruppe nicht gefunden.')
        return redirect('training_select_plan')
    
    # Neue Gruppe-ID erstellen
    new_gruppe_id = uuid.uuid4()
    
    # Original-Gruppenname mit "(Kopie)" ergänzen
    original_gruppe_name = original_plans.first().gruppe_name or 'Gruppe'
    new_gruppe_name = f"{original_gruppe_name} (Kopie)"
    
    # Alle Pläne der Gruppe kopieren
    for idx, original_plan in enumerate(original_plans):
        new_plan = Plan.objects.create(
            user=request.user,
            name=original_plan.name,
            beschreibung=original_plan.beschreibung,
            is_public=False,
            gruppe_id=new_gruppe_id,
            gruppe_name=new_gruppe_name,
            gruppe_reihenfolge=idx
        )
        
        # Übungen kopieren
        for plan_uebung in original_plan.uebungen.all().order_by('reihenfolge'):
            PlanUebung.objects.create(
                plan=new_plan,
                uebung=plan_uebung.uebung,
                reihenfolge=plan_uebung.reihenfolge,
                trainingstag=plan_uebung.trainingstag,
                saetze_ziel=plan_uebung.saetze_ziel,
                wiederholungen_ziel=plan_uebung.wiederholungen_ziel,
                pausenzeit=plan_uebung.pausenzeit,
                superset_gruppe=plan_uebung.superset_gruppe
            )
    
    messages.success(request, f'Gruppe "{original_gruppe_name}" wurde dupliziert ({original_plans.count()} Pläne)!')
    return redirect('training_select_plan')


def share_plan(request, plan_id):
    """Zeigt Sharing-Seite mit QR-Code für einen Plan."""
    from django.db.models import Q
    
    plan = get_object_or_404(Plan, Q(is_public=True) | Q(user=request.user), id=plan_id)
    
    # Prüfe ob User der Owner ist
    is_owner = request.user.is_authenticated and plan.user == request.user
    
    # Generiere Share-URL
    share_url = request.build_absolute_uri(f'/plan/{plan.id}/')
    
    # QR-Code als Base64 generieren
    qr_base64 = None
    try:
        import qrcode
        from io import BytesIO
        import base64
        
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(share_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()
    except ImportError:
        pass  # QR-Code Package nicht installiert
    
    context = {
        'plan': plan,
        'share_url': share_url,
        'qr_base64': qr_base64,
        'is_owner': is_owner,
    }
    return render(request, 'core/share_plan.html', context)


def share_group(request, gruppe_id):
    """Zeigt Sharing-Seite mit QR-Code für eine Plan-Gruppe."""
    from django.db.models import Q
    
    # Finde alle Pläne dieser Gruppe (öffentlich oder eigene)
    if request.user.is_authenticated:
        plans = Plan.objects.filter(
            Q(is_public=True) | Q(user=request.user),
            gruppe_id=gruppe_id
        ).order_by('gruppe_reihenfolge', 'name')
    else:
        plans = Plan.objects.filter(
            is_public=True,
            gruppe_id=gruppe_id
        ).order_by('gruppe_reihenfolge', 'name')
    
    if not plans.exists():
        messages.error(request, 'Gruppe nicht gefunden oder nicht zugänglich.')
        return redirect('training_select_plan')
    
    gruppe_name = plans.first().gruppe_name or 'Gruppe'
    is_owner = request.user.is_authenticated and plans.first().user == request.user
    
    # Generiere Share-URL zur Gruppen-Bibliothek
    share_url = request.build_absolute_uri(f'/plan-library/group/{gruppe_id}/')
    
    # QR-Code als Base64 generieren
    qr_base64 = None
    try:
        import qrcode
        from io import BytesIO
        import base64
        
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(share_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()
    except ImportError:
        pass
    
    context = {
        'plans': plans,
        'gruppe_name': gruppe_name,
        'gruppe_id': gruppe_id,
        'share_url': share_url,
        'qr_base64': qr_base64,
        'is_owner': is_owner,
    }
    return render(request, 'core/share_group.html', context)


def plan_library(request):
    """Öffentliche Plan-Bibliothek - zeigt alle öffentlichen Pläne und Gruppen."""
    from collections import OrderedDict
    
    # Suchfilter
    search_query = request.GET.get('q', '').strip()
    
    # Alle öffentlichen Pläne
    public_plans = Plan.objects.filter(is_public=True).order_by('gruppe_name', 'gruppe_reihenfolge', 'name')
    
    if search_query:
        public_plans = public_plans.filter(
            models.Q(name__icontains=search_query) |
            models.Q(beschreibung__icontains=search_query) |
            models.Q(gruppe_name__icontains=search_query)
        )
    
    # Gruppiere nach gruppe_id
    plan_gruppen = OrderedDict()
    einzelne_plaene = []
    
    for plan in public_plans:
        if plan.gruppe_id:
            gruppe_key = str(plan.gruppe_id)
            if gruppe_key not in plan_gruppen:
                plan_gruppen[gruppe_key] = {
                    'name': plan.gruppe_name or 'Unbenannte Gruppe',
                    'plaene': [],
                    'user': plan.user
                }
            plan_gruppen[gruppe_key]['plaene'].append(plan)
        else:
            einzelne_plaene.append(plan)
    
    context = {
        'plan_gruppen': plan_gruppen,
        'einzelne_plaene': einzelne_plaene,
        'search_query': search_query,
        'total_count': public_plans.count(),
    }
    return render(request, 'core/plan_library.html', context)


def plan_library_group(request, gruppe_id):
    """Detail-Ansicht einer Plan-Gruppe in der Bibliothek."""
    # Finde alle öffentlichen Pläne dieser Gruppe
    plans = Plan.objects.filter(
        is_public=True,
        gruppe_id=gruppe_id
    ).order_by('gruppe_reihenfolge', 'name')
    
    if not plans.exists():
        messages.error(request, 'Gruppe nicht gefunden.')
        return redirect('plan_library')
    
    gruppe_name = plans.first().gruppe_name or 'Gruppe'
    owner = plans.first().user
    
    context = {
        'plans': plans,
        'gruppe_name': gruppe_name,
        'gruppe_id': gruppe_id,
        'owner': owner,
    }
    return render(request, 'core/plan_library_group.html', context)


@login_required
def copy_group(request, gruppe_id):
    """Kopiert eine öffentliche Gruppe in die eigenen Pläne."""
    import uuid
    
    # Alle öffentlichen Pläne dieser Gruppe finden
    original_plans = Plan.objects.filter(
        is_public=True,
        gruppe_id=gruppe_id
    ).order_by('gruppe_reihenfolge', 'name')
    
    if not original_plans.exists():
        messages.error(request, 'Gruppe nicht gefunden.')
        return redirect('plan_library')
    
    # Neue Gruppe-ID erstellen
    new_gruppe_id = uuid.uuid4()
    
    original_gruppe_name = original_plans.first().gruppe_name or 'Gruppe'
    new_gruppe_name = f"{original_gruppe_name} (Kopie)"
    
    # Alle Pläne kopieren
    for idx, original_plan in enumerate(original_plans):
        new_plan = Plan.objects.create(
            user=request.user,
            name=original_plan.name,
            beschreibung=original_plan.beschreibung,
            is_public=False,
            gruppe_id=new_gruppe_id,
            gruppe_name=new_gruppe_name,
            gruppe_reihenfolge=idx
        )
        
        # Übungen kopieren
        for plan_uebung in original_plan.uebungen.all().order_by('reihenfolge'):
            PlanUebung.objects.create(
                plan=new_plan,
                uebung=plan_uebung.uebung,
                reihenfolge=plan_uebung.reihenfolge,
                trainingstag=plan_uebung.trainingstag,
                saetze_ziel=plan_uebung.saetze_ziel,
                wiederholungen_ziel=plan_uebung.wiederholungen_ziel,
                pausenzeit=plan_uebung.pausenzeit,
                superset_gruppe=plan_uebung.superset_gruppe
            )
    
    messages.success(request, f'Gruppe "{original_gruppe_name}" wurde in deine Pläne kopiert ({original_plans.count()} Pläne)!')
    return redirect('training_select_plan')


@login_required
def toggle_plan_public(request, plan_id):
    """Toggle public/private Status eines Plans."""
    plan = get_object_or_404(Plan, id=plan_id, user=request.user)
    plan.is_public = not plan.is_public
    plan.save()
    
    status = "öffentlich" if plan.is_public else "privat"
    messages.success(request, f'Plan "{plan.name}" ist jetzt {status}.')
    return redirect('plan_details', plan_id=plan_id)


@login_required
def toggle_group_public(request, gruppe_id):
    """Toggle public/private Status aller Pläne einer Gruppe."""
    plans = Plan.objects.filter(user=request.user, gruppe_id=gruppe_id)
    
    if not plans.exists():
        messages.error(request, 'Gruppe nicht gefunden.')
        return redirect('training_select_plan')
    
    # Checke aktuellen Status (alle öffentlich?)
    all_public = all(p.is_public for p in plans)
    new_status = not all_public
    
    plans.update(is_public=new_status)
    
    gruppe_name = plans.first().gruppe_name or 'Gruppe'
    status = "öffentlich" if new_status else "privat"
    messages.success(request, f'Gruppe "{gruppe_name}" ist jetzt {status}.')
    return redirect('training_select_plan')


@login_required
def uebungen_auswahl(request):
    """Übersicht aller Übungen mit grafischer Muskelgruppen-Darstellung"""
    # Equipment-Filter: Nur Übungen mit verfügbarem Equipment
    user_equipment_ids = request.user.verfuegbares_equipment.values_list('id', flat=True)
    
    # Include both global exercises and user's custom exercises
    base_queryset = Uebung.objects.filter(
        Q(is_custom=False) | Q(created_by=request.user)
    ).prefetch_related('equipment', 'favoriten')
    
    if user_equipment_ids:
        # Filter: Übungen die ALLE ihre benötigten Equipment haben ODER keine Equipment-Anforderungen
        uebungen = []
        for uebung in base_queryset.order_by('muskelgruppe', 'bezeichnung'):
            required_eq_ids = set(uebung.equipment.values_list('id', flat=True))
            # Verfügbar wenn: keine Equipment nötig ODER alle benötigten Equipment verfügbar
            if not required_eq_ids or required_eq_ids.issubset(set(user_equipment_ids)):
                uebungen.append(uebung)
    else:
        # Keine Equipment ausgewählt: Nur Übungen ohne Equipment-Anforderung
        uebungen = base_queryset.filter(equipment__isnull=True).distinct().order_by('muskelgruppe', 'bezeichnung')
    
    # Gruppiere nach Muskelgruppen
    uebungen_nach_gruppe = {}
    for uebung in uebungen:
        mg_label = dict(MUSKELGRUPPEN).get(uebung.muskelgruppe, uebung.muskelgruppe)
        if mg_label not in uebungen_nach_gruppe:
            uebungen_nach_gruppe[mg_label] = []
        
        # Add hilfsmuskeln labels as temporary attribute for template
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
                # Clean text (remove parentheses content) - Safe regex with bounded quantifier
                hilfs_text_clean = re.sub(r'\([^)]{0,50}\)', '', hilfs_text).strip()
                # Try to get code
                code = text_to_code.get(hilfs_text_clean)
                if code:
                    # Get display label for the code
                    label = dict(MUSKELGRUPPEN).get(code, hilfs_text_clean)
                    hilfs_labels.append(label)
                else:
                    # Fallback: use text as-is
                    hilfs_labels.append(hilfs_text_clean)
        
        # Add temporary attributes for template (avoid modifying model)
        uebung.muskelgruppe_label = mg_label
        uebung.hilfsmuskeln_labels = hilfs_labels
        uebung.hilfsmuskeln_count = len(hilfs_labels)
        
        uebungen_nach_gruppe[mg_label].append(uebung)
    
    context = {
        'uebungen_nach_gruppe': uebungen_nach_gruppe,
        'user_equipment': request.user.verfuegbares_equipment.all(),
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
                progression_prozent = round(((float(letztes_max) - float(erstes_max)) / float(erstes_max)) * 100, 1)
                kraft_progression.append({
                    'uebung': uebung_name,
                    'start_gewicht': float(erstes_max),
                    'aktuell_gewicht': float(letztes_max),
                    'progression': float(progression_prozent),
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
        
        # Datenqualitäts-Check: Bei wenigen Trainingseinheiten softere Formulierung
        wenig_daten = trainings_30_tage < 8
        
        if anzahl == 0:
            status = 'nicht_trainiert'
            status_label = 'Nicht trainiert'
            if wenig_daten:
                erklaerung = f'Noch keine Sätze erfasst. Empfehlung: {min_saetze}-{max_saetze} Sätze/Monat'
            else:
                erklaerung = f'Diese Muskelgruppe wurde nicht trainiert. Empfehlung: {min_saetze}-{max_saetze} Sätze/Monat'
        elif anzahl < min_saetze:
            status = 'untertrainiert'
            if wenig_daten:
                status_label = 'Wenig trainiert'
                erklaerung = f'{anzahl} Sätze in 30 Tagen. Empfehlung: {min_saetze}-{max_saetze} Sätze/Monat (mehr Daten für genauere Analyse)'
            else:
                status_label = 'Untertrainiert'
                erklaerung = f'Nur {anzahl} Sätze in 30 Tagen. Empfehlung: {min_saetze}-{max_saetze} Sätze für optimales Wachstum'
        elif anzahl > max_saetze:
            status = 'uebertrainiert'
            if wenig_daten:
                status_label = 'Viel trainiert'
                erklaerung = f'{anzahl} Sätze - intensiver Start! Beobachte Regeneration. Empfehlung: {min_saetze}-{max_saetze} Sätze/Monat'
            else:
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
            avg_rpe_result = gruppe_saetze.aggregate(Avg('rpe'))['rpe__avg']
            avg_rpe = float(avg_rpe_result) if avg_rpe_result else 0.0
            muskelgruppen_stats.append({
                'key': gruppe_key,
                'name': gruppe_name,
                'saetze': anzahl,
                'volumen': float(round(volumen, 0)),
                'avg_rpe': float(round(avg_rpe, 1)),
                'status': status,
                'status_label': status_label,
                'erklaerung': erklaerung,
                'empfehlung_min': min_saetze,
                'empfehlung_max': max_saetze,
                'prozent_von_optimal': float(round((anzahl / ((min_saetze + max_saetze) / 2)) * 100, 0))
            })
    
    muskelgruppen_stats = sorted(muskelgruppen_stats, key=lambda x: x['saetze'], reverse=True)
    
    # Push/Pull-Balance Analyse (Keys angepasst an MUSKELGRUPPEN in models.py)
    push_groups = ['BRUST', 'SCHULTER_VORN', 'SCHULTER_SEIT', 'TRIZEPS']
    pull_groups = ['RUECKEN_LAT', 'RUECKEN_TRAPEZ', 'RUECKEN_UNTEN', 'RUECKEN_OBERER', 'SCHULTER_HINT', 'BIZEPS']
    
    push_saetze = sum(mg['saetze'] for mg in muskelgruppen_stats if mg['key'] in push_groups)
    pull_saetze = sum(mg['saetze'] for mg in muskelgruppen_stats if mg['key'] in pull_groups)
    
    # Bewertung der Balance
    if push_saetze == 0 and pull_saetze == 0:
        push_pull_ratio = 0
        push_pull_bewertung = 'Keine Daten'
        push_pull_empfehlung = 'Beginne mit ausgewogenem Push- und Pull-Training für optimale Muskelentwicklung.'
    elif pull_saetze > 0:
        push_pull_ratio = round(push_saetze / pull_saetze, 2)
        if 0.9 <= push_pull_ratio <= 1.1:
            push_pull_bewertung = 'Ausgewogen'
            push_pull_empfehlung = 'Perfekt! Push/Pull-Verhältnis ist ausgeglichen.'
        elif push_pull_ratio > 1.1:
            push_pull_bewertung = 'Zu viel Push'
            push_pull_empfehlung = f'Ratio {push_pull_ratio}:1 - Mehr Pull-Training (Rücken, Bizeps) für Schultergesundheit!'
        else:
            push_pull_bewertung = 'Zu viel Pull'
            push_pull_empfehlung = f'Ratio {push_pull_ratio}:1 - Mehr Push-Training (Brust, Schultern) für Balance!'
    else:
        # pull_saetze ist 0, aber push_saetze > 0
        push_pull_ratio = 0
        push_pull_bewertung = 'Nur Push'
        push_pull_empfehlung = 'Füge Pull-Training (Rücken, Bizeps) hinzu für ausgeglichene Entwicklung!'
    
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
        avg_rpe_val = rpe_saetze.aggregate(Avg('rpe'))['rpe__avg']
        avg_rpe = float(round(avg_rpe_val, 1)) if avg_rpe_val else 0.0
        rpe_verteilung = {
            'leicht': int(rpe_saetze.filter(rpe__lte=6).count()),
            'mittel': int(rpe_saetze.filter(rpe__gt=6, rpe__lte=8).count()),
            'schwer': int(rpe_saetze.filter(rpe__gt=8).count())
        }
    else:
        avg_rpe = 0
        rpe_verteilung = {'leicht': 0, 'mittel': 0, 'schwer': 0}
    
    # Volumen-Progression über letzte 12 Wochen (gleiche Logik wie Browser-Ansicht)
    from collections import defaultdict
    weekly_volume_pdf = defaultdict(float)
    
    for satz in alle_saetze.filter(ist_aufwaermsatz=False):
        if satz.gewicht and satz.wiederholungen:
            # ISO-Kalenderwoche des Trainings
            iso_year, iso_week, _ = satz.einheit.datum.isocalendar()
            week_key = f"{iso_year}-W{iso_week:02d}"
            volumen = float(satz.gewicht) * satz.wiederholungen
            weekly_volume_pdf[week_key] += volumen
    
    # Letzte 12 Wochen sortiert
    weekly_labels_pdf = sorted(weekly_volume_pdf.keys())[-12:]
    volumen_wochen = [
        {
            'woche': f"KW{label.split('-W')[1]}",
            'volumen': round(weekly_volume_pdf[label], 0)
        }
        for label in weekly_labels_pdf
    ]
    
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
    push_saetze = int(push_pull_balance.get('push_saetze', 0))
    pull_saetze = int(push_pull_balance.get('pull_saetze', 0))
    push_pull_ratio = float(push_pull_balance.get('ratio', 0))
    push_pull_bewertung = str(push_pull_balance.get('bewertung', ''))
    push_pull_empfehlung = str(push_pull_balance.get('empfehlung', ''))
    
    # Stärken identifizieren (optimale Muskelgruppen)
    staerken = [mg for mg in muskelgruppen_stats if mg['status'] == 'optimal']
    
    # Charts generieren (matplotlib)
    try:
        from core.chart_generator import generate_body_map_with_data
        muscle_heatmap = generate_muscle_heatmap(muskelgruppen_stats)
        volume_chart = generate_volume_chart(volumen_wochen[-8:])
        push_pull_chart = generate_push_pull_pie(push_saetze, pull_saetze)
        body_map_image = generate_body_map_with_data(muskelgruppen_stats)  # Dynamische Body-Map mit User-Daten
        logger.info('Charts successfully generated')
    except Exception as e:
        logger.warning(f'Chart generation failed: {str(e)}')
        muscle_heatmap = None
        volume_chart = None
        push_pull_chart = None
        body_map_image = None
    
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
        'body_map_image': body_map_image,  # Body-Map Visualisierung
        'koerperwerte': koerperwerte,
        'letzter_koerperwert': letzter_koerperwert,
        'gewichts_trend': gewichts_trend,
    }
    
    # HTML rendern (vereinfachtes Template für xhtml2pdf-Kompatibilität)
    try:
        html_string = render_to_string('core/training_pdf_simple.html', context)
    except Exception as e:
        logger.error(f'Template rendering failed: {str(e)}', exc_info=True)
        messages.error(request, 'Template-Fehler: PDF konnte nicht erstellt werden.')
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
        messages.error(request, 'PDF-Generierung fehlgeschlagen. Bitte später erneut versuchen.')
        return redirect('training_stats')


@login_required
def export_plan_pdf(request, plan_id):
    """Exportiert einen Trainingsplan als PDF mit QR-Code."""
    from io import BytesIO
    import logging
    try:
        from xhtml2pdf import pisa
        import qrcode
        import base64
    except ImportError:
        messages.error(request, 'PDF Export nicht verfügbar - Pakete fehlen')
        return redirect('plan_details', plan_id=plan_id)
    
    logger = logging.getLogger(__name__)
    plan = get_object_or_404(Plan, id=plan_id, user=request.user)
    
    # QR-Code generieren (Link zum Plan)
    plan_url = request.build_absolute_uri(f'/plan/{plan.id}/')
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(plan_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    # QR zu Base64 konvertieren
    buffer = BytesIO()
    qr_img.save(buffer, format='PNG')
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()
    
    # Übungen nach Trainingstag gruppieren
    planuebungen = PlanUebung.objects.filter(plan=plan).select_related('uebung').order_by('trainingstag', 'reihenfolge')
    
    # Gruppiere nach Tag
    tage = {}
    for planuebung in planuebungen:
        tag = planuebung.trainingstag or 'Tag 1'
        if tag not in tage:
            tage[tag] = []
        tage[tag].append(planuebung)
    
    # Muskelgruppen für Icon-Mapping
    muskelgruppen_dict = dict(MUSKELGRUPPEN)
    
    # Beschreibung mit Zeilenumbrüchen formatieren
    beschreibung_html = (plan.beschreibung or 'Keine Beschreibung').replace('\n', '<br>')
    
    # HTML Template für PDF
    html_template = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{
                size: A4;
                margin: 2cm;
            }}
            body {{
                font-family: Arial, sans-serif;
                font-size: 10pt;
                line-height: 1.4;
            }}
            h1 {{
                color: #198754;
                font-size: 24pt;
                margin-bottom: 10px;
                border-bottom: 3px solid #198754;
                padding-bottom: 5px;
            }}
            h2 {{
                color: #0dcaf0;
                font-size: 14pt;
                margin-top: 20px;
                margin-bottom: 10px;
                border-left: 4px solid #0dcaf0;
                padding-left: 10px;
            }}
            .header {{
                display: flex;
                justify-content: space-between;
                align-items: start;
                margin-bottom: 20px;
            }}
            .plan-info {{
                flex: 1;
            }}
            .qr-code {{
                text-align: right;
            }}
            .qr-code img {{
                width: 120px;
                height: 120px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 20px;
            }}
            th {{
                background-color: #198754;
                color: white;
                padding: 8px;
                text-align: left;
                font-size: 9pt;
            }}
            td {{
                padding: 6px 8px;
                border-bottom: 1px solid #ddd;
                font-size: 9pt;
            }}
            tr:nth-child(even) {{
                background-color: #f8f9fa;
            }}
            .badge {{
                display: inline-block;
                padding: 3px 8px;
                border-radius: 3px;
                font-size: 8pt;
                font-weight: bold;
            }}
            .badge-primary {{
                background-color: #198754;
                color: white;
            }}
            .badge-secondary {{
                background-color: #6c757d;
                color: white;
            }}
            .footer {{
                position: fixed;
                bottom: 1cm;
                left: 2cm;
                right: 2cm;
                text-align: center;
                font-size: 8pt;
                color: #6c757d;
                border-top: 1px solid #ddd;
                padding-top: 5px;
            }}
            .page-break {{
                page-break-after: always;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="plan-info">
                <h1>{plan.name}</h1>
                <p><strong>Beschreibung:</strong><br>{beschreibung_html}</p>
                <p><strong>Erstellt:</strong> {plan.erstellt_am.strftime("%d.%m.%Y")}</p>
            </div>
            <div class="qr-code">
                <img src="data:image/png;base64,{qr_base64}" alt="QR Code">
                <p style="font-size: 8pt; color: #6c757d;">Scan für Details</p>
            </div>
        </div>
    '''
    
    # Füge jeden Trainingstag hinzu
    for tag_nummer, uebungen in sorted(tage.items()):
        html_template += f'''
        <h2>{tag_nummer}</h2>
        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>Übung</th>
                    <th>Muskelgruppe</th>
                    <th>Sätze</th>
                    <th>Wiederholungen</th>
                </tr>
            </thead>
            <tbody>
        '''
        
        for idx, pu in enumerate(uebungen, 1):
            muskelgruppe = muskelgruppen_dict.get(pu.uebung.muskelgruppe, pu.uebung.muskelgruppe)
            
            html_template += f'''
                <tr>
                    <td>{idx}</td>
                    <td><strong>{pu.uebung.bezeichnung}</strong></td>
                    <td><span class="badge badge-primary">{muskelgruppe}</span></td>
                    <td>{pu.saetze_ziel or "-"}</td>
                    <td>{pu.wiederholungen_ziel or "-"}</td>
                </tr>
            '''
        
        html_template += '''
            </tbody>
        </table>
        '''
    
    # Footer
    html_template += f'''
        <div class="footer">
            HomeGym Trainingsplan | Erstellt: {timezone.now().strftime("%d.%m.%Y %H:%M")} | {plan_url}
        </div>
    </body>
    </html>
    '''
    
    # PDF generieren
    try:
        result = BytesIO()
        pdf = pisa.pisaDocument(BytesIO(html_template.encode('utf-8')), result)
        
        if pdf.err:
            logger.error(f'PDF generation errors: {pdf.err}')
            messages.error(request, 'Fehler bei PDF-Generierung')
            return redirect('plan_details', plan_id=plan_id)
        
        # Response mit PDF
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        filename = f"plan_{plan.name.replace(' ', '_')}_{timezone.now().strftime('%Y%m%d')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
        
    except Exception as e:
        logger.error(f'Plan PDF export failed: {str(e)}', exc_info=True)
        messages.error(request, 'PDF-Generierung fehlgeschlagen. Bitte später erneut versuchen.')
        return redirect('plan_details', plan_id=plan_id)


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
    
    # Zusätzlich Sätze zählen für konsistentere Anzeige mit PDF
    push_saetze = letzte_30_tage_saetze.filter(uebung__muskelgruppe__in=push_gruppen).count()
    pull_saetze = letzte_30_tage_saetze.filter(uebung__muskelgruppe__in=pull_gruppen).count()
    
    if push_effektiv > 0 and pull_effektiv > 0:
        ratio = push_effektiv / pull_effektiv if pull_effektiv > 0 else 999
        saetze_ratio = push_saetze / pull_saetze if pull_saetze > 0 else 999
        
        if ratio > 1.5:  # Zu viel Push
            empfehlungen.append({
                'typ': 'balance',
                'prioritaet': 'mittel',
                'titel': 'Push/Pull Unbalance',
                'beschreibung': f'Dein Push-Training ({push_saetze} Sätze, {int(push_effektiv)} eff. Wdh) ist {ratio:.1f}x intensiver als dein Pull-Training ({pull_saetze} Sätze, {int(pull_effektiv)} eff. Wdh). Dies kann zu Haltungsschäden führen.',
                'empfehlung': 'Mehr Zugübungen (Rücken, Bizeps) trainieren',
                'uebungen': [{'id': u.id, 'name': u.bezeichnung} for u in Uebung.objects.filter(muskelgruppe__in=pull_gruppen)[:3]]
            })
        elif ratio < 0.67:  # Zu viel Pull
            empfehlungen.append({
                'typ': 'balance',
                'prioritaet': 'mittel',
                'titel': 'Push/Pull Unbalance',
                'beschreibung': f'Dein Pull-Training ({pull_saetze} Sätze, {int(pull_effektiv)} eff. Wdh) ist intensiver als dein Push-Training ({push_saetze} Sätze, {int(push_effektiv)} eff. Wdh).',
                'empfehlung': 'Mehr Druckübungen (Brust, Schultern, Trizeps) einbauen',
                'uebungen': [{'id': u.id, 'name': u.bezeichnung} for u in Uebung.objects.filter(muskelgruppe__in=push_gruppen)[:3]]
            })
    
    # === 3. STAGNIERENDE ÜBUNGEN ===
    # Analysiere das MAX-Gewicht pro TRAINING (nicht pro Satz!)
    # Mindestens 4 verschiedene Trainings mit der Übung nötig
    
    from django.db.models import Max
    from collections import defaultdict
    
    # Gruppiere Sätze nach Übung und Trainingsdatum, nimm Max-Gewicht pro Training
    uebung_trainings = defaultdict(list)
    
    for satz in letzte_60_tage_saetze.select_related('uebung', 'einheit'):
        if satz.gewicht and satz.gewicht > 0:
            key = satz.uebung_id
            datum = satz.einheit.datum
            uebung_trainings[key].append({'datum': datum, 'gewicht': float(satz.gewicht)})
    
    for uebung_id, saetze_list in uebung_trainings.items():
        # Gruppiere nach Datum und nimm Max pro Training
        trainings_max = defaultdict(float)
        for s in saetze_list:
            datum_key = s['datum']
            trainings_max[datum_key] = max(trainings_max[datum_key], s['gewicht'])
        
        # Sortiere nach Datum (älteste zuerst)
        sortierte_trainings = sorted(trainings_max.items(), key=lambda x: x[0])
        max_gewichte = [g for d, g in sortierte_trainings]
        
        # Mindestens 4 verschiedene Trainings für sinnvolle Stagnations-Analyse
        if len(max_gewichte) >= 4:
            uebung = Uebung.objects.get(id=uebung_id)
            
            # Vergleiche älteste 2 Trainings vs. neueste 2 Trainings
            erste_trainings = max_gewichte[:2]
            letzte_trainings = max_gewichte[-2:]
            
            avg_erste = sum(erste_trainings) / len(erste_trainings)
            avg_letzte = sum(letzte_trainings) / len(letzte_trainings)
            
            # Stagnation nur wenn:
            # 1. Kein Fortschritt (weniger als 2.5% Steigerung)
            # 2. Alle Max-Gewichte sind identisch
            fortschritt_prozent = ((avg_letzte - avg_erste) / avg_erste * 100) if avg_erste > 0 else 0
            alle_gleich = len(set(max_gewichte)) == 1  # Alle Werte identisch
            
            if fortschritt_prozent < 2.5 and alle_gleich:
                empfehlungen.append({
                    'typ': 'stagnation',
                    'prioritaet': 'niedrig',
                    'titel': f'{uebung.bezeichnung}: Stagnation',
                    'beschreibung': f'Bei dieser Übung gab es in den letzten {len(max_gewichte)} Trainings keinen Fortschritt (konstant {max_gewichte[-1]} kg).',
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
def metriken_help(request):
    """
    Hilfsseite mit Erklärungen zu allen Metriken und Kennzahlen
    """
    return render(request, 'core/metriken_help.html')


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
        logger.error(f'Generate Plan API Error: {e}', exc_info=True)
        return JsonResponse({
            'error': 'Plan konnte nicht generiert werden. Bitte später erneut versuchen.'
        }, status=500)


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
        chat_history = data.get('chat_history', [])  # Chat-Historie für Konversationsgedächtnis
        
        if not session_id or not question:
            return JsonResponse({'error': 'session_id und question erforderlich'}, status=400)
        
        # Prüfe ob Session dem User gehört
        session = get_object_or_404(Trainingseinheit, id=session_id, user=request.user)
        
        # Live Guidance importieren (korrekter Package-Import)
        from ai_coach.live_guidance import LiveGuidance
        from django.conf import settings
        
        # Auf dem Server (DEBUG=False) immer OpenRouter verwenden (keine lokale GPU)
        use_openrouter = not settings.DEBUG or os.getenv('USE_OPENROUTER', 'False').lower() == 'true'
        
        guidance = LiveGuidance(use_openrouter=use_openrouter)
        result = guidance.get_guidance(
            trainingseinheit_id=session_id,
            user_question=question,
            current_uebung_id=exercise_id,
            current_satz_number=set_number,
            chat_history=chat_history  # Chat-Historie für Konversationsgedächtnis
        )
        
        return JsonResponse({
            'answer': result['answer'],
            'cost': result['cost'],
            'model': result['model']
        })
    
    except Trainingseinheit.DoesNotExist:
        return JsonResponse({'error': 'Trainingseinheit nicht gefunden'}, status=404)
    except Exception as e:
        logger.error(f'Live Feedback API Error: {e}', exc_info=True)
        return JsonResponse({'error': 'Feedback konnte nicht gespeichert werden. Bitte später erneut versuchen.'}, status=500)


@login_required
def generate_plan_api(request):
    """
    API Endpoint für KI-Plan-Generierung über Web-Interface
    POST: { plan_type, sets_per_session, analysis_days? }
    oder: { saveCachedPlan: true, plan_data: {...} }
    Returns: { success, plan_ids, cost, message }
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        
        # Check ob wir einen gecachten Plan speichern sollen
        if data.get('saveCachedPlan') and data.get('plan_data'):
            # Direkt den gecachten Plan speichern ohne neu zu generieren
            from ai_coach.plan_generator import PlanGenerator
            
            generator = PlanGenerator(
                user_id=request.user.id,
                plan_type='3er-split',  # Dummy, wird nicht genutzt
            )
            
            plan_data = data['plan_data']
            
            # Plan in DB speichern
            plan_ids = generator._save_plan_to_db(plan_data)
            
            return JsonResponse({
                'success': True,
                'plan_ids': plan_ids,
                'plan_name': plan_data.get('plan_name', ''),
                'sessions': len(plan_data.get('sessions', [])),
                'message': f"Plan '{plan_data.get('plan_name', '')}' erfolgreich gespeichert!"
            })
        
        plan_type = data.get('plan_type', '3er-split')
        sets_per_session = int(data.get('sets_per_session', 18))
        analysis_days = int(data.get('analysis_days', 30))
        periodization = data.get('periodization', 'linear')
        target_profile = data.get('target_profile', 'hypertrophie')
        preview_only = data.get('previewOnly', False)
        
        # Validierung
        valid_plan_types = ['2er-split', '3er-split', '4er-split', 'ganzkörper', 'push-pull-legs']
        if plan_type not in valid_plan_types:
            return JsonResponse({'error': f'Ungültiger Plan-Typ. Erlaubt: {", ".join(valid_plan_types)}'}, status=400)
        
        if sets_per_session < 10 or sets_per_session > 30:
            return JsonResponse({'error': 'Sätze pro Session muss zwischen 10-30 liegen'}, status=400)
        
        valid_periodizations = ['linear', 'wellenfoermig', 'block']
        if periodization not in valid_periodizations:
            periodization = 'linear'
        
        valid_profiles = ['kraft', 'hypertrophie', 'definition']
        if target_profile not in valid_profiles:
            target_profile = 'hypertrophie'
        
        # Plan Generator importieren (korrekter Package-Import)
        from ai_coach.plan_generator import PlanGenerator
        from django.conf import settings
        
        # Auf dem Server (DEBUG=False) immer OpenRouter verwenden (keine lokale GPU)
        use_openrouter = not settings.DEBUG or os.getenv('USE_OPENROUTER', 'False').lower() == 'true'
        
        generator = PlanGenerator(
            user_id=request.user.id,
            plan_type=plan_type,
            analysis_days=analysis_days,
            sets_per_session=sets_per_session,
            periodization=periodization,
            target_profile=target_profile,
            use_openrouter=use_openrouter,
            fallback_to_openrouter=True
        )
        
        if preview_only:
            # Generiere Plan ohne zu speichern für Vorschau
            result = generator.generate(save_to_db=False)
            return JsonResponse({
                'success': True,
                'preview': True,
                'plan_data': result.get('plan_data', {}),
                'cost': 0.003 if use_openrouter else 0.0,
                'model': 'OpenRouter 70B' if use_openrouter else 'Ollama 8B'
            })
        else:
            # Generiere und speichere Plan
            result = generator.generate(save_to_db=True)
            
            return JsonResponse({
                'success': True,
                'plan_ids': result.get('plan_ids', []),
                'plan_name': result.get('plan_data', {}).get('plan_name', ''),
                'sessions': len(result.get('plan_data', {}).get('sessions', [])),
                'cost': 0.003 if use_openrouter else 0.0,
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
        logger.error(f'Analyze Plan API Error: {e}', exc_info=True)
        return JsonResponse({
            'error': 'Plan-Analyse fehlgeschlagen. Bitte später erneut versuchen.',
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
        logger.error(f'Optimize Plan API Error: {e}', exc_info=True)
        return JsonResponse({
            'error': 'Plan-Optimierung fehlgeschlagen. Bitte später erneut versuchen.',
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
        logger.error(f'Apply Optimizations API Error: {e}', exc_info=True)
        return JsonResponse({
            'error': 'Optimierungen konnten nicht angewendet werden. Bitte später erneut versuchen.',
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
        logger.error(f'Import failed: {str(e)}', exc_info=True)
        messages.error(request, 'Import fehlgeschlagen. Bitte überprüfe das JSON-Format.')
    
    return redirect('uebungen_auswahl')


# ============================================
# PLAN TEMPLATES
# ============================================

@login_required
def get_plan_templates(request):
    """API Endpoint: Liefert alle verfügbaren Plan-Templates."""
    try:
        templates_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'plan_templates.json')
        with open(templates_path, 'r', encoding='utf-8') as f:
            templates = json.load(f)
        
        # Nur Metadaten ohne Exercises zurückgeben
        templates_overview = {}
        for key, template in templates.items():
            templates_overview[key] = {
                'name': template['name'],
                'description': template['description'],
                'frequency_per_week': template['frequency_per_week'],
                'difficulty': template['difficulty'],
                'goal': template['goal'],
                'days_count': len(template['days'])
            }
        
        return JsonResponse(templates_overview)
    except Exception as e:
        logger.error(f'Get Plan Templates Error: {e}', exc_info=True)
        return JsonResponse({'error': 'Templates konnten nicht geladen werden. Bitte später erneut versuchen.'}, status=500)


@login_required
@login_required
def get_template_detail(request, template_key):
    """API Endpoint: Liefert alle Details eines Templates inkl. Übungen."""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        templates_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'plan_templates.json')
        with open(templates_path, 'r', encoding='utf-8') as f:
            templates = json.load(f)
        
        if template_key not in templates:
            return JsonResponse({'error': 'Template nicht gefunden'}, status=404)
        
        template = templates[template_key]
        
        # Mapping von Template-Equipment-Namen zu DB Display-Namen
        # Template verwendet vereinfachte Namen, DB hat exakte Display-Namen
        equipment_name_mapping = {
            'kurzhantel': 'kurzhanteln',
            'langhantel': 'langhantel',
            'kabel': 'kabelzug / latzug',
            'barren': 'dipstation / barren',
            'klimmzugstange': 'klimmzugstange',
            'maschine': None,  # Generisch - wird separat behandelt
            'körpergewicht': 'nur körpergewicht',
        }
        
        # User-Equipment ermitteln (Equipment hat ManyToMany 'users', kein 'verfuegbar' Feld)
        # Equipment für User abrufen
        user_equipment = Equipment.objects.filter(users=request.user)
        # Verwende get_name_display() für Display-Namen (z.B. "Klimmzugstange")
        user_equipment_set = set(eq.get_name_display().strip().lower() for eq in user_equipment)
        
        logger.info(f'User equipment: {user_equipment_set}')
        
        def check_equipment_available(template_equip_name):
            """Prüft ob Equipment verfügbar ist (mit Mapping)."""
            template_equip_lower = template_equip_name.strip().lower()
            
            # Körpergewicht ist immer verfügbar
            if template_equip_lower == 'körpergewicht':
                return True
            
            # Mapping anwenden
            mapped_name = equipment_name_mapping.get(template_equip_lower)
            
            if mapped_name:
                # Direktes Mapping gefunden
                return mapped_name in user_equipment_set
            
            # Maschine-Equipment: Prüfe ob passende Maschine vorhanden
            if template_equip_lower == 'maschine':
                # Prüfe ob User irgendeine Maschine hat (Beinpresse, Leg Curl, etc.)
                maschine_keywords = ['beinpresse', 'leg curl', 'leg extension', 'maschine', 'smith']
                return any(kw in eq for eq in user_equipment_set for kw in maschine_keywords)
            
            # Fallback: Direkter Vergleich
            return template_equip_lower in user_equipment_set
        
        # Template anpassen: Prüfe ob Übungen machbar sind
        adapted_template = {
            'name': template.get('name', ''),
            'description': template.get('description', ''),
            'frequency_per_week': template.get('frequency_per_week', 0),
            'difficulty': template.get('difficulty', ''),
            'goal': template.get('goal', ''),
            'days_adapted': []
        }
        
        for day in template.get('days', []):
            adapted_day = {
                'name': day.get('name', ''),
                'exercises': []
            }
            
            for exercise in day.get('exercises', []):
                exercise_copy = {
                    'name': exercise.get('name', ''),
                    'sets': exercise.get('sets', 0),
                    'reps': exercise.get('reps', ''),
                    'equipment': exercise.get('equipment', '')
                }
                required_equipment = exercise.get('equipment', '').strip()
                
                # Prüfe ob Equipment verfügbar (mit Mapping)
                if check_equipment_available(required_equipment):
                    exercise_copy['available'] = True
                    exercise_copy['substitute'] = None
                else:
                    exercise_copy['available'] = False
                    # Finde Ersatzübung
                    substitute = find_substitute_exercise(exercise.get('name', ''), required_equipment.lower(), user_equipment_set)
                    exercise_copy['substitute'] = substitute
                
                adapted_day['exercises'].append(exercise_copy)
            
            adapted_template['days_adapted'].append(adapted_day)
        
        return JsonResponse(adapted_template)
    except Exception as e:
        logger.error(f'Template detail error: {e}', exc_info=True)
        return JsonResponse({'error': 'Trainingsplan-Vorlage konnte nicht geladen werden.', 'template_key': template_key}, status=500)


def find_substitute_exercise(original_name, required_equipment, available_equipment):
    """
    Findet eine Ersatzübung aus der Datenbank.
    Versucht ähnliche Muskelgruppe und Bewegungstyp mit verfügbarem Equipment.
    Priorität: 1. Band-Alternativen, 2. Gleiches Bewegungsmuster, 3. Gleiche Muskelgruppe, 4. Körpergewicht
    """
    from core.models import Uebung, Equipment
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f'Finding substitute for: {original_name}, required: {required_equipment}, available: {available_equipment}')
    
    # Erstelle Reverse-Mapping: Display-Name (lowercase) -> Equipment-Objekt
    all_equipment = Equipment.objects.all()
    equipment_map = {}
    for eq in all_equipment:
        display_name = eq.get_name_display().strip().lower()
        equipment_map[display_name] = eq
    
    # Sammle verfügbare Equipment-Objekte
    available_equipment_objects = []
    for equip_name in available_equipment:
        equip_obj = equipment_map.get(equip_name)
        if equip_obj:
            available_equipment_objects.append(equip_obj)
    
    logger.info(f'Available equipment objects: {[eq.name for eq in available_equipment_objects]}')
    
    # Versuche Original-Übung in DB zu finden
    try:
        # Erst exakter Match
        original_uebung = Uebung.objects.filter(bezeichnung=original_name).first()
        
        # Fallback: Teilmatch
        if not original_uebung:
            clean_name = original_name.split('(')[0].strip()
            original_uebung = Uebung.objects.filter(bezeichnung__icontains=clean_name).first()
        
        if not original_uebung:
            # Kein Original gefunden - versuche allgemeine Suche nach Muskelgruppe
            exercise_to_muscle = {
                'klimmzüge': 'RUECKEN_LAT',
                'klimmzug': 'RUECKEN_LAT',
                'lat pulldown': 'RUECKEN_LAT',
                'latzug': 'RUECKEN_LAT',
                'rudern': 'RUECKEN_LAT',
                'dips': 'TRIZEPS',
                'dip': 'TRIZEPS',
                'liegestütz': 'BRUST',
                'push-up': 'BRUST',
                'bankdrücken': 'BRUST',
                'fliegende': 'BRUST',
                'crossover': 'BRUST',
                'schulterdrücken': 'SCHULTER_VORN',
                'shoulder press': 'SCHULTER_VORN',
                'seitheben': 'SCHULTER_SEIT',
                'lateral raise': 'SCHULTER_SEIT',
                'facepull': 'SCHULTER_HINT',
                'face pull': 'SCHULTER_HINT',
                'bizeps': 'BIZEPS',
                'curl': 'BIZEPS',
                'trizeps': 'TRIZEPS',
                'pushdown': 'TRIZEPS',
                'squat': 'BEINE_QUAD',
                'kniebeuge': 'BEINE_QUAD',
                'beinpresse': 'BEINE_QUAD',
                'beinstrecker': 'BEINE_QUAD',
                'beinbeuger': 'BEINE_HAM',
                'leg curl': 'BEINE_HAM',
                'kreuzheben': 'BEINE_HAM',
                'wadenheben': 'WADEN',
                'calf': 'WADEN',
            }
            
            for key, muscle in exercise_to_muscle.items():
                if key in original_name.lower():
                    # Erstelle Pseudo-Objekt
                    original_uebung = type('obj', (object,), {
                        'muskelgruppe': muscle,
                        'bewegungstyp': 'ISOLATION',
                        'id': -1
                    })()
                    break
        
        if original_uebung:
            muscle_group = getattr(original_uebung, 'muskelgruppe', None)
            movement_type = getattr(original_uebung, 'bewegungstyp', None)
            original_id = getattr(original_uebung, 'id', -1)
            
            logger.info(f'Found original: muscle={muscle_group}, movement={movement_type}')
            
            if muscle_group and len(available_equipment_objects) > 0:
                # 1. Priorität: Band-Alternative (Widerstandsbänder)
                band_eq = equipment_map.get('widerstandsbänder')
                if band_eq and band_eq in available_equipment_objects:
                    band_exercise = Uebung.objects.filter(
                        muskelgruppe=muscle_group,
                        equipment=band_eq
                    ).exclude(id=original_id if original_id > 0 else 0).first()
                    
                    if band_exercise:
                        logger.info(f'Found band alternative: {band_exercise.bezeichnung}')
                        return {
                            'name': band_exercise.bezeichnung,
                            'equipment': 'Widerstandsbänder',
                            'note': 'Band-Alternative'
                        }
                
                # 2. Gleiches Bewegungsmuster + verfügbares Equipment
                if movement_type:
                    for equip_obj in available_equipment_objects:
                        similar = Uebung.objects.filter(
                            muskelgruppe=muscle_group,
                            bewegungstyp=movement_type,
                            equipment=equip_obj
                        ).exclude(id=original_id if original_id > 0 else 0).first()
                        
                        if similar:
                            logger.info(f'Found same movement: {similar.bezeichnung}')
                            return {
                                'name': similar.bezeichnung,
                                'equipment': equip_obj.get_name_display()
                            }
                
                # 3. Nur gleiche Muskelgruppe + verfügbares Equipment
                for equip_obj in available_equipment_objects:
                    similar = Uebung.objects.filter(
                        muskelgruppe=muscle_group,
                        equipment=equip_obj
                    ).exclude(id=original_id if original_id > 0 else 0).first()
                    
                    if similar:
                        logger.info(f'Found same muscle: {similar.bezeichnung}')
                        return {
                            'name': similar.bezeichnung,
                            'equipment': equip_obj.get_name_display()
                        }
            
            # 4. Letzter Fallback: Körpergewicht-Übung
            if muscle_group:
                koerper_eq = Equipment.objects.filter(name='KOERPER').first()
                if koerper_eq:
                    bodyweight_exercise = Uebung.objects.filter(
                        muskelgruppe=muscle_group,
                        equipment=koerper_eq
                    ).exclude(id=original_id if original_id > 0 else 0).first()
                    
                    if bodyweight_exercise:
                        logger.info(f'Found bodyweight: {bodyweight_exercise.bezeichnung}')
                        return {
                            'name': bodyweight_exercise.bezeichnung,
                            'equipment': 'Nur Körpergewicht',
                            'note': 'Körpergewicht-Alternative'
                        }
        
        # Kein Match gefunden
        logger.warning(f'No substitute found for {original_name}')
        return {
            'name': f'Bitte Equipment "{required_equipment}" ergänzen',
            'equipment': required_equipment,
            'note': 'Keine passende Alternative gefunden'
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            'name': f'Alternative für "{original_name}" nicht gefunden',
            'equipment': required_equipment,
            'note': f'Fehler: {str(e)}'
        }


@login_required
def create_plan_from_template(request, template_key):
    """Erstellt einen neuen Plan basierend auf einem Template."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Nur POST erlaubt'}, status=405)
    
    try:
        # Template laden
        templates_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'plan_templates.json')
        with open(templates_path, 'r', encoding='utf-8') as f:
            templates = json.load(f)
        
        if template_key not in templates:
            return JsonResponse({'error': 'Template nicht gefunden'}, status=404)
        
        template = templates[template_key]
        
        # User-Equipment mit Display-Namen
        user_equipment = Equipment.objects.filter(users=request.user)
        user_equipment_set = set(eq.get_name_display().strip().lower() for eq in user_equipment)
        
        # Mapping von Template-Equipment-Namen zu DB Display-Namen
        equipment_name_mapping = {
            'kurzhantel': 'kurzhanteln',
            'langhantel': 'langhantel',
            'kabel': 'kabelzug / latzug',
            'barren': 'dipstation / barren',
            'klimmzugstange': 'klimmzugstange',
            'maschine': None,  # Generisch
            'körpergewicht': 'nur körpergewicht',
        }
        
        def check_equipment_available(template_equip_name):
            """Prüft ob Equipment verfügbar ist (mit Mapping)."""
            template_equip_lower = template_equip_name.strip().lower()
            if template_equip_lower == 'körpergewicht':
                return True
            mapped_name = equipment_name_mapping.get(template_equip_lower)
            if mapped_name:
                return mapped_name in user_equipment_set
            if template_equip_lower == 'maschine':
                maschine_keywords = ['beinpresse', 'leg curl', 'leg extension', 'maschine', 'smith']
                return any(kw in eq for eq in user_equipment_set for kw in maschine_keywords)
            return template_equip_lower in user_equipment_set
        
        # Für jeden Tag einen eigenen Plan erstellen
        created_plans = []
        
        for day in template['days']:
            # Plan für diesen Tag erstellen
            plan = Plan.objects.create(
                user=request.user,
                name=day['name'],
                beschreibung=f"{template['name']}"
            )
            created_plans.append(plan)
            
            # Übungen zum Plan hinzufügen
            reihenfolge = 1
            for exercise_data in day['exercises']:
                # Übung in DB suchen - exakter Match zuerst
                exercise_name = exercise_data['name']
                uebung = Uebung.objects.filter(bezeichnung=exercise_name).first()
                
                # Fallback: Teilmatch
                if not uebung:
                    exercise_name_clean = exercise_name.split('(')[0].strip()
                    uebung = Uebung.objects.filter(bezeichnung__icontains=exercise_name_clean).first()
                
                # Wenn nicht gefunden und Equipment fehlt, versuche Substitut
                if not uebung:
                    required_equipment = exercise_data['equipment'].strip().lower()
                    if not check_equipment_available(exercise_data['equipment']):
                        substitute = find_substitute_exercise(exercise_name, required_equipment, user_equipment_set)
                        if substitute and 'name' in substitute:
                            uebung = Uebung.objects.filter(bezeichnung__icontains=substitute['name'].split('(')[0].strip()).first()
                
                # Wenn Übung gefunden, zum Plan hinzufügen
                if uebung:
                    PlanUebung.objects.create(
                        plan=plan,
                        uebung=uebung,
                        trainingstag=day['name'],
                        reihenfolge=reihenfolge,
                        saetze_ziel=exercise_data['sets'],
                        wiederholungen_ziel=exercise_data['reps']
                    )
                    reihenfolge += 1
        
        plan_count = len(created_plans)
        plan_names = ', '.join([p.name for p in created_plans])
        messages.success(request, f'{plan_count} Pläne erstellt: {plan_names}')
        return JsonResponse({
            'success': True, 
            'plan_ids': [p.id for p in created_plans],
            'plan_count': plan_count
        })
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Plan creation error: {e}', exc_info=True)
        return JsonResponse({'error': 'Trainingsplan konnte nicht erstellt werden.'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def sync_offline_data(request):
    """Synced offline gespeicherte Sätze zum Server."""
    try:
        data = json.loads(request.body)
        results = []
        
        for item in data:
            try:
                # Validiere Training-Zugriff
                training = Trainingseinheit.objects.get(
                    id=item['training_id'],
                    user=request.user
                )
                
                # Hole Übung
                uebung = Uebung.objects.get(id=item['uebung_id'])
                
                # Prüfe ob es ein Update ist (URL enthält /update/)
                is_update = item.get('is_update', False)
                action_url = item.get('action', '')
                
                if is_update or '/update/' in action_url:
                    # Update: Versuche Satz zu finden und aktualisieren
                    # Extrahiere Satz-ID aus URL (z.B. /set/123/update/)
                    import re
                    # Safe regex with bounded quantifier
                    match = re.search(r'/set/(\d{1,10})/update/', action_url)
                    
                    if match:
                        satz_id = int(match.group(1))
                        try:
                            satz = Satz.objects.get(id=satz_id, einheit__user=request.user)
                            
                            # Update existierenden Satz
                            satz.gewicht = Decimal(str(item['gewicht']))
                            satz.wiederholungen = int(item['wiederholungen'])
                            satz.rpe = int(item['rpe']) if item.get('rpe') else None
                            satz.ist_aufwaermsatz = item.get('is_warmup', False)
                            satz.superset_gruppe = int(item.get('superset_gruppe', 0))
                            satz.notiz = item.get('notiz', '') or None
                            satz.save()
                            
                            results.append({
                                'id': item['id'],
                                'success': True,
                                'satz_id': satz.id,
                                'updated': True
                            })
                            continue
                            
                        except Satz.DoesNotExist:
                            # Satz existiert nicht mehr, erstelle neuen
                            pass
                
                # Erstelle neuen Satz (entweder Add oder Update fehlgeschlagen)
                max_satz = training.saetze.filter(uebung=uebung).aggregate(Max('satz_nr'))['satz_nr__max']
                neue_nr = (max_satz or 0) + 1
                
                neuer_satz = Satz.objects.create(
                    einheit=training,
                    uebung=uebung,
                    satz_nr=neue_nr,
                    gewicht=Decimal(str(item['gewicht'])),
                    wiederholungen=int(item['wiederholungen']),
                    rpe=int(item['rpe']) if item.get('rpe') else None,
                    ist_aufwaermsatz=item.get('is_warmup', False),
                    superset_gruppe=int(item.get('superset_gruppe', 0)),
                    notiz=item.get('notiz', '') or None
                )
                
                results.append({
                    'id': item['id'],
                    'success': True,
                    'satz_id': neuer_satz.id,
                    'updated': False
                })
                
            except Trainingseinheit.DoesNotExist:
                results.append({
                    'id': item['id'],
                    'success': False,
                    'error': 'Training nicht gefunden oder keine Berechtigung'
                })
            except Uebung.DoesNotExist:
                results.append({
                    'id': item['id'],
                    'success': False,
                    'error': 'Übung nicht gefunden'
                })
            except Exception as e:
                results.append({
                    'id': item['id'],
                    'success': False,
                    'error': 'Fehler beim Verarbeiten dieses Eintrags'
                })
        
        return JsonResponse({
            'success': True,
            'results': results,
            'synced_count': sum(1 for r in results if r['success'])
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Ungültiges JSON'}, status=400)
    except Exception as e:
        logger.error(f'Offline data sync error: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': 'Offline-Daten konnten nicht synchronisiert werden.'}, status=500)


@cache_control(max_age=0, no_cache=True, no_store=True, must_revalidate=True)
def service_worker(request):
    """Serve the service worker from root path."""
    sw_path = os.path.join(settings.BASE_DIR, 'core', 'static', 'core', 'service-worker.js')
    
    try:
        with open(sw_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return HttpResponse(content, content_type='application/javascript')
    except FileNotFoundError:
        return HttpResponse('Service Worker not found', status=404)


def favicon(request):
    """Serve favicon.ico from static files."""
    from django.http import FileResponse
    favicon_path = os.path.join(settings.BASE_DIR, 'core', 'static', 'core', 'images', 'icon-192x192.png')
    
    try:
        return FileResponse(open(favicon_path, 'rb'), content_type='image/png')
    except FileNotFoundError:
        return HttpResponse(status=204)  # No Content


@login_required
def exercise_detail(request, uebung_id):
    """
    Kombinierte Übungs-Detailansicht:
    - Beschreibung & Info
    - Muskelgruppen-Visualisierung
    - User-spezifische Statistiken
    """
    uebung = get_object_or_404(Uebung.objects.prefetch_related('equipment'), id=uebung_id)
    
    # User-spezifische Sätze
    saetze = Satz.objects.filter(
        einheit__user=request.user,
        uebung=uebung,
        ist_aufwaermsatz=False
    ).select_related('einheit').order_by('einheit__datum')
    
    has_data = saetze.exists()
    
    context = {
        'uebung': uebung,
        'has_data': has_data,
    }
    
    if has_data:
        # === STATISTIKEN BERECHNEN ===
        
        # 1. 1RM Progression
        history_data = {}
        personal_record = 0
        best_weight = 0
        total_volume = 0
        total_sets = saetze.count()
        
        for satz in saetze:
            # Gewicht normalisieren
            effektives_gewicht = float(satz.gewicht) if satz.gewicht else 0
            if uebung.gewichts_typ == 'PRO_SEITE':
                effektives_gewicht *= 2
            
            # 1RM berechnen
            if uebung.gewichts_typ == 'ZEIT':
                one_rep_max = float(satz.wiederholungen)
            else:
                if effektives_gewicht > 0:
                    one_rep_max = effektives_gewicht * (1 + (satz.wiederholungen / 30))
                else:
                    one_rep_max = 0
            
            # Bestwert des Tages
            datum_str = satz.einheit.datum.strftime('%d.%m.%Y')
            if datum_str not in history_data or one_rep_max > history_data[datum_str]:
                history_data[datum_str] = round(one_rep_max, 1)
            
            # Rekorde
            if one_rep_max > personal_record:
                personal_record = round(one_rep_max, 1)
            if effektives_gewicht > best_weight:
                best_weight = effektives_gewicht
            
            # Volumen
            if satz.gewicht and satz.wiederholungen:
                total_volume += float(satz.gewicht) * satz.wiederholungen
        
        # Chart-Daten
        labels = list(history_data.keys())
        data = list(history_data.values())
        
        # 2. RPE-Analyse
        avg_rpe = saetze.aggregate(Avg('rpe'))['rpe__avg']
        avg_rpe_display = round(avg_rpe, 1) if avg_rpe else None
        
        # RPE-Trend
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
                    rpe_trend = 'improving'
                elif diff > 0.3:
                    rpe_trend = 'declining'
                else:
                    rpe_trend = 'stable'
        
        # 3. Letztes Training
        letztes_training = saetze.last().einheit if saetze.exists() else None
        
        context.update({
            'labels_json': json.dumps(labels),
            'data_json': json.dumps(data),
            'personal_record': personal_record,
            'best_weight': best_weight,
            'avg_rpe': avg_rpe_display,
            'rpe_trend': rpe_trend,
            'total_volume': round(total_volume, 0),
            'total_sets': total_sets,
            'letztes_training': letztes_training,
        })
    
    return render(request, 'core/exercise_detail.html', context)


@login_required
def get_alternative_exercises(request, uebung_id):
    """
    API Endpoint: Gibt alternative Übungen zurück basierend auf:
    - Gleicher Bewegungstyp (Compound/Isolation)
    - Gleiche Hauptmuskelgruppe
    - Verfügbares Equipment des Users
    
    Scoring-System:
    - Exakte Übereinstimmung (bewegungstyp + muskelgruppe): 100 Punkte
    - Nur bewegungstyp: 50 Punkte
    - Nur muskelgruppe: 40 Punkte
    - Hilfsmuskel stimmt überein: +10 Punkte
    """
    original = get_object_or_404(Uebung, id=uebung_id)
    
    # User's verfügbares Equipment
    user_equipment_ids = set(request.user.verfuegbares_equipment.values_list('id', flat=True))
    
    # Alle Übungen außer der aktuellen (global + eigene custom)
    all_exercises = Uebung.objects.filter(
        Q(is_custom=False) | Q(created_by=request.user)
    ).exclude(id=original.id).prefetch_related('equipment')
    
    alternatives = []
    
    for exercise in all_exercises:
        # Equipment-Filter: Übung muss mit verfügbarem Equipment machbar sein
        required_eq_ids = set(exercise.equipment.values_list('id', flat=True))
        
        # Skip wenn Equipment nicht verfügbar
        if required_eq_ids and not required_eq_ids.issubset(user_equipment_ids):
            continue
        
        # Scoring
        score = 0
        match_reasons = []
        
        # Exakte Übereinstimmung (bewegungstyp + muskelgruppe)
        if (exercise.bewegungstyp == original.bewegungstyp and 
            exercise.muskelgruppe == original.muskelgruppe):
            score += 100
            match_reasons.append('Gleicher Bewegungstyp & Muskelgruppe')
        else:
            # Teilweise Übereinstimmung
            if exercise.bewegungstyp == original.bewegungstyp:
                score += 50
                match_reasons.append('Gleicher Bewegungstyp')
            
            if exercise.muskelgruppe == original.muskelgruppe:
                score += 40
                match_reasons.append('Gleiche Hauptmuskelgruppe')
        
        # Bonus: Hilfsmuskel-Übereinstimmung
        if original.hilfsmuskeln and exercise.hilfsmuskeln:
            original_hilfs = set(original.hilfsmuskeln) if isinstance(original.hilfsmuskeln, list) else set()
            exercise_hilfs = set(exercise.hilfsmuskeln) if isinstance(exercise.hilfsmuskeln, list) else set()
            
            common_hilfs = original_hilfs & exercise_hilfs
            if common_hilfs:
                score += 10 * len(common_hilfs)
                match_reasons.append(f'{len(common_hilfs)} gemeinsame Hilfsmuskeln')
        
        # Nur Übungen mit mindestens 40 Punkten (irgendeine Übereinstimmung)
        if score >= 40:
            alternatives.append({
                'id': exercise.id,
                'bezeichnung': exercise.bezeichnung,
                'muskelgruppe': exercise.muskelgruppe,
                'muskelgruppe_label': dict(MUSKELGRUPPEN).get(exercise.muskelgruppe, exercise.muskelgruppe),
                'bewegungstyp': exercise.get_bewegungstyp_display(),
                'gewichts_typ': exercise.get_gewichts_typ_display(),
                'is_custom': exercise.is_custom,
                'score': score,
                'match_reasons': match_reasons,
            })
    
    # Sortiere nach Score (höchste zuerst)
    alternatives.sort(key=lambda x: x['score'], reverse=True)
    
    # Limitiere auf Top 10
    alternatives = alternatives[:10]
    
    return JsonResponse({
        'success': True,
        'original': {
            'id': original.id,
            'bezeichnung': original.bezeichnung,
            'muskelgruppe_label': dict(MUSKELGRUPPEN).get(original.muskelgruppe, original.muskelgruppe),
            'bewegungstyp': original.get_bewegungstyp_display(),
        },
        'alternatives': alternatives,
        'count': len(alternatives)
    })


@cache_control(max_age=0, no_cache=True, no_store=True, must_revalidate=True)
def manifest(request):
    """Serve the manifest from root path."""
    manifest_path = os.path.join(settings.BASE_DIR, 'core', 'static', 'core', 'manifest.json')
    
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return HttpResponse(content, content_type='application/json')
    except FileNotFoundError:
        return HttpResponse('Manifest not found', status=404)


# ============================================================
# PLAN GRUPPIERUNG API
# ============================================================

@login_required
@require_http_methods(["POST"])
def api_ungroup_plans(request):
    """Löst die Gruppierung von Plänen auf (entfernt gruppe_id)."""
    import json as json_module
    
    try:
        data = json_module.loads(request.body)
        gruppe_id = data.get('gruppe_id')
        
        if not gruppe_id:
            return JsonResponse({'success': False, 'error': 'Keine Gruppe angegeben'}, status=400)
        
        # Finde alle Pläne mit dieser gruppe_id und entferne die Gruppierung
        updated = Plan.objects.filter(
            user=request.user,
            gruppe_id=gruppe_id
        ).update(gruppe_id=None, gruppe_name='')
        
        return JsonResponse({
            'success': True,
            'message': f'{updated} Pläne wurden aus der Gruppe entfernt'
        })
        
    except Exception as e:
        logger.error(f'Ungroup plans error: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': 'Pläne konnten nicht aus der Gruppe entfernt werden.'}, status=500)


@login_required
@require_http_methods(["POST"])
def api_group_plans(request):
    """Gruppiert mehrere Pläne unter einer neuen Gruppe."""
    import json as json_module
    import uuid
    
    try:
        data = json_module.loads(request.body)
        plan_ids = data.get('plan_ids', [])
        gruppe_name = data.get('gruppe_name', 'Neue Gruppe')
        
        if len(plan_ids) < 2:
            return JsonResponse({'success': False, 'error': 'Mindestens 2 Pläne nötig'}, status=400)
        
        # Erstelle neue Gruppen-ID
        neue_gruppe_id = uuid.uuid4()
        
        # Aktualisiere alle angegebenen Pläne mit Reihenfolge
        plans = Plan.objects.filter(
            user=request.user,
            id__in=plan_ids
        ).order_by('name')  # Alphabetisch sortieren für initiale Reihenfolge
        
        for i, plan in enumerate(plans):
            plan.gruppe_id = neue_gruppe_id
            plan.gruppe_name = gruppe_name
            plan.gruppe_reihenfolge = i
            plan.save(update_fields=['gruppe_id', 'gruppe_name', 'gruppe_reihenfolge'])
        
        return JsonResponse({
            'success': True,
            'message': f'{plans.count()} Pläne wurden gruppiert',
            'gruppe_id': str(neue_gruppe_id)
        })
        
    except Exception as e:
        logger.error(f'Group plans error: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': 'Pläne konnten nicht gruppiert werden.'}, status=500)


@login_required
@require_http_methods(["POST"])
def api_delete_plan(request):
    """Löscht einen einzelnen Plan."""
    import json as json_module
    
    try:
        data = json_module.loads(request.body)
        plan_id = data.get('plan_id')
        
        if not plan_id:
            return JsonResponse({'success': False, 'error': 'Keine Plan-ID angegeben'}, status=400)
        
        # Plan finden und prüfen ob er dem User gehört
        plan = Plan.objects.filter(id=plan_id, user=request.user).first()
        
        if not plan:
            return JsonResponse({'success': False, 'error': 'Plan nicht gefunden oder keine Berechtigung'}, status=404)
        
        plan_name = plan.name
        plan.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Plan "{plan_name}" wurde gelöscht'
        })
        
    except Exception as e:
        logger.error(f'Delete plan error: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': 'Plan konnte nicht gelöscht werden.'}, status=500)


@login_required
@require_http_methods(["POST"])
def api_delete_group(request):
    """Löscht alle Pläne einer Gruppe."""
    import json as json_module
    
    try:
        data = json_module.loads(request.body)
        gruppe_id = data.get('gruppe_id')
        
        if not gruppe_id:
            return JsonResponse({'success': False, 'error': 'Keine Gruppe angegeben'}, status=400)
        
        # Alle Pläne dieser Gruppe finden (nur die des Users)
        plans_to_delete = Plan.objects.filter(
            user=request.user,
            gruppe_id=gruppe_id
        )
        
        count = plans_to_delete.count()
        
        if count == 0:
            return JsonResponse({'success': False, 'error': 'Keine Pläne in dieser Gruppe gefunden'}, status=404)
        
        plans_to_delete.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'{count} Pläne wurden gelöscht'
        })
        
    except Exception as e:
        logger.error(f'Delete group error: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': 'Gruppe konnte nicht gelöscht werden.'}, status=500)


@login_required
@require_http_methods(["POST"])
def api_rename_group(request):
    """Benennt eine Plan-Gruppe um."""
    import json as json_module
    
    try:
        data = json_module.loads(request.body)
        gruppe_id = data.get('gruppe_id')
        new_name = data.get('new_name', '').strip()
        
        if not gruppe_id:
            return JsonResponse({'success': False, 'error': 'Keine Gruppe angegeben'}, status=400)
        
        if not new_name:
            return JsonResponse({'success': False, 'error': 'Kein Name angegeben'}, status=400)
        
        # Alle Pläne dieser Gruppe umbenennen
        updated = Plan.objects.filter(
            user=request.user,
            gruppe_id=gruppe_id
        ).update(gruppe_name=new_name)
        
        if updated == 0:
            return JsonResponse({'success': False, 'error': 'Keine Pläne in dieser Gruppe gefunden'}, status=404)
        
        return JsonResponse({
            'success': True,
            'message': f'Gruppe wurde zu "{new_name}" umbenannt'
        })
        
    except Exception as e:
        logger.error(f'Rename group error: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': 'Gruppe konnte nicht umbenannt werden.'}, status=500)


@login_required
@require_http_methods(["POST"])
def api_reorder_group(request):
    """Ändert die Reihenfolge der Pläne innerhalb einer Gruppe."""
    import json as json_module
    
    try:
        data = json_module.loads(request.body)
        gruppe_id = data.get('gruppe_id')
        plan_id = data.get('plan_id')
        direction = data.get('direction')  # 'up' oder 'down'
        
        if not gruppe_id or not plan_id or not direction:
            return JsonResponse({'success': False, 'error': 'Fehlende Parameter'}, status=400)
        
        # Alle Pläne dieser Gruppe holen, sortiert nach Reihenfolge
        plans = list(Plan.objects.filter(
            user=request.user,
            gruppe_id=gruppe_id
        ).order_by('gruppe_reihenfolge', 'name'))
        
        if not plans:
            return JsonResponse({'success': False, 'error': 'Keine Pläne in dieser Gruppe'}, status=404)
        
        # Index des zu verschiebenden Plans finden
        current_index = None
        for i, p in enumerate(plans):
            if p.id == plan_id:
                current_index = i
                break
        
        if current_index is None:
            return JsonResponse({'success': False, 'error': 'Plan nicht gefunden'}, status=404)
        
        # Neuen Index berechnen
        if direction == 'up' and current_index > 0:
            new_index = current_index - 1
        elif direction == 'down' and current_index < len(plans) - 1:
            new_index = current_index + 1
        else:
            return JsonResponse({'success': True, 'message': 'Keine Änderung nötig'})
        
        # Pläne tauschen
        plans[current_index], plans[new_index] = plans[new_index], plans[current_index]
        
        # Neue Reihenfolge speichern
        for i, p in enumerate(plans):
            p.gruppe_reihenfolge = i
            p.save(update_fields=['gruppe_reihenfolge'])
        
        return JsonResponse({
            'success': True,
            'message': 'Reihenfolge wurde aktualisiert'
        })
        
    except Exception as e:
        logger.error(f'Reorder group error: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': 'Reihenfolge konnte nicht aktualisiert werden.'}, status=500)


# ========== TRAININGSPARTNER-SHARING API ==========

@login_required
@require_http_methods(["GET"])
def api_search_users(request):
    """Sucht User per Username für Trainingspartner-Einladung."""
    from django.contrib.auth.models import User
    
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'users': []})
    
    # Suche nach Username (nicht eigenen User)
    users = User.objects.filter(
        username__icontains=query
    ).exclude(
        id=request.user.id
    ).values('id', 'username')[:10]
    
    return JsonResponse({'users': list(users)})


@login_required
@require_http_methods(["POST"])
def api_share_plan_with_user(request):
    """Teilt einen Plan mit einem Trainingspartner."""
    import json as json_module
    
    try:
        data = json_module.loads(request.body)
        plan_id = data.get('plan_id')
        username = data.get('username', '').strip()
        
        if not plan_id or not username:
            return JsonResponse({'success': False, 'error': 'Plan-ID und Username erforderlich'}, status=400)
        
        # Plan muss dem User gehören
        plan = get_object_or_404(Plan, id=plan_id, user=request.user)
        
        # Ziel-User finden
        from django.contrib.auth.models import User
        try:
            target_user = User.objects.get(username=username)
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': f'User "{username}" nicht gefunden'}, status=404)
        
        if target_user == request.user:
            return JsonResponse({'success': False, 'error': 'Du kannst nicht mit dir selbst teilen'}, status=400)
        
        # Bereits geteilt?
        if plan.shared_with.filter(id=target_user.id).exists():
            return JsonResponse({'success': False, 'error': f'Bereits mit "{username}" geteilt'}, status=400)
        
        # Teilen
        plan.shared_with.add(target_user)
        
        return JsonResponse({
            'success': True,
            'message': f'Plan wurde mit "{username}" geteilt',
            'user': {'id': target_user.id, 'username': target_user.username}
        })
        
    except Exception as e:
        logger.error(f'Share plan with user error: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': 'Plan konnte nicht geteilt werden.'}, status=500)


@login_required
@require_http_methods(["POST"])
def api_unshare_plan_with_user(request):
    """Entfernt Trainingspartner-Freigabe."""
    import json as json_module
    
    try:
        data = json_module.loads(request.body)
        plan_id = data.get('plan_id')
        user_id = data.get('user_id')
        
        if not plan_id or not user_id:
            return JsonResponse({'success': False, 'error': 'Plan-ID und User-ID erforderlich'}, status=400)
        
        # Plan muss dem User gehören
        plan = get_object_or_404(Plan, id=plan_id, user=request.user)
        
        # Ziel-User finden
        from django.contrib.auth.models import User
        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'User nicht gefunden'}, status=404)
        
        # Freigabe entfernen
        plan.shared_with.remove(target_user)
        
        return JsonResponse({
            'success': True,
            'message': f'Freigabe für "{target_user.username}" wurde entfernt'
        })
        
    except Exception as e:
        logger.error(f'Unshare plan with user error: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': 'Freigabe konnte nicht entfernt werden.'}, status=500)


@login_required
@require_http_methods(["POST"])
def api_share_group_with_user(request):
    """Teilt eine komplette Plan-Gruppe mit einem Trainingspartner."""
    import json as json_module
    
    try:
        data = json_module.loads(request.body)
        gruppe_id = data.get('gruppe_id')
        username = data.get('username', '').strip()
        
        if not gruppe_id or not username:
            return JsonResponse({'success': False, 'error': 'Gruppe-ID und Username erforderlich'}, status=400)
        
        # Alle Pläne der Gruppe (müssen dem User gehören)
        plans = Plan.objects.filter(user=request.user, gruppe_id=gruppe_id)
        
        if not plans.exists():
            return JsonResponse({'success': False, 'error': 'Keine Pläne in dieser Gruppe'}, status=404)
        
        # Ziel-User finden
        from django.contrib.auth.models import User
        try:
            target_user = User.objects.get(username=username)
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': f'User "{username}" nicht gefunden'}, status=404)
        
        if target_user == request.user:
            return JsonResponse({'success': False, 'error': 'Du kannst nicht mit dir selbst teilen'}, status=400)
        
        # Alle Pläne der Gruppe teilen
        for plan in plans:
            plan.shared_with.add(target_user)
        
        return JsonResponse({
            'success': True,
            'message': f'Gruppe wurde mit "{username}" geteilt ({plans.count()} Pläne)',
            'user': {'id': target_user.id, 'username': target_user.username}
        })
        
    except Exception as e:
        logger.error(f'Share group with user error: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': 'Gruppe konnte nicht geteilt werden.'}, status=500)


@login_required
@require_http_methods(["POST"])
def api_unshare_group_with_user(request):
    """Entfernt Trainingspartner-Freigabe für eine komplette Gruppe."""
    import json as json_module
    
    try:
        data = json_module.loads(request.body)
        gruppe_id = data.get('gruppe_id')
        user_id = data.get('user_id')
        
        if not gruppe_id or not user_id:
            return JsonResponse({'success': False, 'error': 'Gruppe-ID und User-ID erforderlich'}, status=400)
        
        # Alle Pläne der Gruppe
        plans = Plan.objects.filter(user=request.user, gruppe_id=gruppe_id)
        
        if not plans.exists():
            return JsonResponse({'success': False, 'error': 'Keine Pläne in dieser Gruppe'}, status=404)
        
        # Ziel-User finden
        from django.contrib.auth.models import User
        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'User nicht gefunden'}, status=404)
        
        # Freigabe für alle Pläne entfernen
        for plan in plans:
            plan.shared_with.remove(target_user)
        
        return JsonResponse({
            'success': True,
            'message': f'Freigabe für "{target_user.username}" wurde entfernt'
        })
        
    except Exception as e:
        logger.error(f'Unshare group with user error: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': 'Freigabe konnte nicht entfernt werden.'}, status=500)


@login_required
def api_get_plan_shares(request, plan_id):
    """Gibt Liste der User zurück, mit denen ein Plan geteilt ist."""
    plan = get_object_or_404(Plan, id=plan_id, user=request.user)
    
    shared_users = list(plan.shared_with.values('id', 'username'))
    
    return JsonResponse({
        'success': True,
        'shared_with': shared_users
    })


@login_required
def api_get_group_shares(request, gruppe_id):
    """Gibt Liste der User zurück, mit denen eine Gruppe geteilt ist."""
    # Erster Plan der Gruppe
    plan = Plan.objects.filter(user=request.user, gruppe_id=gruppe_id).first()
    
    if not plan:
        return JsonResponse({'success': False, 'error': 'Gruppe nicht gefunden'}, status=404)
    
    shared_users = list(plan.shared_with.values('id', 'username'))
    
    return JsonResponse({
        'success': True,
        'shared_with': shared_users
    })


# =============================================================================
# CARDIO TRACKING (Lite Cardio - Ausdauertraining ohne Trainingsplan)
# =============================================================================

from .models import CardioEinheit, CARDIO_AKTIVITAETEN, CARDIO_INTENSITAET


@login_required
def cardio_list(request):
    """Zeigt alle Cardio-Einheiten des Users (letzte 30 Tage)."""
    from datetime import timedelta
    
    # Filter: letzte 30 Tage oder alle
    show_all = request.GET.get('all', False)
    
    if show_all:
        cardio_einheiten = CardioEinheit.objects.filter(user=request.user)
    else:
        thirty_days_ago = timezone.now().date() - timedelta(days=30)
        cardio_einheiten = CardioEinheit.objects.filter(
            user=request.user, 
            datum__gte=thirty_days_ago
        )
    
    # Statistiken
    total_minuten = sum(c.dauer_minuten for c in cardio_einheiten)
    total_einheiten = cardio_einheiten.count()
    
    context = {
        'cardio_einheiten': cardio_einheiten,
        'total_minuten': total_minuten,
        'total_einheiten': total_einheiten,
        'show_all': show_all,
    }
    return render(request, 'core/cardio_list.html', context)


@login_required
def cardio_add(request):
    """Fügt eine neue Cardio-Einheit hinzu."""
    if request.method == 'POST':
        aktivitaet = request.POST.get('aktivitaet')
        dauer = request.POST.get('dauer_minuten')
        intensitaet = request.POST.get('intensitaet', 'MODERAT')
        notiz = request.POST.get('notiz', '')
        datum_str = request.POST.get('datum')
        
        # Datum parsen
        if datum_str:
            from datetime import datetime
            try:
                datum = datetime.strptime(datum_str, '%Y-%m-%d').date()
            except ValueError:
                datum = timezone.now().date()
        else:
            datum = timezone.now().date()
        
        # Validierung
        if not aktivitaet or not dauer:
            messages.error(request, 'Bitte Aktivität und Dauer angeben.')
            return redirect('cardio_add')
        
        try:
            dauer_int = int(dauer)
            if dauer_int <= 0:
                raise ValueError
        except ValueError:
            messages.error(request, 'Bitte eine gültige Dauer in Minuten angeben.')
            return redirect('cardio_add')
        
        # Speichern
        CardioEinheit.objects.create(
            user=request.user,
            datum=datum,
            aktivitaet=aktivitaet,
            dauer_minuten=dauer_int,
            intensitaet=intensitaet,
            notiz=notiz[:200] if notiz else ''
        )
        
        messages.success(request, f'{dict(CARDIO_AKTIVITAETEN).get(aktivitaet, aktivitaet)} ({dauer_int} Min) hinzugefügt!')
        return redirect('cardio_list')
    
    # GET: Formular anzeigen
    context = {
        'aktivitaeten': CARDIO_AKTIVITAETEN,
        'intensitaeten': CARDIO_INTENSITAET,
        'heute': timezone.now().date().isoformat(),
    }
    return render(request, 'core/cardio_add.html', context)


@login_required
def cardio_delete(request, cardio_id):
    """Löscht eine Cardio-Einheit."""
    cardio = get_object_or_404(CardioEinheit, id=cardio_id, user=request.user)
    
    if request.method == 'POST':
        aktivitaet = cardio.get_aktivitaet_display()
        cardio.delete()
        messages.success(request, f'{aktivitaet} gelöscht.')
        return redirect('cardio_list')
    
    # GET: Bestätigungs-Seite (oder redirect)
    return redirect('cardio_list')


@login_required
@require_http_methods(["POST"])
def toggle_favorit(request, uebung_id):
    """
    Toggle Favorit-Status einer Übung für den aktuellen User.
    Returns: JSON mit {'is_favorit': bool, 'message': str}
    """
    uebung = get_object_or_404(Uebung, id=uebung_id)
    
    # Toggle: Favorit hinzufügen oder entfernen
    if request.user in uebung.favoriten.all():
        uebung.favoriten.remove(request.user)
        is_favorit = False
        message = f'"{uebung.bezeichnung}" aus Favoriten entfernt'
    else:
        uebung.favoriten.add(request.user)
        is_favorit = True
        message = f'"{uebung.bezeichnung}" zu Favoriten hinzugefügt'
    
    return JsonResponse({
        'is_favorit': is_favorit,
        'message': message
    })


@login_required
@require_http_methods(["POST"])
def create_custom_uebung(request):
    """
    Erstellt eine benutzerdefinierte Übung.
    Returns: JSON mit {'success': bool, 'uebung_id': int, 'message': str}
    """
    try:
        data = json.loads(request.body)
        
        bezeichnung = data.get('bezeichnung', '').strip()
        muskelgruppe = data.get('muskelgruppe')
        gewichts_typ = data.get('gewichts_typ', 'GESAMT')
        bewegungstyp = data.get('bewegungstyp', 'ISOLATION')
        beschreibung = data.get('beschreibung', '').strip()
        equipment_ids = data.get('equipment', [])
        
        # Validation
        if not bezeichnung:
            return JsonResponse({'success': False, 'error': 'Name ist erforderlich'}, status=400)
        
        if not muskelgruppe:
            return JsonResponse({'success': False, 'error': 'Muskelgruppe ist erforderlich'}, status=400)
        
        # Prüfe ob Name bereits existiert (nur für diesen User)
        if Uebung.objects.filter(bezeichnung__iexact=bezeichnung, created_by=request.user).exists():
            return JsonResponse({'success': False, 'error': 'Du hast bereits eine Übung mit diesem Namen'}, status=400)
        
        # Erstelle Custom-Übung
        uebung = Uebung.objects.create(
            bezeichnung=bezeichnung,
            muskelgruppe=muskelgruppe,
            gewichts_typ=gewichts_typ,
            bewegungstyp=bewegungstyp,
            beschreibung=beschreibung,
            created_by=request.user,
            is_custom=True
        )
        
        # Equipment zuweisen
        if equipment_ids:
            equipment_objs = Equipment.objects.filter(id__in=equipment_ids)
            uebung.equipment.set(equipment_objs)
        
        return JsonResponse({
            'success': True,
            'uebung_id': uebung.id,
            'message': f'Übung "{bezeichnung}" erstellt',
            'uebung': {
                'id': uebung.id,
                'name': uebung.bezeichnung,
                'muskelgruppe': uebung.get_muskelgruppe_display(),
                'is_custom': True
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Ungültige JSON-Daten'}, status=400)
    except Exception as e:
        logger.error(f'API request error: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': 'Anfrage konnte nicht verarbeitet werden.'}, status=500)