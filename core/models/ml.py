"""ML-Prediction Models: MLPredictionModel."""

from django.contrib.auth.models import User
from django.db import models

from .exercise import Uebung


class MLPredictionModel(models.Model):
    """Trainierte ML-Modelle für Gewichtsvorhersagen pro User."""

    MODEL_TYPES = [
        ("STRENGTH", "Kraftvorhersage"),
        ("VOLUME", "Volumenempfehlung"),
        ("FREQUENCY", "Trainingsfrequenz"),
    ]
    STATUS_CHOICES = [
        ("TRAINING", "In Training"),
        ("READY", "Einsatzbereit"),
        ("OUTDATED", "Veraltet"),
        ("ERROR", "Fehler"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ml_models")
    model_type = models.CharField(max_length=20, choices=MODEL_TYPES, default="STRENGTH")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="TRAINING")
    model_path = models.CharField(max_length=500, verbose_name="Model File Path")
    trained_at = models.DateTimeField(auto_now=True, verbose_name="Letztes Training")
    training_samples = models.IntegerField(default=0, verbose_name="Anzahl Trainingsdaten")
    accuracy_score = models.FloatField(null=True, blank=True, verbose_name="R² Score")
    mean_absolute_error = models.FloatField(null=True, blank=True, verbose_name="MAE")
    uebung = models.ForeignKey(
        Uebung,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ml_models",
        verbose_name="Übung (für Kraftvorhersage)",
    )
    hyperparameters = models.JSONField(default=dict, blank=True, verbose_name="ML Hyperparameter")
    feature_stats = models.JSONField(default=dict, blank=True, verbose_name="Feature-Statistiken")

    def __str__(self):
        if self.uebung:
            return f"{self.user.username} - {self.get_model_type_display()} - {self.uebung.bezeichnung}"
        return f"{self.user.username} - {self.get_model_type_display()}"

    def is_ready(self):
        """Prüft, ob Modell einsatzbereit ist."""
        return self.status == "READY" and self.training_samples >= 10

    def needs_retraining(self):
        """Prüft, ob Modell neu trainiert werden sollte (>30 Tage alt)."""
        from datetime import timedelta

        from django.utils import timezone

        return timezone.now() - self.trained_at > timedelta(days=30)

    class Meta:
        verbose_name = "ML Prediction Model"
        verbose_name_plural = "ML Prediction Models"
        ordering = ["-trained_at"]
        unique_together = [["user", "model_type", "uebung"]]
        indexes = [
            models.Index(fields=["user", "model_type", "status"]),
            models.Index(fields=["user", "uebung", "status"]),
        ]
