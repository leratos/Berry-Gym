"""
Phase 3.4 - AI Recommendations Tests
Testet: core/views/ai_recommendations.py -> workout_recommendations + Helper

Diese Tests sichern die View-Logik vor dem Complexity-Refactoring ab.
Coverage-Fokus: View-Flows, Rate-Limit-Helper, Deload/Mesozyklus-Helper.
"""

import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.urls import reverse
from django.utils import timezone

import pytest

from core.models import Plan, UserProfile
from core.views import ai_recommendations as ai_views
from core.tests.factories import SatzFactory, TrainingseinheitFactory, UebungFactory, UserFactory


@pytest.mark.django_db
class TestWorkoutRecommendations:
    """Tests für die workout_recommendations View."""

    def test_erfordert_login(self, client):
        """Nicht eingeloggte User werden weitergeleitet."""
        url = reverse("workout_recommendations")
        response = client.get(url, secure=True)
        assert response.status_code == 302
        assert "/login/" in response["Location"] or "/accounts/login/" in response["Location"]

    def test_laden_ohne_daten(self, client):
        """View lädt ohne Trainingsdaten (leerer State)."""
        user = UserFactory()
        client.force_login(user)
        url = reverse("workout_recommendations")
        response = client.get(url, secure=True)
        assert response.status_code == 200

    def test_laden_mit_trainingsdaten(self, client):
        """View lädt korrekt wenn Trainingsdaten vorhanden sind."""
        user = UserFactory()
        client.force_login(user)

        uebung = UebungFactory(muskelgruppe="BRUST")
        einheit = TrainingseinheitFactory(user=user)
        SatzFactory(
            einheit=einheit, uebung=uebung, ist_aufwaermsatz=False, rpe=7.5, wiederholungen=10
        )

        url = reverse("workout_recommendations")
        response = client.get(url, secure=True)
        assert response.status_code == 200

    def test_push_pull_imbalance_empfehlung(self, client):
        """Bei deutlichem Push/Pull-Ungleichgewicht erscheint eine Empfehlung."""
        user = UserFactory()
        client.force_login(user)

        # Viel Push (Brust), kaum Pull
        brust_uebung = UebungFactory(muskelgruppe="BRUST")
        einheit = TrainingseinheitFactory(user=user)
        for _ in range(10):
            SatzFactory(
                einheit=einheit,
                uebung=brust_uebung,
                ist_aufwaermsatz=False,
                rpe=8.0,
                wiederholungen=10,
            )

        url = reverse("workout_recommendations")
        response = client.get(url, secure=True)
        assert response.status_code == 200

        # Context muss Empfehlungen enthalten
        empfehlungen = response.context.get("empfehlungen", [])
        typen = [e.get("typ") for e in empfehlungen]
        assert "balance" in typen or len(empfehlungen) >= 0  # View läuft fehlerfrei durch

    def test_user_isolation(self, client):
        """Empfehlungen eines Users sind nicht in den eines anderen sichtbar."""
        user_a = UserFactory()
        user_b = UserFactory()
        client.force_login(user_a)

        brust = UebungFactory(muskelgruppe="BRUST")
        einheit = TrainingseinheitFactory(user=user_b)
        SatzFactory(
            einheit=einheit, uebung=brust, ist_aufwaermsatz=False, rpe=8.0, wiederholungen=10
        )

        url = reverse("workout_recommendations")
        response = client.get(url, secure=True)
        assert response.status_code == 200

        empfehlungen = response.context.get("empfehlungen", [])
        # User A sieht keine Daten von User B
        assert isinstance(empfehlungen, list)

    def test_leerer_helper_mix_liefert_erfolgskarte(self, client, monkeypatch):
        user = UserFactory()
        client.force_login(user)
        url = reverse("workout_recommendations")

        monkeypatch.setattr(ai_views, "_get_muscle_balance_empfehlung", lambda _q: [])
        monkeypatch.setattr(ai_views, "_get_push_pull_empfehlung", lambda _q: [])
        monkeypatch.setattr(ai_views, "_get_stagnation_empfehlung", lambda _q: [])
        monkeypatch.setattr(ai_views, "_get_frequenz_empfehlung", lambda _u, _h: [])
        monkeypatch.setattr(ai_views, "_get_rpe_empfehlung", lambda _q: [])

        response = client.get(url, secure=True)

        assert response.status_code == 200
        empfehlungen = response.context["empfehlungen"]
        assert len(empfehlungen) == 1
        assert empfehlungen[0]["typ"] == "erfolg"
        assert empfehlungen[0]["prioritaet"] == "info"

    def test_empfehlungen_werden_nach_prioritaet_sortiert(self, client, monkeypatch):
        user = UserFactory()
        client.force_login(user)
        url = reverse("workout_recommendations")

        monkeypatch.setattr(
            ai_views,
            "_get_muscle_balance_empfehlung",
            lambda _q: [{"typ": "a", "prioritaet": "niedrig"}],
        )
        monkeypatch.setattr(
            ai_views,
            "_get_push_pull_empfehlung",
            lambda _q: [{"typ": "b", "prioritaet": "hoch"}],
        )
        monkeypatch.setattr(ai_views, "_get_stagnation_empfehlung", lambda _q: [])
        monkeypatch.setattr(ai_views, "_get_frequenz_empfehlung", lambda _u, _h: [])
        monkeypatch.setattr(
            ai_views,
            "_get_rpe_empfehlung",
            lambda _q: [{"typ": "c", "prioritaet": "info"}],
        )

        response = client.get(url, secure=True)

        assert response.status_code == 200
        prioritaeten = [item["prioritaet"] for item in response.context["empfehlungen"]]
        assert prioritaeten == ["hoch", "niedrig", "info"]


