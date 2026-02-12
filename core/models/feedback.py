"""Feedback & Push-Notification Models: Feedback, PushSubscription."""

from django.contrib.auth.models import User
from django.db import models

from .constants import FEEDBACK_PRIORITY_CHOICES, FEEDBACK_STATUS_CHOICES, FEEDBACK_TYPE_CHOICES


class Feedback(models.Model):
    """Beta-Feedback: Bugreports und Verbesserungsvorschläge."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="feedbacks")
    feedback_type = models.CharField(
        max_length=20, choices=FEEDBACK_TYPE_CHOICES, default="FEATURE"
    )
    title = models.CharField(max_length=200, verbose_name="Kurzbeschreibung")
    description = models.TextField(verbose_name="Detaillierte Beschreibung")
    status = models.CharField(max_length=20, choices=FEEDBACK_STATUS_CHOICES, default="NEW")
    priority = models.CharField(
        max_length=20, choices=FEEDBACK_PRIORITY_CHOICES, default="MEDIUM", blank=True
    )
    admin_response = models.TextField(blank=True, null=True, verbose_name="Admin-Antwort")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"[{self.get_feedback_type_display()}] {self.title} - {self.user.username}"

    def get_status_badge_class(self):
        """Bootstrap Badge-Klasse basierend auf Status."""
        badge_classes = {
            "NEW": "bg-info",
            "ACCEPTED": "bg-success",
            "REJECTED": "bg-danger",
            "IN_PROGRESS": "bg-warning text-dark",
            "DONE": "bg-primary",
        }
        return badge_classes.get(self.status, "bg-secondary")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Feedback"
        verbose_name_plural = "Feedbacks"


class PushSubscription(models.Model):
    """Web Push Notification Subscription für User."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="push_subscriptions")
    endpoint = models.TextField(unique=True, verbose_name="Push Endpoint")
    p256dh = models.TextField(verbose_name="P256DH Key")
    auth = models.TextField(verbose_name="Auth Secret")
    user_agent = models.CharField(max_length=500, blank=True, verbose_name="Browser/Gerät")
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(auto_now=True)
    training_reminders = models.BooleanField(default=True, verbose_name="Trainings-Erinnerungen")
    rest_day_reminders = models.BooleanField(
        default=True, verbose_name="Ruhetag-Benachrichtigungen"
    )
    achievement_notifications = models.BooleanField(
        default=True, verbose_name="Erfolgs-Benachrichtigungen"
    )

    def __str__(self):
        return f"{self.user.username} - {self.user_agent[:50]}"

    class Meta:
        verbose_name = "Push Subscription"
        verbose_name_plural = "Push Subscriptions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
        ]
