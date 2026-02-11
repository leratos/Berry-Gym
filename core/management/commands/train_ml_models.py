"""
Management Command: Trainiert ML-Modelle für alle User

Usage:
    python manage.py train_ml_models
    python manage.py train_ml_models --user-id 123
    python manage.py train_ml_models --min-samples 15
"""

import logging

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from ml_coach.ml_trainer import MLTrainer

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Trainiert ML-Modelle für Gewichtsvorhersagen (scikit-learn, CPU-only)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--user-id",
            type=int,
            help="Trainiert nur für spezifischen User (sonst alle)",
        )
        parser.add_argument(
            "--min-samples",
            type=int,
            default=10,
            help="Minimale Anzahl Trainingsdaten (default: 10)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Erzwingt Re-Training auch für aktuelle Modelle",
        )

    def handle(self, *args, **options):
        user_id = options.get("user_id")
        min_samples = options.get("min_samples", 10)
        force = options.get("force", False)

        self.stdout.write(self.style.SUCCESS("🤖 ML Training Service gestartet"))
        self.stdout.write(f"Minimale Samples: {min_samples}")

        if user_id:
            # Einzelner User
            try:
                user = User.objects.get(id=user_id)
                self.train_user_models(user, min_samples, force)
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"User {user_id} nicht gefunden"))
        else:
            # Alle User
            users = User.objects.filter(is_active=True)
            self.stdout.write(f"Trainiere Modelle für {users.count()} User...\n")

            for user in users:
                self.train_user_models(user, min_samples, force)

        self.stdout.write(self.style.SUCCESS("\n✅ Training abgeschlossen!"))

    def train_user_models(self, user, min_samples, force):
        """Trainiert alle Modelle für einen User"""
        self.stdout.write(f"\n👤 User: {user.username} (ID: {user.id})")

        results = MLTrainer.train_all_user_models(user, min_samples=min_samples)

        if not results:
            self.stdout.write(self.style.WARNING("  Keine Übungen mit genug Daten gefunden"))
            return

        for uebung, metrics in results:
            if metrics.get("created"):
                status = self.style.SUCCESS("✨ NEU")
            else:
                status = self.style.WARNING("🔄 AKTUALISIERT")

            self.stdout.write(
                f"  {status} {uebung.bezeichnung}: "
                f'{metrics["samples"]} Samples, '
                f'MAE={metrics["mae"]}kg, '
                f'R²={metrics["r2_score"]}'
            )

        self.stdout.write(self.style.SUCCESS(f"  → {len(results)} Modelle trainiert"))
