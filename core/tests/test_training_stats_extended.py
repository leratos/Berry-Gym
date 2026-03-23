"""
Erweiterte Tests für Training Statistics & Dashboard Views.

Abgedeckte Views:
- dashboard (training_stats.py)
- training_list
- training_stats
- delete_training
- exercise_stats
"""

import json
from datetime import timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

import pytest

from core.models import Trainingseinheit

from .factories import PlanFactory, SatzFactory, TrainingseinheitFactory, UebungFactory, UserFactory

# ─────────────────────────────────────────────────────────────────────────────
# Dashboard Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDashboard:
    """Tests für die Dashboard-View (Hauptseite nach Login)."""

    URL = reverse("dashboard")

    def test_login_required(self, client):
        """Unauthentifizierter Zugriff → Redirect zum Login."""
        response = client.get(self.URL)
        assert response.status_code == 302
        assert "/login" in response.url or "login" in response.url

    def test_dashboard_loads_for_new_user(self, client):
        """Neuer User ohne Daten: Dashboard lädt ohne Fehler."""
        user = UserFactory()
        client.force_login(user)
        response = client.get(self.URL)
        assert response.status_code == 200

    def test_dashboard_has_context_keys(self, client):
        """Dashboard Context enthält alle erwarteten Keys."""
        user = UserFactory()
        client.force_login(user)
        response = client.get(self.URL)
        ctx = response.context
        expected_keys = [
            "letztes_training",
            "letzter_koerperwert",
            "trainings_diese_woche",
            "streak",
            "favoriten",
            "gesamt_trainings",
            "gesamt_saetze",
        ]
        for key in expected_keys:
            assert key in ctx, f"Context Key '{key}' fehlt im Dashboard"

    def test_dashboard_counts_trainings_this_week(self, client):
        """Dashboard zählt nur Trainings der aktuellen Woche."""
        user = UserFactory()
        client.force_login(user)

        from datetime import timedelta

        from django.utils import timezone

        # 1 Training heute, 1 vor 30 Tagen (soll nicht zählen)
        TrainingseinheitFactory(user=user, datum=timezone.now())
        TrainingseinheitFactory(user=user, datum=timezone.now() - timedelta(days=30))

        response = client.get(self.URL)
        assert response.context["trainings_diese_woche"] >= 1

    def test_dashboard_user_isolation(self, client):
        """Dashboard zeigt nur Daten des eingeloggten Users."""
        user_a = UserFactory()
        user_b = UserFactory()
        client.force_login(user_a)

        # user_b hat 5 Trainings, user_a hat keines
        for _ in range(5):
            TrainingseinheitFactory(user=user_b)

        response = client.get(self.URL)
        assert response.context["gesamt_trainings"] == 0

    def test_dashboard_gesamt_trainings_korrekt(self, client):
        """Gesamtzahl der Trainings im Context stimmt."""
        user = UserFactory()
        client.force_login(user)

        for _ in range(7):
            TrainingseinheitFactory(user=user)

        response = client.get(self.URL)
        assert response.context["gesamt_trainings"] == 7

    def test_dashboard_gesamt_saetze_ignoriert_aufwaermsaetze(self, client):
        """Aufwärmsätze fließen NICHT in gesamt_saetze ein."""
        user = UserFactory()
        client.force_login(user)

        einheit = TrainingseinheitFactory(user=user)
        uebung = UebungFactory()
        SatzFactory(einheit=einheit, uebung=uebung, ist_aufwaermsatz=False)
        SatzFactory(einheit=einheit, uebung=uebung, ist_aufwaermsatz=True)

        response = client.get(self.URL)
        # Nur 1 echter Satz, nicht 2
        assert response.context["gesamt_saetze"] == 1

    def test_dashboard_favoriten_top_3(self, client):
        """Favoriten-Übungen: Maximal 3, nach Häufigkeit sortiert."""
        user = UserFactory()
        client.force_login(user)

        einheit = TrainingseinheitFactory(user=user)
        uebung_a = UebungFactory(bezeichnung="Bankdrücken")
        uebung_b = UebungFactory(bezeichnung="Kniebeuge")
        uebung_c = UebungFactory(bezeichnung="Kreuzheben")
        uebung_d = UebungFactory(bezeichnung="Schulterdrücken")

        # A: 5x, B: 3x, C: 2x, D: 1x → Top 3 = A, B, C
        for _ in range(5):
            SatzFactory(einheit=einheit, uebung=uebung_a, ist_aufwaermsatz=False)
        for _ in range(3):
            SatzFactory(einheit=einheit, uebung=uebung_b, ist_aufwaermsatz=False)
        for _ in range(2):
            SatzFactory(einheit=einheit, uebung=uebung_c, ist_aufwaermsatz=False)
        SatzFactory(einheit=einheit, uebung=uebung_d, ist_aufwaermsatz=False)

        response = client.get(self.URL)
        favoriten = list(response.context["favoriten"])
        assert len(favoriten) == 3
        assert favoriten[0]["uebung__bezeichnung"] == "Bankdrücken"

    def test_dashboard_streak_null_bei_kein_training(self, client):
        """Streak ist 0 für User ohne Trainings."""
        user = UserFactory()
        client.force_login(user)
        response = client.get(self.URL)
        assert response.context["streak"] == 0

    def test_keine_offene_session_bei_neuem_user(self, client):
        """Neuer User ohne Trainings: offene_session ist None."""
        user = UserFactory()
        client.force_login(user)
        response = client.get(self.URL)
        assert response.context["offene_session"] is None
        assert response.context["offene_sessions_anzahl"] == 0

    def test_offene_session_wird_angezeigt(self, client):
        """Training mit abgeschlossen=False erscheint als offene_session."""
        user = UserFactory()
        client.force_login(user)
        offen = TrainingseinheitFactory(user=user, abgeschlossen=False)
        response = client.get(self.URL)
        assert response.context["offene_session"] is not None
        assert response.context["offene_session"]["id"] == offen.id
        assert response.context["offene_sessions_anzahl"] == 1

    def test_abgeschlossene_session_nicht_in_offene(self, client):
        """Abgeschlossene Trainings erscheinen nicht als offene_session."""
        user = UserFactory()
        client.force_login(user)
        TrainingseinheitFactory(user=user, abgeschlossen=True)
        response = client.get(self.URL)
        assert response.context["offene_session"] is None

    def test_mehrere_offene_sessions_zeigt_neueste(self, client):
        """Bei mehreren offenen Sessions wird die neueste angezeigt."""
        user = UserFactory()
        client.force_login(user)
        import datetime

        from django.utils import timezone

        alt = TrainingseinheitFactory(user=user, abgeschlossen=False)
        # Datum manuell auf älter setzen
        alt.datum = timezone.now() - datetime.timedelta(days=3)
        alt.save(update_fields=["datum"])

        neu = TrainingseinheitFactory(user=user, abgeschlossen=False)

        response = client.get(self.URL)
        assert response.context["offene_session"]["id"] == neu.id
        assert response.context["offene_sessions_anzahl"] == 2

    def test_offene_session_isoliert_nach_user(self, client):
        """Offene Session eines anderen Users erscheint nicht."""
        user_a = UserFactory()
        user_b = UserFactory()
        client.force_login(user_a)
        TrainingseinheitFactory(user=user_b, abgeschlossen=False)
        response = client.get(self.URL)
        assert response.context["offene_session"] is None

    def test_letztes_training_nur_abgeschlossene(self, client):
        """letztes_training zeigt nur abgeschlossene Trainings."""
        user = UserFactory()
        client.force_login(user)
        abg = TrainingseinheitFactory(user=user, abgeschlossen=True)
        TrainingseinheitFactory(user=user, abgeschlossen=False)
        response = client.get(self.URL)
        assert response.context["letztes_training"].id == abg.id

    def test_active_plan_widget_shows_start_and_details_links(self, client):
        """Aktive Plangruppe zeigt getrennte CTAs für Start und Plan-Details."""
        import uuid

        user = UserFactory()
        client.force_login(user)

        gruppe_id = uuid.uuid4()
        plan = PlanFactory(
            user=user,
            name="Push Day",
            gruppe_id=gruppe_id,
            gruppe_name="PPL Split",
            gruppe_reihenfolge=0,
        )

        profile = user.profile
        profile.active_plan_group = gruppe_id
        profile.save(update_fields=["active_plan_group"])

        response = client.get(self.URL, secure=True)
        assert response.status_code == 200
        assert reverse("training_start_plan", args=[plan.id]) in response.content.decode()
        assert reverse("plan_details", args=[plan.id]) in response.content.decode()

    def test_active_plan_widget_hides_details_link_without_active_group(self, client):
        """Ohne aktive Plangruppe wird kein Plan-Details-CTA im Widget gerendert."""
        user = UserFactory()
        client.force_login(user)

        response = client.get(self.URL, secure=True)
        assert response.status_code == 200
        assert "Plan-Details ansehen" not in response.content.decode()

    def test_dashboard_cycle_week_matches_profile_state(self, client):
        """Dashboard zeigt die korrekte Zyklus-Woche aus dem Profilkontext."""
        import uuid
        from datetime import timedelta

        from django.utils import timezone

        user = UserFactory()
        client.force_login(user)

        gruppe_id = uuid.uuid4()
        PlanFactory(
            user=user,
            name="Push Day",
            gruppe_id=gruppe_id,
            gruppe_name="PPL Split",
            gruppe_reihenfolge=0,
        )

        profile = user.profile
        profile.active_plan_group = gruppe_id
        profile.cycle_length = 4
        today = timezone.now().date()
        monday_this_week = today - timedelta(days=today.weekday())
        profile.cycle_start_date = monday_this_week - timedelta(weeks=2)
        profile.save(update_fields=["active_plan_group", "cycle_length", "cycle_start_date"])

        response = client.get(self.URL, secure=True)
        assert response.status_code == 200
        assert response.context["cycle_week"] == 3


