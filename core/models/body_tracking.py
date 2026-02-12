"""Body-Tracking Models: KoerperWerte, ProgressPhoto."""

from django.contrib.auth.models import User
from django.db import models


class KoerperWerte(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="koerperwerte", null=True)
    datum = models.DateField(auto_now_add=True, verbose_name="Messdatum")
    groesse_cm = models.PositiveIntegerField(
        verbose_name="Größe (cm)", help_text="Benötigt für BMI/FFMI"
    )
    gewicht = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Gewicht (kg)")
    fettmasse_kg = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True, verbose_name="Fett (kg)"
    )
    koerperfett_prozent = models.DecimalField(
        max_digits=4, decimal_places=1, blank=True, null=True, verbose_name="KFA (%)"
    )
    koerperwasser_kg = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True, verbose_name="Wasser (kg)"
    )
    muskelmasse_kg = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True, verbose_name="Muskeln (kg)"
    )
    knochenmasse_kg = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True, verbose_name="Knochen (kg)"
    )
    notiz = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        verbose_name = "Körperwert"
        verbose_name_plural = "Körperwerte"
        ordering = ["-datum"]
        get_latest_by = "datum"

    @property
    def bmi(self):
        if self.gewicht and self.groesse_cm:
            groesse_m = self.groesse_cm / 100
            return round(float(self.gewicht) / (groesse_m**2), 1)
        return None

    @property
    def ffmi(self):
        fett_kg = None
        if self.fettmasse_kg:
            fett_kg = float(self.fettmasse_kg)
        elif self.gewicht and self.koerperfett_prozent:
            fett_kg = float(self.gewicht) * (float(self.koerperfett_prozent) / 100)
        if self.gewicht and self.groesse_cm and fett_kg is not None:
            fettfreie_masse = float(self.gewicht) - fett_kg
            groesse_m = self.groesse_cm / 100
            ffmi_wert = fettfreie_masse / (groesse_m**2)
            ffmi_norm = ffmi_wert + 6.1 * (1.8 - groesse_m)
            return round(ffmi_norm, 1)
        return None


class ProgressPhoto(models.Model):
    """Fortschrittsfotos zur Dokumentation der Body Transformation."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="progress_photos")
    foto = models.ImageField(upload_to="progress_photos/%Y/%m/", verbose_name="Foto")
    datum = models.DateField(auto_now_add=True, verbose_name="Aufnahmedatum")
    gewicht_kg = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="Gewicht (kg)",
        help_text="Optional: Gewicht zum Zeitpunkt des Fotos",
    )
    notiz = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="Notiz",
        help_text="z.B. 'Start', 'Nach 3 Monaten', 'Bulking Phase'",
    )
    erstellt_am = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.datum.strftime('%d.%m.%Y')}"

    class Meta:
        verbose_name = "Fortschrittsfoto"
        verbose_name_plural = "Fortschrittsfotos"
        ordering = ["-datum"]
        indexes = [
            models.Index(fields=["user", "-datum"]),
        ]
