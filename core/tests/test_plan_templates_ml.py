"""
Tests für Plan-Template und Machine-Learning Views.

plan_templates: get_plan_templates, get_template_detail, create_plan_from_template
machine_learning: ml_train_model, ml_predict_weight, ml_model_info, ml_dashboard
"""

import json
from unittest.mock import MagicMock, patch

from django.test import Client
from django.urls import reverse

import pytest

from core.models import Plan
from core.tests.factories import UebungFactory, UserFactory

# ─────────────────────────────────────────────────────────────────────────────
# Plan Templates
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestGetPlanTemplates:
    """GET /api/plan-templates/"""

    def setup_method(self):
        self.client = Client()
        self.url = reverse("get_plan_templates")

    def test_returns_200_anonymous(self):
        """Endpoint ist öffentlich zugänglich."""
        resp = self.client.get(self.url)
        assert resp.status_code == 200

    def test_returns_json(self):
        """Antwort ist gültiges JSON mit mindestens einem Template."""
        resp = self.client.get(self.url)
        data = resp.json()
        assert isinstance(data, dict)
        assert len(data) > 0

    def test_template_structure(self):
        """Jedes Template hat die erwarteten Felder."""
        resp = self.client.get(self.url)
        data = resp.json()
        for key, template in data.items():
            assert "name" in template
            assert "description" in template
            assert "frequency_per_week" in template
            assert "difficulty" in template
            assert "goal" in template
            assert "days_count" in template

    def test_no_exercises_in_overview(self):
        """Die Übersicht enthält keine vollständigen Exercise-Listen."""
        resp = self.client.get(self.url)
        data = resp.json()
        for key, template in data.items():
            # Overview soll keine tiefen Exercise-Daten haben
            assert "days" not in template

    def test_error_when_file_missing(self):
        """Fehler beim Laden → 500 mit sauberem Error-JSON."""
        with patch("builtins.open", side_effect=FileNotFoundError("not found")):
            resp = self.client.get(self.url)
        assert resp.status_code == 500
        assert "error" in resp.json()


@pytest.mark.django_db
class TestGetTemplateDetail:
    """GET /api/plan-templates/<key>/"""

    def setup_method(self):
        self.client = Client()
        self.user = UserFactory()
        self.client.force_login(self.user)

    def _first_template_key(self):
        url = reverse("get_plan_templates")
        data = self.client.get(url).json()
        return next(iter(data))

    def test_login_required(self):
        """Unauthentifizierter Zugriff → Redirect zur Login-Seite."""
        c = Client()
        key = self._first_template_key()
        url = reverse("get_template_detail", args=[key])
        resp = c.get(url)
        assert resp.status_code == 302

    def test_valid_key_returns_200(self):
        """Bekannter Template-Key → 200 mit Detailstruktur."""
        key = self._first_template_key()
        url = reverse("get_template_detail", args=[key])
        resp = self.client.get(url)
        assert resp.status_code == 200

    def test_response_contains_days(self):
        """Antwort enthält days_adapted als Liste."""
        key = self._first_template_key()
        url = reverse("get_template_detail", args=[key])
        resp = self.client.get(url)
        data = resp.json()
        assert "days_adapted" in data
        assert isinstance(data["days_adapted"], list)

    def test_invalid_key_returns_404(self):
        """Unbekannter Template-Key → 404."""
        url = reverse("get_template_detail", args=["nicht-existent-xyz"])
        resp = self.client.get(url)
        assert resp.status_code == 404

    def test_exercise_has_available_flag(self):
        """Jede Übung in den adapted Days hat available-Flag."""
        key = self._first_template_key()
        url = reverse("get_template_detail", args=[key])
        resp = self.client.get(url)
        data = resp.json()
        for day in data["days_adapted"]:
            for exercise in day["exercises"]:
                assert "available" in exercise


