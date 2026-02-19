"""UserProfile Model — erweitert den Standard-Django-User."""

from django.contrib.auth.models import User
from django.db import models


class UserProfile(models.Model):
    """Erweitert den Standard-Django-User um zusätzliche Felder."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    active_plan_group = models.UUIDField(
        null=True,
        blank=True,
        verbose_name="Aktive Plan-Gruppe",
        help_text="Die gruppe_id der aktuell aktiven Plangruppe",
    )
    cycle_length = models.PositiveIntegerField(
        default=4,
        verbose_name="Zykluslänge (Wochen)",
        help_text="Anzahl Wochen pro Mesozyklus inkl. Deload (z.B. 4 = 3 normal + 1 Deload)",
    )
    cycle_start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Zyklusstart",
        help_text="Wird automatisch beim ersten Training mit aktiver Gruppe gesetzt",
    )
    deload_volume_factor = models.FloatField(
        default=0.8,
        verbose_name="Deload Volumen-Faktor",
        help_text="Faktor für Satz-Reduktion in Deload-Wochen (0.8 = 80% Volumen)",
    )
    deload_rpe_target = models.FloatField(
        default=7.0,
        verbose_name="Deload Ziel-RPE",
        help_text="Ziel-RPE für Deload-Wochen (z.B. 6.5-7.0)",
    )
    deload_weight_factor = models.FloatField(
        default=0.9,
        verbose_name="Deload Gewichts-Faktor",
        help_text="Faktor für Gewichts-Reduktion in Deload-Wochen (0.9 = -10%)",
    )
    groesse_cm = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Körpergröße (cm)",
        help_text="Wird für BMI- und FFMI-Berechnung verwendet",
    )

    def __str__(self):
        return f"Profil von {self.user.username}"

    def get_current_cycle_week(self):
        """Berechnet die aktuelle Woche im Mesozyklus (1-basiert). Gibt None zurück wenn kein Zyklus aktiv."""
        if not self.cycle_start_date or not self.active_plan_group:
            return None
        from django.utils import timezone

        today = timezone.now().date()
        days_since_start = (today - self.cycle_start_date).days
        if days_since_start < 0:
            return 1
        week = (days_since_start // 7) % self.cycle_length + 1
        return week

    def is_deload_week(self):
        """Prüft ob aktuell Deload-Woche ist (letzte Woche im Zyklus)."""
        week = self.get_current_cycle_week()
        if week is None:
            return False
        return week == self.cycle_length

    class Meta:
        verbose_name = "Benutzerprofil"
        verbose_name_plural = "Benutzerprofile"
