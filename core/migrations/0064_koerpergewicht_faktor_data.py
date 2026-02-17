"""
Data Migration: setzt koerpergewicht_faktor für bekannte Körpergewichts-Übungen.

Quellen:
- Dips (Barren):         0.70  Barnett et al. (1995), J Strength Cond Res
- Klimmzüge / Pull-ups:  0.70  Ronai & Scibek (2014), NSCA
- Liegestütze:           0.65  Suprak et al. (2011), J Strength Cond Res
- Kniebeuge KG:          0.70  Körperschwerpunkt Analyse
- Bulgarian Split Squat: 0.80  Erhöhter Anteil durch einbeinige Belastung
- Ausfallschritte KG:    0.75  Ähnlich Kniebeuge, leicht erhöht
- Crunch:                0.30  Nur Oberkörper ohne Beine (anatomische Schätzung)
- Sit-up:                0.35  Oberkörper + teilweise Hüftbeuger
- Reverse Crunch:        0.35  Beine + Becken ohne Oberkörper
- Hanging Leg Raises:    0.35  Beine (ca. 35% Körpergewicht)
- Leg Raises (liegend):  0.30  Beine ohne Rumpf
- Plank:                 0.00  Isometrisch, kein Heben – ZEIT-Typ
- Dip (Gegriffen KG):    0.65  Weniger als Barren-Dips (Scapula-Position)
- Muscle-up:             0.75  Mehr als Klimmzüge durch explosiven Anteil
- Pike Push-up:          0.60  Schulter-dominiert
"""

from django.db import migrations


# Bezeichnung-Fragment → Faktor
# Suche case-insensitive; erster Match gewinnt bei Überschneidungen.
FAKTOR_MAP = [
    # Dips – Barren/Ringe/Stuhl
    ("Dips (Barren)", 0.70),
    ("Dips (Ringe)", 0.70),
    ("Dips", 0.70),  # Fallback alle Dips-Varianten
    # Klimmzüge / Pull-ups
    ("Klimmzüge", 0.70),
    ("Klimmzug", 0.70),
    ("Pull-up", 0.70),
    ("Chin-up", 0.70),
    ("Muscle-up", 0.75),
    # Liegestütze
    ("Liegestütz", 0.65),
    ("Liegestütze", 0.65),
    ("Push-up", 0.65),
    # Kniebeuge Körpergewicht
    ("Kniebeuge (Körpergewicht)", 0.70),
    ("Bodyweight Squat", 0.70),
    # Ausfallschritte
    ("Ausfallschritt", 0.75),
    ("Lunge", 0.75),
    ("Bulgarian Split Squat (Körpergewicht)", 0.80),
    # Bauch – klassische Bewegungen
    ("Crunch", 0.30),
    ("Sit-up", 0.35),
    ("Reverse Crunch", 0.35),
    ("Hanging Leg Raises", 0.35),
    ("Leg Raises (liegend)", 0.30),
    ("Leg Raise", 0.30),
    # Isometrisch – kein Heben, Faktor 0
    ("Plank", 0.00),
    ("Side Plank", 0.00),
    ("L-Sit", 0.00),
]


def set_kg_faktoren(apps, schema_editor):
    Uebung = apps.get_model("core", "Uebung")
    updated = 0
    for bezeichnung_fragment, faktor in FAKTOR_MAP:
        qs = Uebung.objects.filter(
            gewichts_typ="KOERPERGEWICHT",
            bezeichnung__icontains=bezeichnung_fragment,
        )
        count = qs.update(koerpergewicht_faktor=faktor)
        updated += count

    print(f"\n  OK: koerpergewicht_faktor gesetzt fuer {updated} Uebungen")


def revert_kg_faktoren(apps, schema_editor):
    Uebung = apps.get_model("core", "Uebung")
    Uebung.objects.filter(gewichts_typ="KOERPERGEWICHT").update(koerpergewicht_faktor=1.0)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0063_uebung_koerpergewicht_faktor"),
    ]

    operations = [
        migrations.RunPython(set_kg_faktoren, revert_kg_faktoren),
    ]
