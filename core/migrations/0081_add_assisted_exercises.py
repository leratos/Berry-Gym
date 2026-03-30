"""Add assisted Dips and Pull-ups with GEGEN (counterweight) direction."""

from django.db import migrations


def create_assisted_exercises(apps, schema_editor):
    Uebung = apps.get_model("core", "Uebung")

    exercises = [
        {
            "bezeichnung": "Assistierte Dips (Gegengewicht)",
            "muskelgruppe": "TRIZEPS",
            "hilfsmuskeln": ["BRUST", "SCHULTER_VORN"],
            "bewegungstyp": "DRUECKEN",
            "gewichts_typ": "KOERPERGEWICHT",
            "koerpergewicht_faktor": 0.7,
            "gewichts_richtung": "GEGEN",
            "beschreibung": (
                "Assistierte Dips am Gerät mit Gegengewicht. "
                "Knie auf Polster, Gewicht wird vom Körpergewicht abgezogen. "
                "Schulterblätter stabil, kontrolliert absenken."
            ),
        },
        {
            "bezeichnung": "Assistierte Klimmzüge (Gegengewicht)",
            "muskelgruppe": "RUECKEN_LAT",
            "hilfsmuskeln": ["BIZEPS", "UNTERARME", "BAUCH"],
            "bewegungstyp": "ZIEHEN",
            "gewichts_typ": "KOERPERGEWICHT",
            "koerpergewicht_faktor": 0.7,
            "gewichts_richtung": "GEGEN",
            "beschreibung": (
                "Assistierte Klimmzüge am Gerät mit Gegengewicht. "
                "Knie auf Polster, Gewicht wird vom Körpergewicht abgezogen. "
                "Schulterblätter zuerst aktivieren, Brust zur Stange."
            ),
        },
    ]

    for data in exercises:
        Uebung.objects.get_or_create(
            bezeichnung=data["bezeichnung"],
            defaults=data,
        )


def remove_assisted_exercises(apps, schema_editor):
    Uebung = apps.get_model("core", "Uebung")
    Uebung.objects.filter(
        bezeichnung__in=[
            "Assistierte Dips (Gegengewicht)",
            "Assistierte Klimmzüge (Gegengewicht)",
        ]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0080_add_uebung_gewichts_richtung"),
    ]

    operations = [
        migrations.RunPython(
            create_assisted_exercises,
            remove_assisted_exercises,
        ),
    ]
