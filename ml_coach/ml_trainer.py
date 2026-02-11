"""
ML Trainer - Trainiert scikit-learn Modelle für Gewichtsvorhersagen

Tech-Stack:
- scikit-learn Random Forest Regressor
- CPU-only (keine GPU benötigt)
- Kleine Datensätze (pro User)
- Training: <5 Sekunden
"""

import os
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split


class MLTrainer:
    """Trainiert ML-Modelle für Gewichtsvorhersagen"""

    def __init__(self, user, uebung):
        self.user = user
        self.uebung = uebung
        self.model_dir = os.path.join(settings.MEDIA_ROOT, "ml_models")
        os.makedirs(self.model_dir, exist_ok=True)

    def get_training_data(self):
        """
        Sammelt Trainingsdaten für Übung
        Features: [last_weight, last_reps, days_since_last, rpe, set_number]
        Target: next_weight
        """
        from core.models import Satz, Trainingseinheit

        # Alle Sätze dieser Übung vom User (letzte 6 Monate)
        six_months_ago = timezone.now() - timedelta(days=180)
        saetze = (
            Satz.objects.filter(
                einheit__user=self.user,
                uebung=self.uebung,
                einheit__datum__gte=six_months_ago,
                ist_aufwaermsatz=False,  # Nur Arbeitssätze
            )
            .select_related("einheit")
            .order_by("einheit__datum", "id")
        )

        if saetze.count() < 10:
            return None, None  # Zu wenig Daten

        features = []
        targets = []

        # Erstelle Trainingsbeispiele: Nutze Vorherige Sätze um nächstes Gewicht vorherzusagen
        saetze_list = list(saetze)

        for i in range(len(saetze_list) - 1):
            current = saetze_list[i]
            next_satz = saetze_list[i + 1]

            # Features vom aktuellen Satz
            days_since_last = 0
            if i > 0:
                prev_training = saetze_list[i - 1].einheit
                days_since_last = (current.einheit.datum - prev_training.datum).days

            # Satz-Nummer im Training
            set_number = list(current.einheit.saetze.filter(uebung=self.uebung)).index(current) + 1

            features.append(
                [
                    float(current.gewicht),
                    float(current.wiederholungen),
                    float(days_since_last),
                    float(current.rpe or 7.0),  # Default RPE
                    float(set_number),
                ]
            )

            targets.append(float(next_satz.gewicht))

        return np.array(features), np.array(targets)

    def train_model(self):
        """
        Trainiert Random Forest Regressor
        Returns: (model_instance, metrics_dict) oder (None, None) bei Fehler
        """
        from core.models import MLPredictionModel

        # Daten sammeln
        X, y = self.get_training_data()

        if X is None or len(X) < 10:
            return None, {"error": "Nicht genug Trainingsdaten (min. 10 benötigt)"}

        # Train/Test Split (80/20)
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # Random Forest Regressor (CPU-only)
        model = RandomForestRegressor(
            n_estimators=50,  # Wenige Trees für schnelles Training
            max_depth=10,
            min_samples_split=5,
            random_state=42,
            n_jobs=-1,  # Nutzt alle CPU-Cores
        )

        # Training (<5 Sekunden auf CPU)
        model.fit(X_train, y_train)

        # Evaluation
        y_pred = model.predict(X_test)
        mae = mean_absolute_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)

        # Modell speichern
        model_filename = f"user_{self.user.id}_uebung_{self.uebung.id}_strength.pkl"
        model_path = os.path.join(self.model_dir, model_filename)
        joblib.dump(model, model_path)

        # Feature-Statistiken für Normalisierung
        feature_stats = {
            "mean": X.mean(axis=0).tolist(),
            "std": X.std(axis=0).tolist(),
            "min": X.min(axis=0).tolist(),
            "max": X.max(axis=0).tolist(),
        }

        # DB Model aktualisieren oder erstellen
        ml_model, created = MLPredictionModel.objects.update_or_create(
            user=self.user,
            model_type="STRENGTH",
            uebung=self.uebung,
            defaults={
                "model_path": model_path,
                "status": "READY",
                "training_samples": len(X),
                "accuracy_score": r2,
                "mean_absolute_error": mae,
                "hyperparameters": {
                    "n_estimators": 50,
                    "max_depth": 10,
                    "min_samples_split": 5,
                },
                "feature_stats": feature_stats,
            },
        )

        metrics = {
            "samples": len(X),
            "mae": round(mae, 2),
            "r2_score": round(r2, 3),
            "model_path": model_path,
            "created": created,
        }

        return ml_model, metrics

    @staticmethod
    def train_all_user_models(user, min_samples=10):
        """
        Trainiert Modelle für alle Übungen des Users (wo genug Daten vorhanden)
        Returns: Liste von (uebung, metrics) Tuples
        """
        from core.models import Satz

        # Finde alle Übungen mit genug Trainingsdaten
        results = []

        uebungen_mit_daten = (
            Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False)
            .values("uebung")
            .annotate(count=models.Count("id"))
            .filter(count__gte=min_samples)
        )

        for item in uebungen_mit_daten:
            from core.models import Uebung

            uebung = Uebung.objects.get(id=item["uebung"])

            trainer = MLTrainer(user, uebung)
            ml_model, metrics = trainer.train_model()

            if ml_model:
                results.append((uebung, metrics))

        return results


# Quick-Import für Management Commands
from django.db import models
