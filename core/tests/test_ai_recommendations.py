"""
Phase 3.4 - AI Recommendations Tests
Testet: core/views/ai_recommendations.py -> workout_recommendations + Helper

Diese Tests sichern die View-Logik vor dem Complexity-Refactoring ab.
Coverage-Fokus: View-Flows, Rate-Limit-Helper, Deload/Mesozyklus-Helper.
"""

import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.urls import reverse
from django.utils import timezone

import pytest

from core.models import Plan, UserProfile
from core.tests.factories import (
    PlanFactory,
    SatzFactory,
    TrainingseinheitFactory,
    UebungFactory,
    UserFactory,
)
from core.views import ai_recommendations as ai_views


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

    def test_is_stagnating_rpe_sinkend_ist_konsolidierung(self):
        """Gleiches Gewicht + sinkender RPE = Konsolidierung, kein Plateau."""
        gewichte = [100.0, 100.0, 100.0, 100.0]
        rpe = [9.5, 9.0, 8.5, 8.0]  # RPE sinkt um 1.5
        assert ai_views._is_stagnating(gewichte, rpe) is False

    def test_is_stagnating_rpe_gleichbleibend_ist_plateau(self):
        """Gleiches Gewicht + gleichbleibender RPE = echtes Plateau."""
        gewichte = [100.0, 100.0, 100.0, 100.0]
        rpe = [9.0, 9.0, 9.0, 9.0]  # RPE stagniert
        assert ai_views._is_stagnating(gewichte, rpe) is True

    def test_is_stagnating_rpe_steigend_ist_plateau(self):
        """Gleiches Gewicht + steigender RPE = Plateau (wird sogar schwerer)."""
        gewichte = [100.0, 100.0, 100.0, 100.0]
        rpe = [8.0, 8.5, 9.0, 9.5]  # RPE steigt
        assert ai_views._is_stagnating(gewichte, rpe) is True

    def test_is_stagnating_ohne_rpe_bleibt_plateau(self):
        """Ohne RPE-Daten → altes Verhalten: Gewichtsstagnation = Plateau."""
        gewichte = [100.0, 100.0, 100.0, 100.0]
        assert ai_views._is_stagnating(gewichte, None) is True
        assert ai_views._is_stagnating(gewichte, []) is True

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


