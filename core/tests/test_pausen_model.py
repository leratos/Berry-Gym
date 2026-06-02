"""Tests für Phase 32.1 – Datenmodell TrainingsPause + Overlap-Service.

Deckt ab (Konzept §32.1 / §9.1):
- end ≥ start (Model-`clean()` UND DB-`CheckConstraint`),
- offene Pause (end_datum=None) zulässig,
- Overlap abgelehnt über `clean()` UND über den Service,
- nicht-überlappende Mehrfachpausen zulässig, inklusive Grenz-Semantik,
- offenes Ende = +∞: offen-vs-offen UND offen-vs-begrenzt (㉓),
- User-Isolation des Overlap-Checks,
- Service sperrt eine stabile User-Zeile (㉑) und schreibt bei Fehler nichts,
- `update_pause`-Pfad,
- bewusste Lücke: die Factory umgeht `clean()` (darum laufen Overlap-Tests
  über clean/Service, nicht über die Factory) → `bulk_create` für dieses Model
  vermeiden.
"""

from datetime import date
from unittest import mock

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

import pytest

from core.models import TrainingsPause
from core.services import pausen as pausen_service
from core.tests.factories import TrainingsPauseFactory, UserFactory


@pytest.mark.django_db
class TestTrainingsPauseModel:
    """Model-Ebene: Properties, clean(), DB-Constraint."""

    def test_factory_erstellt_pause(self):
        pause = TrainingsPauseFactory()
        assert pause.pk is not None
        assert pause.ist_laufend is False

    def test_ist_laufend_bei_offenem_ende(self):
        pause = TrainingsPauseFactory(end_datum=None)
        assert pause.ist_laufend is True

    def test_grund_key_wird_deutsch_persistiert(self):
        pause = TrainingsPauseFactory(grund=TrainingsPause.Grund.URLAUB)
        pause.refresh_from_db()
        assert pause.grund == "urlaub"  # stabiler DE-Key, nicht der Label-Text

    def test_clean_lehnt_end_vor_start_ab(self):
        user = UserFactory()
        pause = TrainingsPause(
            user=user,
            start_datum=date(2026, 1, 10),
            end_datum=date(2026, 1, 5),
            grund="krankheit",
        )
        with pytest.raises(ValidationError) as exc:
            pause.full_clean()
        assert "end_datum" in exc.value.message_dict

    def test_db_constraint_lehnt_end_vor_start_ab(self):
        """CheckConstraint greift auch, wenn clean() umgangen wird (raw save)."""
        user = UserFactory()
        pause = TrainingsPause(
            user=user,
            start_datum=date(2026, 1, 10),
            end_datum=date(2026, 1, 5),
            grund="krankheit",
        )
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                pause.save()  # umgeht clean() → DB-Constraint muss feuern

    def test_offene_pause_zulaessig(self):
        user = UserFactory()
        pause = pausen_service.create_pause(
            user=user, start_datum=date(2026, 1, 1), end_datum=None, grund="krankheit"
        )
        assert pause.pk is not None
        assert pause.end_datum is None


@pytest.mark.django_db
class TestOverlapValidierung:
    """Overlap-Prädikat über clean() und Service, inkl. NULL-Ende-Zweige (㉓)."""

    def test_overlap_via_clean_abgelehnt(self):
        user = UserFactory()
        TrainingsPauseFactory(user=user, start_datum=date(2026, 1, 1), end_datum=date(2026, 1, 10))
        kollision = TrainingsPause(
            user=user, start_datum=date(2026, 1, 5), end_datum=date(2026, 1, 15), grund="urlaub"
        )
        with pytest.raises(ValidationError):
            kollision.full_clean()

    def test_overlap_via_service_abgelehnt(self):
        user = UserFactory()
        pausen_service.create_pause(
            user=user, start_datum=date(2026, 1, 1), end_datum=date(2026, 1, 10), grund="krankheit"
        )
        with pytest.raises(ValidationError):
            pausen_service.create_pause(
                user=user,
                start_datum=date(2026, 1, 8),
                end_datum=date(2026, 1, 20),
                grund="urlaub",
            )

    def test_nicht_ueberlappende_mehrfachpausen_zulaessig(self):
        user = UserFactory()
        p1 = pausen_service.create_pause(
            user=user, start_datum=date(2026, 1, 1), end_datum=date(2026, 1, 10), grund="krankheit"
        )
        # Tag danach beginnend → kein gemeinsamer Tag → erlaubt
        p2 = pausen_service.create_pause(
            user=user, start_datum=date(2026, 1, 11), end_datum=date(2026, 1, 20), grund="urlaub"
        )
        assert p1.pk != p2.pk
        assert TrainingsPause.objects.filter(user=user).count() == 2

    def test_gemeinsamer_grenztag_ist_overlap(self):
        """Inklusive Range-Semantik: geteilter Grenztag = Overlap."""
        user = UserFactory()
        pausen_service.create_pause(
            user=user, start_datum=date(2026, 1, 1), end_datum=date(2026, 1, 10), grund="krankheit"
        )
        with pytest.raises(ValidationError):
            pausen_service.create_pause(
                user=user,
                start_datum=date(2026, 1, 10),
                end_datum=date(2026, 1, 20),
                grund="urlaub",
            )

    def test_offen_vs_offen_overlap(self):
        """Zwei offene Pausen (+∞) überlappen immer."""
        user = UserFactory()
        pausen_service.create_pause(
            user=user, start_datum=date(2026, 1, 1), end_datum=None, grund="krankheit"
        )
        with pytest.raises(ValidationError):
            pausen_service.create_pause(
                user=user, start_datum=date(2026, 3, 1), end_datum=None, grund="urlaub"
            )

    def test_offen_vs_begrenzt_overlap_bei_spaeterer_begrenzter(self):
        """Bestehende offene Pause ab Jan, neue begrenzte im Feb → Overlap."""
        user = UserFactory()
        pausen_service.create_pause(
            user=user, start_datum=date(2026, 1, 1), end_datum=None, grund="krankheit"
        )
        with pytest.raises(ValidationError):
            pausen_service.create_pause(
                user=user,
                start_datum=date(2026, 2, 1),
                end_datum=date(2026, 2, 10),
                grund="urlaub",
            )

    def test_offen_vs_begrenzt_kein_overlap_wenn_begrenzte_davor_endet(self):
        """Bestehende offene Pause ab Mär, neue begrenzte im Jan (endet davor) → ok."""
        user = UserFactory()
        pausen_service.create_pause(
            user=user, start_datum=date(2026, 3, 1), end_datum=None, grund="krankheit"
        )
        ok = pausen_service.create_pause(
            user=user, start_datum=date(2026, 1, 1), end_datum=date(2026, 1, 10), grund="urlaub"
        )
        assert ok.pk is not None

    def test_neue_offene_vs_bestehende_begrenzte_davor_kein_overlap(self):
        """Neue offene Pause ab Mär, bestehende begrenzte endet im Jan → ok."""
        user = UserFactory()
        pausen_service.create_pause(
            user=user, start_datum=date(2026, 1, 1), end_datum=date(2026, 1, 10), grund="krankheit"
        )
        ok = pausen_service.create_pause(
            user=user, start_datum=date(2026, 3, 1), end_datum=None, grund="urlaub"
        )
        assert ok.pk is not None

    def test_overlap_ist_pro_user(self):
        """Overlap-Check isoliert auf den User – fremde Pausen blocken nicht."""
        user_a = UserFactory()
        user_b = UserFactory()
        pausen_service.create_pause(
            user=user_a,
            start_datum=date(2026, 1, 1),
            end_datum=date(2026, 1, 10),
            grund="krankheit",
        )
        ok = pausen_service.create_pause(
            user=user_b,
            start_datum=date(2026, 1, 1),
            end_datum=date(2026, 1, 10),
            grund="krankheit",
        )
        assert ok.pk is not None


