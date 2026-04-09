"""Synchronisiert Übungen aus initial_exercises.json in die Datenbank.

Aktualisiert bestehende Übungen (by ID) und erstellt fehlende.
Sicher für wiederholte Ausführung (idempotent).
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand

from core.models import Equipment, Uebung
from core.models.constants import EQUIPMENT_CHOICES


class Command(BaseCommand):
    help = "Synchronisiert Übungen aus core/fixtures/initial_exercises.json (update + create)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Zeigt Änderungen ohne sie auszuführen",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        fixture_path = Path(__file__).resolve().parents[2] / "fixtures" / "initial_exercises.json"

        if not fixture_path.exists():
            self.stderr.write(self.style.ERROR(f"Fixture nicht gefunden: {fixture_path}"))
            return

        with open(fixture_path, encoding="utf-8") as f:
            data = json.load(f)
        exercises = data["exercises"] if isinstance(data, dict) else data

        # Equipment-Name → Objekt Mapping aufbauen
        equipment_map = {}
        for eq in Equipment.objects.all():
            equipment_map[eq.name] = eq
        for choice_value, choice_display in EQUIPMENT_CHOICES:
            if choice_display not in equipment_map:
                obj = Equipment.objects.filter(name=choice_value).first()
                if obj:
                    equipment_map[choice_display] = obj

        created, updated, unchanged = 0, 0, 0

        for ex_data in exercises:
            ex_id = ex_data.get("id")
            if not ex_id:
                continue

            defaults = {
                "bezeichnung": ex_data["bezeichnung"],
                "muskelgruppe": ex_data.get("muskelgruppe", "GANZKOERPER"),
                "hilfsmuskeln": ex_data.get("hilfsmuskeln", []),
                "bewegungstyp": ex_data.get("bewegungstyp", "ISOLATION"),
                "gewichts_typ": ex_data.get("gewichts_typ", "GESAMT"),
                "koerpergewicht_faktor": float(ex_data.get("koerpergewicht_faktor", 1.0)),
                "gewichts_richtung": ex_data.get("gewichts_richtung", "ZUSATZ"),
                "standard_beginner": ex_data.get("standard_beginner"),
                "standard_intermediate": ex_data.get("standard_intermediate"),
                "standard_advanced": ex_data.get("standard_advanced"),
                "standard_elite": ex_data.get("standard_elite"),
                "beschreibung": ex_data.get("beschreibung", ""),
            }

            equipment_names = ex_data.get("equipment", [])
            equipment_objs = [equipment_map[n] for n in equipment_names if n in equipment_map]

            existing = Uebung.objects.filter(id=ex_id).first()

            if dry_run:
                if existing:
                    # Prüfe ob sich was geändert hat
                    changed_fields = [k for k, v in defaults.items() if getattr(existing, k) != v]
                    if changed_fields:
                        self.stdout.write(
                            f"  UPDATE #{ex_id} {defaults['bezeichnung']}: {', '.join(changed_fields)}"
                        )
                        updated += 1
                    else:
                        unchanged += 1
                else:
                    self.stdout.write(
                        self.style.SUCCESS(f"  CREATE #{ex_id} {defaults['bezeichnung']}")
                    )
                    created += 1
                continue

            uebung, was_created = Uebung.objects.update_or_create(id=ex_id, defaults=defaults)
            uebung.equipment.set(equipment_objs)

            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f"  + {defaults['bezeichnung']}"))
            else:
                updated += 1

        prefix = "[DRY-RUN] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{prefix}{created} erstellt, {updated} aktualisiert, {unchanged} unverändert"
            )
        )
