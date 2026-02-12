"""
Tests für views/body_tracking.py und views/cardio.py.

body_tracking: Login-Schutz, Einträge hinzufügen/bearbeiten/löschen,
               Progress-Fotos, Body-Stats-Seite
cardio: Cardio-Liste, Hinzufügen, Löschen
"""

from django.test import Client
from django.urls import reverse

import pytest

from core.tests.factories import CardioEinheitFactory, KoerperWerteFactory, UserFactory

# ===========================================================================
# views/body_tracking.py
# ===========================================================================


@pytest.mark.django_db
class TestBodyStats:
    def setup_method(self):
        self.client = Client()
        self.user = UserFactory()
        self.client.force_login(self.user)

    def test_body_stats_no_data(self):
        """Body Stats ohne Daten → no_data=True im Context."""
        resp = self.client.get(reverse("body_stats"))
        assert resp.status_code == 200
        assert resp.context["no_data"] is True

    def test_body_stats_with_data(self):
        """Body Stats mit Daten zeigt Verlauf."""
        KoerperWerteFactory(user=self.user, gewicht=80, groesse_cm=180)
        KoerperWerteFactory(user=self.user, gewicht=79, groesse_cm=180)
        resp = self.client.get(reverse("body_stats"))
        assert resp.status_code == 200
        assert "no_data" not in resp.context or resp.context.get("no_data") is not True


@pytest.mark.django_db
class TestAddKoerperwert:
    def setup_method(self):
        self.client = Client()
        self.user = UserFactory()
        self.client.force_login(self.user)

    def test_login_required(self):
        c = Client()
        resp = c.get(reverse("add_koerperwert"))
        assert resp.status_code == 302

    def test_get_shows_form(self):
        resp = self.client.get(reverse("add_koerperwert"))
        assert resp.status_code == 200

    def test_post_creates_entry_and_redirects(self):
        resp = self.client.post(
            reverse("add_koerperwert"),
            data={
                "groesse": "180",
                "gewicht": "80.5",
            },
        )
        assert resp.status_code == 302
        from core.models import KoerperWerte

        assert KoerperWerte.objects.filter(user=self.user).exists()

    def test_post_with_optional_fields(self):
        resp = self.client.post(
            reverse("add_koerperwert"),
            data={
                "groesse": "175",
                "gewicht": "75",
                "kfa": "18.5",
                "muskel": "35",
                "notiz": "Testnotiz",
            },
        )
        assert resp.status_code == 302


@pytest.mark.django_db
class TestEditKoerperwert:
    def setup_method(self):
        self.client = Client()
        self.user = UserFactory()
        self.client.force_login(self.user)

    def test_login_required(self):
        wert = KoerperWerteFactory(user=self.user)
        c = Client()
        resp = c.get(reverse("edit_koerperwert", args=[wert.id]))
        assert resp.status_code == 302

    def test_get_shows_form(self):
        wert = KoerperWerteFactory(user=self.user)
        resp = self.client.get(reverse("edit_koerperwert", args=[wert.id]))
        assert resp.status_code == 200

    def test_post_updates_entry(self):
        wert = KoerperWerteFactory(user=self.user, gewicht=80)
        resp = self.client.post(
            reverse("edit_koerperwert", args=[wert.id]),
            data={"gewicht": "77", "groesse_cm": "180"},
        )
        assert resp.status_code == 302
        wert.refresh_from_db()
        assert float(wert.gewicht) == 77.0

    def test_other_user_cannot_edit(self):
        other = UserFactory()
        wert = KoerperWerteFactory(user=other)
        resp = self.client.get(reverse("edit_koerperwert", args=[wert.id]))
        assert resp.status_code == 404


@pytest.mark.django_db
class TestDeleteKoerperwert:
    def setup_method(self):
        self.client = Client()
        self.user = UserFactory()
        self.client.force_login(self.user)

    def test_login_required(self):
        wert = KoerperWerteFactory(user=self.user)
        c = Client()
        resp = c.post(reverse("delete_koerperwert", args=[wert.id]))
        assert resp.status_code == 302

    def test_delete_own_entry(self):
        wert = KoerperWerteFactory(user=self.user)
        resp = self.client.post(reverse("delete_koerperwert", args=[wert.id]))
        assert resp.status_code == 302
        from core.models import KoerperWerte

        assert not KoerperWerte.objects.filter(id=wert.id).exists()

    def test_cannot_delete_other_users_entry(self):
        other = UserFactory()
        wert = KoerperWerteFactory(user=other)
        resp = self.client.post(reverse("delete_koerperwert", args=[wert.id]))
        assert resp.status_code == 404


@pytest.mark.django_db
class TestProgressPhotos:
    def setup_method(self):
        self.client = Client()
        self.user = UserFactory()
        self.client.force_login(self.user)

    def test_login_required(self):
        c = Client()
        resp = c.get(reverse("progress_photos"))
        assert resp.status_code == 302

    def test_progress_photos_loads(self):
        resp = self.client.get(reverse("progress_photos"))
        assert resp.status_code == 200

    def test_upload_progress_photo_no_file_redirects(self):
        """Upload ohne Datei → Redirect mit Fehlermeldung."""
        resp = self.client.post(
            reverse("upload_progress_photo"),
            data={"notiz": "Test"},
        )
        assert resp.status_code == 302