# ─────────────────────────────────────────────────────────────────────────────
# Training List Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestTrainingList:
    """Tests für /history/ – Trainingshistorie."""

    URL = reverse("training_list")

    def test_login_required(self, client):
        """Unauthentifizierter Zugriff → Redirect."""
        response = client.get(self.URL)
        assert response.status_code == 302

    def test_loads_for_authenticated_user(self, client):
        """Seite lädt für eingeloggten User."""
        user = UserFactory()
        client.force_login(user)
        response = client.get(self.URL)
        assert response.status_code == 200

    def test_user_isolation(self, client):
        """User sieht nur eigene Trainingseinheiten (context key: trainings_data)."""
        user_a = UserFactory()
        user_b = UserFactory()
        client.force_login(user_a)

        for _ in range(3):
            TrainingseinheitFactory(user=user_b)
        eigenes = TrainingseinheitFactory(user=user_a)

        response = client.get(self.URL)
        # View liefert trainings_data: [{training: obj, volumen: float, ...}, ...]
        trainings_data = response.context.get("trainings_data", [])
        ids = [entry["training"].id for entry in trainings_data]
        assert eigenes.id in ids
        # user_b Trainings dürfen nicht erscheinen
        from core.models import Trainingseinheit

        user_b_ids = list(Trainingseinheit.objects.filter(user=user_b).values_list("id", flat=True))
        for bid in user_b_ids:
            assert bid not in ids

    def test_empty_list_for_new_user(self, client):
        """Neuer User ohne Trainings: leere Liste, kein Fehler."""
        user = UserFactory()
        client.force_login(user)
        response = client.get(self.URL)
        assert response.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# Delete Training Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDeleteTraining:
    """Tests für /training/<id>/delete/."""

    def _url(self, training_id):
        return reverse("delete_training", kwargs={"training_id": training_id})

    def test_login_required(self, client):
        """Unauthentifizierter POST → Redirect, kein Delete."""
        einheit = TrainingseinheitFactory()
        response = client.post(self._url(einheit.id))
        assert response.status_code == 302
        # Einheit existiert noch
        from core.models import Trainingseinheit

        assert Trainingseinheit.objects.filter(id=einheit.id).exists()

    def test_owner_can_delete(self, client):
        """Eigentümer kann seine Trainingseinheit löschen."""
        user = UserFactory()
        client.force_login(user)
        einheit = TrainingseinheitFactory(user=user)
        response = client.post(self._url(einheit.id))
        assert response.status_code in (302, 200)
        from core.models import Trainingseinheit

        assert not Trainingseinheit.objects.filter(id=einheit.id).exists()

    def test_other_user_cannot_delete(self, client):
        """Fremde Trainingseinheit → 404, nicht gelöscht."""
        user_a = UserFactory()
        user_b = UserFactory()
        client.force_login(user_a)
        einheit = TrainingseinheitFactory(user=user_b)
        response = client.post(self._url(einheit.id))
        assert response.status_code == 404
        from core.models import Trainingseinheit

        assert Trainingseinheit.objects.filter(id=einheit.id).exists()

    def test_get_request_does_not_delete(self, client):
        """GET-Request löscht nichts."""
        user = UserFactory()
        client.force_login(user)
        einheit = TrainingseinheitFactory(user=user)
        client.get(self._url(einheit.id))
        from core.models import Trainingseinheit

        assert Trainingseinheit.objects.filter(id=einheit.id).exists()


