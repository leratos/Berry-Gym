"""
Data Migration: korrigiert Wadenheben-Uebungen von GESAMT auf KOERPERGEWICHT.

Begruendung: Wadenheben stehend ist konzeptionell eine Koerpergewichts-Uebung
(man hebt sein eigenes Koerpergewicht auf die Zehen). Zusatzgewicht wie Langhantel
oder Maschine wird als Zusatzlast auf die Schultern gelegt – also Zusatzgewicht,
nicht Gesamtgewicht.

Konsequenz fuer bestehende Satz-Daten:
- Sätze mit gewicht=0: waren schon korrekt (nur Koerpergewicht)
- Saetze mit gewicht>0: bedeuten weiterhin Zusatzgewicht (unveraendert korrekt,
  da der User laut Angabe nur Zusatzgewicht eingetragen hat)

Faktor: 1.0 – beim Wadenheben wird das volle Koerpergewicht auf die Waden-
muskeln uebertragen (anders als z.B. Crunch wo nur Teilgewicht wirkt).
"""

from django.db import migrations


WADENHEBEN_BEZEICHNUNGEN = [
    "Wadenheben (Stehend)",
    "Wadenheben stehend (Calf Raises)",
    "Single Leg Calf Raises (Körpergewicht)",  # bereits KG, Faktor pruefen
]


def fix_wadenheben(apps, schema_editor):
    Uebung = apps.get_model("core", "Uebung")
    updated = Uebung.objects.filter(
        gewichts_typ="GESAMT",
        bezeichnung__in=[
            "Wadenheben (Stehend)",
            "Wadenheben stehend (Calf Raises)",
        ],
    ).update(gewichts_typ="KOERPERGEWICHT", koerpergewicht_faktor=1.0)
    print(f"\n  OK: {updated} Wadenheben-Uebungen auf KOERPERGEWICHT korrigiert")


def revert_wadenheben(apps, schema_editor):
    Uebung = apps.get_model("core", "Uebung")
    Uebung.objects.filter(
        gewichts_typ="KOERPERGEWICHT",
        bezeichnung__in=[
            "Wadenheben (Stehend)",
            "Wadenheben stehend (Calf Raises)",
        ],
    ).update(gewichts_typ="GESAMT", koerpergewicht_faktor=1.0)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0064_koerpergewicht_faktor_data"),
    ]

    operations = [
        migrations.RunPython(fix_wadenheben, revert_wadenheben),
    ]
