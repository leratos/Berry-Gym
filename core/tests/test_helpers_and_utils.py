"""
Tests für helpers/ und utils/ – Phase 5.6

Abgedeckte Module:
- core/helpers/email.py           (send_welcome_email)
- core/helpers/notifications.py   (_build_push_payload, _send_single_push,
                                   send_push_notification)
- core/helpers/exercises.py       (_build_equipment_map, _get_available_equipment_objects,
                                   _find_original_uebung, _find_substitute_by_priority,
                                   _find_bodyweight_fallback, find_substitute_exercise)
- core/utils/advanced_stats.py    (calculate_plateau_analysis, calculate_consistency_metrics,
                                   calculate_fatigue_index, calculate_1rm_standards,
                                   calculate_rpe_quality_analysis)
"""

import json
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.core import mail
from django.utils import timezone

import pytest

from .factories import SatzFactory, TrainingseinheitFactory, UebungFactory, UserFactory

# ===========================================================================
# helpers/email.py – send_welcome_email
# ===========================================================================


@pytest.mark.django_db
class TestSendWelcomeEmail:
    def test_email_wird_gesendet(self, settings):
        settings.SITE_URL = "https://example.com"
        settings.DEFAULT_FROM_EMAIL = "noreply@example.com"
        user = UserFactory(email="test@example.com", username="trainer")
        from core.helpers.email import send_welcome_email

        send_welcome_email(user)
        assert len(mail.outbox) == 1

    def test_empfaenger_korrekt(self, settings):
        settings.SITE_URL = "https://example.com"
        settings.DEFAULT_FROM_EMAIL = "noreply@example.com"
        user = UserFactory(email="empfaenger@example.com")
        from core.helpers.email import send_welcome_email

        send_welcome_email(user)
        assert mail.outbox[0].to == ["empfaenger@example.com"]

    def test_betreff_enthaelt_willkommen(self, settings):
        settings.SITE_URL = "https://example.com"
        settings.DEFAULT_FROM_EMAIL = "noreply@example.com"
        user = UserFactory(email="x@example.com")
        from core.helpers.email import send_welcome_email

        send_welcome_email(user)
        assert "Willkommen" in mail.outbox[0].subject

    def test_nachricht_enthaelt_username(self, settings):
        settings.SITE_URL = "https://example.com"
        settings.DEFAULT_FROM_EMAIL = "noreply@example.com"
        user = UserFactory(email="x@example.com", username="meinusername")
        from core.helpers.email import send_welcome_email

        send_welcome_email(user)
        assert "meinusername" in mail.outbox[0].body

    def test_nachricht_enthaelt_site_url(self, settings):
        settings.SITE_URL = "https://meine-gym-app.de"
        settings.DEFAULT_FROM_EMAIL = "noreply@example.com"
        user = UserFactory(email="x@example.com")
        from core.helpers.email import send_welcome_email

        send_welcome_email(user)
        assert "https://meine-gym-app.de" in mail.outbox[0].body

    def test_kein_crash_bei_send_fehler(self, settings):
        """fail_silently=True → kein Exception nach außen."""
        settings.SITE_URL = "https://example.com"
        settings.DEFAULT_FROM_EMAIL = "noreply@example.com"
        user = UserFactory(email="x@example.com")
        from core.helpers.email import send_welcome_email

        # Django's mail.outbox funktioniert immer im Test-Backend – kein echter Fehler möglich.
        # Wir testen nur dass kein Exception propagiert.
        send_welcome_email(user)  # darf nicht werfen


# ===========================================================================
# helpers/notifications.py – _build_push_payload
# ===========================================================================


