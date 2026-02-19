"""
Authentication and user management views module.

This module handles:
- Beta access applications and waitlist management
- User registration with invite codes
- User profile management
- User feedback (bug reports and feature requests)
"""

import logging

from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import F
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from ..helpers.email import send_welcome_email
from ..models import InviteCode, WaitlistEntry

logger = logging.getLogger(__name__)


def _validate_invite_code(code_str: str) -> str | None:
    """Prüft Einladungscode. Gibt Fehlermeldung zurück oder None wenn OK."""
    if not code_str:
        return "Einladungscode fehlt."
    if not InviteCode.objects.filter(code=code_str, used_count__lt=F("max_uses")).exists():
        return "Ungültiger oder aufgebrauchter Code."
    return None


def _validate_registration_fields(username: str, email: str, pass1: str, pass2: str) -> list[str]:
    """Validiert Pflichtfelder für Registrierung. Gibt Liste von Fehlermeldungen zurück."""
    errors: list[str] = []
    if not username:
        errors.append("Benutzername fehlt.")
    elif User.objects.filter(username=username).exists():
        errors.append("Benutzername vergeben.")

    if not email:
        errors.append("E-Mail fehlt.")
    elif User.objects.filter(email=email).exists():
        errors.append("E-Mail bereits registriert.")

    if not pass1 or pass1 != pass2:
        errors.append("Passwörter ungültig oder nicht identisch.")
    elif len(pass1) < 8:
        errors.append("Passwort zu kurz (min. 8 Zeichen).")

    return errors


def _handle_update_profile(user, new_username: str, new_email: str) -> list[str]:
    """Aktualisiert Username/E-Mail. Gibt Fehlerliste zurück (leer = Erfolg + gespeichert)."""
    errors: list[str] = []
    if new_username and new_username != user.username:
        if User.objects.filter(username=new_username).exists():
            errors.append("Dieser Benutzername ist bereits vergeben.")
        elif len(new_username) < 3:
            errors.append("Benutzername muss mindestens 3 Zeichen haben.")
        else:
            user.username = new_username

    if new_email and new_email != user.email:
        if User.objects.filter(email=new_email).exists():
            errors.append("Diese E-Mail ist bereits registriert.")
        else:
            user.email = new_email

    if not errors:
        user.save()
    return errors


def _handle_change_password(
    user, current_password: str, new_password: str, confirm_password: str
) -> list[str]:
    """Ändert Passwort. Gibt Fehlerliste zurück (leer = Erfolg + gespeichert)."""
    from django.contrib.auth.hashers import check_password

    if not current_password or not new_password or not confirm_password:
        return ["❌ Bitte alle Felder ausfüllen."]
    if not check_password(current_password, user.password):
        return ["❌ Aktuelles Passwort ist falsch. Bitte nochmal versuchen."]
    if len(new_password) < 8:
        return ["❌ Neues Passwort muss mindestens 8 Zeichen haben."]
    if new_password != confirm_password:
        return ["❌ Die neuen Passwörter stimmen nicht überein. Bitte überprüfen!"]

    user.set_password(new_password)
    user.save()
    return []


def apply_beta(request: HttpRequest) -> HttpResponse:
    """Bewerbungsseite für Beta-Zugang"""
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        reason = request.POST.get("reason", "").strip()
        experience = request.POST.get("experience")
        interests = request.POST.getlist("interests")
        github_username = request.POST.get("github_username", "").strip()

        if not email or not reason or not experience:
            messages.error(request, "Bitte fülle alle Pflichtfelder aus.")
            return render(request, "registration/apply_beta.html")

        if WaitlistEntry.objects.filter(email=email).exists():
            messages.info(request, "Diese E-Mail ist bereits auf der Warteliste.")
            return redirect("apply_beta")

        from django.contrib.auth.models import User

        if User.objects.filter(email=email).exists():
            messages.info(request, "Mit dieser E-Mail existiert bereits ein Account.")
            return redirect("login")

        WaitlistEntry.objects.create(
            email=email,
            reason=reason,
            experience=experience,
            interests=interests,
            github_username=github_username or None,
        )

        messages.success(request, "✅ Bewerbung eingereicht! Du erhältst in 48h eine E-Mail.")
        return redirect("login")

    return render(request, "registration/apply_beta.html")


