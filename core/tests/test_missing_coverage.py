"""
Tests für bisher nicht abgedeckte Modell-Methoden und View-Logik.

Abdeckung:
- SiteSettings: Singleton-Verhalten (load, save, delete, __str__)
- Feedback: get_status_badge_class() für alle Status-Werte
- PushSubscription: __str__()
- CardioEinheit: ermuedungs_punkte bei unbekannter Intensität (Fallback)
- config.get_last_set: Progressive-Overload-Logik (alle 4 Branches)
- cardio_list / cardio_add / cardio_delete View-Endpunkte
- onboarding Views: mark_onboarding_complete, restart_onboarding
- sources_list: Kategorie-Filterung und Context-Aufbau
- notifications: subscribe_push, unsubscribe_push, get_vapid_public_key
"""

import json
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from core.models import CardioEinheit, Feedback, PushSubscription, SiteSettings, TrainingSource
from core.tests.factories import (
    CardioEinheitFactory,
    SatzFactory,
    TrainingsblockFactory,
    TrainingseinheitFactory,
    UebungFactory,
    UserFactory,
)


# ===========================================================================
# SiteSettings – Singleton-Pattern
# ===========================================================================


@pytest.mark.django_db
class TestSiteSettingsSingleton:
    """Tests für das Singleton-Pattern von SiteSettings."""

    def test_load_erstellt_instanz_beim_ersten_aufruf(self):
        """SiteSettings.load() erstellt bei leerem DB eine Instanz."""
        SiteSettings.objects.all().delete()
        assert SiteSettings.objects.count() == 0
        instance = SiteSettings.load()
        assert instance is not None
        assert SiteSettings.objects.count() == 1

    def test_load_gibt_gleiche_instanz_zurueck(self):
        """Zweimaliger Aufruf von load() liefert dasselbe Objekt (pk=1)."""
        first = SiteSettings.load()
        second = SiteSettings.load()
        assert first.pk == second.pk == 1

    def test_save_erzwingt_pk_1(self):
        """save() setzt pk immer auf 1 – verhindert mehrere Instanzen."""
        settings = SiteSettings(
            ai_limit_plan_generation=5,
            ai_limit_live_guidance=20,
            ai_limit_analysis=8,
        )
        settings.pk = 999  # Explizit falschen PK setzen
        settings.save()
        assert settings.pk == 1
        assert SiteSettings.objects.count() == 1

    def test_delete_loescht_nicht(self):
        """delete() entfernt die Singleton-Instanz NICHT aus der DB."""
        instance = SiteSettings.load()
        assert SiteSettings.objects.count() == 1
        instance.delete()
        # Instanz sollte nach delete() immer noch in der DB sein
        assert SiteSettings.objects.count() == 1

    def test_str_gibt_lesbaren_namen_zurueck(self):
        """__str__() gibt den erwarteten String zurück."""
        instance = SiteSettings.load()
        assert str(instance) == "Site-Einstellungen (KI-Limits)"

    def test_standardwerte_sind_korrekt(self):
        """Neue Instanz hat die erwarteten Default-Limits."""
        SiteSettings.objects.all().delete()
        instance = SiteSettings.load()
        assert instance.ai_limit_plan_generation == 3
        assert instance.ai_limit_live_guidance == 50
        assert instance.ai_limit_analysis == 10

    def test_limits_koennen_geaendert_werden(self):
        """Limits lassen sich überschreiben und persistieren."""
        instance = SiteSettings.load()
        instance.ai_limit_plan_generation = 10
        instance.save()

        reloaded = SiteSettings.load()
        assert reloaded.ai_limit_plan_generation == 10


# ===========================================================================
# Feedback – get_status_badge_class
# ===========================================================================


