"""Cardio-Tracking Model: CardioEinheit."""

from django.contrib.auth.models import User
from django.db import models

from .constants import CARDIO_AKTIVITAETEN, CARDIO_INTENSITAET


class CardioEinheit(models.Model):
    """Einfaches Cardio-Tracking für Ausdauertraining ohne Trainingsplan."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="cardio_einheiten")
    datum = models.DateField(verbose_name="Datum")
    aktivitaet = models.CharField(
        max_length=20, choices=CARDIO_AKTIVITAETEN, verbose_name="Aktivität"
    )
    dauer_minuten = models.PositiveIntegerField(verbose_name="Dauer (Minuten)")
    intensitaet = models.CharField(
        max_length=20, choices=CARDIO_INTENSITAET, default="MODERAT", verbose_name="Intensität"
    )
    notiz = models.CharField(max_length=200, blank=True, verbose_name="Notiz")
    erstellt_am = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_aktivitaet_display()} - {self.dauer_minuten} Min ({self.datum.strftime('%d.%m.%Y')})"

    @property
    def ermuedungs_punkte(self):
        """Berechnet Ermüdungspunkte basierend auf Intensität und Dauer."""
        basis = {
            "LEICHT": 0.1,
            "MODERAT": 0.2,
            "INTENSIV": 0.4,
        }
        return round(self.dauer_minuten * basis.get(self.intensitaet, 0.15), 1)

    class Meta:
        verbose_name = "Cardio-Einheit"
        verbose_name_plural = "Cardio-Einheiten"
        ordering = ["-datum", "-erstellt_am"]
        indexes = [
            models.Index(fields=["user", "datum"]),
        ]