def register(request: HttpRequest) -> HttpResponse:
    """Registrierung mit Einladungscode"""
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        code_str = request.POST.get("invite_code", "").strip().upper()
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip().lower()
        pass1 = request.POST.get("password1")
        pass2 = request.POST.get("password2")

        errors = []
        code_error = _validate_invite_code(code_str)
        if code_error:
            errors.append(code_error)
        errors.extend(_validate_registration_fields(username, email, pass1, pass2))

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, "registration/register_new.html", {"invite_code": code_str})

        user = User.objects.create_user(username=username, email=email, password=pass1)
        invite = InviteCode.objects.get(code=code_str)
        invite.use()

        entry = WaitlistEntry.objects.filter(email=email, invite_code=invite).first()
        if entry:
            entry.status = "registered"
            entry.save()

        send_welcome_email(user)

        user = authenticate(username=username, password=pass1)
        login(request, user)
        messages.success(request, f"🎉 Willkommen {username}!")
        return redirect("dashboard")

    code_param = request.GET.get("code", "").strip().upper()
    return render(request, "registration/register_new.html", {"invite_code": code_param})


@login_required
def feedback_list(request: HttpRequest) -> HttpResponse:
    """Liste aller eigenen Feedbacks"""
    from ..models import Feedback

    feedbacks = Feedback.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "core/feedback_list.html", {"feedbacks": feedbacks})


@login_required
def feedback_create(request: HttpRequest) -> HttpResponse:
    """Neues Feedback (Bug/Feature) erstellen"""
    from ..models import Feedback

    if request.method == "POST":
        feedback_type = request.POST.get("feedback_type", "FEATURE")
        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "").strip()

        if not title or not description:
            return render(
                request,
                "core/feedback_create.html",
                {
                    "error": "Bitte fülle alle Felder aus.",
                    "feedback_type": feedback_type,
                    "title": title,
                    "description": description,
                },
            )

        Feedback.objects.create(
            user=request.user,
            feedback_type=feedback_type,
            title=title,
            description=description,
        )

        from django.contrib import messages

        messages.success(request, "✅ Danke für dein Feedback! Wir werden es prüfen.")
        return redirect("feedback_list")

    # GET - Formular anzeigen
    feedback_type = request.GET.get("type", "FEATURE")
    return render(request, "core/feedback_create.html", {"feedback_type": feedback_type})


@login_required
def feedback_detail(request: HttpRequest, feedback_id: int) -> HttpResponse:
    """Feedback-Details anzeigen"""
    from ..models import Feedback

    feedback = get_object_or_404(Feedback, id=feedback_id, user=request.user)
    return render(request, "core/feedback_detail.html", {"feedback": feedback})


@login_required
def profile(request: HttpRequest) -> HttpResponse:
    """Profil-Seite zum Bearbeiten von Benutzerdaten"""
    if request.method == "POST":
        from django.contrib.auth import update_session_auth_hash

        action = request.POST.get("action")
        user = request.user

        if action == "update_profile":
            new_username = request.POST.get("username", "").strip()
            new_email = request.POST.get("email", "").strip().lower()
            errors = _handle_update_profile(user, new_username, new_email)
            if errors:
                for error in errors:
                    messages.error(request, error)
            else:
                messages.success(request, "✅ Profil erfolgreich aktualisiert!")

        elif action == "change_password":
            errors = _handle_change_password(
                user,
                request.POST.get("current_password"),
                request.POST.get("new_password"),
                request.POST.get("confirm_password"),
            )
            if errors:
                for error in errors:
                    messages.error(request, error)
            else:
                update_session_auth_hash(request, user)
                messages.success(
                    request, "✅ Passwort erfolgreich geändert! Du bleibst eingeloggt."
                )

        elif action == "update_body_data":
            groesse_str = request.POST.get("groesse_cm", "").strip()
            if groesse_str and groesse_str.isdigit():
                groesse = int(groesse_str)
                if 100 <= groesse <= 250:
                    profile = request.user.profile
                    profile.groesse_cm = groesse
                    profile.save(update_fields=["groesse_cm"])
                    messages.success(request, f"✅ Körpergröße auf {groesse} cm gesetzt.")
                else:
                    messages.error(request, "Körpergröße muss zwischen 100 und 250 cm liegen.")
            else:
                messages.error(request, "Bitte eine gültige Körpergröße eingeben.")

        return redirect("profile")

    return render(request, "core/profile.html", {"user_profile": request.user.profile})
