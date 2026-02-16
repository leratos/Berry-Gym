"""
Scientific Training Source Model.

Verwaltet wissenschaftliche Quellen/Literatur die als Basis für
die Algorithmen und Empfehlungen in der App dienen.
"""

from django.db import models


class TrainingSource(models.Model):
    """
    Wissenschaftliche Quelle / Literaturangabe.

    Wird verwendet um Algorithmen und Empfehlungen der App
    mit realen Quellen zu belegen. Über das `applies_to`-Feld
    kann gesteuert werden, wo in der UI Tooltips erscheinen.
    """

    CATEGORY_CHOICES = [
        ("VOLUME", "Trainingsvolumen"),
        ("INTENSITY", "Trainingsintensität / RPE"),
        ("RECOVERY", "Regeneration & Deload"),
        ("PERIODIZATION", "Periodisierung"),
        ("ONE_RM", "1RM & Kraftstandards"),
        ("BODY_COMP", "Körperkomposition"),
        ("GENERAL", "Allgemein"),
    ]

    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        verbose_name="Kategorie",
        db_index=True,
    )

    title = models.CharField(
        max_length=300,
        verbose_name="Titel",
    )

    authors = models.CharField(
        max_length=400,
        verbose_name="Autoren",
        help_text='Format: "Nachname, V., & Nachname, V."',
    )

    year = models.PositiveSmallIntegerField(
        verbose_name="Jahr",
    )

    journal = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Journal / Verlag",
    )

    doi = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="DOI",
        help_text="Ohne https://doi.org/ Prefix, z.B. 10.1080/02640414.2016.1210197",
    )

    url = models.URLField(
        blank=True,
        verbose_name="URL",
        help_text="Direkter Link zur Quelle (optional, als Fallback wenn kein DOI)",
    )

    key_findings = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Key Findings",
        help_text='Liste von Strings, z.B. ["Höheres Volumen korreliert mit mehr Hypertrophie"]',
    )

    applies_to = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Anwendungsbereiche",
        help_text=(
            "Steuert wo Tooltips erscheinen. Mögliche Werte: "
            '"fatigue_index", "1rm_standards", "rpe_quality", '
            '"plateau_analysis", "volume_metrics", "general"'
        ),
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Aktiv",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Wissenschaftliche Quelle"
        verbose_name_plural = "Wissenschaftliche Quellen"
        ordering = ["category", "year", "authors"]
        indexes = [
            models.Index(fields=["category", "is_active"], name="source_cat_active_idx"),
        ]

    def __str__(self):
        return f"{self.authors.split(',')[0]} ({self.year}) – {self.title[:60]}"

    @property
    def doi_url(self):
        """Vollständige DOI-URL."""
        if self.doi:
            return f"https://doi.org/{self.doi}"
        return self.url or ""

    @property
    def citation_short(self):
        """Kurzzitation für Tooltips, z.B. 'Schoenfeld et al. (2017)'."""
        first_author = self.authors.split(",")[0].strip()
        # Mehrere Autoren erkennbar am '&' (nicht nur Nachname, Vorname)
        if "&" in self.authors:
            return f"{first_author} et al. ({self.year})"
        return f"{first_author} ({self.year})"