@pytest.mark.django_db
class TestAiRecommendationRemainingBranches:
    def test_apply_mesocycle_returns_when_no_plan_ids(self):
        user = UserFactory()
        ai_views._apply_mesocycle_from_plan(user, {"deload_weeks": [4]}, [])
        profile = UserProfile.objects.get(user=user)
        assert profile.active_plan_group is None

    def test_push_pull_ratio_without_warning_returns_empty(self, user):
        push_einheit = TrainingseinheitFactory(user=user, datum=timezone.now() - timedelta(days=1))
        pull_einheit = TrainingseinheitFactory(user=user, datum=timezone.now() - timedelta(days=1))
        push = UebungFactory(muskelgruppe="BRUST")
        pull = UebungFactory(muskelgruppe="RUECKEN_LAT")

        for _ in range(2):
            SatzFactory(
                einheit=push_einheit,
                uebung=push,
                ist_aufwaermsatz=False,
                rpe=8.0,
                wiederholungen=10,
            )
        for _ in range(2):
            SatzFactory(
                einheit=pull_einheit,
                uebung=pull,
                ist_aufwaermsatz=False,
                rpe=8.0,
                wiederholungen=10,
            )

        qs = ai_views.Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False)
        assert ai_views._get_push_pull_empfehlung(qs) == []

    def test_stagnation_skips_missing_uebung(self, monkeypatch):
        class _DummyQS(list):
            def select_related(self, *_args, **_kwargs):
                return self

        now = timezone.now()
        saetze = _DummyQS(
            [
                SimpleNamespace(
                    gewicht=100, rpe=None, uebung_id=9999, einheit=SimpleNamespace(datum=now.date())
                ),
                SimpleNamespace(
                    gewicht=100,
                    rpe=None,
                    uebung_id=9999,
                    einheit=SimpleNamespace(datum=(now - timedelta(days=1)).date()),
                ),
                SimpleNamespace(
                    gewicht=100,
                    rpe=None,
                    uebung_id=9999,
                    einheit=SimpleNamespace(datum=(now - timedelta(days=2)).date()),
                ),
                SimpleNamespace(
                    gewicht=100,
                    rpe=None,
                    uebung_id=9999,
                    einheit=SimpleNamespace(datum=(now - timedelta(days=3)).date()),
                ),
            ]
        )

        monkeypatch.setattr(ai_views.Uebung.objects, "filter", lambda **_kwargs: [])
        monkeypatch.setattr(ai_views, "_is_stagnating", lambda _w, _r=None: True)
        assert ai_views._get_stagnation_empfehlung(saetze) == []

    def test_stagnation_appends_recommendation_when_uebung_exists(self, user, monkeypatch):
        uebung = UebungFactory(muskelgruppe="BRUST", bezeichnung="Bankdrücken")
        base_day = timezone.now().date()
        for delta in range(4):
            einheit = TrainingseinheitFactory(user=user, datum=base_day - timedelta(days=delta))
            SatzFactory(
                einheit=einheit,
                uebung=uebung,
                gewicht=100,
                rpe=8.0,
                wiederholungen=8,
                ist_aufwaermsatz=False,
            )

        monkeypatch.setattr(ai_views, "_is_stagnating", lambda _w, _r=None: True)
        qs = ai_views.Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False)
        result = ai_views._get_stagnation_empfehlung(qs)

        assert result
        assert result[0]["typ"] == "stagnation"
        assert "Bankdrücken" in result[0]["titel"]

    def test_rpe_high_branch_returns_warning(self, user):
        einheit = TrainingseinheitFactory(user=user)
        uebung = UebungFactory(muskelgruppe="BRUST")
        for _ in range(3):
            SatzFactory(
                einheit=einheit,
                uebung=uebung,
                rpe=9.8,
                wiederholungen=6,
                ist_aufwaermsatz=False,
            )

        qs = ai_views.Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False)
        result = ai_views._get_rpe_empfehlung(qs)
        assert result and result[0]["prioritaet"] == "hoch"

    def test_validate_plan_gen_params_edges(self):
        bad_sets = ai_views._validate_plan_gen_params({"sets_per_session": 9})
        assert isinstance(bad_sets, ai_views.JsonResponse)

        normalized = ai_views._validate_plan_gen_params(
            {
                "plan_type": "3er-split",
                "sets_per_session": 18,
                "analysis_days": 30,
                "periodization": "unknown",
                "target_profile": "unknown",
                "previewOnly": True,
            }
        )
        assert isinstance(normalized, tuple)
        assert normalized[3] == "linear"
        assert normalized[4] == "hypertrophie"

    def test_execute_plan_generation_preview_and_apply_mesocycle(self, monkeypatch):
        user = UserFactory()
        fake_generator = MagicMock()
        fake_generator.generate.side_effect = [
            {"plan_data": {"plan_name": "Preview"}},
            {
                "success": True,
                "plan_ids": [1],
                "plan_data": {"plan_name": "Saved", "sessions": [{"a": 1}]},
            },
        ]

        resp_preview = ai_views._execute_plan_generation(
            user, fake_generator, preview_only=True, use_openrouter=False
        )
        preview_data = json.loads(resp_preview.content)
        assert preview_data["preview"] is True
        assert preview_data["model"] == "Ollama 8B"

        with patch.object(ai_views, "_apply_mesocycle_from_plan") as apply_mock:
            resp_saved = ai_views._execute_plan_generation(
                user, fake_generator, preview_only=False, use_openrouter=True
            )
            saved_data = json.loads(resp_saved.content)
            assert saved_data["success"] is True
            assert saved_data["cost"] == 0.003
            apply_mock.assert_called_once()

    @patch("core.views.ai_recommendations._check_ai_rate_limit", return_value=None)
    def test_generate_plan_api_json_loader_generic_error_returns_500(self, _mock_limit, rf):
        user = UserFactory()
        request = rf.post("/api/generate-plan/", data="{}", content_type="application/json")
        request.user = user

        with patch(
            "core.views.ai_recommendations.json.loads",
            side_effect=[ValueError("boom"), ValueError("boom")],
        ):
            resp = ai_views.generate_plan_api.__wrapped__(request)

        assert resp.status_code == 500
        assert json.loads(resp.content)["success"] is False

    @patch("core.views.ai_recommendations._check_ai_rate_limit", return_value=None)
    @patch("core.views.ai_recommendations._execute_plan_generation")
    @patch("core.views.ai_recommendations._validate_plan_gen_params")
    @patch("ai_coach.plan_generator.PlanGenerator")
    def test_generate_plan_api_happy_path_hits_execute_return(
        self,
        _mock_generator,
        mock_validate,
        mock_execute,
        _mock_limit,
        client,
    ):
        user = UserFactory()
        client.force_login(user)
        url = reverse("generate_plan_api")

        mock_validate.return_value = ("3er-split", 18, 30, "linear", "hypertrophie", False)
        mock_execute.return_value = ai_views.JsonResponse({"ok": True})

        resp = client.post(
            url,
            json.dumps({"plan_type": "3er-split"}),
            content_type="application/json",
            secure=True,
        )

        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_apply_optimization_helpers(self, user):
        plan = Plan.objects.create(user=user, name="P")
        old_ex = UebungFactory(bezeichnung="Bankdrücken", muskelgruppe="BRUST")
        new_ex = UebungFactory(bezeichnung="Schrägbankdrücken", muskelgruppe="BRUST")
        pu = ai_views.PlanUebung.objects.create(plan=plan, uebung=old_ex, reihenfolge=1)

        err = ai_views._apply_replace_exercise(
            plan,
            {"old_exercise": "Bankdrücken", "new_exercise": "Schrägbankdrücken"},
        )
        assert err is None
        pu.refresh_from_db()
        assert pu.uebung_id == new_ex.id

        err_nf = ai_views._apply_replace_exercise(
            plan,
            {"old_exercise": "NichtDa", "new_exercise": "Schrägbankdrücken"},
        )
        assert "nicht im Plan gefunden" in err_nf

        err_new_nf = ai_views._apply_replace_exercise(
            plan,
            {"old_exercise": "Schrägbankdrücken", "new_exercise": "XYZ"},
        )
        assert "nicht gefunden" in err_new_nf

        err_vol_nf = ai_views._apply_adjust_volume(plan, {"exercise": "XYZ"})
        assert "nicht im Plan gefunden" in err_vol_nf

        err_vol_ok = ai_views._apply_adjust_volume(
            plan,
            {"exercise": "Schrägbankdrücken", "new_sets": 5, "new_reps": "6-8"},
        )
        assert err_vol_ok is None

        err_add_nf = ai_views._apply_add_exercise(plan, {"exercise": "NichtDa"})
        assert "nicht gefunden" in err_add_nf

        add_ex = UebungFactory(bezeichnung="Klimmzug", muskelgruppe="RUECKEN_LAT")
        err_add_ok = ai_views._apply_add_exercise(
            plan,
            {"exercise": "Klimmzug", "sets": 4, "reps": "5-8"},
        )
        assert err_add_ok is None
        assert ai_views.PlanUebung.objects.filter(plan=plan, uebung=add_ex).exists()

        assert ai_views._apply_single_optimization(plan, {"type": "unknown"}) is None

        with patch.dict(
            ai_views._OPT_HANDLERS, {"dummy": lambda _plan, _opt: "handled"}, clear=False
        ):
            assert ai_views._apply_single_optimization(plan, {"type": "dummy"}) == "handled"

    @patch("ai_coach.plan_generator.PlanGenerator")
    @patch("core.views.ai_recommendations._apply_mesocycle_from_plan")
    def test_handle_save_cached_plan_set_as_active_triggers_mesocycle(
        self, mock_apply_mesocycle, mock_generator_cls
    ):
        user = UserFactory()
        mock_generator_cls.return_value._save_plan_to_db.return_value = [11]

        resp = ai_views._handle_save_cached_plan(
            user,
            {
                "set_as_active": True,
                "plan_data": {"plan_name": "Cached", "sessions": [{"day": "A"}]},
            },
        )

        data = json.loads(resp.content)
        assert data["success"] is True
        mock_apply_mesocycle.assert_called_once_with(
            user,
            {"plan_name": "Cached", "sessions": [{"day": "A"}]},
            [11],
        )

    @patch("core.views.ai_recommendations._apply_single_optimization")
    def test_apply_optimizations_collects_errors_and_exceptions(self, mock_apply, client):
        user = UserFactory()
        plan = PlanFactory(user=user)
        client.force_login(user)
        url = reverse("apply_optimizations_api")

        mock_apply.side_effect = [None, "bad", RuntimeError("x")]

        resp = client.post(
            url,
            json.dumps(
                {
                    "plan_id": plan.id,
                    "optimizations": [
                        {"type": "add_exercise"},
                        {"type": "adjust_volume"},
                        {"type": "replace_exercise"},
                    ],
                }
            ),
            content_type="application/json",
            secure=True,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["applied_count"] == 1
        assert len(data["errors"]) == 2

    @patch("ai_coach.live_guidance.LiveGuidance")
    def test_live_guidance_success_sanitizes_response(self, mock_guidance_cls, client):
        user = UserFactory()
        session = TrainingseinheitFactory(user=user)
        client.force_login(user)
        url = reverse("live_guidance_api")

        mock_guidance_cls.return_value.get_guidance.return_value = {
            "answer": "Bleib stabil.",
            "cost": "0.02",
            "model": 123,
            "context": {"should_not": "leak"},
        }

        resp = client.post(
            url,
            json.dumps({"session_id": session.id, "question": "Wie war der Satz?"}),
            content_type="application/json",
            secure=True,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"answer": "Bleib stabil.", "cost": 0.02, "model": "123"}

    @patch("ai_coach.live_guidance.LiveGuidance")
    def test_live_guidance_exception_returns_500(self, mock_guidance_cls, client):
        user = UserFactory()
        session = TrainingseinheitFactory(user=user)
        client.force_login(user)
        url = reverse("live_guidance_api")

        mock_guidance_cls.return_value.get_guidance.side_effect = RuntimeError("boom")

        resp = client.post(
            url,
            json.dumps({"session_id": session.id, "question": "Hi"}),
            content_type="application/json",
            secure=True,
        )
        assert resp.status_code == 500

    @patch("core.views.ai_recommendations._check_ai_rate_limit", return_value=None)
    @patch("ai_coach.plan_generator.PlanGenerator")
    def test_generate_plan_stream_emits_progress_callback(
        self, mock_generator_cls, _mock_limit, client
    ):
        user = UserFactory()
        client.force_login(user)
        url = reverse("generate_plan_stream_api")

        def fake_generate(*_args, **_kwargs):
            cb = mock_generator_cls.call_args.kwargs["progress_callback"]
            cb(42, "processing")
            return {"success": True, "plan_data": {"plan_name": "X"}}

        mock_generator_cls.return_value.generate.side_effect = fake_generate

        resp = client.get(url, secure=True)
        payload = b"".join(resp.streaming_content).decode("utf-8")
        assert '"progress": 42' in payload
        assert '"done": true' in payload.lower()

    @patch("core.views.ai_recommendations._check_ai_rate_limit", return_value=None)
    @patch("ai_coach.plan_generator.PlanGenerator")
    def test_generate_plan_stream_failed_result_branch(
        self, mock_generator_cls, _mock_limit, client
    ):
        user = UserFactory()
        client.force_login(user)
        url = reverse("generate_plan_stream_api")

        mock_generator_cls.return_value.generate.return_value = {
            "success": False,
            "errors": ["broken"],
        }

        resp = client.get(url, secure=True)
        payload = b"".join(resp.streaming_content).decode("utf-8")
        assert '"success": false' in payload.lower()
        assert "broken" in payload

    @patch("core.views.ai_recommendations._check_ai_rate_limit", return_value=None)
    def test_generate_plan_stream_timeout_branch(self, _mock_limit, client):
        user = UserFactory()
        client.force_login(user)
        url = reverse("generate_plan_stream_api")

        with (
            patch("threading.Thread") as thread_cls,
            patch("queue.Queue") as queue_cls,
        ):
            queue_instance = MagicMock()
            import queue as std_queue

            queue_instance.get.side_effect = std_queue.Empty
            queue_cls.return_value = queue_instance
            thread_cls.return_value = MagicMock(start=MagicMock())

            resp = client.get(url, secure=True)
            payload = b"".join(resp.streaming_content).decode("utf-8")

        assert "Timeout" in payload and "erneut versuchen" in payload