@pytest.mark.django_db
class TestFeedbackModel:
    """Tests für das Feedback-Model, insbesondere get_status_badge_class."""

    def _create_feedback(self, status="NEW"):
        user = UserFactory()
        return Feedback.objects.create(
            user=user,
            feedback_type="FEATURE",
            title="Test Feedback",
            description="Test Beschreibung",
            status=status,
        )

    def test_badge_klasse_new(self):
        """Status NEW → bg-info."""
        fb = self._create_feedback(status="NEW")
        assert fb.get_status_badge_class() == "bg-info"

    def test_badge_klasse_accepted(self):
        """Status ACCEPTED → bg-success."""
        fb = self._create_feedback(status="ACCEPTED")
        assert fb.get_status_badge_class() == "bg-success"

    def test_badge_klasse_rejected(self):
        """Status REJECTED → bg-danger."""
        fb = self._create_feedback(status="REJECTED")
        assert fb.get_status_badge_class() == "bg-danger"

    def test_badge_klasse_in_progress(self):
        """Status IN_PROGRESS → bg-warning text-dark."""
        fb = self._create_feedback(status="IN_PROGRESS")
        assert fb.get_status_badge_class() == "bg-warning text-dark"

    def test_badge_klasse_done(self):
        """Status DONE → bg-primary."""
        fb = self._create_feedback(status="DONE")
        assert fb.get_status_badge_class() == "bg-primary"

    def test_badge_klasse_unbekannter_status(self):
        """Unbekannter Status → Fallback bg-secondary."""
        fb = self._create_feedback(status="NEW")
        fb.status = "UNBEKANNT"  # Nicht in der DB speichern, nur im Objekt
        assert fb.get_status_badge_class() == "bg-secondary"

    def test_str_representation(self):
        """__str__() enthält Typ, Titel und Username."""
        user = UserFactory(username="feedback_user")
        fb = Feedback.objects.create(
            user=user,
            feedback_type="BUG",
            title="Login kaputt",
            description="Ich kann mich nicht einloggen.",
            status="NEW",
        )
        result = str(fb)
        assert "Login kaputt" in result
        assert "feedback_user" in result

    def test_default_feedback_type_ist_feature(self):
        """Neues Feedback hat standardmäßig feedback_type=FEATURE."""
        user = UserFactory()
        fb = Feedback.objects.create(
            user=user,
            title="Neues Feature",
            description="Wäre cool wenn...",
        )
        assert fb.feedback_type == "FEATURE"

    def test_default_status_ist_new(self):
        """Neues Feedback hat standardmäßig status=NEW."""
        user = UserFactory()
        fb = Feedback.objects.create(
            user=user,
            title="Test",
            description="Test",
        )
        assert fb.status == "NEW"


# ===========================================================================
# PushSubscription – __str__
# ===========================================================================


@pytest.mark.django_db
class TestPushSubscriptionModel:
    """Tests für das PushSubscription-Model."""

    def test_str_enthaelt_username_und_user_agent(self):
        """__str__() enthält Username und (gekürzten) User-Agent."""
        user = UserFactory(username="push_user")
        sub = PushSubscription.objects.create(
            user=user,
            endpoint="https://push.example.com/sub/abc123",
            p256dh="testkey",
            auth="testauth",
            user_agent="Mozilla/5.0 Chrome/120",
        )
        result = str(sub)
        assert "push_user" in result
        assert "Mozilla" in result or "Chrome" in result

    def test_str_kuerzt_langen_user_agent(self):
        """__str__() kürzt User-Agent auf 50 Zeichen."""
        user = UserFactory(username="long_ua_user")
        langer_ua = "A" * 200
        sub = PushSubscription.objects.create(
            user=user,
            endpoint="https://push.example.com/sub/xyz",
            p256dh="key",
            auth="auth",
            user_agent=langer_ua,
        )
        result = str(sub)
        # Der User-Agent-Teil (nach dem Username und " - ") sollte max 50 Zeichen sein
        ua_part = result.split(" - ", 1)[1] if " - " in result else result
        assert len(ua_part) <= 50

    def test_default_notification_flags(self):
        """Neue Subscription hat alle Benachrichtigungs-Flags auf True."""
        user = UserFactory()
        sub = PushSubscription.objects.create(
            user=user,
            endpoint="https://push.example.com/sub/default",
            p256dh="key",
            auth="auth",
        )
        assert sub.training_reminders is True
        assert sub.rest_day_reminders is True
        assert sub.achievement_notifications is True

    def test_update_or_create_aktualisiert_bestehende_subscription(self):
        """update_or_create mit gleicher endpoint aktualisiert den Eintrag."""
        user = UserFactory()
        endpoint = "https://push.example.com/sub/update_test"
        PushSubscription.objects.create(
            user=user,
            endpoint=endpoint,
            p256dh="old_key",
            auth="old_auth",
        )
        obj, created = PushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={"user": user, "p256dh": "new_key", "auth": "new_auth"},
        )
        assert not created
        assert obj.p256dh == "new_key"
        assert PushSubscription.objects.filter(endpoint=endpoint).count() == 1