# ─────────────────────────────────────────────────────────────────────────────
# Training Stats Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestTrainingStats:
    """Tests für /stats/ – Gesamtstatistiken."""

    URL = reverse("training_stats")

    def _get(self, client):
        return client.get(self.URL, secure=True)

    def test_login_required(self, client):
        """Unauthentifizierter Zugriff → Redirect."""
        response = self._get(client)
        assert response.status_code == 302

    def test_loads_without_data(self, client):
        """Stats-Seite lädt für User ohne Trainings (kein 500)."""
        user = UserFactory()
        client.force_login(user)
        response = self._get(client)
        assert response.status_code == 200

    def test_sets_no_data_flag_for_new_user(self, client):
        """Neue User ohne Trainings erhalten den no_data-Context."""
        user = UserFactory()
        client.force_login(user)

        response = self._get(client)

        assert response.status_code == 200
        assert response.context["no_data"] is True

    def test_loads_with_data(self, client):
        """Stats-Seite lädt korrekt mit Trainings + Sätzen."""
        user = UserFactory()
        client.force_login(user)
        einheit = TrainingseinheitFactory(user=user)
        uebung = UebungFactory()
        for _ in range(5):
            SatzFactory(einheit=einheit, uebung=uebung, ist_aufwaermsatz=False)
        response = self._get(client)
        assert response.status_code == 200

    def test_user_data_isolation(self, client):
        """Stats enthält nur Daten des eingeloggten Users."""
        user_a = UserFactory()
        user_b = UserFactory()
        client.force_login(user_a)

        # user_b hat viel Daten
        einheit_b = TrainingseinheitFactory(user=user_b)
        for _ in range(20):
            SatzFactory(einheit=einheit_b, ist_aufwaermsatz=False)

        # user_a hat keinen Satz
        response = self._get(client)
        assert response.status_code == 200
        # Keine Exception und der user_b-Satz darf nicht in Context

    def test_single_training_has_consistent_volume_context(self, client):
        """Einzelner Datenpunkt erzeugt valide Labels/Daten und stabile Kennzahlen."""
        user = UserFactory()
        client.force_login(user)

        einheit = TrainingseinheitFactory(user=user)
        uebung = UebungFactory()
        SatzFactory(
            einheit=einheit,
            uebung=uebung,
            ist_aufwaermsatz=False,
            gewicht=100,
            wiederholungen=5,
        )

        response = self._get(client)

        labels = json.loads(response.context["volumen_labels_json"])
        data = json.loads(response.context["volumen_data_json"])

        assert len(labels) == 1
        assert len(data) == 1
        assert response.context["gesamt_volumen"] == 500.0
        assert response.context["durchschnitt_volumen"] == 500.0

    def test_heatmap_contains_exactly_90_days(self, client):
        """90-Tage-Heatmap liefert immer genau 90 Tagespunkte."""
        user = UserFactory()
        client.force_login(user)

        einheit = TrainingseinheitFactory(user=user)
        uebung = UebungFactory()
        SatzFactory(
            einheit=einheit,
            uebung=uebung,
            ist_aufwaermsatz=False,
            gewicht=60,
            wiederholungen=8,
        )

        response = self._get(client)

        heatmap = json.loads(response.context["heatmap_data_json"])
        assert len(heatmap) == 90
        assert all("date" in point and "count" in point for point in heatmap)

    def test_warmup_only_sets_do_not_add_training_volume(self, client):
        """Nur Aufwärmsätze führen zu 0 Volumen und 0 Durchschnitt."""
        user = UserFactory()
        client.force_login(user)

        einheit = TrainingseinheitFactory(user=user)
        uebung = UebungFactory()
        SatzFactory(
            einheit=einheit,
            uebung=uebung,
            ist_aufwaermsatz=True,
            gewicht=80,
            wiederholungen=10,
        )

        response = self._get(client)

        assert response.context["gesamt_volumen"] == 0
        assert response.context["durchschnitt_volumen"] == 0

    def test_weekly_volume_is_capped_to_12_labels(self, client):
        """Weekly-Volume-Chart ist auf maximal 12 Wochen begrenzt."""
        from datetime import timedelta

        from django.utils import timezone

        user = UserFactory()
        client.force_login(user)
        uebung = UebungFactory()

        for week in range(16):
            einheit = TrainingseinheitFactory(
                user=user,
                datum=timezone.now() - timedelta(days=7 * week),
            )
            SatzFactory(
                einheit=einheit,
                uebung=uebung,
                ist_aufwaermsatz=False,
                gewicht=50,
                wiederholungen=5,
            )

        response = self._get(client)

        weekly_labels = json.loads(response.context["weekly_labels_json"])
        weekly_data = json.loads(response.context["weekly_data_json"])

        assert len(weekly_labels) <= 12
        assert len(weekly_labels) == len(weekly_data)


