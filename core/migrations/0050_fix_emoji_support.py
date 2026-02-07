# Generated migration to support Emojis in notiz fields
from django.db import migrations, connection


def apply_utf8mb4_if_mysql(apps, schema_editor):
    """Nur auf MySQL/MariaDB ausführen - SQLite unterstützt Emojis bereits"""
    if connection.vendor == 'mysql':
        with connection.cursor() as cursor:
            # Nur die Spalten die wirklich existieren (auf Production)
            cursor.execute("ALTER TABLE core_satz MODIFY notiz TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            cursor.execute("ALTER TABLE core_plan MODIFY beschreibung TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            # Andere Spalten könnten nicht existieren - ignoriere Fehler
            try:
                cursor.execute("ALTER TABLE core_trainingseinheit MODIFY notizen TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            except:
                pass
            try:
                cursor.execute("ALTER TABLE core_planuebung MODIFY notiz TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            except:
                pass


def reverse_utf8mb4_if_mysql(apps, schema_editor):
    """Rollback nur auf MySQL"""
    if connection.vendor == 'mysql':
        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE core_satz MODIFY notiz TEXT CHARACTER SET utf8 COLLATE utf8_unicode_ci;")
            cursor.execute("ALTER TABLE core_plan MODIFY beschreibung TEXT CHARACTER SET utf8 COLLATE utf8_unicode_ci;")
            try:
                cursor.execute("ALTER TABLE core_trainingseinheit MODIFY notizen TEXT CHARACTER SET utf8 COLLATE utf8_unicode_ci;")
            except:
                pass
            try:
                cursor.execute("ALTER TABLE core_planuebung MODIFY notiz TEXT CHARACTER SET utf8 COLLATE utf8_unicode_ci;")
            except:
                pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0025_pushsubscription'),  # Fallback auf sichere Migration
    ]

    operations = [
        migrations.RunPython(apply_utf8mb4_if_mysql, reverse_utf8mb4_if_mysql),
    ]
