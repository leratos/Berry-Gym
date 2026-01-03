from django.core.management.base import BaseCommand
from core.models import Uebung


class Command(BaseCommand):
    help = 'Fügt neue Übungen hinzu (nur Eigengewicht/Hanteln/Bank)'

    def handle(self, *args, **options):
        neue_uebungen = [
            # RUECKEN_OBERER
            {
                "bezeichnung": "Breites Rudern (Kurzhantel)",
                "muskelgruppe": "RUECKEN_OBERER",
                "hilfsmuskeln": ["Bizeps", "Rücken - Latissimus", "Rücken - Nacken/Trapez"],
                "gewichts_typ": "PRO_SEITE",
                "bewegungstyp": "ZIEHEN",
                "beschreibung": "Vorgebeugt, Hanteln seitlich zum Oberkörper ziehen. Ellbogen nach außen. Schulterblätter zusammenziehen.",
            },
            {
                "bezeichnung": "T-Bar Row (Langhantel)",
                "muskelgruppe": "RUECKEN_OBERER",
                "hilfsmuskeln": ["Bizeps", "Rücken - Latissimus", "Rücken - Nacken/Trapez"],
                "gewichts_typ": "GESAMT",
                "bewegungstyp": "ZIEHEN",
                "beschreibung": "Langhantel in Ecke. Vorgebeugt zur Brust ziehen. Schulterblätter zusammen, Rücken gerade.",
            },
            {
                "bezeichnung": "Seal Rows (Bank, Kurzhantel)",
                "muskelgruppe": "RUECKEN_OBERER",
                "hilfsmuskeln": ["Bizeps", "Rücken - Latissimus"],
                "gewichts_typ": "PRO_SEITE",
                "bewegungstyp": "ZIEHEN",
                "beschreibung": "Bauchlage auf Bank. Hanteln vertikal hochziehen. Keine Schwungbewegung, isoliert oberen Rücken.",
            },
            {
                "bezeichnung": "Inverted Rows (Körpergewicht)",
                "muskelgruppe": "RUECKEN_OBERER",
                "hilfsmuskeln": ["Bizeps", "Rücken - Latissimus", "Bauch"],
                "gewichts_typ": "KOERPERGEWICHT",
                "bewegungstyp": "ZIEHEN",
                "beschreibung": "Unter Tisch/Stange. Körper steif, hochziehen bis Brust fast Stange berührt. Schulterblätter aktiv.",
            },
            # RUECKEN_UNTEN
            {
                "bezeichnung": "Hyperextensions (Körpergewicht)",
                "muskelgruppe": "RUECKEN_UNTEN",
                "hilfsmuskeln": ["Po", "Beine - Oberschenkel hinten"],
                "gewichts_typ": "KOERPERGEWICHT",
                "bewegungstyp": "HEBEN",
                "beschreibung": "Bauchlage auf Bank. Oberkörper kontrolliert senken und heben. Rücken stabil, keine Überstreckung.",
            },
            {
                "bezeichnung": "Superman Holds (Körpergewicht)",
                "muskelgruppe": "RUECKEN_UNTEN",
                "hilfsmuskeln": ["Po", "Rücken - Oberer"],
                "gewichts_typ": "ZEIT",
                "bewegungstyp": "HEBEN",
                "beschreibung": "Bauchlage, Arme und Beine gestreckt anheben. Position halten. Fokus auf unteren Rücken.",
            },
            {
                "bezeichnung": "Stiff Leg Deadlift (Kurzhantel)",
                "muskelgruppe": "RUECKEN_UNTEN",
                "hilfsmuskeln": ["Po", "Beine - Oberschenkel hinten"],
                "gewichts_typ": "PRO_SEITE",
                "bewegungstyp": "HEBEN",
                "beschreibung": "Beine fast gestreckt, Hanteln vor Körper senken. Rücken gerade, Hüfte nach hinten. Dehnung in Hamstrings.",
            },
            {
                "bezeichnung": "Bird Dogs (Körpergewicht)",
                "muskelgruppe": "RUECKEN_UNTEN",
                "hilfsmuskeln": ["Po", "Bauch"],
                "gewichts_typ": "KOERPERGEWICHT",
                "bewegungstyp": "HEBEN",
                "beschreibung": "Vierfüßlerstand. Gegenarm und Bein strecken, halten, wechseln. Rücken stabil.",
            },
            # SCHULTER
            {
                "bezeichnung": "Pike Push-ups (Körpergewicht)",
                "muskelgruppe": "SCHULTER_VORN",
                "hilfsmuskeln": ["Trizeps", "Brust"],
                "gewichts_typ": "KOERPERGEWICHT",
                "bewegungstyp": "DRUECKEN",
                "beschreibung": "A-Position (Po hoch). Kopf zum Boden senken, hochdrücken. Fokus vordere Schulter.",
            },
            {
                "bezeichnung": "Front Raises (Kurzhantel)",
                "muskelgruppe": "SCHULTER_VORN",
                "hilfsmuskeln": [],
                "gewichts_typ": "PRO_SEITE",
                "bewegungstyp": "ISOLATION",
                "beschreibung": "Stehend, Hanteln vor Körper bis Schulterhöhe heben. Kontrolliert senken, kein Schwung.",
            },
            {
                "bezeichnung": "Upright Rows (Langhantel)",
                "muskelgruppe": "SCHULTER_SEIT",
                "hilfsmuskeln": ["Rücken - Nacken/Trapez", "Schulter - Vordere"],
                "gewichts_typ": "GESAMT",
                "bewegungstyp": "ZIEHEN",
                "beschreibung": "Enger Griff, Stange zum Kinn ziehen. Ellbogen hoch, kontrolliert senken.",
            },
            {
                "bezeichnung": "Lying Lateral Raises (Bank, Kurzhantel)",
                "muskelgruppe": "SCHULTER_SEIT",
                "hilfsmuskeln": [],
                "gewichts_typ": "PRO_SEITE",
                "bewegungstyp": "ISOLATION",
                "beschreibung": "Seitlage auf Bank. Obere Hantel seitlich heben. Isoliert seitliche Schulter.",
            },
            # TRAPEZ
            {
                "bezeichnung": "Langhantel Shrugs (Langhantel)",
                "muskelgruppe": "RUECKEN_TRAPEZ",
                "hilfsmuskeln": ["Nacken"],
                "gewichts_typ": "GESAMT",
                "bewegungstyp": "HEBEN",
                "beschreibung": "Stehend, Stange vor Körper. Schultern vertikal heben (shrugging motion). Keine Rotation.",
            },
            {
                "bezeichnung": "Prone I-Y-T Raises (Körpergewicht/leichte DB)",
                "muskelgruppe": "RUECKEN_TRAPEZ",
                "hilfsmuskeln": ["Schulter - Hintere", "Rücken - Oberer"],
                "gewichts_typ": "PRO_SEITE",
                "bewegungstyp": "HEBEN",
                "beschreibung": "Bauchlage auf Bank. Arme in I-, Y- und T-Position heben. Langsam, kontrolliert.",
            },
            # WADEN
            {
                "bezeichnung": "Single Leg Calf Raises (Körpergewicht)",
                "muskelgruppe": "WADEN",
                "hilfsmuskeln": [],
                "gewichts_typ": "KOERPERGEWICHT",
                "bewegungstyp": "ISOLATION",
                "beschreibung": "Einbeinig auf Kante/Stufe. Ferse senken, auf Zehenspitzen heben. Pro Seite.",
            },
            {
                "bezeichnung": "Seated Calf Raises (Kurzhantel auf Knien)",
                "muskelgruppe": "WADEN",
                "hilfsmuskeln": [],
                "gewichts_typ": "PRO_SEITE",
                "bewegungstyp": "ISOLATION",
                "beschreibung": "Sitzend, Hantel auf Knien. Fersen heben und senken. Fokus auf Soleus-Muskel.",
            },
            {
                "bezeichnung": "Donkey Calf Raises (Körpergewicht)",
                "muskelgruppe": "WADEN",
                "hilfsmuskeln": [],
                "gewichts_typ": "KOERPERGEWICHT",
                "bewegungstyp": "ISOLATION",
                "beschreibung": "Vorgebeugt, Hände auf Bank. Fersen heben und senken. Maximale Wadendehnung.",
            },
            # UNTERARME
            {
                "bezeichnung": "Reverse Wrist Curls (Kurzhantel)",
                "muskelgruppe": "UNTERARME",
                "hilfsmuskeln": [],
                "gewichts_typ": "PRO_SEITE",
                "bewegungstyp": "ISOLATION",
                "beschreibung": "Unterarme auf Bank, Handrücken oben. Hanteln mit Handgelenk heben. Unterarmstrecker trainieren.",
            },
            {
                "bezeichnung": "Farmer Walk (Kurzhantel)",
                "muskelgruppe": "UNTERARME",
                "hilfsmuskeln": ["Rücken - Nacken/Trapez", "Bauch"],
                "gewichts_typ": "PRO_SEITE",
                "bewegungstyp": "HEBEN",
                "beschreibung": "Schwere Hanteln halten und gehen. Aufrechte Haltung, Griffkraft trainieren.",
            },
            # PO
            {
                "bezeichnung": "Glute Kickbacks (Körpergewicht)",
                "muskelgruppe": "PO",
                "hilfsmuskeln": ["Beine - Oberschenkel hinten"],
                "gewichts_typ": "KOERPERGEWICHT",
                "bewegungstyp": "ISOLATION",
                "beschreibung": "Vierfüßlerstand. Bein nach hinten/oben strecken. Po anspannen, kontrolliert.",
            },
            {
                "bezeichnung": "Single Leg Hip Thrust (Körpergewicht/Hantel)",
                "muskelgruppe": "PO",
                "hilfsmuskeln": ["Beine - Oberschenkel hinten", "Bauch"],
                "gewichts_typ": "PRO_SEITE",
                "bewegungstyp": "HEBEN",
                "beschreibung": "Rücken auf Bank, ein Bein gestreckt. Hüfte heben, Po anspannen. Pro Seite.",
            },
            # ADDUKTOREN
            {
                "bezeichnung": "Side Lunges (Kurzhantel)",
                "muskelgruppe": "ADDUKTOREN",
                "hilfsmuskeln": ["Beine - Oberschenkel vorne", "Po"],
                "gewichts_typ": "PRO_SEITE",
                "bewegungstyp": "BEUGEN",
                "beschreibung": "Seitlicher Ausfallschritt. Gewicht auf Ferse, Knie über Fuß. Adduktoren dehnen.",
            },
            {
                "bezeichnung": "Copenhagen Planks (Körpergewicht)",
                "muskelgruppe": "ADDUKTOREN",
                "hilfsmuskeln": ["Bauch", "Rücken - Unterer"],
                "gewichts_typ": "ZEIT",
                "bewegungstyp": "ISOLATION",
                "beschreibung": "Seitlicher Plank, oberes Bein auf Bank. Körper gerade halten. Adduktoren aktiviert.",
            },
            {
                "bezeichnung": "Sumo Squats (Kurzhantel)",
                "muskelgruppe": "ADDUKTOREN",
                "hilfsmuskeln": ["Beine - Oberschenkel vorne", "Po"],
                "gewichts_typ": "GESAMT",
                "bewegungstyp": "BEUGEN",
                "beschreibung": "Breiter Stand, Füße nach außen. Tief beugen, Hantel zwischen Beinen. Adduktoren fokussieren.",
            },
            {
                "bezeichnung": "Cossack Squats (Körpergewicht/Kurzhantel)",
                "muskelgruppe": "ADDUKTOREN",
                "hilfsmuskeln": ["Beine - Oberschenkel vorne", "Po"],
                "gewichts_typ": "PRO_SEITE",
                "bewegungstyp": "BEUGEN",
                "beschreibung": "Breiter Stand. Zu einer Seite tief beugen, anderes Bein gestreckt. Seitenwechsel.",
            },
            # ABDUKTOREN
            {
                "bezeichnung": "Side-Lying Leg Raises (Körpergewicht)",
                "muskelgruppe": "ABDUKTOREN",
                "hilfsmuskeln": ["Po"],
                "gewichts_typ": "KOERPERGEWICHT",
                "bewegungstyp": "ISOLATION",
                "beschreibung": "Seitlage. Oberes Bein gerade anheben und senken. Fokus auf Abduktoren.",
            },
            {
                "bezeichnung": "Clamshells (Körpergewicht)",
                "muskelgruppe": "ABDUKTOREN",
                "hilfsmuskeln": ["Po"],
                "gewichts_typ": "KOERPERGEWICHT",
                "bewegungstyp": "ISOLATION",
                "beschreibung": "Seitlage, Knie gebeugt. Oberes Knie öffnen wie Muschel. Füße zusammen.",
            },
            {
                "bezeichnung": "Fire Hydrants (Körpergewicht)",
                "muskelgruppe": "ABDUKTOREN",
                "hilfsmuskeln": ["Po"],
                "gewichts_typ": "KOERPERGEWICHT",
                "bewegungstyp": "ISOLATION",
                "beschreibung": "Vierfüßlerstand. Knie seitlich anheben (90° Hüfte). Abduktoren und Po aktivieren.",
            },
            {
                "bezeichnung": "Standing Hip Abduction (Körpergewicht)",
                "muskelgruppe": "ABDUKTOREN",
                "hilfsmuskeln": ["Po", "Bauch"],
                "gewichts_typ": "KOERPERGEWICHT",
                "bewegungstyp": "ISOLATION",
                "beschreibung": "Stehend, ein Bein seitlich abheben. Balance halten, kontrolliert senken. Pro Seite.",
            },
            # HUEFTBEUGER
            {
                "bezeichnung": "Lying Leg Raises (Körpergewicht)",
                "muskelgruppe": "HUEFTBEUGER",
                "hilfsmuskeln": ["Bauch"],
                "gewichts_typ": "KOERPERGEWICHT",
                "bewegungstyp": "BEUGEN",
                "beschreibung": "Rückenlage. Gestreckte Beine anheben bis 90°. Kontrolliert senken ohne Boden zu berühren.",
            },
            {
                "bezeichnung": "Standing Knee Raises (Körpergewicht)",
                "muskelgruppe": "HUEFTBEUGER",
                "hilfsmuskeln": ["Bauch"],
                "gewichts_typ": "KOERPERGEWICHT",
                "bewegungstyp": "BEUGEN",
                "beschreibung": "Stehend. Knie abwechselnd bis Hüfthöhe ziehen. Kontrolliert, kein Schwung.",
            },
            {
                "bezeichnung": "Psoas Marches (Körpergewicht)",
                "muskelgruppe": "HUEFTBEUGER",
                "hilfsmuskeln": ["Bauch"],
                "gewichts_typ": "KOERPERGEWICHT",
                "bewegungstyp": "BEUGEN",
                "beschreibung": "Rückenlage, Beine 90° angewinkelt. Abwechselnd Ferse zum Boden senken ohne abzusetzen.",
            },
            {
                "bezeichnung": "Mountain Climbers (Körpergewicht)",
                "muskelgruppe": "HUEFTBEUGER",
                "hilfsmuskeln": ["Bauch", "Brust", "Schulter - Vordere"],
                "gewichts_typ": "KOERPERGEWICHT",
                "bewegungstyp": "BEUGEN",
                "beschreibung": "Plank-Position. Knie abwechselnd schnell zur Brust ziehen. Cardio und Hüftbeuger.",
            },
        ]

        count = 0
        for data in neue_uebungen:
            uebung, created = Uebung.objects.get_or_create(
                bezeichnung=data["bezeichnung"],
                defaults=data
            )
            if created:
                count += 1
                self.stdout.write(self.style.SUCCESS(f'✓ {data["bezeichnung"]}'))
            else:
                self.stdout.write(f'  {data["bezeichnung"]} (bereits vorhanden)')

        self.stdout.write(self.style.SUCCESS(f'\n{count} neue Übungen hinzugefügt!'))
        self.stdout.write(f'Gesamt: {Uebung.objects.count()} Übungen')