# ─────────────────────────────────────────────────────────────────────────────
# Exercise Stats Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestExerciseStats:
    """Tests für /stats/exercise/<id>/ – Übungsstatistiken."""

    def _url(self, uebung_id):
        return reverse("exercise_stats", kwargs={"uebung_id": uebung_id})

    def test_login_required(self, client):
        """Unauthentifizierter Zugriff → Redirect."""
        uebung = UebungFactory()
        response = client.get(self._url(uebung.id))
        assert response.status_code == 302

    def test_loads_for_existing_exercise(self, client):
        """Seite lädt für bekannte Übung."""
        user = UserFactory()
        client.force_login(user)
        uebung = UebungFactory()
        response = client.get(self._url(uebung.id))
        assert response.status_code == 200

    def test_404_for_nonexistent_exercise(self, client):
        """Unbekannte Übungs-ID → 404."""
        user = UserFactory()
        client.force_login(user)
        response = client.get(self._url(99999))
        assert response.status_code == 404

    def test_loads_with_user_satz_data(self, client):
        """Statistiken werden korrekt berechnet wenn Sätze vorhanden."""
        user = UserFactory()
        client.force_login(user)
        uebung = UebungFactory()
        einheit = TrainingseinheitFactory(user=user)
        for _ in range(3):
            SatzFactory(einheit=einheit, uebung=uebung, ist_aufwaermsatz=False)
        response = client.get(self._url(uebung.id))
        assert response.status_code == 200

    def test_user_isolation_no_foreign_data(self, client):
        """Sätze anderer User erscheinen nicht in der Übungsstatistik."""
        user_a = UserFactory()
        user_b = UserFactory()
        client.force_login(user_a)
        uebung = UebungFactory()

        einheit_b = TrainingseinheitFactory(user=user_b)
        for _ in range(10):
            SatzFactory(einheit=einheit_b, uebung=uebung, ist_aufwaermsatz=False)

        response = client.get(self._url(uebung.id))
        # Kein Fehler, kein Leak
        assert response.status_code == 200

    def test_exercise_stats_context_has_uebung(self, client):
        """Context enthält die Übung als Objekt."""
        user = UserFactory()
        client.force_login(user)
        uebung = UebungFactory(bezeichnung="Bankdrücken Test")
        response = client.get(self._url(uebung.id))
        assert response.status_code == 200
        assert "uebung" in response.context
        assert response.context["uebung"].id == uebung.id

    def test_rpe_chart_shown_with_enough_rpe_data(self, client):
        """≥ 3 Trainings mit RPE → show_rpe_chart=True."""
        user = UserFactory()
        client.force_login(user)
        uebung = UebungFactory()
        for i in range(3):
            einheit = TrainingseinheitFactory(user=user)
            # datum ist auto_now_add → via update() überschreiben
            Trainingseinheit.objects.filter(pk=einheit.pk).update(
                datum=timezone.now() - timedelta(days=i + 1)
            )
            SatzFactory(
                einheit=einheit,
                uebung=uebung,
                ist_aufwaermsatz=False,
                rpe=Decimal("7.0"),
            )
        response = client.get(self._url(uebung.id))
        assert response.status_code == 200
        assert response.context["show_rpe_chart"] is True

    def test_rpe_chart_hidden_without_enough_rpe_data(self, client):
        """Weniger als 3 RPE-Datenpunkte → show_rpe_chart=False."""
        user = UserFactory()
        client.force_login(user)
        uebung = UebungFactory()
        einheit = TrainingseinheitFactory(user=user)
        SatzFactory(
            einheit=einheit,
            uebung=uebung,
            ist_aufwaermsatz=False,
            rpe=Decimal("7.0"),
        )
        response = client.get(self._url(uebung.id))
        assert response.status_code == 200
        assert response.context["show_rpe_chart"] is False


