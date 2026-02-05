"""
ML Prediction Service - Nutzt trainierte Modelle für Gewichtsvorhersagen

Funktionen:
- predict_next_weight(): Vorhersage basierend auf letzten Sätzen
- get_model_confidence(): Liefert Confidence-Score
- Inferenz: <10ms auf CPU
"""

import os
import joblib
import numpy as np
from datetime import timedelta
from django.core.cache import cache


class MLPredictor:
    """Macht Vorhersagen mit trainierten ML-Modellen"""
    
    def __init__(self, user, uebung):
        self.user = user
        self.uebung = uebung
        self._model = None
        self._ml_model_instance = None
    
    def load_model(self):
        """Lädt trainiertes Modell aus Cache oder Disk"""
        from core.models import MLPredictionModel
        
        # Cache-Key
        cache_key = f"ml_model_user_{self.user.id}_uebung_{self.uebung.id}"
        
        # Versuche aus Cache zu laden (schneller)
        cached_model = cache.get(cache_key)
        if cached_model:
            self._model, self._ml_model_instance = cached_model
            return True
        
        # Lade aus Datenbank
        try:
            ml_model = MLPredictionModel.objects.get(
                user=self.user,
                uebung=self.uebung,
                model_type='STRENGTH',
                status='READY'
            )
            
            # Lade Pickle-File
            if os.path.exists(ml_model.model_path):
                model = joblib.load(ml_model.model_path)
                self._model = model
                self._ml_model_instance = ml_model
                
                # Cache für 1 Stunde
                cache.set(cache_key, (model, ml_model), 3600)
                return True
            else:
                print(f"Modell-Datei nicht gefunden: {ml_model.model_path}")
                return False
                
        except MLPredictionModel.DoesNotExist:
            return False
    
    def predict_next_weight(self, last_weight=None, last_reps=None, rpe=None):
        """
        Vorhersage des nächsten Gewichts
        
        Args:
            last_weight: Letztes Gewicht (optional, sonst aus DB)
            last_reps: Letzte Wiederholungen (optional)
            rpe: RPE des letzten Satzes (optional)
        
        Returns:
            dict: {
                'predicted_weight': float,
                'confidence': float (0-1),
                'method': 'ml' | 'fallback',
                'explanation': str
            }
        """
        from core.models import Satz
        
        # Lade Modell
        if not self.load_model():
            return self._fallback_prediction(last_weight, last_reps, rpe)
        
        # Hole letzte Trainingsdaten falls nicht übergeben
        if last_weight is None or last_reps is None:
            last_satz = Satz.objects.filter(
                einheit__user=self.user,
                uebung=self.uebung,
                ist_aufwaermsatz=False
            ).select_related('einheit').order_by('-einheit__datum', '-id').first()
            
            if not last_satz:
                return {
                    'predicted_weight': None,
                    'confidence': 0.0,
                    'method': 'no_data',
                    'explanation': 'Keine vorherigen Trainingsdaten gefunden.'
                }
            
            last_weight = float(last_satz.gewicht)
            last_reps = float(last_satz.wiederholungen)
            rpe = float(last_satz.rpe or 7.0)
            
            # Days seit letztem Training
            previous_satz = Satz.objects.filter(
                einheit__user=self.user,
                uebung=self.uebung,
                ist_aufwaermsatz=False,
                einheit__datum__lt=last_satz.einheit.datum
            ).order_by('-einheit__datum').first()
            
            if previous_satz:
                days_since_last = (last_satz.training.datum - previous_satz.training.datum).days
            else:
                days_since_last = 7  # Default
        else:
            days_since_last = 7  # Default wenn manuell übergeben
        
        # Bereite Features vor
        # [last_weight, last_reps, days_since_last, rpe, set_number]
        set_number = 1  # Annahme: erster Satz
        features = np.array([[
            float(last_weight),
            float(last_reps),
            float(days_since_last),
            float(rpe or 7.0),
            float(set_number)
        ]])
        
        # Prediction (< 10ms)
        predicted_weight = self._model.predict(features)[0]
        
        # Confidence basierend auf MAE und Modell-Qualität
        mae = self._ml_model_instance.mean_absolute_error or 5.0
        r2 = self._ml_model_instance.accuracy_score or 0.5
        
        # Confidence: Je niedriger MAE und höher R², desto höher Confidence
        confidence = min(1.0, max(0.3, r2 * (1 - mae / 50)))
        
        # Runde auf sinnvolle Werte (2.5kg Schritte für Gewichte >20kg)
        if predicted_weight > 20:
            predicted_weight = round(predicted_weight / 2.5) * 2.5
        else:
            predicted_weight = round(predicted_weight * 2) / 2  # 0.5kg Schritte
        
        # Sicherheits-Check: Nicht mehr als +10kg auf einmal
        max_increase = last_weight + 10
        min_weight = last_weight - 5  # Max 5kg weniger
        predicted_weight = max(min_weight, min(predicted_weight, max_increase))
        
        return {
            'predicted_weight': round(predicted_weight, 1),
            'confidence': round(confidence, 2),
            'method': 'ml',
            'explanation': f'ML-Vorhersage (R²={r2:.2f}, MAE={mae:.1f}kg)',
            'model_samples': self._ml_model_instance.training_samples,
            'last_trained': self._ml_model_instance.trained_at.strftime('%d.%m.%Y')
        }
    
    def _fallback_prediction(self, last_weight, last_reps, rpe):
        """Fallback auf regelbasierte Vorhersage wenn kein ML-Modell vorhanden"""
        from core.models import Satz
        
        # Hole letztes Gewicht aus DB falls nicht übergeben
        if last_weight is None:
            last_satz = Satz.objects.filter(
                einheit__user=self.user,
                uebung=self.uebung,
                ist_aufwaermsatz=False
            ).order_by('-einheit__datum', '-id').first()
            
            if not last_satz:
                return {
                    'predicted_weight': None,
                    'confidence': 0.0,
                    'method': 'no_data',
                    'explanation': 'Keine Trainingsdaten vorhanden.'
                }
            
            last_weight = last_satz.gewicht
            last_reps = last_satz.wiederholungen
            rpe = last_satz.rpe or 7.0
        
        # Regelbasierte Logik (wie bisherige Gewichtsempfehlungen)
        if rpe and rpe < 7:
            # RPE zu leicht → Gewicht erhöhen
            increase = 2.5 if last_weight > 40 else 1.25
            predicted = last_weight + increase
            explanation = f"RPE {rpe} zu leicht → +{increase}kg empfohlen"
        elif last_reps and last_reps > 12:
            # Zu viele Wiederholungen → Gewicht erhöhen
            increase = 2.5
            predicted = last_weight + increase
            explanation = f"{last_reps} Wdh. erreicht → +{increase}kg"
        else:
            # Halten
            predicted = last_weight
            explanation = "Gewicht beibehalten"
        
        return {
            'predicted_weight': round(predicted, 1),
            'confidence': 0.5,  # Mittlere Confidence bei Regel-basiert
            'method': 'rules',
            'explanation': f'Regelbasiert: {explanation} (Kein ML-Modell trainiert)',
            'suggestion': 'Trainiere mind. 10 Sätze für ML-Vorhersage'
        }
    
    def get_model_info(self):
        """Liefert Infos über das trainierte Modell"""
        if not self.load_model():
            return None
        
        return {
            'status': self._ml_model_instance.status,
            'samples': self._ml_model_instance.training_samples,
            'r2_score': self._ml_model_instance.accuracy_score,
            'mae': self._ml_model_instance.mean_absolute_error,
            'last_trained': self._ml_model_instance.trained_at,
            'needs_retrain': self._ml_model_instance.needs_retraining(),
            'hyperparameters': self._ml_model_instance.hyperparameters,
        }