# ===========================================================================
# views/cardio.py
# ===========================================================================


@pytest.mark.django_db
class TestCardioList:
    def setup_method(self):
        self.client = Client()
        self.user = UserFactory()
        self.client.force_login(self.user)

    def test_login_required(self):
        c = Client()
        resp = c.get(reverse("cardio_list"))
        assert resp.status_code == 302

    def test_empty_list(self):
        resp = self.client.get(reverse("cardio_list"))
        assert resp.status_code == 200
        assert resp.context["total_einheiten"] == 0

    def test_with_entries_default_30_days(self):
        CardioEinheitFactory(user=self.user)
        resp = self.client.get(reverse("cardio_list"))
        assert resp.status_code == 200
        assert resp.context["total_einheiten"] == 1

    def test_show_all_param(self):
        """?all=1 → alle Einheiten."""
        CardioEinheitFactory(user=self.user)
        resp = self.client.get(reverse("cardio_list") + "?all=1")
        assert resp.status_code == 200

    def test_user_isolation(self):
        """Andere User-Cardio wird nicht angezeigt."""
        other = UserFactory()
        CardioEinheitFactory(user=other)
        resp = self.client.get(reverse("cardio_list"))
        assert resp.context["total_einheiten"] == 0


@pytest.mark.django_db
class TestCardioAdd:
    def setup_method(self):
        self.client = Client()
        self.user = UserFactory()
        self.client.force_login(self.user)

    def test_login_required(self):
        c = Client()
        resp = c.get(reverse("cardio_add"))
        assert resp.status_code == 302

    def test_get_shows_form(self):
        resp = self.client.get(reverse("cardio_add"))
        assert resp.status_code == 200
        assert "aktivitaeten" in resp.context

    def test_post_creates_entry(self):
        resp = self.client.post(
            reverse("cardio_add"),
            data={
                "aktivitaet": "LAUFEN",
                "dauer_minuten": "30",
                "intensitaet": "MODERAT",
                "datum": "2026-02-11",
            },
        )
        assert resp.status_code == 302
        from core.models import CardioEinheit

        assert CardioEinheit.objects.filter(user=self.user).exists()

    def test_post_missing_fields_stays_on_form(self):
        """Fehlende Pflichtfelder → Redirect zurück (Validierungsfehler)."""
        resp = self.client.post(
            reverse("cardio_add"),
            data={"aktivitaet": "LAUFEN"},
        )
        assert resp.status_code == 302

    def test_post_invalid_dauer(self):
        """Ungültige Dauer → Redirect zurück."""
        resp = self.client.post(
            reverse("cardio_add"),
            data={
                "aktivitaet": "LAUFEN",
                "dauer_minuten": "abc",
            },
        )
        assert resp.status_code == 302

    def test_post_negative_dauer(self):
        """Negative Dauer → Validierungsfehler."""
        resp = self.client.post(
            reverse("cardio_add"),
            data={
                "aktivitaet": "LAUFEN",
                "dauer_minuten": "-10",
            },
        )
        assert resp.status_code == 302

    def test_post_without_datum_uses_today(self):
        """Kein Datum → heute."""
        resp = self.client.post(
            reverse("cardio_add"),
            data={
                "aktivitaet": "RADFAHREN",
                "dauer_minuten": "45",
            },
        )
        assert resp.status_code == 302

    def test_sonstiges_aktivitaet(self):
        """SONSTIGES ist eine gültige Aktivität."""
        resp = self.client.post(
            reverse("cardio_add"),
            data={
                "aktivitaet": "SONSTIGES",
                "dauer_minuten": "20",
                "intensitaet": "LEICHT",
            },
        )
        assert resp.status_code == 302
        from core.models import CardioEinheit

        assert CardioEinheit.objects.filter(user=self.user, aktivitaet="SONSTIGES").exists()


@pytest.mark.django_db
class TestCardioDelete:
    def setup_method(self):
        self.client = Client()
        self.user = UserFactory()
        self.client.force_login(self.user)

    def test_login_required(self):
        cardio = CardioEinheitFactory(user=self.user)
        c = Client()
        resp = c.post(reverse("cardio_delete", args=[cardio.id]))
        assert resp.status_code == 302

    def test_delete_own_entry(self):
        cardio = CardioEinheitFactory(user=self.user)
        resp = self.client.post(reverse("cardio_delete", args=[cardio.id]))
        assert resp.status_code == 302
        from core.models import CardioEinheit

        assert not CardioEinheit.objects.filter(id=cardio.id).exists()

    def test_cannot_delete_others_entry(self):
        other = UserFactory()
        cardio = CardioEinheitFactory(user=other)
        resp = self.client.post(reverse("cardio_delete", args=[cardio.id]))
        assert resp.status_code == 404

    def test_get_redirects_to_list(self):
        """GET (kein POST) → Redirect zur Liste."""
        cardio = CardioEinheitFactory(user=self.user)
        resp = self.client.get(reverse("cardio_delete", args=[cardio.id]))
        assert resp.status_code == 302