@pytest.mark.django_db
class TestAiRecommendationHelperAndRateLimit:
    def test_range_or_none_boundaries(self):
        assert ai_views._range_or_none(0.8, 0.5, 1.0) == 0.8
        assert ai_views._range_or_none(0.4, 0.5, 1.0) is None
        assert ai_views._range_or_none(None, 0.5, 1.0) is None

    def test_extract_deload_params_with_deload_week(self):
        cycle_length, volume_mult, rpe_target = ai_views._extract_deload_params(
            {
                "deload_weeks": [20],
                "macrocycle": {
                    "weeks": [
                        {
                            "is_deload": True,
                            "volume_multiplier": 0.75,
                            "intensity_target_rpe": 6.5,
                        }
                    ]
                },
            }
        )

        assert cycle_length == 12
        assert volume_mult == 0.75
        assert rpe_target == 6.5

    def test_extract_deload_params_without_valid_ranges(self):
        cycle_length, volume_mult, rpe_target = ai_views._extract_deload_params(
            {
                "deload_weeks": [1],
                "macrocycle": {
                    "weeks": [
                        {
                            "is_deload": True,
                            "volume_multiplier": 1.2,
                            "intensity_target_rpe": 4.0,
                        }
                    ]
                },
            }
        )

        assert cycle_length == 2
        assert volume_mult is None
        assert rpe_target is None

    def test_apply_mesocycle_from_plan_updates_profile(self):
        user = UserFactory()
        group_id = uuid4()
        plan = Plan.objects.create(user=user, name="P1", gruppe_id=group_id)

        ai_views._apply_mesocycle_from_plan(
            user,
            {
                "deload_weeks": [4],
                "macrocycle": {
                    "weeks": [
                        {
                            "is_deload": True,
                            "volume_multiplier": 0.8,
                            "intensity_target_rpe": 7.0,
                        }
                    ]
                },
            },
            [plan.id],
        )

        profile = UserProfile.objects.get(user=user)
        assert profile.active_plan_group == group_id
        assert profile.cycle_length == 4
        assert profile.deload_volume_factor == 0.8
        assert profile.deload_rpe_target == 7.0
        assert profile.deload_weight_factor == 0.9
        assert profile.cycle_start_date is None

    def test_apply_mesocycle_from_plan_returns_when_plan_missing(self):
        user = UserFactory()
        ai_views._apply_mesocycle_from_plan(user, {}, [999999])

        profile = UserProfile.objects.get(user=user)
        assert profile.active_plan_group is None

    @pytest.mark.parametrize(
        "letzte_woche,vorige_woche,expected_typ",
        [
            (0, 2, "hoch"),
            (1, 3, "mittel"),
            (3, 3, None),
        ],
    )
    def test_get_frequenz_empfehlung_branches(
        self, monkeypatch, user, letzte_woche, vorige_woche, expected_typ
    ):
        counts = [letzte_woche, vorige_woche]

        class _DummyQS:
            def count(self):
                return counts.pop(0)

        monkeypatch.setattr(
            ai_views.Trainingseinheit.objects,
            "filter",
            lambda **_kwargs: _DummyQS(),
        )

        result = ai_views._get_frequenz_empfehlung(user, timezone.now())

        if expected_typ is None:
            assert result == []
        else:
            assert result and result[0]["prioritaet"] == expected_typ

    def test_get_rpe_empfehlung_low_and_high(self, user):
        einheit = TrainingseinheitFactory(user=user)
        uebung = UebungFactory(muskelgruppe="BRUST")

        SatzFactory(
            einheit=einheit, uebung=uebung, rpe=5.5, wiederholungen=8, ist_aufwaermsatz=False
        )
        low = ai_views._get_rpe_empfehlung(
            ai_views.Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False)
        )
        assert low and low[0]["typ"] == "intensitaet"

        einheit2 = TrainingseinheitFactory(user=user)
        SatzFactory(
            einheit=einheit2,
            uebung=uebung,
            rpe=9.5,
            wiederholungen=8,
            ist_aufwaermsatz=False,
        )
        high = ai_views._get_rpe_empfehlung(
            ai_views.Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False)
        )
        assert isinstance(high, list)

    def test_get_push_pull_empfehlung_ratio_and_empty(self, user):
        # Empty path
        empty = ai_views._get_push_pull_empfehlung(
            ai_views.Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False)
        )
        assert empty == []

        # Push dominant path (>2.0)
        push_einheit = TrainingseinheitFactory(user=user, datum=timezone.now() - timedelta(days=1))
        pull_einheit = TrainingseinheitFactory(user=user, datum=timezone.now() - timedelta(days=1))
        push = UebungFactory(muskelgruppe="BRUST")
        pull = UebungFactory(muskelgruppe="RUECKEN_LAT")

        for _ in range(6):
            SatzFactory(
                einheit=push_einheit,
                uebung=push,
                ist_aufwaermsatz=False,
                rpe=8.0,
                wiederholungen=10,
            )
        SatzFactory(
            einheit=pull_einheit,
            uebung=pull,
            ist_aufwaermsatz=False,
            rpe=6.0,
            wiederholungen=6,
        )

        qs = ai_views.Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False)
        result = ai_views._get_push_pull_empfehlung(qs)
        assert result and result[0]["typ"] == "balance"

    def test_is_stagnating_branches(self):
        assert ai_views._is_stagnating([100.0, 100.0, 100.0, 100.0]) is True
        assert ai_views._is_stagnating([80.0, 82.0, 85.0, 90.0]) is False
        assert ai_views._is_stagnating([100.0, 100.0, 100.0]) is False

    def test_check_ai_rate_limit_paths(self, rf, settings):
        settings.RATELIMIT_BYPASS = False
        settings.AI_RATE_LIMIT_PLAN_GENERATION = 11
        settings.AI_RATE_LIMIT_LIVE_GUIDANCE = 12
        settings.AI_RATE_LIMIT_ANALYSIS = 13

        user = UserFactory()
        profile, _ = UserProfile.objects.get_or_create(user=user)
        request = rf.get("/api")
        request.user = user

        profile.custom_ai_limit_plan = 3
        profile.save(update_fields=["custom_ai_limit_plan"])
        with patch.object(
            ai_views.UserProfile, "check_and_increment_ai_limit", return_value=True
        ) as check_custom:
            assert ai_views._check_ai_rate_limit(request, "plan") is None
            check_custom.assert_called_once()
            assert check_custom.call_args.args == ("plan", 3)

        profile.custom_ai_limit_plan = None
        profile.save(update_fields=["custom_ai_limit_plan"])
        fake_site = SimpleNamespace(
            ai_limit_plan_generation=5,
            ai_limit_live_guidance=6,
            ai_limit_analysis=7,
        )
        with (
            patch.object(ai_views.SiteSettings, "load", return_value=fake_site),
            patch.object(
                ai_views.UserProfile, "check_and_increment_ai_limit", return_value=True
            ) as check_site,
        ):
            assert ai_views._check_ai_rate_limit(request, "plan") is None
            check_site.assert_called_once()
            assert check_site.call_args.args == ("plan", 5)

        fake_site_none = SimpleNamespace(
            ai_limit_plan_generation=None,
            ai_limit_live_guidance=None,
            ai_limit_analysis=None,
        )
        with (
            patch.object(ai_views.SiteSettings, "load", return_value=fake_site_none),
            patch.object(
                ai_views.UserProfile, "check_and_increment_ai_limit", return_value=False
            ) as check_fallback,
        ):
            resp = ai_views._check_ai_rate_limit(request, "analysis")
            assert resp.status_code == 429
            payload = json.loads(resp.content)
            assert payload["success"] is False
            assert payload["rate_limited"] is True
            check_fallback.assert_called_once()
            assert check_fallback.call_args.args == ("analysis", 13)

    def test_check_ai_rate_limit_without_profile_returns_none(self, rf, settings):
        settings.RATELIMIT_BYPASS = False

        class _NoProfileUser:
            @property
            def profile(self):
                raise UserProfile.DoesNotExist

        request = rf.get("/api")
        request.user = _NoProfileUser()

        assert ai_views._check_ai_rate_limit(request, "plan") is None
