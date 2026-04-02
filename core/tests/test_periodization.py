"""
Tests für Periodisierungs-Intelligence (Phase 10 + Phase 12).

Testet:
- get_next_block_recommendation() für jeden Block-Typ
- get_block_age_warning() für verschiedene Block-Alter
- Dashboard-Integration (block_age_warning im Context)
- Phase 12: Muskelgruppen-Größenklassifikation, Modus-Profile,
  Volumen-Schwellenwerte, Rep-Range-Klassifikation
"""

from datetime import date, timedelta
from unittest.mock import MagicMock

from django.test import TestCase

from core.models.constants import MUSKELGRUPPEN
from core.utils.periodization import (
    MUSKELGRUPPEN_GROESSE,
    get_block_age_warning,
    get_modus_profil,
    get_next_block_recommendation,
    get_volumen_schwellenwerte,
    klassifiziere_rep_range,
)


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

    def _make_block(self, weeks_ago: int, typ: str = "kraft", plan_dauer_wochen: int | None = None):
        """Erstellt einen Mock-Trainingsblock der vor weeks_ago Wochen gestartet wurde."""
        block = MagicMock()
        block.typ = typ
        block.weeks_since_start = weeks_ago
        block.plan_dauer_wochen = plan_dauer_wochen
        block.warning_threshold_weeks = plan_dauer_wochen if plan_dauer_wochen else 8
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


# ─────────────────────────────────────────────────────────────────────────────
# Phase 12: Kontextsensitive Empfehlungen
# ─────────────────────────────────────────────────────────────────────────────


class TestMuskelgruppenGroesse(TestCase):
    """Tests für MUSKELGRUPPEN_GROESSE Mapping."""

    def test_jede_muskelgruppe_hat_groesse(self):
        """Jede Muskelgruppe aus constants.py muss in MUSKELGRUPPEN_GROESSE enthalten sein."""
        for key, _ in MUSKELGRUPPEN:
            self.assertIn(
                key,
                MUSKELGRUPPEN_GROESSE,
                f"Muskelgruppe '{key}' fehlt in MUSKELGRUPPEN_GROESSE",
            )

    def test_grosse_gruppen(self):
        for key in ["BRUST", "RUECKEN_LAT", "BEINE_QUAD", "BEINE_HAM", "PO"]:
            self.assertEqual(MUSKELGRUPPEN_GROESSE[key], "gross")

    def test_mittlere_gruppen(self):
        for key in ["SCHULTER_VORN", "SCHULTER_SEIT", "TRIZEPS", "BAUCH"]:
            self.assertEqual(MUSKELGRUPPEN_GROESSE[key], "mittel")

    def test_kleine_gruppen(self):
        for key in ["BIZEPS", "WADEN", "UNTERARME"]:
            self.assertEqual(MUSKELGRUPPEN_GROESSE[key], "klein")

    def test_haltungsgruppen(self):
        for key in ["HUEFTBEUGER", "RUECKEN_UNTEN"]:
            self.assertEqual(MUSKELGRUPPEN_GROESSE[key], "haltung")

    def test_ganzkoerper_ist_spezial(self):
        self.assertEqual(MUSKELGRUPPEN_GROESSE["GANZKOERPER"], "spezial")

    def test_nur_bekannte_kategorien(self):
        erlaubte = {"gross", "mittel", "klein", "haltung", "spezial"}
        for key, kategorie in MUSKELGRUPPEN_GROESSE.items():
            self.assertIn(kategorie, erlaubte, f"'{key}' hat unbekannte Kategorie '{kategorie}'")


