"""Social/Beta-Zugang Models: InviteCode, WaitlistEntry."""

from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db import models


class InviteCode(models.Model):
    """Einladungscode für Beta-Registrierung."""

    code = models.CharField(max_length=20, unique=True, verbose_name="Einladungscode")
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_invite_codes",
        verbose_name="Erstellt von",
    )
    max_uses = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name="Max. Verwendungen",
        help_text="Wie oft kann dieser Code verwendet werden?",
    )
    used_count = models.IntegerField(default=0, verbose_name="Bereits verwendet")
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Ablaufdatum",
        help_text="Leer lassen für unbegrenzte Gültigkeit",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.code} ({self.used_count}/{self.max_uses})"

    def is_valid(self):
        """Prüft ob Code noch gültig ist."""
        from django.utils import timezone

        if self.used_count >= self.max_uses:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True

    class Meta:
        verbose_name = "Einladungscode"
        verbose_name_plural = "Einladungscodes"
        ordering = ["-created_at"]


class WaitlistEntry(models.Model):
    """Wartelisten-Eintrag für Beta-Bewerbungen. Wird nach 48h automatisch approved."""

    EXPERIENCE_CHOICES = [
        ("beginner", "Anfänger (< 1 Jahr Training)"),
        ("intermediate", "Fortgeschritten (1-3 Jahre)"),
        ("advanced", "Erfahren (> 3 Jahre)"),
        ("returning", "Wiedereinstieg nach Pause"),
    ]
    INTEREST_CHOICES = [
        ("ai_plans", "KI-Trainingspläne"),
        ("tracking", "Trainingstracking"),
        ("analytics", "Analyse & Statistiken"),
        ("opensource", "Open-Source / Entwicklung"),
    ]
    STATUS_CHOICES = [
        ("pending", "Warteliste"),
        ("approved", "Eingeladen"),
        ("registered", "Registriert"),
        ("spam", "Blockiert"),
    ]

    email = models.EmailField(unique=True, verbose_name="E-Mail")
    reason = models.TextField(
        verbose_name="Motivation", help_text="Warum möchtest du HomeGym nutzen?"
    )
    experience = models.CharField(
        max_length=20, choices=EXPERIENCE_CHOICES, verbose_name="Trainingserfahrung"
    )
    interests = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Interessen",
        help_text="Mehrfachauswahl möglich",
    )
    github_username = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="GitHub Username (optional)"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending", verbose_name="Status"
    )
    invite_code = models.OneToOneField(
        InviteCode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="waitlist_entry",
        verbose_name="Zugewiesener Code",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.email} ({self.get_status_display()})"

    def should_auto_approve(self):
        """Prüft ob Eintrag alt genug für Auto-Approve ist (48h)."""
        from datetime import timedelta

        from django.utils import timezone

        if self.status != "pending":
            return False
        age = timezone.now() - self.created_at
        return age >= timedelta(hours=48)

    def approve_and_send_code(self):
        """Approved den Eintrag und sendet Einladungscode per Email."""
        import secrets

        from django.utils import timezone

        if self.status != "pending":
            return False

        code = f"BETA{secrets.token_hex(6).upper()}"
        invite = InviteCode.objects.create(
            code=code,
            created_by=None,
            max_uses=1,
            expires_at=timezone.now() + timezone.timedelta(days=30),
        )
        self.status = "approved"
        self.approved_at = timezone.now()
        self.invite_code = invite
        self.save()
        self.send_invite_email()
        return True

    def send_invite_email(self):
        """Sendet Einladungscode per Email."""
        from django.conf import settings
        from django.core.mail import send_mail

        if not self.invite_code:
            return False

        subject = "🎉 Dein HomeGym Beta-Zugang ist bereit!"
        message = f"""Hallo!

Vielen Dank für dein Interesse an HomeGym! 🏋️

Deine Bewerbung wurde geprüft und du bist jetzt für die Beta-Phase freigeschaltet.

🔑 Dein persönlicher Einladungscode:
{self.invite_code.code}

📝 So geht's weiter:
1. Gehe zu: {settings.SITE_URL}/register/?code={self.invite_code.code}
2. Erstelle deinen Account
3. Starte dein erstes Training!

Der Code ist 30 Tage gültig und kann nur einmal verwendet werden.

Viel Erfolg beim Training!

Dein HomeGym Team
https://gym.last-strawberry.com
"""
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[self.email],
                fail_silently=False,
            )
            return True
        except Exception as e:
            print(f"Email sending failed: {e}")
            return False

    class Meta:
        verbose_name = "Wartelisten-Eintrag"
        verbose_name_plural = "Warteliste"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["email"]),
        ]