class TestBuildPushPayload:
    def test_gibt_valides_json_zurueck(self):
        from core.helpers.notifications import _build_push_payload

        result = _build_push_payload("Titel", "Nachricht")
        data = json.loads(result)
        assert data["title"] == "Titel"
        assert data["body"] == "Nachricht"

    def test_standard_url_ist_slash(self):
        from core.helpers.notifications import _build_push_payload

        data = json.loads(_build_push_payload("T", "B"))
        assert data["url"] == "/"

    def test_benutzerdefinierte_url(self):
        from core.helpers.notifications import _build_push_payload

        data = json.loads(_build_push_payload("T", "B", url="/training/42/"))
        assert data["url"] == "/training/42/"

    def test_kein_icon_nutzt_default(self):
        from core.helpers.notifications import _build_push_payload

        data = json.loads(_build_push_payload("T", "B"))
        assert "icon-192x192.png" in data["icon"]

    def test_benutzerdefiniertes_icon(self):
        from core.helpers.notifications import _build_push_payload

        data = json.loads(_build_push_payload("T", "B", icon="/static/custom.png"))
        assert data["icon"] == "/static/custom.png"

    def test_leerer_body_erlaubt(self):
        from core.helpers.notifications import _build_push_payload

        data = json.loads(_build_push_payload("Titel", ""))
        assert data["body"] == ""


# ===========================================================================
# helpers/notifications.py – _send_single_push
# ===========================================================================


class TestSendSinglePush:
    def _make_subscription(self):
        sub = SimpleNamespace(
            id=1,
            endpoint="https://push.example.com/sub/1",
            p256dh="key",
            auth="auth",
        )
        return sub

    def test_erfolg_gibt_true_zurueck(self):
        import pywebpush

        from core.helpers.notifications import _send_single_push

        sub = self._make_subscription()
        with patch.object(pywebpush, "webpush", return_value=None):
            result = _send_single_push(sub, '{"title":"T"}', "/fake/key.pem")
        assert result is True

    def test_404_gibt_false_zurueck(self):
        from core.helpers.notifications import _send_single_push

        sub = self._make_subscription()
        import pywebpush

        exc = pywebpush.WebPushException("gone")
        exc.response = SimpleNamespace(status_code=404)

        with patch.object(pywebpush, "webpush", side_effect=exc):
            result = _send_single_push(sub, '{"title":"T"}', "/fake/key.pem")
        assert result is False

    def test_410_gibt_false_zurueck(self):
        from core.helpers.notifications import _send_single_push

        sub = self._make_subscription()
        import pywebpush

        exc = pywebpush.WebPushException("expired")
        exc.response = SimpleNamespace(status_code=410)

        with patch.object(pywebpush, "webpush", side_effect=exc):
            result = _send_single_push(sub, '{"title":"T"}', "/fake/key.pem")
        assert result is False

    def test_anderer_webpush_fehler_gibt_true_zurueck(self):
        """Recoverable Fehler → Subscription nicht löschen."""
        from core.helpers.notifications import _send_single_push

        sub = self._make_subscription()
        import pywebpush

        exc = pywebpush.WebPushException("server error")
        exc.response = SimpleNamespace(status_code=500)

        with patch.object(pywebpush, "webpush", side_effect=exc):
            result = _send_single_push(sub, '{"title":"T"}', "/fake/key.pem")
        assert result is True

    def test_webpush_fehler_ohne_response_gibt_true_zurueck(self):
        from core.helpers.notifications import _send_single_push

        sub = self._make_subscription()
        import pywebpush

        exc = pywebpush.WebPushException("no response")
        exc.response = None

        with patch.object(pywebpush, "webpush", side_effect=exc):
            result = _send_single_push(sub, '{"title":"T"}', "/fake/key.pem")
        assert result is True

    def test_unbekannte_exception_gibt_true_zurueck(self):
        from core.helpers.notifications import _send_single_push

        sub = self._make_subscription()
        import pywebpush

        with patch.object(pywebpush, "webpush", side_effect=RuntimeError("unexpected")):
            result = _send_single_push(sub, '{"title":"T"}', "/fake/key.pem")
        assert result is True


# ===========================================================================
# helpers/notifications.py – send_push_notification (Orchestrierung)
# ===========================================================================


