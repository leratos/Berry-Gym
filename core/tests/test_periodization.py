"""
Tests für Phase 10 – Periodisierungs-Intelligence.

Testet:
- get_next_block_recommendation() für jeden Block-Typ
- get_block_age_warning() für verschiedene Block-Alter
- Dashboard-Integration (block_age_warning im Context)
"""

from datetime import date, timedelta
from unittest.mock import MagicMock

from django.test import TestCase

from core.utils.periodization import get_block_age_warning, get_next_block_recommendation


class TestGetNextBlockRecommendation(TestCase):
    """Tests für get_next_block_recommendation()."""

    def test_kraft_empfiehlt_hypertrophie_primary(self):
        rec = get_next_block_recommendation("kraft")
        self.assertEqual(rec["primary"]["typ"], "masse")
        self.assertEqual(rec["primary"]["target_profile"], "hypertrophie")

    def test_kraft_alternative_ist_definition(self):
        rec = get_next_block_recommendation("kraft")
        self.assertEqual(rec["alternative"]["typ"], "definition")
        self.assertEqual(rec["alternative"]["target_profile"], "definition")

    def test_masse_empfiehlt_kraft_primary(self):
        rec = get_next_block_recommendation("masse")
        self.assertEqual(rec["primary"]["typ"], "kraft")
        self.assertEqual(rec["primary"]["target_profile"], "kraft")

    def test_definition_empfiehlt_masse_primary(self):
        rec = get_next_block_recommendation("definition")
        self.assertEqual(rec["primary"]["typ"], "masse")
        self.assertEqual(rec["primary"]["target_profile"], "hypertrophie")

    def test_peaking_empfiehlt_deload_primary(self):
        rec = get_next_block_recommendation("peaking")
        self.assertEqual(rec["primary"]["typ"], "deload")
        self.assertIsNone(rec["primary"]["target_profile"])

    def test_deload_empfiehlt_masse_primary(self):
        rec = get_next_block_recommendation("deload")
        self.assertEqual(rec["primary"]["typ"], "masse")
        self.assertEqual(rec["primary"]["target_profile"], "hypertrophie")

    def test_sonstige_empfiehlt_masse_primary(self):
        rec = get_next_block_recommendation("sonstige")
        self.assertEqual(rec["primary"]["typ"], "masse")

    def test_unbekannter_typ_faellt_auf_sonstige(self):
        rec = get_next_block_recommendation("gibts_nicht")
        self.assertEqual(rec["primary"]["typ"], "masse")

    def test_jeder_typ_hat_primary_und_alternative(self):
        """Sicherstellen dass kein Typ im Mapping fehlt."""
        from core.models.training import Trainingsblock

        for typ_key, _ in Trainingsblock.BLOCK_TYP_CHOICES:
            rec = get_next_block_recommendation(typ_key)
            self.assertIn("primary", rec, f"Typ '{typ_key}' hat kein primary")
            self.assertIn("alternative", rec, f"Typ '{typ_key}' hat kein alternative")
            self.assertIn("typ", rec["primary"])
            self.assertIn("label", rec["primary"])
            self.assertIn("reason", rec["primary"])

    def test_primary_reason_ist_nicht_leer(self):
        """Begründungen sollten substanziell sein."""
        from core.models.training import Trainingsblock

        for typ_key, _ in Trainingsblock.BLOCK_TYP_CHOICES:
            rec = get_next_block_recommendation(typ_key)
            self.assertGreater(
                len(rec["primary"]["reason"]),
                20,
                f"Typ '{typ_key}' primary reason zu kurz",
            )