class TestGetModusProfil(TestCase):
    """Tests für get_modus_profil()."""

    _PFLICHT_KEYS = {
        "label",
        "volumen_empfehlung",
        "rpe_target_range",
        "rpe_zu_niedrig_text",
        "rpe_zu_hoch_text",
        "stagnation_tipp",
        "volumen_faktor",
    }

    def test_masse_profil(self):
        profil = get_modus_profil("masse")
        self.assertEqual(profil["rpe_target_range"], (6.5, 8.5))
        self.assertEqual(profil["volumen_faktor"], 1.0)

    def test_definition_profil(self):
        profil = get_modus_profil("definition")
        self.assertEqual(profil["rpe_target_range"], (7.0, 9.0))
        self.assertEqual(profil["volumen_faktor"], 0.85)

    def test_kraft_profil(self):
        profil = get_modus_profil("kraft")
        self.assertEqual(profil["rpe_target_range"], (7.5, 9.5))
        self.assertEqual(profil["volumen_faktor"], 0.75)

    def test_deload_profil(self):
        profil = get_modus_profil("deload")
        self.assertEqual(profil["rpe_target_range"], (5.0, 7.0))
        self.assertEqual(profil["rpe_zu_niedrig_text"], "")
        self.assertEqual(profil["stagnation_tipp"], "")

    def test_none_gibt_default(self):
        profil = get_modus_profil(None)
        self.assertEqual(profil["rpe_target_range"], (6.0, 9.0))
        self.assertEqual(profil["volumen_faktor"], 1.0)

    def test_unbekannter_typ_gibt_default(self):
        profil = get_modus_profil("gibts_nicht")
        self.assertEqual(profil["label"], "Standard")

    def test_alle_profile_haben_pflicht_keys(self):
        for typ in ["masse", "definition", "kraft", "deload", None, "peaking", "sonstige"]:
            profil = get_modus_profil(typ)
            for key in self._PFLICHT_KEYS:
                self.assertIn(key, profil, f"Profil für '{typ}' fehlt Key '{key}'")


class TestGetVolumenSchwellenwerte(TestCase):
    """Tests für get_volumen_schwellenwerte()."""

    def test_brust_ohne_block(self):
        result = get_volumen_schwellenwerte("BRUST")
        self.assertEqual(result, (12, 25))

    def test_bizeps_ohne_block(self):
        result = get_volumen_schwellenwerte("BIZEPS")
        self.assertEqual(result, (8, 16))

    def test_hueftbeuger_ohne_block(self):
        result = get_volumen_schwellenwerte("HUEFTBEUGER")
        self.assertEqual(result, (6, 12))

    def test_ganzkoerper_gibt_none(self):
        result = get_volumen_schwellenwerte("GANZKOERPER")
        self.assertIsNone(result)

    def test_unbekannte_gruppe_gibt_none(self):
        result = get_volumen_schwellenwerte("GIBTS_NICHT")
        self.assertIsNone(result)

    def test_brust_kraft_block_reduziert(self):
        result = get_volumen_schwellenwerte("BRUST", "kraft")
        # 12 * 0.75 = 9, 25 * 0.75 = 18.75 → 19
        self.assertEqual(result, (9, 19))

    def test_brust_definition_block_reduziert(self):
        result = get_volumen_schwellenwerte("BRUST", "definition")
        # 12 * 0.85 = 10.2 → 10, 25 * 0.85 = 21.25 → 21
        self.assertEqual(result, (10, 21))

    def test_brust_deload_block_stark_reduziert(self):
        result = get_volumen_schwellenwerte("BRUST", "deload")
        # 12 * 0.5 = 6, 25 * 0.5 = 12.5 → 12
        self.assertEqual(result, (6, 12))

    def test_brust_masse_block_unveraendert(self):
        result = get_volumen_schwellenwerte("BRUST", "masse")
        self.assertEqual(result, (12, 25))


class TestKlassifiziereRepRange(TestCase):
    """Tests für klassifiziere_rep_range()."""

    def test_kraft_bereich(self):
        for reps in [1, 3, 5, 6]:
            self.assertEqual(
                klassifiziere_rep_range(reps), "kraft", f"Reps {reps} sollte Kraft sein"
            )

    def test_hypertrophie_bereich(self):
        for reps in [7, 8, 10, 12]:
            self.assertEqual(
                klassifiziere_rep_range(reps),
                "hypertrophie",
                f"Reps {reps} sollte Hypertrophie sein",
            )

    def test_ausdauer_bereich(self):
        for reps in [13, 15, 20, 30]:
            self.assertEqual(
                klassifiziere_rep_range(reps),
                "ausdauer",
                f"Reps {reps} sollte Ausdauer sein",
            )

    def test_grenzwerte(self):
        self.assertEqual(klassifiziere_rep_range(6), "kraft")
        self.assertEqual(klassifiziere_rep_range(7), "hypertrophie")
        self.assertEqual(klassifiziere_rep_range(12), "hypertrophie")
        self.assertEqual(klassifiziere_rep_range(13), "ausdauer")