@pytest.mark.django_db
class TestCreatePlanFromTemplate:
    """POST /api/plan-templates/<key>/create/"""

    def setup_method(self):
        self.client = Client()
        self.user = UserFactory()
        self.client.force_login(self.user)

    def _first_template_key(self):
        url = reverse("get_plan_templates")
        data = self.client.get(url).json()
        return next(iter(data))

    def test_login_required(self):
        """Unauthentifizierter Zugriff → Redirect zur Login-Seite."""
        c = Client()
        key = self._first_template_key()
        url = reverse("create_plan_from_template", args=[key])
        resp = c.post(url)
        assert resp.status_code == 302

    def test_get_returns_405(self):
        """GET auf Create-Endpoint → 405 Method Not Allowed."""
        key = self._first_template_key()
        url = reverse("create_plan_from_template", args=[key])
        resp = self.client.get(url)
        assert resp.status_code == 405

    def test_creates_plans_from_template(self):
        """POST erstellt Plan(s) für den User."""
        key = self._first_template_key()
        url = reverse("create_plan_from_template", args=[key])
        before = Plan.objects.filter(user=self.user).count()
        resp = self.client.post(url)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert Plan.objects.filter(user=self.user).count() > before

    def test_invalid_key_returns_404(self):
        """Unbekannter Template-Key beim Erstellen → 404."""
        url = reverse("create_plan_from_template", args=["nicht-existent-xyz"])
        resp = self.client.post(url)
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Machine Learning Views
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestMlTrainModel:
    """POST /api/ml/train/"""

    def setup_method(self):
        self.client = Client()
        self.user = UserFactory()
        self.client.force_login(self.user)
        self.url = reverse("ml_train_model")

    def test_login_required(self):
        """Unauthentifizierter Zugriff → Redirect zur Login-Seite."""
        c = Client()
        resp = c.post(self.url, content_type="application/json", data=json.dumps({}))
        assert resp.status_code == 302

    @patch("core.views.machine_learning.MLTrainer", create=True)
    def test_train_single_uebung_success(self, mock_trainer_class):
        """Training einer Übung → success True."""
        uebung = UebungFactory()
        mock_trainer = MagicMock()
        mock_trainer.train_model.return_value = (
            MagicMock(),  # ml_model
            {"mae": 1.5, "r2_score": 0.85, "samples": 15},
        )
        mock_trainer_class.return_value = mock_trainer

        with patch("core.views.machine_learning.MLTrainer", mock_trainer_class):
            with patch(
                "importlib.import_module",
                side_effect=lambda m: (
                    MagicMock(MLTrainer=mock_trainer_class) if "ml_trainer" in m else __import__(m)
                ),
            ):
                pass  # Patch für den lokalen Import in der View

        # Direkter Ansatz: Patch den Import innerhalb der View-Funktion
        with patch.dict(
            "sys.modules",
            {
                "ml_coach": MagicMock(),
                "ml_coach.ml_trainer": MagicMock(MLTrainer=mock_trainer_class),
                "ml_coach.prediction_service": MagicMock(),
            },
        ):
            resp = self.client.post(
                self.url,
                data=json.dumps({"uebung_id": uebung.id}),
                content_type="application/json",
            )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @patch("core.views.machine_learning.MLTrainer", create=True)
    def test_train_without_enough_data(self, mock_trainer_class):
        """Nicht genug Daten → success False, 400."""
        uebung = UebungFactory()
        mock_trainer = MagicMock()
        mock_trainer.train_model.return_value = (None, {"error": "Zu wenig Daten"})
        mock_trainer_class.return_value = mock_trainer

        with patch.dict(
            "sys.modules",
            {
                "ml_coach": MagicMock(),
                "ml_coach.ml_trainer": MagicMock(MLTrainer=mock_trainer_class),
                "ml_coach.prediction_service": MagicMock(),
            },
        ):
            resp = self.client.post(
                self.url,
                data=json.dumps({"uebung_id": uebung.id}),
                content_type="application/json",
            )
        assert resp.status_code == 400
        assert resp.json()["success"] is False

    def test_train_nonexistent_uebung_returns_404(self):
        """Nicht-existierende Übung → 404."""
        with patch.dict(
            "sys.modules",
            {
                "ml_coach": MagicMock(),
                "ml_coach.ml_trainer": MagicMock(),
                "ml_coach.prediction_service": MagicMock(),
            },
        ):
            resp = self.client.post(
                self.url,
                data=json.dumps({"uebung_id": 99999}),
                content_type="application/json",
            )
        assert resp.status_code == 404


