"""
core/models/__init__.py

Re-exportiert alle Models aus den Sub-Modulen.
WICHTIG: Alle bestehenden Imports (from core.models import X) funktionieren
weiterhin ohne Änderungen — dieses File ist das einzige Interface nach außen.
"""

# Body Tracking
from .body_tracking import KoerperWerte, ProgressPhoto  # noqa: F401

# Cardio
from .cardio import CardioEinheit  # noqa: F401

# Konstanten & Choices
from .constants import (  # noqa: F401
    BEWEGUNGS_TYP,
    CARDIO_AKTIVITAETEN,
    CARDIO_INTENSITAET,
    EQUIPMENT_CHOICES,
    FEEDBACK_PRIORITY_CHOICES,
    FEEDBACK_STATUS_CHOICES,
    FEEDBACK_TYPE_CHOICES,
    GEWICHTS_TYP,
    MUSKELGRUPPEN,
    TAG_KATEGORIEN,
)

# Disclaimer (bereits eigene Datei — bleibt wie gehabt)
from .disclaimer import ScientificDisclaimer  # noqa: F401

# Exercise
from .exercise import Equipment, Uebung, UebungTag  # noqa: F401

# Feedback & Notifications
from .feedback import Feedback, PushSubscription  # noqa: F401

# ML
from .ml import MLPredictionModel  # noqa: F401

# Plan
from .plan import Plan, PlanUebung  # noqa: F401

# Social / Beta-Zugang
from .social import InviteCode, WaitlistEntry  # noqa: F401

# Training
from .training import Satz, Trainingseinheit  # noqa: F401

# Scientific Sources
from .training_source import TrainingSource  # noqa: F401

# User Profile
from .user_profile import UserProfile  # noqa: F401

__all__ = [
    # Konstanten
    "BEWEGUNGS_TYP",
    "CARDIO_AKTIVITAETEN",
    "CARDIO_INTENSITAET",
    "EQUIPMENT_CHOICES",
    "FEEDBACK_PRIORITY_CHOICES",
    "FEEDBACK_STATUS_CHOICES",
    "FEEDBACK_TYPE_CHOICES",
    "GEWICHTS_TYP",
    "MUSKELGRUPPEN",
    "TAG_KATEGORIEN",
    # Models
    "CardioEinheit",
    "Equipment",
    "Feedback",
    "InviteCode",
    "KoerperWerte",
    "MLPredictionModel",
    "Plan",
    "PlanUebung",
    "ProgressPhoto",
    "PushSubscription",
    "Satz",
    "ScientificDisclaimer",
    "Trainingseinheit",
    "TrainingSource",
    "Uebung",
    "UebungTag",
    "UserProfile",
    "WaitlistEntry",
]
