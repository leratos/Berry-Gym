"""
Scientific Disclaimer Management.

Verwaltet wissenschaftliche Hinweise und Disclaimer für die App.
"""

from django.db import models


class ScientificDisclaimer(models.Model):
    """
    Wissenschaftliche Disclaimer für verschiedene Features.

    Transparent kommunizieren über:
    - Limitationen der 1RM-Standards
    - Wissenschaftliche Quellen
    - Unsicherheiten in Berechnungen
    """

    CATEGORY_CHOICES = [
        ("1RM_STANDARDS", "1RM Standards"),
        ("FATIGUE_INDEX", "Ermüdungsindex"),
        ("BODY_COMPOSITION", "Körperkomposition"),
        ("TRAINING_VOLUME", "Trainingsvolumen"),
        ("GENERAL", "Allgemein"),
    ]

    category = models.CharField(
        max_length=50, choices=CATEGORY_CHOICES, unique=True, verbose_name="Kategorie"
    )

    title = models.CharField(max_length=200, verbose_name="Titel")

    message = models.TextField(
        verbose_name="Nachricht",
        help_text="Markdown-formatierter Text. Nutze **fett**, *kursiv*, [Links](url)",
    )

    severity = models.CharField(
        max_length=20,
        choices=[("INFO", "Info"), ("WARNING", "Warnung"), ("CRITICAL", "Kritisch")],
        default="INFO",
        verbose_name="Schweregrad",
    )

    show_on_pages = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Seiten anzeigen",
        help_text='Liste von URL-Patterns, z.B. ["uebungen/", "stats/"]',
    )

    is_active = models.BooleanField(default=True, verbose_name="Aktiv")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Wissenschaftlicher Disclaimer"
        verbose_name_plural = "Wissenschaftliche Disclaimer"
        ordering = ["category"]

    def __str__(self):
        return f"{self.get_category_display()}: {self.title}"