# ─────────────────────────────────────────────────────────────────────────────
# Phase 17: Plandauer-bezogene Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestBlockAgeWarningWithPlannedDuration(TestCase):
    """Phase 17.4: Block-Alter-Warnung nutzt geplante Dauer statt pauschal 8 Wochen."""

    def _make_block(self, weeks_ago: int, typ: str = "kraft", plan_dauer_wochen: int | None = None):
        block = MagicMock()
        block.typ = typ
        block.weeks_since_start = weeks_ago
        block.plan_dauer_wochen = plan_dauer_wochen
        block.warning_threshold_weeks = plan_dauer_wochen if plan_dauer_wochen else 8
        block.get_typ_display.return_value = "Kraft"
        return block

    def test_6_wochen_plan_warnt_ab_woche_6(self):
        block = self._make_block(weeks_ago=6, plan_dauer_wochen=6)
        warning = get_block_age_warning(block)
        self.assertIsNotNone(warning)
        self.assertEqual(warning["weeks"], 6)

    def test_6_wochen_plan_keine_warnung_bei_woche_5(self):
        block = self._make_block(weeks_ago=5, plan_dauer_wochen=6)
        warning = get_block_age_warning(block)
        self.assertIsNone(warning)

    def test_16_wochen_plan_keine_warnung_bei_woche_15(self):
        block = self._make_block(weeks_ago=15, plan_dauer_wochen=16)
        warning = get_block_age_warning(block)
        self.assertIsNone(warning)

    def test_16_wochen_plan_warnt_ab_woche_16(self):
        block = self._make_block(weeks_ago=16, plan_dauer_wochen=16)
        warning = get_block_age_warning(block)
        self.assertIsNotNone(warning)

    def test_severity_danger_bei_150_prozent_der_plandauer(self):
        # 6 Wochen Plan, danger bei 9 Wochen (6 * 1.5)
        block = self._make_block(weeks_ago=9, plan_dauer_wochen=6)
        warning = get_block_age_warning(block)
        self.assertEqual(warning["severity"], "danger")

    def test_severity_warning_knapp_ueber_threshold(self):
        block = self._make_block(weeks_ago=7, plan_dauer_wochen=6)
        warning = get_block_age_warning(block)
        self.assertEqual(warning["severity"], "warning")

    def test_ohne_plan_dauer_fallback_auf_8_wochen(self):
        block = self._make_block(weeks_ago=7, plan_dauer_wochen=None)
        warning = get_block_age_warning(block)
        self.assertIsNone(warning)

        block2 = self._make_block(weeks_ago=8, plan_dauer_wochen=None)
        warning2 = get_block_age_warning(block2)
        self.assertIsNotNone(warning2)


class TestTrainingsblockPlanDauer(TestCase):
    """Phase 17.4: Trainingsblock-Modell mit plan_dauer_wochen."""

    def test_planned_end_datum_berechnung(self):
        from core.tests.factories import TrainingsblockFactory

        block = TrainingsblockFactory(
            start_datum=date(2026, 1, 1),
            plan_dauer_wochen=8,
        )
        self.assertEqual(block.planned_end_datum, date(2026, 2, 26))

    def test_planned_end_datum_none_wenn_nicht_gesetzt(self):
        from core.tests.factories import TrainingsblockFactory

        block = TrainingsblockFactory(
            start_datum=date(2026, 1, 1),
            plan_dauer_wochen=None,
        )
        self.assertIsNone(block.planned_end_datum)

    def test_warning_threshold_mit_plan_dauer(self):
        from core.tests.factories import TrainingsblockFactory

        block = TrainingsblockFactory(plan_dauer_wochen=10)
        self.assertEqual(block.warning_threshold_weeks, 10)

    def test_warning_threshold_fallback_auf_8(self):
        from core.tests.factories import TrainingsblockFactory

        block = TrainingsblockFactory(plan_dauer_wochen=None)
        self.assertEqual(block.warning_threshold_weeks, 8)
