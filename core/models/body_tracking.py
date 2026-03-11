"""Body-Tracking Models: KoerperWerte, ProgressPhoto."""

from django.contrib.auth.models import User
from django.db import models


class KoerperWerte(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="koerperwerte", null=True)
    datum = models.DateField(auto_now_add=True, verbose_name="Messdatum")
    groesse_cm = models.PositiveIntegerField(
        verbose_name="Größe (cm)",
        help_text="Benötigt für BMI/FFMI – wird aus Profil übernommen",
        null=True,
        blank=True,
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
    koerperwasser_prozent = models.DecimalField(
        max_digits=4, decimal_places=1, blank=True, null=True, verbose_name="Wasser (%)"
    )
    viszeralfett = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        verbose_name="Viszeralfett (Stufe)",
        help_text="Viszeralfett-Stufe (1-59), je nach Waage",
    )
    grundumsatz_kcal = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name="Grundumsatz (kcal)",
        help_text="Basaler Energieumsatz (BMR) in kcal",
    )
    muskelmasse_kg = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True, verbose_name="Muskeln (kg)"
    )
    muskelmasse_prozent = models.DecimalField(
        max_digits=4, decimal_places=1, blank=True, null=True, verbose_name="Muskeln (%)"
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

    def _get_groesse_cm(self) -> int | None:
        """Gibt Körpergröße zurück: erst eigener Wert, dann Profil-Wert."""
        if self.groesse_cm:
            return self.groesse_cm
        try:
            return self.user.profile.groesse_cm
        except Exception:
            return None

    @property
    def bmi(self):
        groesse = self._get_groesse_cm()
        if self.gewicht and groesse:
            groesse_m = groesse / 100
            return round(float(self.gewicht) / (groesse_m**2), 1)
        return None

    @property
    def ffmi(self):
        groesse = self._get_groesse_cm()
        fett_kg = self._get_fett_kg()
        if self.gewicht and groesse and fett_kg is not None:
            fettfreie_masse = float(self.gewicht) - fett_kg
            groesse_m = groesse / 100
            ffmi_wert = fettfreie_masse / (groesse_m**2)
            ffmi_norm = ffmi_wert + 6.1 * (1.8 - groesse_m)
            return round(ffmi_norm, 1)
        return None

    @property
    def lbm_kg(self):
        """Lean Body Mass (fettfreie Masse) in kg."""
        fett_kg = self._get_fett_kg()
        if self.gewicht and fett_kg is not None:
            return round(float(self.gewicht) - fett_kg, 2)
        return None

    @property
    def muskel_fett_ratio(self):
        """Verhältnis Muskelmasse zu Fettmasse."""
        fett_kg = self._get_fett_kg()
        if self.muskelmasse_kg and fett_kg and fett_kg > 0:
            return round(float(self.muskelmasse_kg) / fett_kg, 2)
        return None

    def _get_fett_kg(self) -> float | None:
        """Fettmasse in kg aus direktem Wert oder Prozent berechnet."""
        if self.fettmasse_kg:
            return float(self.fettmasse_kg)
        if self.gewicht and self.koerperfett_prozent:
            return float(self.gewicht) * (float(self.koerperfett_prozent) / 100)
        return None

    def gewichts_veraenderung_rate(self) -> float | None:
        """Gewichtsveränderung in kg/Woche – Vergleich über mindestens 7 Tage.

        Sucht den ältesten Eintrag innerhalb der letzten 30 Tage, der mindestens
        7 Tage zurückliegt. Tagesschwankungen (z.B. durch Creatine-Wassereinlagerung)
        werden so herausgefiltert.
        """
        from datetime import timedelta

        mindest_datum = self.datum - timedelta(days=7)
        max_datum = self.datum - timedelta(days=30)
        # Bevorzuge Eintrag der möglichst nahe an 7 Tagen liegt (neuester der ≥7 Tage alten)
        referenz = (
            KoerperWerte.objects.filter(
                user=self.user,
                datum__lte=mindest_datum,
                datum__gte=max_datum,
            )
            .order_by("-datum")
            .first()
        )
        # Fallback: ältester verfügbarer Eintrag wenn kein Eintrag im 7-30d Fenster
        if not referenz:
            referenz = (
                KoerperWerte.objects.filter(user=self.user, datum__lt=self.datum)
                .order_by("datum")
                .first()
            )
        if not referenz or not referenz.gewicht:
            return None
        tage = (self.datum - referenz.datum).days
        if tage <= 0:
            return None
        diff_kg = float(self.gewicht) - float(referenz.gewicht)
        return round(diff_kg / tage * 7, 2)


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
