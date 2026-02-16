"""
Management Command: load_training_sources

Lädt 10 wissenschaftliche Quellen als Fixtures in die Datenbank.
Idempotent – kann mehrfach ausgeführt werden (get_or_create via doi/title).

Verwendung:
    python manage.py load_training_sources
    python manage.py load_training_sources --clear  # Löscht vorher alle Quellen
"""

from django.core.management.base import BaseCommand

from core.models import TrainingSource

SOURCES = [
    {
        "category": "VOLUME",
        "title": (
            "The Mechanisms of Muscle Hypertrophy and Their Application" " to Resistance Training"
        ),
        "authors": "Schoenfeld, B.J.",
        "year": 2010,
        "journal": "Journal of Strength and Conditioning Research",
        "doi": "10.1519/JSC.0b013e3181e840f3",
        "key_findings": [
            "Drei primäre Mechanismen der Muskelhypertrophie: mechanische Spannung,"
            " metabolischer Stress und Muskelschädigung.",
            "Mechanische Spannung ist der wichtigste Stimulus für langfristiges" " Muskelwachstum.",
            "Alle drei Mechanismen können durch richtiges Widerstandstraining" " optimiert werden.",
        ],
        "applies_to": ["volume_metrics", "general"],
    },
    {
        "category": "VOLUME",
        "title": (
            "Dose-response relationship between weekly resistance training volume"
            " and increases in muscle mass: A systematic review and meta-analysis"
        ),
        "authors": "Schoenfeld, B.J., Ogborn, D., & Krieger, J.W.",
        "year": 2017,
        "journal": "Journal of Sports Sciences",
        "doi": "10.1080/02640414.2016.1210197",
        "key_findings": [
            "Höheres Trainingsvolumen (>10 Sätze/Muskel/Woche) korreliert"
            " signifikant mit mehr Hypertrophie.",
            "Linearer Zusammenhang zwischen Volumen und Muskelmasse bis zu einem"
            " individuellen Maximum Recoverable Volume (MRV).",
            "Mindestvolumen für messbare Hypertrophie: ca. 4-6 Sätze/Muskel/Woche.",
        ],
        "applies_to": ["volume_metrics", "fatigue_index"],
    },
    {
        "category": "INTENSITY",
        "title": (
            "Validating the Use of a Psychophysiological Model for Autoregulating"
            " Resistance Training"
        ),
        "authors": (
            "Zourdos, M.C., Klemp, A., Dolan, C., Quiles, J.M., Schau, K.A.,"
            " Jo, E., Helms, E., Esgro, B., Duncan, S., Garcia Merino, S.,"
            " & Blanco, R."
        ),
        "year": 2016,
        "journal": "Journal of Strength and Conditioning Research",
        "doi": "10.1519/JSC.0000000000001291",
        "key_findings": [
            "Die RPE-Skala ist für Kraftsport auf 1-10 adaptierbar (RIR-basiert).",
            "RPE 7 = 3 Wdh. im Tank; RPE 8 = 2; RPE 9 = 1; RPE 10 = Versagen.",
            "Autoregulation via RPE führt zu besserer Anpassung an tagesaktuelle"
            " Leistungsfähigkeit als starre Prozentsätze.",
        ],
        "applies_to": ["rpe_quality", "fatigue_index"],
    },
    {
        "category": "GENERAL",
        "title": ("Fundamentals of Resistance Training: Progression and Exercise" " Prescription"),
        "authors": "Kraemer, W.J., & Ratamess, N.A.",
        "year": 2004,
        "journal": "Medicine & Science in Sports & Exercise",
        "doi": "10.1249/01.MSS.0000121945.36635.61",
        "key_findings": [
            "Progressive Überlastung ist das fundamentale Prinzip für Kraftzuwachs.",
            "Optimale Trainingsvariablen hängen vom individuellen Ziel ab.",
            "Anfänger: 3x8-12, ~70% 1RM. Fortgeschrittene profitieren von" " Periodisierung.",
        ],
        "applies_to": ["volume_metrics", "1rm_standards", "general"],
    },
    {
        "category": "PERIODIZATION",
        "title": "Essentials of Strength Training and Conditioning (4th Edition)",
        "authors": "Haff, G.G., & Triplett, N.T. (Eds.)",
        "year": 2016,
        "journal": "Human Kinetics / NSCA",
        "doi": "",
        "url": (
            "https://www.nsca.com/education/books/"
            "essentials-of-strength-training-and-conditioning/"
        ),
        "key_findings": [
            "Deload-Wochen alle 4-8 Wochen reduzieren akkumulierte Ermüdung und"
            " fördern Superkompensation.",
            "Periodisierung optimiert Langzeitfortschritt.",
            "Trainingsfrequenz: 2-4x pro Muskelgruppe/Woche für Hypertrophie.",
        ],
        "applies_to": ["fatigue_index", "plateau_analysis"],
    },
    {
        "category": "ONE_RM",
        "title": "Prediction of 1 and 6 RM strength from repetition-weight data",
        "authors": "Epley, B.",
        "year": 1985,
        "journal": "Boyd Epley Workout (University of Nebraska)",
        "doi": "",
        "url": "",
        "key_findings": [
            "Epley-Formel: 1RM = Gewicht x (1 + Wdh/30). Einfachste und"
            " meistgenutzte 1RM-Schätzformel.",
            "Genauer bei mittleren Wiederholungsbereichen (3-10). Bei >10 Wdh."
            " tendenziell leichte Überschätzung.",
            "Für Vergleiche über Zeit geeignet, da Fehler konsistent ist.",
        ],
        "applies_to": ["1rm_standards", "plateau_analysis"],
    },
    {
        "category": "RECOVERY",
        "title": ("Resistance exercise overtraining and overreaching:" " Neuroendocrine responses"),
        "authors": "Fry, A.C., & Kraemer, W.J.",
        "year": 1997,
        "journal": "Sports Medicine",
        "doi": "10.2165/00007256-199723002-00003",
        "key_findings": [
            "Akkumulierte Ermüdung ohne ausreichende Regeneration führt zu"
            " Leistungsrückgängen und Übertraining.",
            "Frühwarnzeichen: steigende RPE bei gleichem Gewicht, sinkende"
            " Motivation, Schlafstörungen.",
            "Deload: 40-50% Volumenreduktion für 1 Woche genügt zur Erholung.",
        ],
        "applies_to": ["fatigue_index"],
    },
    {
        "category": "PERIODIZATION",
        "title": "Scientific Principles of Strength Training",
        "authors": "Israetel, M., Hoffmann, J., & Rogge, T.",
        "year": 2019,
        "journal": "Renaissance Periodization",
        "doi": "",
        "url": "https://renaissanceperiodization.com/",
        "key_findings": [
            "MEV / MAV / MRV-Konzepte für individuelle Volumenplanung.",
            "Mesozyklus-Struktur: 4-8 Wochen Akkumulation + 1 Woche Deload.",
            "Progressiver Overload innerhalb eines Mesozyklus ist wichtiger als"
            " wöchentliche Steigerungen.",
        ],
        "applies_to": ["volume_metrics", "fatigue_index", "plateau_analysis"],
    },
    {
        "category": "INTENSITY",
        "title": (
            "RPE and Velocity Relationships for the Back Squat, Bench Press,"
            " and Deadlift in Powerlifters"
        ),
        "authors": "Helms, E.R., Cronin, J., Storey, A., & Zourdos, M.C.",
        "year": 2016,
        "journal": "Journal of Strength and Conditioning Research",
        "doi": "10.1519/JSC.0000000000001517",
        "key_findings": [
            "RPE-Skala korreliert stark mit % des 1RM in Grundübungen.",
            "RPE 7-9 entspricht ~75-95% des 1RM – optimaler Trainingsbereich.",
            "Konsistenz in der RPE-Bewertung verbessert sich mit Erfahrung.",
        ],
        "applies_to": ["rpe_quality"],
    },
    {
        "category": "VOLUME",
        "title": ("A Meta-Analysis to Determine the Dose Response" " for Strength Development"),
        "authors": "Rhea, M.R., Alvar, B.A., Burkett, L.N., & Ball, S.D.",
        "year": 2003,
        "journal": "Medicine & Science in Sports & Exercise",
        "doi": "10.1249/01.MSS.0000048636.73053.D6",
        "key_findings": [
            "Optimales Volumen: ~4 Sätze/Übung für Fortgeschrittene.",
            "Trainingsfrequenz von 2x/Woche je Muskelgruppe optimiert Kraftzuwachs.",
            "Mehr ist nicht immer besser – individuelle Erholung ist der" " limitierende Faktor.",
        ],
        "applies_to": ["volume_metrics", "plateau_analysis"],
    },
]


class Command(BaseCommand):
    help = "Lädt 10 wissenschaftliche Quellen als Fixtures in die Datenbank."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Löscht alle bestehenden Quellen vor dem Laden.",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            count, _ = TrainingSource.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"{count} Quellen gelöscht."))

        created_count = 0
        updated_count = 0

        for source_data in SOURCES:
            if source_data.get("doi"):
                obj, created = TrainingSource.objects.get_or_create(
                    doi=source_data["doi"],
                    defaults=source_data,
                )
            else:
                obj, created = TrainingSource.objects.get_or_create(
                    title=source_data["title"],
                    year=source_data["year"],
                    defaults=source_data,
                )

            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"  + Erstellt: {obj.citation_short}"))
            else:
                for field, value in source_data.items():
                    setattr(obj, field, value)
                obj.save()
                updated_count += 1
                self.stdout.write(f"  ~ Aktualisiert: {obj.citation_short}")

        self.stdout.write(
            self.style.SUCCESS(f"\nFertig: {created_count} erstellt, {updated_count} aktualisiert.")
        )