@pytest.mark.django_db
class TestPausenService:
    """Service-Härtung: User-Lock (㉑), Atomarität, Update-Pfad."""

    def test_create_sperrt_user_zeile(self):
        """Vor dem Overlap-Check wird die stabile User-Zeile gesperrt (㉑)."""
        user = UserFactory()
        with mock.patch.object(
            pausen_service, "_lock_user_row", wraps=pausen_service._lock_user_row
        ) as locked:
            pausen_service.create_pause(
                user=user, start_datum=date(2026, 1, 1), end_datum=date(2026, 1, 5), grund="urlaub"
            )
        locked.assert_called_once_with(user.pk)

    def test_overlap_schreibt_nichts(self):
        """Bei Overlap wird die zweite Pause nicht (teilweise) angelegt."""
        user = UserFactory()
        pausen_service.create_pause(
            user=user, start_datum=date(2026, 1, 1), end_datum=date(2026, 1, 10), grund="krankheit"
        )
        with pytest.raises(ValidationError):
            pausen_service.create_pause(
                user=user, start_datum=date(2026, 1, 5), end_datum=date(2026, 1, 8), grund="urlaub"
            )
        assert TrainingsPause.objects.filter(user=user).count() == 1

    def test_update_in_overlap_abgelehnt(self):
        user = UserFactory()
        pausen_service.create_pause(
            user=user, start_datum=date(2026, 1, 1), end_datum=date(2026, 1, 10), grund="krankheit"
        )
        p2 = pausen_service.create_pause(
            user=user, start_datum=date(2026, 2, 1), end_datum=date(2026, 2, 10), grund="urlaub"
        )
        with pytest.raises(ValidationError):
            pausen_service.update_pause(p2, start_datum=date(2026, 1, 5))
        p2.refresh_from_db()
        assert p2.start_datum == date(2026, 2, 1)  # unverändert

    def test_update_setzt_ende_auf_offen(self):
        user = UserFactory()
        p = pausen_service.create_pause(
            user=user, start_datum=date(2026, 1, 1), end_datum=date(2026, 1, 10), grund="krankheit"
        )
        pausen_service.update_pause(p, end_datum=None)
        p.refresh_from_db()
        assert p.end_datum is None

    def test_update_excludet_self_kein_falscher_overlap(self):
        """Eine Pause überlappt sich beim Update nicht mit sich selbst."""
        user = UserFactory()
        p = pausen_service.create_pause(
            user=user, start_datum=date(2026, 1, 1), end_datum=date(2026, 1, 10), grund="krankheit"
        )
        pausen_service.update_pause(p, notiz="aktualisiert", grund="verletzung")
        p.refresh_from_db()
        assert p.notiz == "aktualisiert"
        assert p.grund == "verletzung"


@pytest.mark.django_db
class TestFactoryUmgehtClean:
    """Dokumentierte Lücke: Factory/bulk_create umgehen clean() (Konzept §32.1).

    Darum laufen Validierungs-Tests bewusst über clean()/Service. Dieser Test
    fixiert die Begründung, warum `bulk_create` für dieses Model vermieden wird:
    es würde Overlaps still durchlassen.
    """

    def test_factory_laesst_overlap_durch(self):
        user = UserFactory()
        TrainingsPauseFactory(user=user, start_datum=date(2026, 1, 1), end_datum=date(2026, 1, 10))
        # Kein Fehler – die Factory ruft kein clean() auf:
        TrainingsPauseFactory(user=user, start_datum=date(2026, 1, 5), end_datum=date(2026, 1, 15))
        assert TrainingsPause.objects.filter(user=user).count() == 2
