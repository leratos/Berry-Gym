"""
Site-weite Einstellungen (Singleton-Pattern).
"""

from django.db import models


class SiteSettings(models.Model):
    """
    Site-weite Konfiguration (Singleton).

    Nur eine Instanz sollte existieren - wird via Admin verwaltet.
    Enthält globale Defaults für KI-Rate-Limits.
    """

    # === KI Rate Limits (täglich, Mitternacht UTC Reset) ===
    ai_limit_plan_generation = models.PositiveIntegerField(
        default=3,
        verbose_name="KI-Limit: Plan-Generierung",
        help_text="Wie viele Plan-Generierungen pro User/Tag (Standard: 3)",
    )
    ai_limit_live_guidance = models.PositiveIntegerField(
        default=50,
        verbose_name="KI-Limit: Live-Guidance",
        help_text="Wie viele Live-Guidance Calls pro User/Tag (Standard: 50)",
    )
    ai_limit_analysis = models.PositiveIntegerField(
        default=10,
        verbose_name="KI-Limit: Analysen",
        help_text="Wie viele Analyse-Calls pro User/Tag (Standard: 10)",
    )

    # === Metadaten ===
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Zuletzt geändert")

    class Meta:
        verbose_name = "Site-Einstellungen"
        verbose_name_plural = "Site-Einstellungen"

    def __str__(self):
        return "Site-Einstellungen (KI-Limits)"

    def save(self, *args, **kwargs):
        """Singleton-Pattern: Immer nur eine Instanz."""
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Singleton kann nicht gelöscht werden."""
        pass

    @classmethod
    def load(cls):
        """Lädt die Singleton-Instanz oder erstellt sie mit Defaults."""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
