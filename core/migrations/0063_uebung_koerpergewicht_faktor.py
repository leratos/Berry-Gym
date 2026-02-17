from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0062_trainingsource"),
    ]

    operations = [
        migrations.AddField(
            model_name="uebung",
            name="koerpergewicht_faktor",
            field=models.FloatField(
                default=1.0,
                verbose_name="Körpergewicht-Faktor",
                help_text=(
                    "Anteil des Körpergewichts der bei dieser Übung bewegt wird (0.0–1.0). "
                    "Nur relevant für KOERPERGEWICHT-Übungen. "
                    "Dips/Klimmzüge ≈ 0.70, Crunch ≈ 0.30, volle KG-Übung = 1.0"
                ),
            ),
        ),
    ]