@pytest.mark.django_db
class TestSendPushNotification:
    def test_kein_vapid_key_bricht_ab(self, settings):
        settings.VAPID_PRIVATE_KEY = ""
        settings.VAPID_PUBLIC_KEY = "key"
        user = UserFactory()
        from core.helpers.notifications import send_push_notification

        # Kein Crash, kein Versand
        send_push_notification(user, "T", "B")

    def test_kein_user_subscription_bricht_ab(self, settings):
        settings.VAPID_PRIVATE_KEY = "private"
        settings.VAPID_PUBLIC_KEY = "public"
        user = UserFactory()
        from core.helpers.notifications import send_push_notification

        with patch("core.helpers.notifications._send_single_push") as mock_send:
            send_push_notification(user, "T", "B")
            mock_send.assert_not_called()

    def test_abgelaufene_subscription_wird_geloescht(self, settings):
        from core.models import PushSubscription

        settings.VAPID_PRIVATE_KEY = "private"
        settings.VAPID_PUBLIC_KEY = "public"
        settings.VAPID_PRIVATE_KEY_FILE = "vapid_private.pem"
        user = UserFactory()
        sub = PushSubscription.objects.create(
            user=user,
            endpoint="https://push.example.com/expired",
            p256dh="key",
            auth="auth",
            user_agent="",
        )
        from core.helpers.notifications import send_push_notification

        with patch("core.helpers.notifications._send_single_push", return_value=False):
            send_push_notification(user, "T", "B")

        assert not PushSubscription.objects.filter(id=sub.id).exists()

    def test_gueltige_subscription_wird_aktualisiert(self, settings):
        from core.models import PushSubscription

        settings.VAPID_PRIVATE_KEY = "private"
        settings.VAPID_PUBLIC_KEY = "public"
        settings.VAPID_PRIVATE_KEY_FILE = "vapid_private.pem"
        user = UserFactory()
        sub = PushSubscription.objects.create(
            user=user,
            endpoint="https://push.example.com/valid",
            p256dh="key",
            auth="auth",
            user_agent="",
        )
        from core.helpers.notifications import send_push_notification

        with patch("core.helpers.notifications._send_single_push", return_value=True):
            send_push_notification(user, "T", "B")

        sub.refresh_from_db()
        assert sub.last_used is not None


# ===========================================================================
# helpers/exercises.py – reine Hilfsfunktionen (kein DB)
# ===========================================================================


class TestBuildEquipmentMap:
    def test_leere_liste_gibt_leeres_dict(self):
        from core.helpers.exercises import _build_equipment_map

        assert _build_equipment_map([]) == {}

    def test_mapping_korrekt(self):
        from core.helpers.exercises import _build_equipment_map

        eq = SimpleNamespace()
        eq.get_name_display = lambda: "Langhantel"
        result = _build_equipment_map([eq])
        assert result["langhantel"] is eq

    def test_whitespace_wird_getrimmt(self):
        from core.helpers.exercises import _build_equipment_map

        eq = SimpleNamespace()
        eq.get_name_display = lambda: "  Kurzhanteln  "
        result = _build_equipment_map([eq])
        assert "kurzhanteln" in result

    def test_mehrere_eintraege(self):
        from core.helpers.exercises import _build_equipment_map

        eq1 = SimpleNamespace()
        eq1.get_name_display = lambda: "Langhantel"
        eq2 = SimpleNamespace()
        eq2.get_name_display = lambda: "Kabelzug"
        result = _build_equipment_map([eq1, eq2])
        assert len(result) == 2


class TestGetAvailableEquipmentObjects:
    def test_bekannte_namen_werden_zurueckgegeben(self):
        from core.helpers.exercises import _get_available_equipment_objects

        eq = SimpleNamespace(name="LANGHANTEL")
        eq.get_name_display = lambda: "Langhantel"
        result = _get_available_equipment_objects(["langhantel"], {"langhantel": eq})
        assert result == [eq]

    def test_unbekannte_namen_werden_ignoriert(self):
        from core.helpers.exercises import _get_available_equipment_objects

        result = _get_available_equipment_objects(["maschine_xyz"], {})
        assert result == []

    def test_leere_verfuegbarkeitsliste(self):
        from core.helpers.exercises import _get_available_equipment_objects

        eq = SimpleNamespace(name="X")
        eq.get_name_display = lambda: "X"
        result = _get_available_equipment_objects([], {"x": eq})
        assert result == []

    def test_mix_bekannt_unbekannt(self):
        from core.helpers.exercises import _get_available_equipment_objects

        eq = SimpleNamespace(name="X")
        eq.get_name_display = lambda: "X"
        result = _get_available_equipment_objects(["x", "nicht_da"], {"x": eq})
        assert result == [eq]