# ===========================================================================
# CardioEinheit – ermuedungs_punkte Fallback
# ===========================================================================


@pytest.mark.django_db
class TestCardioEinheitErmuedungsFallback:
    """Zusätzlicher Test für die ermuedungs_punkte-Eigenschaft."""

    def test_unbekannte_intensitaet_nutzt_fallback_koeffizient(self):
        """Unbekannte Intensität nutzt den Fallback-Koeffizient 0.15."""
        user = UserFactory()
        cardio = CardioEinheit.objects.create(
            user=user,
            datum=timezone.now().date(),
            aktivitaet="LAUFEN",
            dauer_minuten=100,
            intensitaet="UNBEKANNT",  # Nicht in CARDIO_INTENSITAET
        )
        # Fallback: 100 * 0.15 = 15.0
        assert cardio.ermuedungs_punkte == 15.0

    def test_ermuedungs_punkte_leicht(self):
        """Intensität LEICHT: Koeffizient 0.1."""
        user = UserFactory()
        cardio = CardioEinheitFactory(user=user, intensitaet="LEICHT", dauer_minuten=60)
        assert cardio.ermuedungs_punkte == 6.0

    def test_ermuedungs_punkte_moderat(self):
        """Intensität MODERAT: Koeffizient 0.2."""
        user = UserFactory()
        cardio = CardioEinheitFactory(user=user, intensitaet="MODERAT", dauer_minuten=60)
        assert cardio.ermuedungs_punkte == 12.0

    def test_ermuedungs_punkte_intensiv(self):
        """Intensität INTENSIV: Koeffizient 0.4."""
        user = UserFactory()
        cardio = CardioEinheitFactory(user=user, intensitaet="INTENSIV", dauer_minuten=60)
        assert cardio.ermuedungs_punkte == 24.0


# ===========================================================================
# config.get_last_set – Progressive-Overload-Logik
# ===========================================================================