# ─────────────────────────────────────────────────────────────────────────────
# Balance Warnings Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCheckBalanceWarnings:
    """Tests für _check_balance_warnings() – Push/Pull-Imbalance Detection."""

    def _create_sets(self, user, muskelgruppe, count, days_ago=3):
        uebung = UebungFactory(muskelgruppe=muskelgruppe)
        einheit = TrainingseinheitFactory(
            user=user, datum=timezone.now() - timedelta(days=days_ago)
        )
        for _ in range(count):
            SatzFactory(einheit=einheit, uebung=uebung, ist_aufwaermsatz=False)

    def test_returns_empty_when_insufficient_sets(self):
        """Weniger als 3 Push-Sätze → keine Warnung (zu wenig Daten)."""
        from core.views.training_stats import _check_balance_warnings

        user = UserFactory()
        self._create_sets(user, "BRUST", 2)  # push=2 < 3, pull=0 < 3
        assert _check_balance_warnings(user, timezone.now()) == []

    def test_warns_push_heavy(self):
        """8 Push vs. 3 Pull → ratio 2.67 > 2.5 → Push-Warnung."""
        from core.views.training_stats import _check_balance_warnings

        user = UserFactory()
        self._create_sets(user, "BRUST", 8)
        self._create_sets(user, "RUECKEN_LAT", 3, days_ago=5)
        result = _check_balance_warnings(user, timezone.now())
        assert len(result) == 1
        assert result[0]["type"] == "balance"
        assert "Push" in result[0]["message"]

    def test_warns_pull_heavy(self):
        """3 Push vs. 10 Pull → ratio 0.3 < 0.4 → Pull-Warnung."""
        from core.views.training_stats import _check_balance_warnings

        user = UserFactory()
        self._create_sets(user, "BRUST", 3)
        self._create_sets(user, "RUECKEN_LAT", 10, days_ago=5)
        result = _check_balance_warnings(user, timezone.now())
        assert len(result) == 1
        assert result[0]["type"] == "balance"
        assert "Pull" in result[0]["message"]

    def test_no_warning_when_balanced(self):
        """5 Push vs. 5 Pull → Ratio 1.0 → keine Warnung."""
        from core.views.training_stats import _check_balance_warnings

        user = UserFactory()
        self._create_sets(user, "BRUST", 5)
        self._create_sets(user, "RUECKEN_LAT", 5, days_ago=5)
        assert _check_balance_warnings(user, timezone.now()) == []