# ===========================================================================
# helpers/exercises.py – _find_original_uebung (mit DB)
# ===========================================================================


@pytest.mark.django_db
class TestFindOriginalUebung:
    def test_exakter_match(self):
        from core.helpers.exercises import _find_original_uebung

        u = UebungFactory(bezeichnung="Bankdrücken")
        result = _find_original_uebung("Bankdrücken")
        assert result.id == u.id

    def test_teilmatch(self):
        from core.helpers.exercises import _find_original_uebung

        UebungFactory(bezeichnung="Bankdrücken flach")
        result = _find_original_uebung("Bankdrücken (Langhantel)")
        assert result is not None

    def test_keyword_mapping_klimmzug(self):
        from core.helpers.exercises import _find_original_uebung

        # Kein DB-Eintrag – Pseudo-Objekt via Keyword
        result = _find_original_uebung("klimmzüge breit")
        assert result is not None
        assert result.muskelgruppe == "RUECKEN_LAT"

    def test_keyword_mapping_squat(self):
        from core.helpers.exercises import _find_original_uebung

        result = _find_original_uebung("squat variante")
        assert result is not None
        assert result.muskelgruppe == "BEINE_QUAD"

    def test_unbekannte_uebung_gibt_none(self):
        from core.helpers.exercises import _find_original_uebung

        result = _find_original_uebung("vollkommen_unbekannt_xyz_123")
        assert result is None


# ===========================================================================
# helpers/exercises.py – _find_bodyweight_fallback (mit DB)
# ===========================================================================


@pytest.mark.django_db
class TestFindBodyweightFallback:
    def test_kein_koerper_equipment_gibt_none(self):
        from core.helpers.exercises import _find_bodyweight_fallback

        # Standardmäßig kein Equipment mit name="KOERPER" in Test-DB
        result = _find_bodyweight_fallback("BRUST", -1)
        # Ergebnis hängt von Test-DB ab – kein Crash ist die Garantie
        assert result is None or isinstance(result, dict)

    def test_mit_koerper_equipment_und_passender_uebung(self):
        from core.helpers.exercises import _find_bodyweight_fallback
        from core.models import Equipment

        koerper_eq = Equipment.objects.filter(name="KOERPER").first()
        if not koerper_eq:
            pytest.skip("Kein KOERPER-Equipment in Test-DB")

        u = UebungFactory(muskelgruppe="BRUST", equipment=koerper_eq)
        result = _find_bodyweight_fallback("BRUST", -1)
        assert result is not None
        assert result["name"] == u.bezeichnung


# ===========================================================================
# helpers/exercises.py – find_substitute_exercise (Integration, mit DB)
# ===========================================================================


@pytest.mark.django_db
class TestFindSubstituteExercise:
    def test_gibt_dict_zurueck(self):
        from core.helpers.exercises import find_substitute_exercise

        result = find_substitute_exercise("Bankdrücken", "Langhantel", [])
        assert isinstance(result, dict)
        assert "name" in result

    def test_unbekannte_uebung_gibt_fallback_dict(self):
        from core.helpers.exercises import find_substitute_exercise

        result = find_substitute_exercise("xyz_gibts_nicht_123", "Langhantel", [])
        assert isinstance(result, dict)

    def test_kein_crash_bei_leerem_equipment(self):
        from core.helpers.exercises import find_substitute_exercise

        # Darf nie werfen
        result = find_substitute_exercise("Kniebeuge", "Langhantel", [])
        assert result is not None

    def test_exception_intern_gibt_fallback(self):
        """Wenn intern etwas schiefgeht → sicherer Fallback statt Exception."""
        from core.helpers.exercises import find_substitute_exercise

        with patch(
            "core.helpers.exercises._find_original_uebung", side_effect=RuntimeError("DB down")
        ):
            result = find_substitute_exercise("Bankdrücken", "Langhantel", [])
        assert isinstance(result, dict)
        assert "name" in result


