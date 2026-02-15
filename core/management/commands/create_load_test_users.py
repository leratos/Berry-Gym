"""
Management Command: create_load_test_users
==========================================
Erstellt oder löscht Test-User für Locust Load Tests.

Usage:
  python manage.py create_load_test_users          # erstellen
  python manage.py create_load_test_users --delete # löschen
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

LOAD_TEST_USERS = [
    {"username": "loadtest_user1", "password": "LoadTest2024!"},
    {"username": "loadtest_user2", "password": "LoadTest2024!"},
    {"username": "loadtest_user3", "password": "LoadTest2024!"},
    {"username": "loadtest_user4", "password": "LoadTest2024!"},
    {"username": "loadtest_user5", "password": "LoadTest2024!"},
]


class Command(BaseCommand):
    help = "Erstellt oder löscht Test-User für Locust Load Tests"

    def add_arguments(self, parser):
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Test-User löschen statt erstellen",
        )

    def handle(self, *args, **options):
        if options["delete"]:
            self._delete_users()
        else:
            self._create_users()

    def _create_users(self):
        created = 0
        skipped = 0
        for credentials in LOAD_TEST_USERS:
            username = credentials["username"]
            if User.objects.filter(username=username).exists():
                self.stdout.write(f"  Übersprungen (existiert): {username}")
                skipped += 1
            else:
                User.objects.create_user(
                    username=username,
                    password=credentials["password"],
                    email=f"{username}@loadtest.local",
                )
                self.stdout.write(self.style.SUCCESS(f"  Erstellt: {username}"))
                created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\n{created} User erstellt, {skipped} übersprungen. " "Locust kann jetzt starten."
            )
        )

    def _delete_users(self):
        deleted, _ = User.objects.filter(username__startswith="loadtest_user").delete()
        self.stdout.write(self.style.SUCCESS(f"{deleted} Load-Test-User gelöscht."))
