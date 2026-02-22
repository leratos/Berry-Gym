"""KIApiLog – protokolliert jeden LLM-API-Call mit Kosten und Token-Verbrauch."""

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class KIApiLog(models.Model):
    """
    Ein Eintrag pro LLM-API-Call.

    Ermöglicht:
    - Kosten-Tracking pro User und Monat
    - Erkennen welche Endpunkte teuer sind
    - Retry-Kosten sichtbar machen (mehrere Logs mit plan_generate_id verknüpft)
    """

    class Endpoint(models.TextChoices):
        PLAN_GENERATE = "plan_generate", "Plan Generierung"
        PLAN_OPTIMIZE = "plan_optimize", "Plan Optimierung"
        LIVE_GUIDANCE = "live_guidance", "Live Guidance"
        OTHER = "other", "Sonstiges"

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ki_api_logs",
        verbose_name="User",
    )
    endpoint = models.CharField(
        max_length=20,
        choices=Endpoint.choices,
        default=Endpoint.OTHER,
        verbose_name="Endpunkt",
    )
    model_name = models.CharField(
        max_length=100,
        default="",
        blank=True,
        verbose_name="Modell",
        help_text="z.B. google/gemini-2.5-flash",
    )
    tokens_input = models.PositiveIntegerField(
        default=0,
        verbose_name="Input-Tokens",
    )
    tokens_output = models.PositiveIntegerField(
        default=0,
        verbose_name="Output-Tokens",
    )
    cost_eur = models.DecimalField(
        max_digits=8,
        decimal_places=6,
        default=0,
        verbose_name="Kosten (€)",
        help_text="Kosten in Euro. Bei Ollama/lokal: 0.000000",
    )
    success = models.BooleanField(
        default=True,
        verbose_name="Erfolgreich",
        help_text="False wenn LLM-Call fehlschlug oder Validierung scheiterte",
    )
    is_retry = models.BooleanField(
        default=False,
        verbose_name="Retry",
        help_text="True wenn dieser Call ein Korrektur-Retry eines vorherigen Calls war",
    )
    error_message = models.TextField(
        blank=True,
        default="",
        verbose_name="Fehlermeldung",
        help_text="Leer bei Erfolg",
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="Zeitpunkt",
        db_index=True,
    )

    class Meta:
        verbose_name = "KI API Log"
        verbose_name_plural = "KI API Logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["endpoint", "created_at"]),
        ]

    def __str__(self):
        user_str = self.user.username if self.user else "anon"
        return (
            f"[{self.created_at:%Y-%m-%d %H:%M}] {user_str} / "
            f"{self.endpoint} – {self.cost_eur}€"
        )

    @property
    def tokens_total(self) -> int:
        return self.tokens_input + self.tokens_output
