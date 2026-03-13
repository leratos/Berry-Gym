"""Training-bezogene Models: Trainingseinheit, Satz."""

from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .exercise import Uebung


class Trainingseinheit(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="trainings", null=True)
    plan = models.ForeignKey(
        "core.Plan",
        on_delete=models.SET_NULL,
        related_name="trainings",
        null=True,
        blank=True,
        verbose_name="Trainingsplan",
    )
    datum = models.DateTimeField(auto_now_add=True)
    dauer_minuten = models.PositiveIntegerField(blank=True, null=True, verbose_name="Dauer (Min)")
    kommentar = models.TextField(blank=True, null=True, verbose_name="Wie lief's?")
    ist_deload = models.BooleanField(
        default=False,
        verbose_name="Deload-Training",
        help_text="Deload-Trainings werden nicht in Statistiken (1RM, Volumen-Trends, Plateaus) eingerechnet",
    )
    abgeschlossen = models.BooleanField(
        default=False,
        verbose_name="Abgeschlossen",
        help_text="Wird auf True gesetzt wenn der User das Training explizit abgeschlossen hat",
    )

    def __str__(self):
        return f"Training vom {self.datum.strftime('%d.%m.%Y %H:%M')}"

    class Meta:
        verbose_name = "Trainingseinheit"
        verbose_name_plural = "Trainingseinheiten"
        ordering = ["-datum"]
        indexes = [
            models.Index(fields=["datum"]),
            models.Index(fields=["user", "datum"], name="training_user_datum_idx"),
            models.Index(fields=["user", "ist_deload"], name="training_user_deload_idx"),
            models.Index(fields=["user", "abgeschlossen"], name="training_user_done_idx"),
        ]


class Satz(models.Model):
    PR_TYPE_CHOICES = [
        ("best_1rm", "Bestes 1RM"),
        ("max_weight", "Neues Max-Gewicht"),
        ("max_reps", "Neue Wdh auf gleichem Gewicht"),
        ("first", "Erster Satz dieser Übung"),
    ]

    einheit = models.ForeignKey(Trainingseinheit, on_delete=models.CASCADE, related_name="saetze")
    uebung = models.ForeignKey(Uebung, on_delete=models.PROTECT, verbose_name="Übung")
    satz_nr = models.PositiveIntegerField(default=1, verbose_name="Satz Nr.")
    gewicht = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="Gewicht (kg)")
    wiederholungen = models.PositiveIntegerField(verbose_name="Wdh.")
    ist_aufwaermsatz = models.BooleanField(default=False, verbose_name="Warmup")
    rpe = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        blank=True,
        null=True,
        verbose_name="RPE (1-10)",
        validators=[MinValueValidator(1.0), MaxValueValidator(10.0)],
    )
    notiz = models.TextField(blank=True, null=True, verbose_name="Notiz")
    superset_gruppe = models.PositiveIntegerField(
        default=0,
        verbose_name="Superset-Gruppe",
        help_text="0 = keine Gruppe, 1-9 = Gruppennummer für Supersätze",
    )
    is_pr = models.BooleanField(
        default=False,
        verbose_name="Persönlicher Rekord",
        help_text="Dieser Satz ist ein neuer persönlicher Rekord",
    )
    pr_type = models.CharField(
        max_length=20,
        choices=PR_TYPE_CHOICES,
        null=True,
        blank=True,
        verbose_name="PR-Typ",
    )
    pr_previous_value = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Vorheriger Rekordwert",
        help_text="1RM-Wert vor diesem PR",
    )

    class Meta:
        verbose_name = "Satz"
        verbose_name_plural = "Sätze"
        ordering = ["einheit", "satz_nr"]
        indexes = [
            models.Index(fields=["uebung", "einheit"]),
            models.Index(fields=["einheit", "ist_aufwaermsatz"], name="satz_einheit_warmup_idx"),
        ]
