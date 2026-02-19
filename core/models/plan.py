"""Plan-bezogene Models: Plan, PlanUebung."""

from django.contrib.auth.models import User
from django.db import models

from .exercise import Uebung


class Plan(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="plaene", null=True)
    name = models.CharField(max_length=100, verbose_name="Name des Plans")
    beschreibung = models.TextField(blank=True, verbose_name="Beschreibung")
    is_public = models.BooleanField(default=False, verbose_name="Öffentlich")
    erstellt_am = models.DateTimeField(auto_now_add=True)
    shared_with = models.ManyToManyField(
        User,
        related_name="shared_plans",
        blank=True,
        verbose_name="Geteilt mit",
        help_text="User, die diesen Plan sehen können (ohne öffentlich zu sein)",
    )
    gruppe_id = models.UUIDField(
        null=True,
        blank=True,
        verbose_name="Gruppen-ID",
        help_text="Pläne mit gleicher ID gehören zusammen (z.B. Split-Tage)",
    )
    gruppe_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Gruppenname",
        help_text="Name der Plangruppe (z.B. 'Push/Pull/Legs Split')",
    )
    gruppe_reihenfolge = models.PositiveIntegerField(
        default=0,
        verbose_name="Reihenfolge in Gruppe",
        help_text="Position des Plans innerhalb der Gruppe (0, 1, 2, ...)",
    )

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.gruppe_id and not self.gruppe_name and " - " in self.name:
            self.gruppe_name = self.name.rsplit(" - ", 1)[0]
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Trainingsplan"
        verbose_name_plural = "Trainingspläne"
        indexes = [
            models.Index(fields=["user", "is_public"], name="plan_user_public_idx"),
        ]


class PlanUebung(models.Model):
    """Verknüpft Übungen mit einem Plan in einer festen Reihenfolge."""

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="uebungen")
    uebung = models.ForeignKey(Uebung, on_delete=models.CASCADE, verbose_name="Übung")
    reihenfolge = models.PositiveIntegerField(default=1, verbose_name="Reihenfolge")
    trainingstag = models.CharField(max_length=100, blank=True, verbose_name="Trainingstag/Session")
    saetze_ziel = models.PositiveIntegerField(default=3, verbose_name="Geplante Sätze")
    wiederholungen_ziel = models.CharField(
        max_length=50, blank=True, verbose_name="Ziel-Wdh (z.B. 8-12)"
    )
    pausenzeit = models.PositiveIntegerField(
        default=120,
        verbose_name="Pausenzeit (Sekunden)",
        help_text="Empfohlene Pause zwischen Sätzen (60-300s)",
    )
    superset_gruppe = models.PositiveIntegerField(
        default=0,
        verbose_name="Superset-Gruppe",
        help_text="0 = keine Gruppe, 1-9 = Gruppennummer für Supersätze",
    )
    notiz = models.TextField(
        blank=True,
        null=True,
        verbose_name="Übungshinweis",
        help_text="Technik-Hinweis oder Erinnerung die beim Training angezeigt wird",
    )

    class Meta:
        verbose_name = "Plan-Übung"
        verbose_name_plural = "Plan-Übungen"
        ordering = ["reihenfolge"]
        indexes = [
            models.Index(fields=["plan", "trainingstag"], name="planuebung_plan_tag_idx"),
        ]
