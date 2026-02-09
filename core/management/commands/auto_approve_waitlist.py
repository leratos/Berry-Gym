"""
Management Command: Auto-Approve Wartelisten-Einträge nach 48h
Verwendung: python manage.py auto_approve_waitlist
Empfohlen als Cron-Job (täglich ausführen)
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import WaitlistEntry


class Command(BaseCommand):
    help = "Approved automatisch Wartelisten-Einträge, die älter als 48 Stunden sind"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Zeigt nur an, was passieren würde (ohne Änderungen)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        # Finde alle Einträge die approved werden sollten
        pending_entries = WaitlistEntry.objects.filter(status="pending")

        approved_count = 0
        for entry in pending_entries:
            if entry.should_auto_approve():
                if dry_run:
                    self.stdout.write(
                        self.style.WARNING(f"[DRY-RUN] Würde approven: {entry.email}")
                    )
                else:
                    success = entry.approve_and_send_code()
                    if success:
                        self.stdout.write(
                            self.style.SUCCESS(f"✅ Approved & Email gesendet: {entry.email}")
                        )
                        approved_count += 1
                    else:
                        self.stdout.write(self.style.ERROR(f"❌ Fehler bei: {entry.email}"))

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"\n[DRY-RUN] {approved_count} Einträge würden approved werden")
            )
        else:
            self.stdout.write(self.style.SUCCESS(f"\n✅ {approved_count} Einträge wurden approved"))

        # Statistik
        total_pending = WaitlistEntry.objects.filter(status="pending").count()
        total_approved = WaitlistEntry.objects.filter(status="approved").count()
        total_registered = WaitlistEntry.objects.filter(status="registered").count()

        self.stdout.write("\n--- Wartelisten-Statistik ---")
        self.stdout.write(f"Wartend: {total_pending}")
        self.stdout.write(f"Approved: {total_approved}")
        self.stdout.write(f"Registriert: {total_registered}")