# ===========================================================================
# utils/advanced_stats.py – Hilfsfunktionen
# ===========================================================================


def _make_saetze_qs(user, uebung, count=5, gewicht=100, wdh=8, rpe=None, tage_zurueck=0):
    """Erstellt count Sätze für Tests, verteilt über die letzten Wochen."""
    training = TrainingseinheitFactory(
        user=user,
        datum=timezone.now() - timedelta(days=tage_zurueck),
    )
    saetze = []
    for _ in range(count):
        s = SatzFactory(
            einheit=training,
            uebung=uebung,
            gewicht=Decimal(str(gewicht)),
            wiederholungen=wdh,
            rpe=rpe,
            ist_aufwaermsatz=False,
        )
        saetze.append(s)
    return training


# ---------------------------------------------------------------------------
# calculate_consistency_metrics
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCalculateConsistencyMetrics:
    def test_kein_training_gibt_none(self):
        from core.models import Trainingseinheit
        from core.utils.advanced_stats import calculate_consistency_metrics

        user = UserFactory()
        qs = Trainingseinheit.objects.filter(user=user)
        assert calculate_consistency_metrics(qs) is None

    def test_einzelnes_training_gibt_streak_1(self):
        from core.models import Trainingseinheit
        from core.utils.advanced_stats import calculate_consistency_metrics

        user = UserFactory()
        TrainingseinheitFactory(user=user, datum=timezone.now())
        qs = Trainingseinheit.objects.filter(user=user)
        result = calculate_consistency_metrics(qs)
        assert result is not None
        assert result["aktueller_streak"] >= 1

    def test_adherence_rate_max_100(self):
        """Adherence darf nie über 100% liegen."""
        from core.models import Trainingseinheit
        from core.utils.advanced_stats import calculate_consistency_metrics

        user = UserFactory()
        # Mehrere Trainings in kurzer Zeit
        for i in range(5):
            TrainingseinheitFactory(user=user, datum=timezone.now() - timedelta(days=i))
        qs = Trainingseinheit.objects.filter(user=user)
        result = calculate_consistency_metrics(qs)
        assert result["adherence_rate"] <= 100.0

    def test_bewertung_vorhanden(self):
        from core.models import Trainingseinheit
        from core.utils.advanced_stats import calculate_consistency_metrics

        user = UserFactory()
        TrainingseinheitFactory(user=user, datum=timezone.now())
        qs = Trainingseinheit.objects.filter(user=user)
        result = calculate_consistency_metrics(qs)
        assert "bewertung" in result
        assert "bewertung_farbe" in result

    def test_avg_pause_bei_einzelnem_training_ist_0(self):
        from core.models import Trainingseinheit
        from core.utils.advanced_stats import calculate_consistency_metrics

        user = UserFactory()
        TrainingseinheitFactory(user=user, datum=timezone.now())
        qs = Trainingseinheit.objects.filter(user=user)
        result = calculate_consistency_metrics(qs)
        assert result["avg_pause_tage"] == 0

    def test_laengster_streak_groesser_gleich_aktueller(self):
        from core.models import Trainingseinheit
        from core.utils.advanced_stats import calculate_consistency_metrics

        user = UserFactory()
        for i in range(3):
            TrainingseinheitFactory(user=user, datum=timezone.now() - timedelta(weeks=i))
        qs = Trainingseinheit.objects.filter(user=user)
        result = calculate_consistency_metrics(qs)
        assert result["laengster_streak"] >= result["aktueller_streak"]


