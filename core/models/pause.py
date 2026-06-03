"""Trainingspausen / Ausfallzeiten: TrainingsPause (Phase 32).

Dokumentiert trainingsfreie Zeiträume (Krankheit, Verletzung, Urlaub) explizit,
damit die Analyse-Schichten eine dokumentierte Pause als *begründete Lücke*
behandeln statt als stilles Datenloch.

Wichtig (Konzept §32.1):
- `ist_ausfall` etc. werden NICHT persistiert, sondern zur Analysezeit aus den
  Pausen-Ranges berechnet (SoT = dieses Model).
- Der deutsche `grund`-Key wird persistiert; übersetzt wird nur beim Rendern.
- Overlap-Schutz: MariaDB hat keine Exclusion-Constraints; der harte,
  transaktional serialisierte Schutz sitzt in `core/services/pausen.py`. Das
  `clean()` hier ist die zweite Schicht (Forms/Admin) und teilt sich das
  Overlap-Prädikat mit dem Service.
"""

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils.translation import gettext_lazy as _


class TrainingsPause(models.Model):
    """Ein dokumentierter trainingsfreier Zeitraum eines Users.

    `end_datum=None` bedeutet eine **laufende** (noch offene) Pause = unbegrenzt
    in die Zukunft (+∞) für alle Overlap-/Grenz-Betrachtungen.
    """

    class Grund(models.TextChoices):
        KRANKHEIT = "krankheit", _("Krankheit")
        VERLETZUNG = "verletzung", _("Verletzung")
        URLAUB = "urlaub", _("Urlaub")
        SONSTIGES = "sonstiges", _("Sonstiges")

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="trainingspausen",
        db_index=True,
    )
    start_datum = models.DateField(verbose_name=_("Startdatum"))
    end_datum = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Enddatum"),
        help_text=_("Leer lassen für eine noch laufende Pause."),
    )
    grund = models.CharField(
        max_length=20,
        choices=Grund.choices,
        default=Grund.SONSTIGES,
        verbose_name=_("Grund"),
    )
    notiz = models.TextField(blank=True, verbose_name=_("Notiz"))
    erstellt_am = models.DateTimeField(auto_now_add=True)
    geaendert_am = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Trainingspause")
        verbose_name_plural = _("Trainingspausen")
        ordering = ["-start_datum"]
        indexes = [
            models.Index(fields=["user", "start_datum"], name="pause_user_start_idx"),
            models.Index(fields=["user", "end_datum"], name="pause_user_end_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_datum__isnull=True) | Q(end_datum__gte=F("start_datum")),
                name="trainingspause_end_nach_start",
            ),
        ]

    def __str__(self) -> str:
        ende = self.end_datum.strftime("%d.%m.%Y") if self.end_datum else "offen"
        start = self.start_datum.strftime("%d.%m.%Y") if self.start_datum else "?"
        return f"{self.get_grund_display()} ({start} – {ende})"

    @property
    def ist_laufend(self) -> bool:
        """True, solange kein Enddatum gesetzt ist (= laufende Pause, +∞)."""
        return self.end_datum is None

    @classmethod
    def ueberlappende(cls, *, user, start_datum, end_datum, exclude_pk=None):
        """Queryset der Pausen dieses Users, die [start_datum, end_datum] schneiden.

        Inklusive Range-Semantik (gemeinsame Grenztage zählen als Overlap). Ein
        offenes Ende (`end_datum is None`) wird als unbegrenzt (+∞) behandelt –
        sowohl für die bestehende als auch für die neue Pause (Konzept §32.1, ㉓).
        SQL-Vergleiche mit NULL sind nie TRUE, daher explizite Zweige:

        - Bestehende Pause endet am/nach `start_datum` ODER ist offen (+∞).
        - Bestehende Pause beginnt am/vor `end_datum`; ist die NEUE Pause offen
          (`end_datum is None`), entfällt diese Obergrenze ganz.
        """
        qs = cls.objects.filter(user=user)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        qs = qs.filter(Q(end_datum__gte=start_datum) | Q(end_datum__isnull=True))
        if end_datum is not None:
            qs = qs.filter(start_datum__lte=end_datum)
        return qs

    def clean(self):
        """Form-/Admin-Validierung: end≥start und kein Overlap pro User.

        Zweite Schicht – der autoritative, transaktional gesperrte Check sitzt im
        Service. Django ruft `clean()` NICHT automatisch in `save()` auf.
        """
        super().clean()
        if (
            self.start_datum is not None
            and self.end_datum is not None
            and self.end_datum < self.start_datum
        ):
            raise ValidationError(
                {"end_datum": _("Das Enddatum darf nicht vor dem Startdatum liegen.")}
            )
        if self.start_datum is not None and self.user_id is not None:
            overlap = self.ueberlappende(
                user=self.user,
                start_datum=self.start_datum,
                end_datum=self.end_datum,
                exclude_pk=self.pk,
            )
            if overlap.exists():
                raise ValidationError(
                    _(
                        "Dieser Zeitraum überschneidet sich mit einer bereits "
                        "eingetragenen Pause."
                    )
                )