class TestGetBlockAgeWarning(TestCase):
    """Tests für get_block_age_warning()."""

    def _make_block(self, weeks_ago: int, typ: str = "kraft"):
        """Erstellt einen Mock-Trainingsblock der vor weeks_ago Wochen gestartet wurde."""
        block = MagicMock()
        block.typ = typ
        block.weeks_since_start = weeks_ago
        block.get_typ_display.return_value = dict(
            kraft="Kraft",
            masse="Masseaufbau",
            definition="Definition / Hypertrophie",
            peaking="Peaking / Wettkampf",
            deload="Deload-Block",
            sonstige="Sonstige",
        ).get(typ, typ)
        return block

    def test_kein_block_gibt_none(self):
        self.assertIsNone(get_block_age_warning(None))

    def test_block_unter_8_wochen_gibt_none(self):
        block = self._make_block(weeks_ago=7)
        self.assertIsNone(get_block_age_warning(block))

    def test_block_genau_8_wochen_gibt_warnung(self):
        block = self._make_block(weeks_ago=8, typ="kraft")
        warning = get_block_age_warning(block)
        self.assertIsNotNone(warning)
        self.assertEqual(warning["weeks"], 8)
        self.assertEqual(warning["severity"], "warning")
        self.assertEqual(warning["block_type_display"], "Kraft")
        self.assertEqual(warning["recommendation"]["typ"], "masse")

    def test_block_12_wochen_severity_danger(self):
        block = self._make_block(weeks_ago=12, typ="masse")
        warning = get_block_age_warning(block)
        self.assertIsNotNone(warning)
        self.assertEqual(warning["severity"], "danger")

    def test_block_9_wochen_severity_warning(self):
        block = self._make_block(weeks_ago=9, typ="definition")
        warning = get_block_age_warning(block)
        self.assertEqual(warning["severity"], "warning")

    def test_peaking_block_empfiehlt_deload(self):
        block = self._make_block(weeks_ago=10, typ="peaking")
        warning = get_block_age_warning(block)
        self.assertEqual(warning["recommendation"]["typ"], "deload")
        self.assertIsNone(warning["recommendation"]["target_profile"])

    def test_deload_block_empfiehlt_masse(self):
        block = self._make_block(weeks_ago=8, typ="deload")
        warning = get_block_age_warning(block)
        self.assertEqual(warning["recommendation"]["typ"], "masse")
        self.assertEqual(warning["recommendation"]["target_profile"], "hypertrophie")

    def test_block_type_display_wird_durchgereicht(self):
        block = self._make_block(weeks_ago=10, typ="masse")
        warning = get_block_age_warning(block)
        self.assertEqual(warning["block_type_display"], "Masseaufbau")


class TestDashboardBlockAgeIntegration(TestCase):
    """Integrationstests: block_age_warning im Dashboard-Context."""

    def setUp(self):
        from django.contrib.auth.models import User
        from django.core.cache import cache

        cache.clear()
        self.user = User.objects.create_user(username="testuser_phase10", password="testpass123")
        self.client.login(username="testuser_phase10", password="testpass123")

    def test_dashboard_ohne_block_kein_warning(self):
        """Dashboard ohne aktiven Trainingsblock → kein block_age_warning."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context.get("block_age_warning"))

    def test_dashboard_mit_jungem_block_kein_warning(self):
        """Block < 8 Wochen → kein block_age_warning."""
        from core.models import Trainingsblock

        Trainingsblock.objects.create(
            user=self.user,
            typ="kraft",
            start_datum=date.today() - timedelta(weeks=5),
        )
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context.get("block_age_warning"))

    def test_dashboard_mit_altem_block_hat_warning(self):
        """Block >= 8 Wochen → block_age_warning vorhanden."""
        from core.models import Trainingsblock

        Trainingsblock.objects.create(
            user=self.user,
            typ="kraft",
            start_datum=date.today() - timedelta(weeks=9),
        )
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        warning = response.context.get("block_age_warning")
        self.assertIsNotNone(warning)
        self.assertEqual(warning["recommendation"]["typ"], "masse")

    def test_dashboard_template_rendert_warnung(self):
        """Block-Alter-Warnung wird im HTML gerendert."""
        from django.core.cache import cache

        from core.models import Trainingsblock

        cache.clear()
        Trainingsblock.objects.create(
            user=self.user,
            typ="kraft",
            start_datum=date.today() - timedelta(weeks=10),
        )
        response = self.client.get("/")
        content = response.content.decode()
        # Prüfe auf den spezifischen Warnungstext (nicht nur das Icon)
        self.assertIn("läuft seit", content)
        self.assertIn("Hypertrophie", content)

    def test_dashboard_template_kein_warning_html_ohne_block(self):
        """Ohne Block kein Warning-HTML."""
        from django.core.cache import cache

        cache.clear()
        response = self.client.get("/")
        content = response.content.decode()
        self.assertNotIn("läuft seit", content)