@pytest.mark.django_db
class TestGetLastSetApi:
    """Tests für die get_last_set API (Progressive Overload Logik)."""

    def setup_method(self):
        self.client = Client()
        self.user = UserFactory()
        self.client.force_login(self.user)
        self.uebung = UebungFactory()
        self.einheit = TrainingseinheitFactory(user=self.user)

    def _url(self, ziel=None):
        url = reverse("get_last_set", args=[self.uebung.id])
        if ziel:
            url += f"?ziel={ziel}"
        return url

    def test_kein_satz_vorhanden_gibt_success_false(self):
        """Ohne vorherigen Satz: success=False."""
        resp = self.client.get(self._url())
        assert resp.status_code == 200
        assert resp.json()["success"] is False

    def test_aufwaermsatz_wird_ignoriert(self):
        """Aufwärmsätze werden nicht als letzter Satz gewertet."""
        SatzFactory(
            einheit=self.einheit,
            uebung=self.uebung,
            ist_aufwaermsatz=True,
            gewicht=Decimal("40.0"),
        )
        resp = self.client.get(self._url())
        assert resp.json()["success"] is False

    def test_letzter_satz_wird_zurueckgegeben(self):
        """Vorhandener Satz liefert Gewicht und Wiederholungen zurück."""
        SatzFactory(
            einheit=self.einheit,
            uebung=self.uebung,
            ist_aufwaermsatz=False,
            gewicht=Decimal("80.0"),
            wiederholungen=8,
            rpe=Decimal("7.5"),
        )
        resp = self.client.get(self._url())
        data = resp.json()
        assert data["success"] is True
        assert data["letztes_gewicht"] == 80.0
        assert data["letzte_wdh"] == 8

    def test_progression_bei_niedriger_rpe(self):
        """RPE < 7 → Gewicht um 2,5 kg erhöhen."""
        SatzFactory(
            einheit=self.einheit,
            uebung=self.uebung,
            ist_aufwaermsatz=False,
            gewicht=Decimal("80.0"),
            wiederholungen=8,
            rpe=Decimal("6.5"),  # RPE < 7
        )
        resp = self.client.get(self._url())
        data = resp.json()
        assert data["gewicht"] == 82.5  # +2.5kg
        assert "+2.5kg" in data["progression_hint"]

    def test_progression_bei_ziel_wdh_erreicht(self):
        """Obere Zielgrenze erreicht → +2,5 kg, Wdh auf Minimum."""
        SatzFactory(
            einheit=self.einheit,
            uebung=self.uebung,
            ist_aufwaermsatz=False,
            gewicht=Decimal("80.0"),
            wiederholungen=12,  # Obere Grenze bei Ziel 8-12
            rpe=Decimal("7.5"),
        )
        resp = self.client.get(self._url(ziel="8-12"))
        data = resp.json()
        assert data["gewicht"] == 82.5  # +2.5kg
        assert data["wiederholungen"] == 8  # Zurück auf Minimum
        assert "+2.5kg" in data["progression_hint"]

    def test_progression_bei_hoher_rpe(self):
        """RPE >= 9 → Wiederholungen erhöhen, kein Gewichtssprung."""
        SatzFactory(
            einheit=self.einheit,
            uebung=self.uebung,
            ist_aufwaermsatz=False,
            gewicht=Decimal("80.0"),
            wiederholungen=8,
            rpe=Decimal("9.0"),  # Hoch
        )
        resp = self.client.get(self._url(ziel="8-12"))
        data = resp.json()
        assert data["gewicht"] == 80.0  # Kein Gewichtssprung
        assert data["wiederholungen"] == 9  # +1 Wdh
        assert "Wiederholungen" in data["progression_hint"]

    def test_progression_normal_bereich(self):
        """Mittlere RPE und Wdh im Bereich → Hinweis zum Halten."""
        SatzFactory(
            einheit=self.einheit,
            uebung=self.uebung,
            ist_aufwaermsatz=False,
            gewicht=Decimal("80.0"),
            wiederholungen=9,
            rpe=Decimal("8.0"),  # Zwischen 7 und 9
        )
        resp = self.client.get(self._url(ziel="8-12"))
        data = resp.json()
        assert data["gewicht"] == 80.0
        assert data["wiederholungen"] == 9
        assert "Halte" in data["progression_hint"] or "steigere" in data["progression_hint"]

    def test_ziel_als_einzelwert(self):
        """Ziel als einzelne Zahl (kein Bindestrich) wird verarbeitet."""
        SatzFactory(
            einheit=self.einheit,
            uebung=self.uebung,
            ist_aufwaermsatz=False,
            gewicht=Decimal("80.0"),
            wiederholungen=5,
            rpe=Decimal("7.0"),
        )
        resp = self.client.get(self._url(ziel="5"))
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_ziel_ungueltig_fallback_8_12(self):
        """Ungültiges Ziel-Format → Fallback auf 8-12."""
        SatzFactory(
            einheit=self.einheit,
            uebung=self.uebung,
            ist_aufwaermsatz=False,
            gewicht=Decimal("80.0"),
            wiederholungen=8,
            rpe=Decimal("8.0"),
        )
        resp = self.client.get(self._url(ziel="ungueltig"))
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_login_required(self):
        """Ohne Login → Redirect zur Login-Seite."""
        c = Client()
        resp = c.get(reverse("get_last_set", args=[self.uebung.id]))
        assert resp.status_code == 302


# ===========================================================================
# cardio Views
# ===========================================================================


