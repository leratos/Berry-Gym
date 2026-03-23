# Generated manually 2026-03-23

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0077_add_pr_fields_to_satz"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Trainingsblock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "name",
                    models.CharField(blank=True, max_length=100, verbose_name="Blockname"),
                ),
                (
                    "typ",
                    models.CharField(
                        choices=[
                            ("definition", "Definition / Hypertrophie"),
                            ("masse", "Masseaufbau"),
                            ("kraft", "Kraft"),
                            ("peaking", "Peaking / Wettkampf"),
                            ("deload", "Deload-Block"),
                            ("sonstige", "Sonstige"),
                        ],
                        default="sonstige",
                        max_length=20,
                        verbose_name="Block-Typ",
                    ),
                ),
                ("start_datum", models.DateField(verbose_name="Startdatum")),
                ("end_datum", models.DateField(blank=True, null=True, verbose_name="Enddatum")),
                (
                    "ziel_rep_range_min",
                    models.PositiveIntegerField(blank=True, null=True, verbose_name="Ziel-Wdh. (min)"),
                ),
                (
                    "ziel_rep_range_max",
                    models.PositiveIntegerField(blank=True, null=True, verbose_name="Ziel-Wdh. (max)"),
                ),
                ("notiz", models.TextField(blank=True, verbose_name="Notiz")),
                (
                    "plan",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="trainingsblöcke",
                        to="core.plan",
                        verbose_name="Trainingsplan",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="trainingsblöcke",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Trainingsblock",
                "verbose_name_plural": "Trainingsblöcke",
                "ordering": ["-start_datum"],
            },
        ),
        migrations.AddIndex(
            model_name="trainingsblock",
            index=models.Index(fields=["user", "start_datum"], name="block_user_start_idx"),
        ),
        migrations.AddIndex(
            model_name="trainingsblock",
            index=models.Index(fields=["user", "end_datum"], name="block_user_end_idx"),
        ),
    ]
