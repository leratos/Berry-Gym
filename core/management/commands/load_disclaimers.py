"""
Management Command: Lädt Standard-Disclaimer in die Datenbank.

Usage: python manage.py load_disclaimers
"""

from django.core.management.base import BaseCommand

from core.models_disclaimer import ScientificDisclaimer


class Command(BaseCommand):
    help = "Lädt wissenschaftliche Standard-Disclaimer"

    def handle(self, *args, **options):
        disclaimers = [
            {
                "category": "1RM_STANDARDS",
                "title": "⚠️ 1RM-Standards: Eingeschränkte wissenschaftliche Basis",
                "message": """**Wichtiger Hinweis zur Interpretation der 1RM-Standards:**

Die dargestellten 1RM-Standards (Anfänger/Fortgeschritten/Elite) basieren auf einer **sehr begrenzten Datengrundlage** und sollten mit Vorsicht interpretiert werden:

**Probleme:**
- Nur ~20-30 Lifter pro Übung und Geschlecht
- Keine statistisch signifikanten Unterschiede zwischen den Levels
- Stark abhängig von Trainingsalter, nicht Leistungsniveau
- Fehlende Berücksichtigung von Körpergewicht und Technik

**Empfehlung:** Nutze die Standards als **grobe Orientierung**, nicht als absolutes Ziel. Fokussiere dich auf **individuelle Progression** und vergleiche dich primär mit deinen eigenen früheren Leistungen.

Für wissenschaftlich fundierte Standards siehe [Strength Level](https://strengthlevel.com) oder [ExRx](https://exrx.net/Testing/WeightLifting/StrengthStandards).""",
                "severity": "WARNING",
                "show_on_pages": ["stats/", "uebungen/"],
            },
            {
                "category": "FATIGUE_INDEX",
                "title": "ℹ️ Ermüdungsindex: Vereinfachtes Modell",
                "message": """**Der Ermüdungsindex ist ein vereinfachtes Modell:**

Die Berechnung basiert auf empirischen Annahmen, nicht auf wissenschaftlichen Studien:
- Volumenlast × RPE-Faktor
- Keine Berücksichtigung von Recovery-Kapazität
- Individuelle Unterschiede werden nicht erfasst

**Nutzen:** Überwachung von Belastungstrends, nicht absolute Fatigue-Messung.""",
                "severity": "INFO",
                "show_on_pages": ["dashboard/"],
            },
            {
                "category": "GENERAL",
                "title": "🔬 HomeGym: Fitness-Tracker, nicht medizinische Software",
                "message": """**HomeGym ist ein Trainings-Tracker für Kraftsportler**, kein medizinisches oder wissenschaftliches Tool.

**Wichtig:**
- Alle Berechnungen (1RM, Kalorien, FFMI) sind **Schätzungen**
- Bei Schmerzen oder gesundheitlichen Problemen: **Konsultiere einen Arzt**
- Keine Garantie für Richtigkeit der Trainingspläne oder Empfehlungen
- Nutzer trägt eigenverantwortlich das Verletzungsrisiko

**Empfehlung:** Nutze HomeGym als **Unterstützung** für dein Training, ersetze aber niemals professionelle Beratung.""",
                "severity": "INFO",
                "show_on_pages": [],
            },
        ]

        created_count = 0
        updated_count = 0

        for data in disclaimers:
            disclaimer, created = ScientificDisclaimer.objects.update_or_create(
                category=data["category"], defaults=data
            )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"[+] Erstellt: {disclaimer.get_category_display()}")
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f"[~] Aktualisiert: {disclaimer.get_category_display()}")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\n[OK] Fertig! {created_count} erstellt, {updated_count} aktualisiert"
            )
        )