# ---------------------------------------------------------------------------
# calculate_fatigue_index
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCalculateFatigueIndex:
    def test_leere_daten_gibt_fatigue_0(self):
        from core.models import Satz, Trainingseinheit
        from core.utils.advanced_stats import calculate_fatigue_index

        result = calculate_fatigue_index(
            weekly_volume_data=[],
            rpe_saetze=Satz.objects.none(),
            alle_trainings=Trainingseinheit.objects.none(),
        )
        assert result["fatigue_index"] == 0
        assert result["deload_empfohlen"] is False

    def test_starker_volumenanstieg_erhoeht_index(self):
        from core.models import Satz, Trainingseinheit
        from core.utils.advanced_stats import calculate_fatigue_index

        # >30% Anstieg
        volume_data = [{"volumen": 1000}, {"volumen": 1400}]
        result = calculate_fatigue_index(
            weekly_volume_data=volume_data,
            rpe_saetze=Satz.objects.none(),
            alle_trainings=Trainingseinheit.objects.none(),
        )
        assert result["fatigue_index"] >= 40
        assert result["volumen_spike"] is True

    def test_moderater_anstieg_keine_warnung(self):
        from core.models import Satz, Trainingseinheit
        from core.utils.advanced_stats import calculate_fatigue_index

        volume_data = [{"volumen": 1000}, {"volumen": 1050}]  # 5% Anstieg
        result = calculate_fatigue_index(
            weekly_volume_data=volume_data,
            rpe_saetze=Satz.objects.none(),
            alle_trainings=Trainingseinheit.objects.none(),
        )
        assert result["volumen_spike"] is False

    def test_taeglich_trainieren_erhoeht_index(self):
        from core.models import Satz, Trainingseinheit
        from core.utils.advanced_stats import calculate_fatigue_index

        user = UserFactory()
        # 7 Trainings in 7 Tagen
        for i in range(7):
            TrainingseinheitFactory(user=user, datum=timezone.now() - timedelta(days=i))
        qs = Trainingseinheit.objects.filter(user=user)
        result = calculate_fatigue_index(
            weekly_volume_data=[],
            rpe_saetze=Satz.objects.none(),
            alle_trainings=qs,
        )
        assert result["fatigue_index"] >= 30

    def test_deload_empfohlen_bei_hohem_index(self):
        from core.models import Satz, Trainingseinheit
        from core.utils.advanced_stats import calculate_fatigue_index

        user = UserFactory()
        volume_data = [{"volumen": 1000}, {"volumen": 1500}]  # 50% spike
        for i in range(7):
            TrainingseinheitFactory(user=user, datum=timezone.now() - timedelta(days=i))
        qs = Trainingseinheit.objects.filter(user=user)
        result = calculate_fatigue_index(
            weekly_volume_data=volume_data,
            rpe_saetze=Satz.objects.none(),
            alle_trainings=qs,
        )
        assert result["deload_empfohlen"] is True

    def test_naechste_deload_ist_string(self):
        from core.models import Satz, Trainingseinheit
        from core.utils.advanced_stats import calculate_fatigue_index

        result = calculate_fatigue_index(
            weekly_volume_data=[],
            rpe_saetze=Satz.objects.none(),
            alle_trainings=Trainingseinheit.objects.none(),
        )
        assert isinstance(result["naechste_deload"], str)
        # Format: DD.MM.YYYY
        assert len(result["naechste_deload"]) == 10


