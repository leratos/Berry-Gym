"""
Konstanten & Auswahlmöglichkeiten für alle Models.
Zentrale Stelle für alle Choice-Listen.
"""

MUSKELGRUPPEN = [
    # Oberkörper Druck
    ("BRUST", "Brust (Pectoralis major)"),
    ("SCHULTER_VORN", "Schulter - Vordere (Deltoideus pars clavicularis)"),
    ("SCHULTER_SEIT", "Schulter - Seitliche (Deltoideus pars acromialis)"),
    ("SCHULTER_HINT", "Schulter - Hintere (Deltoideus pars spinalis)"),
    ("TRIZEPS", "Trizeps (Triceps brachii)"),
    # Oberkörper Zug
    ("RUECKEN_LAT", "Rücken - Breiter Muskel (Latissimus dorsi)"),
    ("RUECKEN_TRAPEZ", "Rücken - Nacken/Trapez (Trapezius)"),
    ("RUECKEN_UNTEN", "Unterer Rücken (Erector spinae)"),
    ("BIZEPS", "Bizeps (Biceps brachii)"),
    ("UNTERARME", "Unterarme (Brachioradialis/Flexoren)"),
    ("RUECKEN_OBERER", "Oberer Rücken (Rhomboiden, mittlerer Trapez)"),
    # Unterkörper
    ("BEINE_QUAD", "Oberschenkel Vorn (Quadrizeps)"),
    ("BEINE_HAM", "Oberschenkel Hinten (Hamstrings/Ischiocrurale)"),
    ("PO", "Gesäß (Gluteus maximus/medius)"),
    ("WADEN", "Waden (Gastrocnemius/Soleus)"),
    ("ADDUKTOREN", "Oberschenkel Innen (Adduktoren)"),
    ("ABDUKTOREN", "Oberschenkel Außen (Abduktoren)"),
    ("HUEFTBEUGER", "Hüftbeuger (Iliopsoas)"),
    # Sonstiges
    ("BAUCH", "Bauch (Abdominals)"),
    ("GANZKOERPER", "Ganzkörper / Cardio"),
]

GEWICHTS_TYP = [
    ("GESAMT", "Gesamtgewicht (z.B. Langhantel)"),
    ("PRO_SEITE", "Pro Seite/Hand (z.B. Kurzhanteln)"),
    ("KOERPERGEWICHT", "Körpergewicht (+/- Zusatz)"),
    ("ZEIT", "Zeit / Dauer (Sekunden)"),
]

GEWICHTS_RICHTUNG = [
    ("ZUSATZ", "Zusatzgewicht (wird addiert)"),
    ("GEGEN", "Gegengewicht (wird subtrahiert, z.B. assistierte Dips)"),
]

BEWEGUNGS_TYP = [
    ("DRUECKEN", "Drücken (Push)"),
    ("ZIEHEN", "Ziehen (Pull)"),
    ("BEUGEN", "Beugen (Squat-Pattern)"),
    ("HEBEN", "Heben (Hinge-Pattern)"),
    ("ISOLATION", "Isolation / Sonstiges"),
]

TAG_KATEGORIEN = [
    ("COMPOUND", "Compound (Mehrgelenksübung)"),
    ("ISOLATION", "Isolation (Eingelenkübung)"),
    ("BEGINNER", "Anfängerfreundlich"),
    ("ADVANCED", "Fortgeschritten"),
    ("FUNCTIONAL", "Funktionell"),
    ("POWER", "Explosiv / Power"),
    ("MOBILITY", "Mobilität / Beweglichkeit"),
    ("CARDIO", "Kardiovaskulär"),
    ("CORE", "Core / Rumpfstabilität"),
    ("UNILATERAL", "Unilateral (einseitig)"),
    ("INJURY_PRONE", "Verletzungsanfällig"),
    ("LOW_IMPACT", "Gelenkschonend"),
]

EQUIPMENT_CHOICES = [
    ("LANGHANTEL", "Langhantel"),
    ("KURZHANTEL", "Kurzhanteln"),
    ("KETTLEBELL", "Kettlebell"),
    ("BANK", "Flachbank"),
    ("SCHRAEGBANK", "Schrägbank"),
    ("KLIMMZUG", "Klimmzugstange"),
    ("DIP", "Dipstation / Barren"),
    ("KABELZUG", "Kabelzug / Latzug"),
    ("BEINPRESSE", "Beinpresse"),
    ("LEG_CURL", "Leg Curl Maschine"),
    ("LEG_EXT", "Leg Extension Maschine"),
    ("SMITHMASCHINE", "Smith Maschine"),
    ("HACKENSCHMIDT", "Hackenschmidt"),
    ("RUDERMASCHINE", "Rudermaschine"),
    ("WIDERSTANDSBAND", "Widerstandsbänder"),
    ("SUSPENSION", "Suspension Trainer (TRX)"),
    ("MEDIZINBALL", "Medizinball"),
    ("BOXEN", "Plyo Box"),
    ("MATTE", "Trainingsmatte"),
    ("KOERPER", "Nur Körpergewicht"),
    ("ADDUKTOREN_MASCHINE", "Adduktoren Maschine"),
    ("ABDUKTOREN_MASCHINE", "Abduktoren Maschine"),
    ("BRUSTPRESSE_MASCHINE", "Brustpresse Maschine"),
]

CARDIO_AKTIVITAETEN = [
    ("SCHWIMMEN", "Schwimmen"),
    ("LAUFEN", "Laufen"),
    ("RADFAHREN", "Radfahren"),
    ("RUDERN", "Rudern"),
    ("GEHEN", "Gehen / Walking"),
    ("HIIT", "HIIT / Intervall"),
    ("STEPPER", "Stepper / Crosstrainer"),
    ("SEILSPRINGEN", "Seilspringen"),
    ("SONSTIGES", "Sonstiges"),
]

CARDIO_INTENSITAET = [
    ("LEICHT", "Leicht (Zone 2 - kann sich unterhalten)"),
    ("MODERAT", "Moderat (Zone 3 - anstrengend aber machbar)"),
    ("INTENSIV", "Intensiv (Zone 4-5 - sehr anstrengend)"),
]

FEEDBACK_TYPE_CHOICES = [
    ("BUG", "🐛 Bugreport"),
    ("FEATURE", "💡 Verbesserungsvorschlag"),
    ("QUESTION", "❓ Frage"),
]

FEEDBACK_STATUS_CHOICES = [
    ("NEW", "🆕 Neu"),
    ("ACCEPTED", "✅ Angenommen"),
    ("REJECTED", "❌ Abgelehnt"),
    ("IN_PROGRESS", "🔄 In Bearbeitung"),
    ("DONE", "🎉 Umgesetzt"),
]

FEEDBACK_PRIORITY_CHOICES = [
    ("LOW", "🟢 Niedrig"),
    ("MEDIUM", "🟡 Mittel"),
    ("HIGH", "🔴 Hoch"),
]