@pytest.mark.django_db
class TestCardioListView:
    """Tests für die Cardio-Liste."""

    def setup_method(self):
        self.client = Client()
        self.user = UserFactory()
        self.client.force_login(self.user)

    def test_login_required(self):
        """Nicht eingeloggt → Redirect."""
        c = Client()
        resp = c.get(reverse("cardio_list"))
        assert resp.status_code == 302

    def test_leere_liste_rendert_korrekt(self):
        """Leere Cardio-Liste → HTTP 200, total_minuten=0."""
        resp = self.client.get(reverse("cardio_list"))
        assert resp.status_code == 200
        assert resp.context["total_minuten"] == 0
        assert resp.context["total_einheiten"] == 0

    def test_eintraege_der_letzten_30_tage_werden_angezeigt(self):
        """Einträge aus den letzten 30 Tagen erscheinen in der Standardansicht."""
        CardioEinheitFactory(user=self.user, dauer_minuten=45, datum=timezone.now().date())
        resp = self.client.get(reverse("cardio_list"))
        assert resp.context["total_einheiten"] == 1
        assert resp.context["total_minuten"] == 45

    def test_alte_eintraege_werden_ohne_show_all_ausgeblendet(self):
        """Einträge älter als 30 Tage erscheinen nicht ohne ?all=1."""
        alter_tag = timezone.now().date() - timedelta(days=40)
        CardioEinheitFactory(user=self.user, dauer_minuten=30, datum=alter_tag)
        resp = self.client.get(reverse("cardio_list"))
        assert resp.context["total_einheiten"] == 0

    def test_show_all_zeigt_alle_eintraege(self):
        """?all=1 zeigt auch Einträge älter als 30 Tage."""
        alter_tag = timezone.now().date() - timedelta(days=40)
        CardioEinheitFactory(user=self.user, dauer_minuten=30, datum=alter_tag)
        resp = self.client.get(reverse("cardio_list") + "?all=1")
        assert resp.context["total_einheiten"] == 1

    def test_eintraege_anderer_user_werden_nicht_angezeigt(self):
        """Einträge fremder User sind nicht sichtbar."""
        anderer_user = UserFactory()
        CardioEinheitFactory(user=anderer_user, dauer_minuten=60)
        resp = self.client.get(reverse("cardio_list"))
        assert resp.context["total_einheiten"] == 0