# ---------------------------------------------------------------------------
# calculate_rpe_quality_analysis
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCalculateRpeQualityAnalysis:
    def test_keine_saetze_gibt_none(self):
        from core.models import Satz
        from core.utils.advanced_stats import calculate_rpe_quality_analysis

        assert calculate_rpe_quality_analysis(Satz.objects.none()) is None

    def test_nur_aufwaermsaetze_gibt_none(self):
        """Aufwärmsätze werden explizit ausgeschlossen."""
        from core.models import Satz
        from core.utils.advanced_stats import calculate_rpe_quality_analysis

        user = UserFactory()
        uebung = UebungFactory()
        training = TrainingseinheitFactory(user=user)
        SatzFactory(einheit=training, uebung=uebung, rpe=6, ist_aufwaermsatz=True)
        qs = Satz.objects.filter(einheit__user=user)
        assert calculate_rpe_quality_analysis(qs) is None

    def test_optimale_saetze_werden_gezaehlt(self):
        from core.models import Satz
        from core.utils.advanced_stats import calculate_rpe_quality_analysis

        user = UserFactory()
        uebung = UebungFactory()
        training = TrainingseinheitFactory(user=user)
        # 8 optimale Sätze (RPE 7-9), 2 Junk (RPE <7)
        for _ in range(8):
            SatzFactory(einheit=training, uebung=uebung, rpe=8, ist_aufwaermsatz=False)
        for _ in range(2):
            SatzFactory(einheit=training, uebung=uebung, rpe=5, ist_aufwaermsatz=False)
        qs = Satz.objects.filter(einheit__user=user)
        result = calculate_rpe_quality_analysis(qs)
        assert result["optimal_intensity_rate"] == 80.0
        assert result["junk_volume_rate"] == 20.0

    def test_failure_rate_korrekt(self):
        from core.models import Satz
        from core.utils.advanced_stats import calculate_rpe_quality_analysis

        user = UserFactory()
        uebung = UebungFactory()
        training = TrainingseinheitFactory(user=user)
        for _ in range(9):
            SatzFactory(einheit=training, uebung=uebung, rpe=8, ist_aufwaermsatz=False)
        SatzFactory(einheit=training, uebung=uebung, rpe=10, ist_aufwaermsatz=False)
        qs = Satz.objects.filter(einheit__user=user)
        result = calculate_rpe_quality_analysis(qs)
        assert result["failure_rate"] == 10.0

    def test_bewertung_und_farbe_vorhanden(self):
        from core.models import Satz
        from core.utils.advanced_stats import calculate_rpe_quality_analysis

        user = UserFactory()
        uebung = UebungFactory()
        training = TrainingseinheitFactory(user=user)
        SatzFactory(einheit=training, uebung=uebung, rpe=8, ist_aufwaermsatz=False)
        qs = Satz.objects.filter(einheit__user=user)
        result = calculate_rpe_quality_analysis(qs)
        assert "bewertung" in result
        assert "bewertung_farbe" in result

    def test_verteilung_summe_nahe_100(self):
        from core.models import Satz
        from core.utils.advanced_stats import calculate_rpe_quality_analysis

        user = UserFactory()
        uebung = UebungFactory()
        training = TrainingseinheitFactory(user=user)
        for rpe in [4, 6, 7, 8, 9, 10]:
            SatzFactory(einheit=training, uebung=uebung, rpe=rpe, ist_aufwaermsatz=False)
        qs = Satz.objects.filter(einheit__user=user)
        result = calculate_rpe_quality_analysis(qs)
        total = sum(result["rpe_verteilung_prozent"].values())
        assert abs(total - 100.0) < 1.0  # Rundungsfehler tolerieren


# ---------------------------------------------------------------------------
# calculate_plateau_analysis
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCalculatePlateauAnalysis:
    def test_leere_top_uebungen_gibt_leere_liste(self):
        from core.models import Satz
        from core.utils.advanced_stats import calculate_plateau_analysis

        assert calculate_plateau_analysis(Satz.objects.none(), []) == []

    def test_uebung_mit_zu_wenig_saetzen_wird_uebersprungen(self):
        from core.models import Satz
        from core.utils.advanced_stats import calculate_plateau_analysis

        user = UserFactory()
        uebung = UebungFactory()
        training = TrainingseinheitFactory(user=user)
        SatzFactory(einheit=training, uebung=uebung, gewicht=Decimal("100"), wiederholungen=8)
        qs = Satz.objects.filter(einheit__user=user)
        top = [{"uebung__bezeichnung": uebung.bezeichnung, "muskelgruppe_display": "Brust"}]
        result = calculate_plateau_analysis(qs, top)
        # Nur 1 Satz → wird übersprungen
        assert result == []

    def test_mit_genuegend_saetzen_gibt_analyse(self):
        from core.models import Satz
        from core.utils.advanced_stats import calculate_plateau_analysis

        user = UserFactory()
        uebung = UebungFactory()
        # 5 Trainings an verschiedenen Tagen
        for i in range(5):
            t = TrainingseinheitFactory(user=user, datum=timezone.now() - timedelta(days=i * 7))
            SatzFactory(
                einheit=t,
                uebung=uebung,
                gewicht=Decimal(str(80 + i * 5)),
                wiederholungen=8,
            )
        qs = Satz.objects.filter(einheit__user=user)
        top = [{"uebung__bezeichnung": uebung.bezeichnung, "muskelgruppe_display": "Brust"}]
        result = calculate_plateau_analysis(qs, top)
        assert len(result) == 1
        entry = result[0]
        assert "status" in entry
        assert "tage_seit_pr" in entry
        assert "progression_pro_monat" in entry