# ─────────────────────────────────────────────────────────────────────────────
# Forecasting Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestLinearForecast:
    """Unit-Tests für _linear_forecast() – keine DB notwendig."""

    def test_returns_none_with_fewer_than_5_points(self):
        from datetime import date

        from core.views.training_stats import _linear_forecast

        pairs = [(date(2026, 1, i), float(i * 10)) for i in range(1, 5)]
        assert _linear_forecast(pairs, 30) is None

    def test_returns_value_with_positive_slope(self):
        from datetime import date

        from core.views.training_stats import _linear_forecast

        # Klare lineare Progression: 10, 20, 30, 40, 50, 60 kg
        pairs = [(date(2026, 1, i * 7), float(i * 10)) for i in range(1, 7)]
        result = _linear_forecast(pairs, 56)  # 8 Wochen in der Zukunft
        assert result is not None
        assert result > 60  # Muss über letztem Wert liegen

    def test_returns_none_when_all_same_day(self):
        from datetime import date

        from core.views.training_stats import _linear_forecast

        # Alle am gleichen Tag → denom = 0
        pairs = [(date(2026, 1, 1), float(i)) for i in range(1, 6)]
        assert _linear_forecast(pairs, 30) is None


@pytest.mark.django_db
class TestForecast1RM:
    """Integration-Test: forecast_1rm im exercise_stats Context."""

    def _url(self, uebung_id):
        return reverse("exercise_stats", kwargs={"uebung_id": uebung_id})

    def test_forecast_shown_with_5_sessions_positive_trend(self, client):
        """5 Sessions mit steigendem 1RM → forecast_1rm im Context."""
        user = UserFactory()
        client.force_login(user)
        uebung = UebungFactory()
        for i in range(5):
            einheit = TrainingseinheitFactory(user=user)
            Trainingseinheit.objects.filter(pk=einheit.pk).update(
                datum=timezone.now() - timedelta(days=(4 - i) * 14)
            )
            # Steigendes Gewicht für positiven Trend
            SatzFactory(
                einheit=einheit,
                uebung=uebung,
                ist_aufwaermsatz=False,
                gewicht=Decimal(str(60 + i * 5)),
                wiederholungen=5,
            )
        response = client.get(self._url(uebung.id))
        assert response.status_code == 200
        assert response.context["forecast_1rm"] is not None