@pytest.mark.django_db
class TestCardioAddView:
    """Tests für das Hinzufügen von Cardio-Einträgen."""

    def setup_method(self):
        self.client = Client()
        self.user = UserFactory()
        self.client.force_login(self.user)

    def test_get_zeigt_formular(self):
        """GET liefert das Formular."""
        resp = self.client.get(reverse("cardio_add"))
        assert resp.status_code == 200
        assert "aktivitaeten" in resp.context

    def test_post_erstellt_eintrag_und_leitet_weiter(self):
        """Gültiges POST erstellt einen Eintrag und leitet zur Liste weiter."""
        resp = self.client.post(
            reverse("cardio_add"),
            {
                "aktivitaet": "LAUFEN",
                "dauer_minuten": "30",
                "intensitaet": "MODERAT",
                "notiz": "Morgenrunde",
                "datum": date.today().isoformat(),
            },
        )
        assert resp.status_code == 302
        assert CardioEinheit.objects.filter(user=self.user, aktivitaet="LAUFEN").exists()

    def test_post_ohne_aktivitaet_gibt_fehlermeldung(self):
        """POST ohne Aktivität → Redirect zurück mit Fehlermeldung."""
        resp = self.client.post(
            reverse("cardio_add"),
            {"dauer_minuten": "30"},
        )
        assert resp.status_code == 302
        assert CardioEinheit.objects.filter(user=self.user).count() == 0

    def test_post_mit_ungültiger_dauer_gibt_fehlermeldung(self):
        """POST mit ungültiger Dauer → Redirect zurück mit Fehlermeldung."""
        resp = self.client.post(
            reverse("cardio_add"),
            {"aktivitaet": "LAUFEN", "dauer_minuten": "abc"},
        )
        assert resp.status_code == 302
        assert CardioEinheit.objects.filter(user=self.user).count() == 0

    def test_post_mit_negativer_dauer_gibt_fehlermeldung(self):
        """POST mit Dauer <= 0 → Redirect zurück mit Fehlermeldung."""
        resp = self.client.post(
            reverse("cardio_add"),
            {"aktivitaet": "LAUFEN", "dauer_minuten": "0"},
        )
        assert resp.status_code == 302
        assert CardioEinheit.objects.filter(user=self.user).count() == 0

    def test_post_mit_ungueltigem_datum_nutzt_heute(self):
        """POST mit ungültigem Datum-Format → nutzt Tagesdatum als Fallback."""
        resp = self.client.post(
            reverse("cardio_add"),
            {
                "aktivitaet": "LAUFEN",
                "dauer_minuten": "30",
                "intensitaet": "MODERAT",
                "datum": "nicht-ein-datum",
            },
        )
        assert resp.status_code == 302
        eintrag = CardioEinheit.objects.filter(user=self.user).first()
        assert eintrag is not None
        assert eintrag.datum == date.today()

    def test_post_ohne_datum_nutzt_heute(self):
        """POST ohne Datum-Feld → nutzt Tagesdatum."""
        resp = self.client.post(
            reverse("cardio_add"),
            {"aktivitaet": "LAUFEN", "dauer_minuten": "45", "intensitaet": "LEICHT"},
        )
        assert resp.status_code == 302
        eintrag = CardioEinheit.objects.filter(user=self.user).first()
        assert eintrag is not None
        assert eintrag.datum == date.today()

    def test_login_required(self):
        """Nicht eingeloggt → Redirect."""
        c = Client()
        resp = c.post(
            reverse("cardio_add"),
            {"aktivitaet": "LAUFEN", "dauer_minuten": "30"},
        )
        assert resp.status_code == 302


@pytest.mark.django_db
class TestCardioDeleteView:
    """Tests für das Löschen von Cardio-Einträgen."""

    def setup_method(self):
        self.client = Client()
        self.user = UserFactory()
        self.client.force_login(self.user)

    def test_post_loescht_eigenen_eintrag(self):
        """POST löscht den eigenen Eintrag."""
        cardio = CardioEinheitFactory(user=self.user)
        resp = self.client.post(reverse("cardio_delete", args=[cardio.id]))
        assert resp.status_code == 302
        assert not CardioEinheit.objects.filter(id=cardio.id).exists()

    def test_fremden_eintrag_loeschen_gibt_404(self):
        """Fremden Eintrag löschen → 404."""
        anderer_user = UserFactory()
        fremde_cardio = CardioEinheitFactory(user=anderer_user)
        resp = self.client.post(reverse("cardio_delete", args=[fremde_cardio.id]))
        assert resp.status_code == 404
        assert CardioEinheit.objects.filter(id=fremde_cardio.id).exists()

    def test_get_auf_delete_leitet_zur_liste_weiter(self):
        """GET auf Delete-URL leitet zur Liste weiter (keine Bestätigungsseite)."""
        cardio = CardioEinheitFactory(user=self.user)
        resp = self.client.get(reverse("cardio_delete", args=[cardio.id]))
        assert resp.status_code == 302


# ===========================================================================
# onboarding Views
# ===========================================================================


@pytest.mark.django_db
class TestMarkOnboardingComplete:
    """Tests für den mark_onboarding_complete Endpunkt."""

    def setup_method(self):
        self.client = Client()
        self.user = UserFactory()
        self.client.force_login(self.user)

    def test_post_markiert_onboarding_als_abgeschlossen(self):
        """POST setzt has_seen_onboarding=True."""
        assert not self.user.profile.has_seen_onboarding
        resp = self.client.post(reverse("mark_onboarding_complete"))
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        self.user.profile.refresh_from_db()
        assert self.user.profile.has_seen_onboarding is True

    def test_nur_post_erlaubt(self):
        """GET ist nicht erlaubt (require_POST)."""
        resp = self.client.get(reverse("mark_onboarding_complete"))
        assert resp.status_code == 405

    def test_login_required(self):
        """Ohne Login → Redirect."""
        c = Client()
        resp = c.post(reverse("mark_onboarding_complete"))
        assert resp.status_code == 302

    def test_fehler_gibt_500(self):
        """Exception beim Speichern → HTTP 500, success=False."""
        with patch.object(
            type(self.user.profile), "save", side_effect=Exception("DB-Fehler")
        ):
            resp = self.client.post(reverse("mark_onboarding_complete"))
        assert resp.status_code == 500
        assert resp.json()["success"] is False