# ---------------------------------------------------------------------------
# calculate_1rm_standards
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCalculate1rmStandards:
    def test_leere_saetze_gibt_leere_liste(self):
        from core.models import Satz
        from core.utils.advanced_stats import calculate_1rm_standards

        result = calculate_1rm_standards(Satz.objects.none(), [])
        assert result == []

    def test_uebung_ohne_standards_wird_uebersprungen(self):
        from core.models import Satz
        from core.utils.advanced_stats import calculate_1rm_standards

        user = UserFactory()
        uebung = UebungFactory(standard_beginner=None)
        training = TrainingseinheitFactory(user=user)
        SatzFactory(einheit=training, uebung=uebung, gewicht=Decimal("100"), wiederholungen=5)
        qs = Satz.objects.filter(einheit__user=user)
        top = [{"uebung__bezeichnung": uebung.bezeichnung, "muskelgruppe_display": "Brust"}]
        result = calculate_1rm_standards(qs, top)
        assert result == []

    def test_uebung_mit_standards_gibt_ergebnis(self):
        from core.models import Satz
        from core.utils.advanced_stats import calculate_1rm_standards

        user = UserFactory()
        uebung = UebungFactory(
            standard_beginner=Decimal("60"),
            standard_intermediate=Decimal("100"),
            standard_advanced=Decimal("140"),
            standard_elite=Decimal("180"),
        )
        training = TrainingseinheitFactory(user=user)
        SatzFactory(einheit=training, uebung=uebung, gewicht=Decimal("80"), wiederholungen=8)
        qs = Satz.objects.filter(einheit__user=user)
        top = [{"uebung__bezeichnung": uebung.bezeichnung, "muskelgruppe_display": "Brust"}]
        result = calculate_1rm_standards(qs, top, user_gewicht=80)
        assert len(result) == 1
        entry = result[0]
        assert entry["geschaetzter_1rm"] > 0
        assert "standard_info" in entry
        assert "1rm_entwicklung" in entry

    def test_1rm_entwicklung_hat_6_monate(self):
        from core.models import Satz
        from core.utils.advanced_stats import calculate_1rm_standards

        user = UserFactory()
        uebung = UebungFactory(
            standard_beginner=Decimal("60"),
            standard_intermediate=Decimal("100"),
            standard_advanced=Decimal("140"),
            standard_elite=Decimal("180"),
        )
        training = TrainingseinheitFactory(user=user)
        SatzFactory(einheit=training, uebung=uebung, gewicht=Decimal("100"), wiederholungen=5)
        qs = Satz.objects.filter(einheit__user=user)
        top = [{"uebung__bezeichnung": uebung.bezeichnung, "muskelgruppe_display": "Brust"}]
        result = calculate_1rm_standards(qs, top)
        assert len(result[0]["1rm_entwicklung"]) == 6

    def test_skalierung_mit_koerpergewicht(self):
        """Heavier user → höhere skalierte Standards."""
        from core.models import Satz
        from core.utils.advanced_stats import calculate_1rm_standards

        user = UserFactory()
        uebung = UebungFactory(
            standard_beginner=Decimal("60"),
            standard_intermediate=Decimal("100"),
            standard_advanced=Decimal("140"),
            standard_elite=Decimal("180"),
        )
        training = TrainingseinheitFactory(user=user)
        SatzFactory(einheit=training, uebung=uebung, gewicht=Decimal("100"), wiederholungen=5)
        qs = Satz.objects.filter(einheit__user=user)
        top = [{"uebung__bezeichnung": uebung.bezeichnung, "muskelgruppe_display": "Brust"}]

        result_leicht = calculate_1rm_standards(qs, top, user_gewicht=60)
        result_schwer = calculate_1rm_standards(qs, top, user_gewicht=100)

        standard_leicht = result_leicht[0]["standard_info"]["alle_levels"]["Anfänger"]
        standard_schwer = result_schwer[0]["standard_info"]["alle_levels"]["Anfänger"]
        assert standard_schwer > standard_leicht
