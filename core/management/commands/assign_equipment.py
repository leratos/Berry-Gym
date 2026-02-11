"""
Management Command: Equipment zu Übungen zuordnen
Weist automatisch Equipment basierend auf Übungsnamen zu
"""

from django.core.management.base import BaseCommand

from core.models import EQUIPMENT_CHOICES, Equipment, Uebung


class Command(BaseCommand):
    help = "Weist Übungen automatisch passendes Equipment zu"

    def handle(self, *args, **options):
        # Equipment initial erstellen
        self.stdout.write("Erstelle Equipment-Einträge...")
        for eq_code, eq_name in EQUIPMENT_CHOICES:
            eq, created = Equipment.objects.get_or_create(name=eq_code)
            if created:
                self.stdout.write(f"  ✓ {eq_name} erstellt")

        # Equipment Mapping (Code → Equipment Object)
        equipment_map = {eq.name: eq for eq in Equipment.objects.all()}

        # Keyword-basierte Zuordnung
        equipment_keywords = {
            "LANGHANTEL": [
                "langhantel",
                "barbell",
                "squat",
                "kreuzheben",
                "deadlift",
                "frontdrücken",
            ],
            "KURZHANTEL": ["kurzhantel", "dumbbell", "kh-"],
            "KETTLEBELL": ["kettlebell", "kb-"],
            "BANK": ["bankdrücken", "bench press", "fliegend", "floor press"],
            "SCHRAEGBANK": ["schrägbank", "incline"],
            "KLIMMZUG": ["klimmzug", "pull-up", "chin-up"],
            "DIP": ["dips", "dip"],
            "KABELZUG": ["kabel", "cable", "latzug", "lat pulldown", "facepull"],
            "BEINPRESSE": ["beinpresse", "leg press"],
            "LEG_CURL": ["leg curl", "beinbeuger"],
            "LEG_EXT": ["leg extension", "beinstrecker"],
            "SMITHMASCHINE": ["smith"],
            "HACKENSCHMIDT": ["hackenschmidt", "hack squat"],
            "RUDERMASCHINE": ["rudermaschine", "seilzug"],
            "WIDERSTANDSBAND": ["widerstandsband", "band"],
            "SUSPENSION": ["trx", "suspension"],
            "MEDIZINBALL": ["medizinball"],
            "BOXEN": ["box jump", "plyo"],
            "MATTE": ["plank", "sit-up", "crunch", "hollow", "superman", "bird dog"],
            "KOERPER": [
                "push-up",
                "liegestütz",
                "burpee",
                "mountain climber",
                "wandsitz",
                "ausfallschritt",
            ],
        }

        # Spezielle Equipment-Kombinationen
        special_cases = {
            # Übungsname (teilweise) → Equipment-Liste
            "bankdrücken (langhantel)": ["LANGHANTEL", "BANK"],
            "bankdrücken (kurzhantel)": ["KURZHANTEL", "BANK"],
            "schrägbankdrücken": ["LANGHANTEL", "SCHRAEGBANK"],
            "frontsquat": ["LANGHANTEL"],
            "back squat": ["LANGHANTEL"],
            "romanian deadlift": ["LANGHANTEL"],
            "rdl": ["LANGHANTEL"],
            "overhead press": ["LANGHANTEL"],
            "military press": ["LANGHANTEL"],
            "bent over row": ["LANGHANTEL"],
            "langhantel-rudern": ["LANGHANTEL"],
        }

        self.stdout.write("\nZuordnung von Equipment zu Übungen...")
        updated_count = 0

        for uebung in Uebung.objects.all():
            name_lower = uebung.bezeichnung.lower()
            assigned_equipment = set()

            # Spezielle Cases prüfen
            for special_key, eq_codes in special_cases.items():
                if special_key in name_lower:
                    for eq_code in eq_codes:
                        if eq_code in equipment_map:
                            assigned_equipment.add(equipment_map[eq_code])

            # Keyword-basierte Zuordnung
            if not assigned_equipment:  # Nur wenn noch nichts zugewiesen
                for eq_code, keywords in equipment_keywords.items():
                    for keyword in keywords:
                        if keyword.lower() in name_lower:
                            if eq_code in equipment_map:
                                assigned_equipment.add(equipment_map[eq_code])

            # Equipment zuweisen
            if assigned_equipment:
                uebung.equipment.set(assigned_equipment)
                eq_names = ", ".join([str(eq) for eq in assigned_equipment])
                self.stdout.write(f"  ✓ {uebung.bezeichnung}: {eq_names}")
                updated_count += 1
            else:
                # Fallback: Nur Körpergewicht
                if "KOERPER" in equipment_map:
                    uebung.equipment.add(equipment_map["KOERPER"])
                    self.stdout.write(f"  ⚠ {uebung.bezeichnung}: Nur Körpergewicht (Fallback)")
                    updated_count += 1

        self.stdout.write(self.style.SUCCESS(f"\n✅ {updated_count} Übungen aktualisiert"))

        # Statistik
        self.stdout.write("\n📊 Statistik:")
        for eq in Equipment.objects.all():
            count = eq.uebungen.count()
            self.stdout.write(f"  {eq}: {count} Übungen")
