"""
Management Command zum Synchronisieren der Equipment-Verknüpfungen für neue Übungen.

Usage:
    python manage.py sync_equipment
"""

from django.core.management.base import BaseCommand

from core.models import Equipment, Uebung


class Command(BaseCommand):
    help = "Synchronisiert Equipment-Verknüpfungen für neue Übungen"

    def handle(self, *args, **options):
        self.stdout.write("=" * 80)
        self.stdout.write("EQUIPMENT-VERKNÜPFUNGEN SYNCHRONISIEREN")
        self.stdout.write("=" * 80)

        # Mapping: Übungsname -> Equipment-Namen (DB-Keys)
        exercise_equipment = {
            "Brustpresse (Kabelzug)": ["KABELZUG"],
            "Brustpresse (Maschine)": ["BRUSTPRESSE_MASCHINE"],
            "Farmers Carry": ["KETTLEBELL", "KURZHANTEL"],
            "Pull-Through (Kabelzug)": ["KABELZUG"],
            "Seitstütz (Side Plank)": ["MATTE"],
        }

        updated_count = 0
        created_equipment = []
        errors = []

        for uebung_name, equipment_names in exercise_equipment.items():
            try:
                # Übung finden
                uebung = Uebung.objects.get(bezeichnung=uebung_name)

                equipment_objs = []
                for eq_name in equipment_names:
                    # Equipment holen oder erstellen
                    eq, created = Equipment.objects.get_or_create(name=eq_name)
                    if created:
                        created_equipment.append(f"{eq_name} ({eq.get_name_display()})")
                    equipment_objs.append(eq)

                # Equipment zuweisen
                uebung.equipment.set(equipment_objs)

                eq_display = ", ".join(eq.get_name_display() for eq in equipment_objs)
                self.stdout.write(self.style.SUCCESS(f"OK {uebung_name}"))
                self.stdout.write(f"  Equipment: {eq_display}")

                updated_count += 1

            except Uebung.DoesNotExist:
                msg = f"Übung nicht gefunden: {uebung_name}"
                errors.append(msg)
                self.stdout.write(self.style.WARNING(f"WARNUNG {msg}"))

            except Exception as e:
                msg = f"Fehler bei {uebung_name}: {e}"
                errors.append(msg)
                self.stdout.write(self.style.ERROR(f"FEHLER {msg}"))

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(f"Übungen aktualisiert: {updated_count}")

        if created_equipment:
            self.stdout.write("\nNEU erstelltes Equipment:")
            for eq in created_equipment:
                self.stdout.write(f"  - {eq}")

        if errors:
            self.stdout.write(self.style.ERROR(f"\nFehler: {len(errors)}"))
            for err in errors:
                self.stdout.write(f"  - {err}")
        else:
            self.stdout.write(self.style.SUCCESS("\nAlle Verknüpfungen erfolgreich!"))

        self.stdout.write("=" * 80)

        # Verifikation
        self.stdout.write("\nVERIFIKATION:")
        try:
            eq = Equipment.objects.get(name="BRUSTPRESSE_MASCHINE")
            count = eq.uebungen.count()
            self.stdout.write(f"Brustpresse Maschine: {count} Übung(en)")
            if count > 0:
                self.stdout.write(self.style.SUCCESS("Equipment ist jetzt verfügbar!"))
        except Equipment.DoesNotExist:
            self.stdout.write(self.style.ERROR("BRUSTPRESSE_MASCHINE nicht gefunden!"))