@pytest.mark.django_db
class TestRestartOnboarding:
    """Tests für den restart_onboarding Endpunkt."""

    def setup_method(self):
        self.client = Client()
        self.user = UserFactory()
        self.client.force_login(self.user)
        self.user.profile.has_seen_onboarding = True
        self.user.profile.save()

    def test_ajax_setzt_onboarding_zurueck(self):
        """AJAX GET setzt has_seen_onboarding=False zurück."""
        resp = self.client.get(
            reverse("restart_onboarding"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        self.user.profile.refresh_from_db()
        assert self.user.profile.has_seen_onboarding is False

    def test_normaler_request_leitet_zum_dashboard(self):
        """Normaler GET leitet zum Dashboard weiter."""
        resp = self.client.get(reverse("restart_onboarding"))
        assert resp.status_code == 302
        self.user.profile.refresh_from_db()
        assert self.user.profile.has_seen_onboarding is False

    def test_login_required(self):
        """Ohne Login → Redirect."""
        c = Client()
        resp = c.get(reverse("restart_onboarding"))
        assert resp.status_code == 302

    def test_ajax_fehler_gibt_500(self):
        """AJAX-Request bei Exception → HTTP 500, success=False."""
        with patch.object(
            type(self.user.profile), "save", side_effect=Exception("DB-Fehler")
        ):
            resp = self.client.get(
                reverse("restart_onboarding"),
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
        assert resp.status_code == 500
        assert resp.json()["success"] is False


# ===========================================================================
# sources_list View
# ===========================================================================


@pytest.mark.django_db
class TestSourcesListView:
    """Tests für die öffentliche Quellen-Liste."""

    def _source(self, category="VOLUME", is_active=True, **kwargs):
        return TrainingSource.objects.create(
            category=category,
            title=kwargs.get("title", f"Quelle {category}"),
            authors=kwargs.get("authors", "Autor, A."),
            year=kwargs.get("year", 2020),
            is_active=is_active,
        )

    def test_seite_ohne_login_erreichbar(self, client):
        """Quellen-Seite ist öffentlich ohne Login zugänglich."""
        resp = client.get(reverse("sources_list"))
        assert resp.status_code == 200

    def test_nur_aktive_quellen_werden_angezeigt(self, client):
        """Inaktive Quellen erscheinen nicht."""
        self._source(category="VOLUME", is_active=True, title="Aktiv")
        self._source(category="INTENSITY", is_active=False, title="Inaktiv")
        resp = client.get(reverse("sources_list"))
        quellen = list(resp.context["quellen"])
        titles = [q.title for q in quellen]
        assert "Aktiv" in titles
        assert "Inaktiv" not in titles

    def test_kategorie_filter_schraenkt_ergebnisse_ein(self, client):
        """?category=VOLUME zeigt nur VOLUME-Quellen."""
        self._source(category="VOLUME", title="Vol Quelle")
        self._source(category="INTENSITY", title="Int Quelle")
        resp = client.get(reverse("sources_list") + "?category=VOLUME")
        quellen = list(resp.context["quellen"])
        assert all(q.category == "VOLUME" for q in quellen)

    def test_gesamt_count_entspricht_allen_aktiven_quellen(self, client):
        """gesamt_count zählt alle aktiven Quellen unabhängig vom Filter."""
        self._source(category="VOLUME")
        self._source(category="INTENSITY")
        resp = client.get(reverse("sources_list") + "?category=VOLUME")
        assert resp.context["gesamt_count"] == 2

    def test_kategorien_liste_im_context(self, client):
        """kategorien-Liste enthält Kategorie-Objekte mit key/label/count."""
        self._source(category="VOLUME")
        resp = client.get(reverse("sources_list"))
        kategorien = resp.context["kategorien"]
        assert isinstance(kategorien, list)
        assert len(kategorien) >= 1
        assert "key" in kategorien[0]
        assert "count" in kategorien[0]

    def test_selected_label_ohne_filter(self, client):
        """Ohne Filter: selected_label = 'Alle Quellen'."""
        resp = client.get(reverse("sources_list"))
        assert resp.context["selected_label"] == "Alle Quellen"


# ===========================================================================
# Push-Notification Views
# ===========================================================================


@pytest.mark.django_db
class TestPushNotificationViews:
    """Tests für Subscribe, Unsubscribe und VAPID-Key-Endpunkte."""

    def setup_method(self):
        self.client = Client()
        self.user = UserFactory()
        self.client.force_login(self.user)

    def _subscription_payload(self, endpoint="https://push.example.com/sub/test"):
        return {
            "subscription": {
                "endpoint": endpoint,
                "keys": {"p256dh": "fake_p256dh_key", "auth": "fake_auth_key"},
            }
        }

    def test_subscribe_erstellt_neue_subscription(self):
        """POST mit gültigen Daten → neue PushSubscription wird angelegt."""
        resp = self.client.post(
            reverse("subscribe_push"),
            data=json.dumps(self._subscription_payload()),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert PushSubscription.objects.filter(user=self.user).exists()

    def test_subscribe_aktualisiert_bestehende_subscription(self):
        """Gleicher Endpoint → Update, kein Duplikat."""
        endpoint = "https://push.example.com/sub/update"
        PushSubscription.objects.create(
            user=self.user,
            endpoint=endpoint,
            p256dh="old_key",
            auth="old_auth",
        )
        resp = self.client.post(
            reverse("subscribe_push"),
            data=json.dumps(self._subscription_payload(endpoint=endpoint)),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert PushSubscription.objects.filter(endpoint=endpoint).count() == 1

    def test_subscribe_ohne_subscription_daten_gibt_400(self):
        """POST ohne 'subscription' Key → 400."""
        resp = self.client.post(
            reverse("subscribe_push"),
            data=json.dumps({"kein_subscription_key": True}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_subscribe_login_required(self):
        """Ohne Login → Redirect."""
        c = Client()
        resp = c.post(
            reverse("subscribe_push"),
            data=json.dumps(self._subscription_payload()),
            content_type="application/json",
        )
        assert resp.status_code == 302

    def test_unsubscribe_loescht_subscription(self):
        """POST mit endpoint → PushSubscription wird gelöscht."""
        endpoint = "https://push.example.com/sub/delete"
        PushSubscription.objects.create(
            user=self.user,
            endpoint=endpoint,
            p256dh="key",
            auth="auth",
        )
        resp = self.client.post(
            reverse("unsubscribe_push"),
            data=json.dumps({"endpoint": endpoint}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert not PushSubscription.objects.filter(endpoint=endpoint).exists()

    def test_unsubscribe_ohne_endpoint_gibt_400(self):
        """POST ohne 'endpoint' Key → 400."""
        resp = self.client.post(
            reverse("unsubscribe_push"),
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_unsubscribe_nicht_vorhandener_endpoint_gibt_success(self):
        """Nicht existierender Endpoint → trotzdem success (0 gelöscht)."""
        resp = self.client.post(
            reverse("unsubscribe_push"),
            data=json.dumps({"endpoint": "https://push.example.com/sub/not_exist"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_vapid_key_nicht_konfiguriert_gibt_503(self):
        """Fehlender VAPID-Key → 503."""
        # Im Test-Environment ist VAPID_PUBLIC_KEY=None (keine .pem Datei)
        resp = self.client.get(reverse("get_vapid_public_key"))
        assert resp.status_code == 503

    def test_vapid_key_login_required(self):
        """Ohne Login → Redirect."""
        c = Client()
        resp = c.get(reverse("get_vapid_public_key"))
        assert resp.status_code == 302
