"""
Authentication and user management views module.

This module handles:
- Beta access applications and waitlist management
- User registration with invite codes
- User profile management
- User feedback (bug reports and feature requests)
"""

from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.mail import send_mail
import logging

from ..models import InviteCode, WaitlistEntry

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
        from django.db.models import F
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


@login_required
def feedback_list(request):
    """Liste aller eigenen Feedbacks"""
    from ..models import Feedback
    feedbacks = Feedback.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'core/feedback_list.html', {'feedbacks': feedbacks})


@login_required
def feedback_create(request):
    """Neues Feedback (Bug/Feature) erstellen"""
    from ..models import Feedback

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
    from ..models import Feedback
    feedback = get_object_or_404(Feedback, id=feedback_id, user=request.user)
    return render(request, 'core/feedback_detail.html', {'feedback': feedback})


@login_required
def profile(request):
    """Profil-Seite zum Bearbeiten von Benutzerdaten"""
    from django.contrib.auth.hashers import check_password
    from django.contrib.auth import update_session_auth_hash

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

            if not current_password or not new_password or not confirm_password:
                messages.error(request, '❌ Bitte alle Felder ausfüllen.')
            elif not check_password(current_password, user.password):
                messages.error(request, '❌ Aktuelles Passwort ist falsch. Bitte nochmal versuchen.')
            elif len(new_password) < 8:
                messages.error(request, '❌ Neues Passwort muss mindestens 8 Zeichen haben.')
            elif new_password != confirm_password:
                messages.error(request, '❌ Die neuen Passwörter stimmen nicht überein. Bitte überprüfen!')
            else:
                user.set_password(new_password)
                user.save()
                # Session aktualisieren ohne neu einzuloggen (behält Messages!)
                update_session_auth_hash(request, user)
                messages.success(request, '✅ Passwort erfolgreich geändert! Du bleibst eingeloggt.')

        return redirect('profile')

    return render(request, 'core/profile.html')
