"""
Machine learning view module for weight prediction using scikit-learn.

Handles ML model training, weight predictions, and model information retrieval
for fitness exercises. Provides REST API endpoints for training models and
generating predictions based on historical training data.
"""

import json
import logging
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods

from ..models import Uebung

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["POST"])
def ml_train_model(request):
    """
    Trainiert ML-Modell für Gewichtsvorhersagen
    POST /api/ml/train/ mit {"uebung_id": 123} oder ohne (alle Übungen)
    """
    from ml_coach.ml_trainer import MLTrainer

    try:
        data = json.loads(request.body) if request.body else {}
        uebung_id = data.get('uebung_id')

        if uebung_id:
            # Einzelne Übung trainieren
            uebung = get_object_or_404(Uebung, id=uebung_id)
            trainer = MLTrainer(request.user, uebung)
            ml_model, metrics = trainer.train_model()

            if ml_model:
                return JsonResponse({
                    'success': True,
                    'message': f'Modell für {uebung.bezeichnung} trainiert',
                    'metrics': metrics
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Nicht genug Trainingsdaten (mind. 10 Sätze benötigt)',
                    'error': metrics.get('error', 'Unbekannter Fehler')
                }, status=400)
        else:
            # Alle Übungen trainieren
            results = MLTrainer.train_all_user_models(request.user, min_samples=10)

            return JsonResponse({
                'success': True,
                'message': f'{len(results)} Modelle trainiert',
                'trained_models': [
                    {
                        'uebung': uebung.bezeichnung,
                        'samples': metrics['samples'],
                        'mae': metrics['mae'],
                        'r2_score': metrics['r2_score']
                    }
                    for uebung, metrics in results
                ]
            })

    except Exception as e:
        logger.error(f'ML Training Error: {e}', exc_info=True)
        return JsonResponse({
            'success': False,
            'message': 'Fehler beim Trainieren des Modells',
            'error': 'Interner Serverfehler'
        }, status=500)


@login_required
@require_http_methods(["GET", "POST"])
def ml_predict_weight(request, uebung_id):
    """
    Vorhersage des nächsten Gewichts für eine Übung
    GET/POST /api/ml/predict/<uebung_id>/
    Optional POST: {"last_weight": 80, "last_reps": 10, "rpe": 8}
    """
    from ml_coach.prediction_service import MLPredictor

    try:
        uebung = get_object_or_404(Uebung, id=uebung_id)
        predictor = MLPredictor(request.user, uebung)

        # Optional: Manuelle Daten für Vorhersage
        last_weight = None
        last_reps = None
        rpe = None

        if request.method == 'POST' and request.body:
            # Sichere JSON-Verarbeitung und Validierung der numerischen Felder
            try:
                data = json.loads(request.body)
            except (TypeError, ValueError) as exc:
                logger.warning(f'Ungültige JSON-Daten für ml_predict_weight: {exc}')
                return JsonResponse({
                    'success': False,
                    'message': 'Ungültige JSON-Daten'
                }, status=400)

            def _to_number(value, field_name):
                """
                Konvertiert Eingaben in numerische Werte oder None.
                Erlaubt sind: None, int, float oder numerische Strings.
                """
                if value is None:
                    return None
                if isinstance(value, (int, float)):
                    return value
                if isinstance(value, str):
                    stripped = value.strip()
                    if stripped == '':
                        return None
                    try:
                        return float(stripped)
                    except ValueError:
                        raise ValueError(field_name)
                # Alle anderen Typen (dict, list, bool, etc.) sind ungültig
                raise ValueError(field_name)

            try:
                last_weight = _to_number(data.get('last_weight'), 'last_weight')
                last_reps = _to_number(data.get('last_reps'), 'last_reps')
                rpe = _to_number(data.get('rpe'), 'rpe')
            except ValueError as invalid_field:
                field_name = invalid_field.args[0] if invalid_field.args else 'feld'
                logger.warning(f'Ungültiger numerischer Wert für {field_name} in ml_predict_weight')
                return JsonResponse({
                    'success': False,
                    'message': f'Ungültiger numerischer Wert für {field_name}'
                }, status=400)

        # Prediction
        result = predictor.predict_next_weight(
            last_weight=last_weight,
            last_reps=last_reps,
            rpe=rpe
        )

        return JsonResponse({
            'success': True,
            'uebung': uebung.bezeichnung,
            'prediction': result
        })

    except Exception as e:
        logger.error(f'ML Prediction Error: {e}', exc_info=True)
        return JsonResponse({
            'success': False,
            'message': 'Fehler bei Gewichtsvorhersage'
        }, status=500)


@login_required
@require_http_methods(["GET"])
def ml_model_info(request, uebung_id):
    """
    Info über trainiertes ML-Modell für eine Übung
    GET /api/ml/model-info/<uebung_id>/
    """
    from ml_coach.prediction_service import MLPredictor

    try:
        uebung = get_object_or_404(Uebung, id=uebung_id)
        predictor = MLPredictor(request.user, uebung)

        info = predictor.get_model_info()

        if info:
            return JsonResponse({
                'success': True,
                'uebung': uebung.bezeichnung,
                'model_info': info
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Kein Modell für diese Übung trainiert'
            }, status=404)

    except Exception as e:
        logger.error(f'ML Model Info Error: {e}', exc_info=True)
        return JsonResponse({
            'success': False,
            'message': 'Fehler beim Abrufen der Modell-Infos'
        }, status=500)


@login_required
@require_http_methods(["GET"])
def ml_dashboard(request):
    """
    Dashboard mit Übersicht aller trainierten ML-Modelle
    GET /ml/dashboard/
    """
    from ..models import MLPredictionModel

    models = MLPredictionModel.objects.filter(
        user=request.user
    ).select_related('uebung').order_by('-trained_at')

    context = {
        'ml_models': models,
        'total_models': models.count(),
        'ready_models': models.filter(status='READY').count(),
        'needs_training': models.filter(status='OUTDATED').count(),
    }

    return render(request, 'core/ml_dashboard.html', context)
