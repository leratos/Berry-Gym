from django.core.management.base import BaseCommand
from core.models import UebungTag

class Command(BaseCommand):
    help = 'Erstellt Standard-Tags für Übungen'

    def handle(self, *args, **options):
        # Tag-Konfigurationen (Name, Farbe)
        tags_config = [
            ('COMPOUND', '#0d6efd'),      # Blau - Mehrgelenksübung
            ('ISOLATION', '#6f42c1'),     # Lila - Isolation
            ('BEGINNER', '#198754'),      # Grün - Anfängerfreundlich
            ('ADVANCED', '#dc3545'),      # Rot - Fortgeschritten
            ('FUNCTIONAL', '#fd7e14'),    # Orange - Funktionell
            ('POWER', '#e83e8c'),         # Pink - Explosiv
            ('MOBILITY', '#20c997'),      # Türkis - Mobilität
            ('CARDIO', '#d63384'),        # Magenta - Kardio
            ('CORE', '#ffc107'),          # Gelb - Core
            ('UNILATERAL', '#17a2b8'),    # Cyan - Unilateral
            ('INJURY_PRONE', '#dc3545'),  # Rot - Verletzungsanfällig
            ('LOW_IMPACT', '#28a745'),    # Grün - Gelenkschonend
        ]

        created_count = 0
        for tag_name, farbe in tags_config:
            tag, created = UebungTag.objects.get_or_create(
                name=tag_name,
                defaults={'farbe': farbe}
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Tag erstellt: {tag.get_name_display()} ({farbe})')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'- Tag existiert bereits: {tag.get_name_display()}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'\n✅ {created_count} neue Tags erstellt, {len(tags_config) - created_count} bereits vorhanden')
        )