@pytest.mark.django_db
class TestMlPredictWeight:
    """GET /api/ml/predict/<uebung_id>/"""

    def setup_method(self):
        self.client = Client()
        self.user = UserFactory()
        self.client.force_login(self.user)

    def test_login_required(self):
        """Unauthentifizierter Zugriff → Redirect zur Login-Seite."""
        uebung = UebungFactory()
        c = Client()
        url = reverse("ml_predict_weight", args=[uebung.id])
        resp = c.get(url)
        assert resp.status_code == 302

    def test_nonexistent_uebung_returns_404(self):
        """Nicht-existierende Übung → 404."""
        url = reverse("ml_predict_weight", args=[99999])
        with patch.dict(
            "sys.modules",
            {
                "ml_coach": MagicMock(),
                "ml_coach.prediction_service": MagicMock(),
            },
        ):
            resp = self.client.get(url)
        assert resp.status_code == 404

    def test_predict_get_success(self):
        """GET mit gültigem Modell → success True."""
        uebung = UebungFactory()
        mock_predictor = MagicMock()
        mock_predictor.predict_next_weight.return_value = {"predicted_weight": 82.5}
        mock_predictor_class = MagicMock(return_value=mock_predictor)

        with patch.dict(
            "sys.modules",
            {
                "ml_coach": MagicMock(),
                "ml_coach.prediction_service": MagicMock(MLPredictor=mock_predictor_class),
            },
        ):
            resp = self.client.get(reverse("ml_predict_weight", args=[uebung.id]))
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_predict_invalid_json_post(self):
        """POST mit invalidem JSON → 400."""
        uebung = UebungFactory()
        with patch.dict(
            "sys.modules",
            {
                "ml_coach": MagicMock(),
                "ml_coach.prediction_service": MagicMock(),
            },
        ):
            resp = self.client.post(
                reverse("ml_predict_weight", args=[uebung.id]),
                data="kein-json",
                content_type="application/json",
            )
        assert resp.status_code == 400

    def test_predict_invalid_numeric_value(self):
        """POST mit not-a-number last_weight → 400."""
        uebung = UebungFactory()
        mock_predictor = MagicMock()
        mock_predictor_class = MagicMock(return_value=mock_predictor)

        with patch.dict(
            "sys.modules",
            {
                "ml_coach": MagicMock(),
                "ml_coach.prediction_service": MagicMock(MLPredictor=mock_predictor_class),
            },
        ):
            resp = self.client.post(
                reverse("ml_predict_weight", args=[uebung.id]),
                data=json.dumps({"last_weight": "keine-zahl", "last_reps": 10}),
                content_type="application/json",
            )
        assert resp.status_code == 400


@pytest.mark.django_db
class TestMlModelInfo:
    """GET /api/ml/model-info/<uebung_id>/"""

    def setup_method(self):
        self.client = Client()
        self.user = UserFactory()
        self.client.force_login(self.user)

    def test_login_required(self):
        """Unauthentifizierter Zugriff → Redirect zur Login-Seite."""
        uebung = UebungFactory()
        c = Client()
        url = reverse("ml_model_info", args=[uebung.id])
        resp = c.get(url)
        assert resp.status_code == 302

    def test_no_model_returns_404(self):
        """Kein Modell trainiert → 404."""
        uebung = UebungFactory()
        mock_predictor = MagicMock()
        mock_predictor.get_model_info.return_value = None
        mock_predictor_class = MagicMock(return_value=mock_predictor)

        with patch.dict(
            "sys.modules",
            {
                "ml_coach": MagicMock(),
                "ml_coach.prediction_service": MagicMock(MLPredictor=mock_predictor_class),
            },
        ):
            resp = self.client.get(reverse("ml_model_info", args=[uebung.id]))
        assert resp.status_code == 404

    def test_model_info_success(self):
        """Trainiertes Modell → success True mit model_info."""
        uebung = UebungFactory()
        mock_predictor = MagicMock()
        mock_predictor.get_model_info.return_value = {
            "status": "READY",
            "accuracy": 0.88,
            "samples": 30,
        }
        mock_predictor_class = MagicMock(return_value=mock_predictor)

        with patch.dict(
            "sys.modules",
            {
                "ml_coach": MagicMock(),
                "ml_coach.prediction_service": MagicMock(MLPredictor=mock_predictor_class),
            },
        ):
            resp = self.client.get(reverse("ml_model_info", args=[uebung.id]))
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "model_info" in data


@pytest.mark.django_db
class TestMlDashboard:
    """GET /ml/dashboard/"""

    def setup_method(self):
        self.client = Client()
        self.user = UserFactory()
        self.client.force_login(self.user)

    def test_login_required(self):
        """Unauthentifizierter Zugriff → Redirect zur Login-Seite."""
        c = Client()
        resp = c.get(reverse("ml_dashboard"))
        assert resp.status_code == 302

    def test_dashboard_loads(self):
        """Dashboard rendert ohne Fehler."""
        with patch.dict(
            "sys.modules",
            {"ml_coach": MagicMock(), "ml_coach.prediction_service": MagicMock()},
        ):
            resp = self.client.get(reverse("ml_dashboard"))
        assert resp.status_code == 200

    def test_dashboard_context(self):
        """Context enthält ml_models und Zähler."""
        with patch.dict(
            "sys.modules",
            {"ml_coach": MagicMock(), "ml_coach.prediction_service": MagicMock()},
        ):
            resp = self.client.get(reverse("ml_dashboard"))
        assert "ml_models" in resp.context
        assert "total_models" in resp.context
        assert "ready_models" in resp.context
