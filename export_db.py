#!/usr/bin/env python
"""
HomeGym - Datenbank Export/Import Tool
=======================================
Exportiert alle Benutzerdaten (User, Training, Pläne, Körperwerte etc.)
von der lokalen SQLite DB für den Import auf dem Production Server.

Verwendung:
    # Lokales System (Windows/Linux):
    python export_db.py
    
    # Server (Linux) - Import:
    python3 import_db.py homegym_backup_2026-01-04.json

Features:
    - Exportiert alle relevanten Daten als JSON
    - Bewahrt Relationen zwischen Objekten
    - Überspringt Übungen (werden via initial_exercises.json geladen)
    - Timestamp im Dateinamen
    - Sicherer Import mit Validierung
    
HINWEIS:
    Für Export: .env Datei wird temporär umbenannt um SQLite zu nutzen
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

# VOR Django-Import: .env temporär umbenennen um SQLite zu erzwingen
ENV_FILE = Path(__file__).parent / '.env'
ENV_BACKUP = Path(__file__).parent / '.env.backup_temp'
env_renamed = False

def restore_env():
    """Stellt .env wieder her falls umbenannt."""
    global env_renamed
    if env_renamed and ENV_BACKUP.exists():
        ENV_BACKUP.rename(ENV_FILE)
        env_renamed = False
        print("✓ .env wiederhergestellt")

# Bei Export-Modus: .env temporär entfernen
if len(sys.argv) == 1 and ENV_FILE.exists():
    ENV_FILE.rename(ENV_BACKUP)
    env_renamed = True
    print("ℹ️  .env temporär deaktiviert - nutze SQLite für Export")
    print()

# Django Setup
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

try:
    django.setup()
except Exception as e:
    restore_env()
    raise

from django.core import management
from django.core.management import call_command
from io import StringIO


# Apps und Models die exportiert werden sollen
EXPORT_MODELS = [
    # User & Auth
    'auth.User',
    
    # Core App - Übungen (WICHTIG: Müssen mit exportiert werden!)
    'core.Uebung',
    
    # Core App - User-Daten
    'core.Koerperwerte',
    'core.Plan',
    'core.Trainingseinheit',
    'core.Satz',
]

# Models die NICHT exportiert werden (werden auf Server neu geladen)
SKIP_MODELS = [
    # Nichts mehr - Übungen werden jetzt mit exportiert für konsistente IDs
]


def export_data():
    """Exportiert alle Benutzerdaten als JSON."""
    
    try:
        print("=" * 70)
        print("🏋️ HomeGym - Datenbank Export")
        print("=" * 70)
        print()
        
        # Timestamp für Dateinamen
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"homegym_backup_{timestamp}.json"
        
        print(f"📦 Exportiere Daten nach: {filename}")
        print()
        
        # Models-Info anzeigen
        print("📋 Zu exportierende Daten:")
        for model in EXPORT_MODELS:
            print(f"   ✓ {model}")
        print()
        
        print("⏳ Exportiere Daten...")
        
        # Daten als JSON exportieren
        output = StringIO()
        call_command(
            'dumpdata',
            *EXPORT_MODELS,
            indent=2,
            natural_foreign=True,
            natural_primary=True,
            stdout=output
        )
        
        # JSON parsen und formatieren
        data = json.loads(output.getvalue())
        
        # Statistiken sammeln
        stats = {}
        for item in data:
            model = item['model']
            stats[model] = stats.get(model, 0) + 1
        
        # JSON in Datei schreiben
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print()
        print("✅ Export erfolgreich!")
        print()
        print("📊 Exportierte Objekte:")
        for model, count in sorted(stats.items()):
            print(f"   {model:30s} {count:5d} Objekte")
        
        # Dateigröße
        size = Path(filename).stat().st_size
        size_mb = size / (1024 * 1024)
        print()
        print(f"💾 Dateigröße: {size_mb:.2f} MB")
        print()
        
        # Nächste Schritte
        print("-" * 70)
        print("📤 Nächste Schritte:")
        print()
        print("1. Datei auf Server hochladen:")
        print(f"   scp {filename} user@server:/var/www/vhosts/DOMAIN/homegym/")
        print()
        print("2. Auf Server importieren:")
        print(f"   cd /var/www/vhosts/DOMAIN/homegym/")
        print(f"   python3 import_db.py {filename}")
        print()
        print("⚠️  WICHTIG:")
        print("   - ERST Backup importieren (enthält Übungen mit korrekten IDs)")
        print("   - NICHT add_new_exercises ausführen (IDs würden nicht passen)")
        print("   - Backup-Datei enthält sensible User-Daten - sicher aufbewahren!")
        print("-" * 70)
        print()
        
        return 0
        
    except Exception as e:
        print()
        print(f"❌ Fehler beim Export: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # .env wiederherstellen
        restore_env()


def import_data(filename):
    """Importiert Daten aus JSON-Datei."""
    
    print("=" * 70)
    print("🏋️ HomeGym - Datenbank Import")
    print("=" * 70)
    print()
    
    # Prüfen ob Datei existiert
    if not Path(filename).exists():
        print(f"❌ Fehler: Datei '{filename}' nicht gefunden!")
        return 1
    
    print(f"📥 Importiere Daten aus: {filename}")
    print()
    
    # Dateigröße anzeigen
    size = Path(filename).stat().st_size
    size_mb = size / (1024 * 1024)
    print(f"💾 Dateigröße: {size_mb:.2f} MB")
    print()
    
    # JSON laden und validieren
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"✓ JSON-Datei valide ({len(data)} Objekte)")
        print()
        
    except json.JSONDecodeError as e:
        print(f"❌ Fehler: Ungültige JSON-Datei!")
        print(f"   {e}")
        return 1
    
    # Statistiken
    stats = {}
    for item in data:
        model = item['model']
        stats[model] = stats.get(model, 0) + 1
    
    print("📊 Zu importierende Objekte:")
    for model, count in sorted(stats.items()):
        print(f"   {model:30s} {count:5d} Objekte")
    print()
    
    # Sicherheitsabfrage
    print("⚠️  ACHTUNG: Import überschreibt evtl. vorhandene Daten!")
    response = input("Fortfahren? (yes/no): ").strip().lower()
    
    if response not in ['yes', 'y', 'ja', 'j']:
        print("❌ Import abgebrochen.")
        return 1
    
    print()
    print("⏳ Importiere Daten...")
    
    try:
        # Daten importieren
        call_command('loaddata', filename, verbosity=2)
        
        print()
        print("✅ Import erfolgreich abgeschlossen!")
        print()
        print("🎉 Alle Benutzerdaten wurden übertragen!")
        print()
        
        # Empfehlungen
        print("-" * 70)
        print("📋 Nächste Schritte:")
        print()
        print("1. Benutzer überprüfen:")
        print("   python3 manage.py shell")
        print("   >>> from django.contrib.auth.models import User")
        print("   >>> User.objects.all()")
        print()
        print("2. App neustarten:")
        print("   sudo systemctl restart homegym")
        print()
        print("3. Im Browser testen:")
        print("   - Mit vorhandenem User einloggen")
        print("   - Trainingspläne prüfen")
        print("   - Trainings-Historie prüfen")
        print("-" * 70)
        print()
        
        return 0
        
    except Exception as e:
        print()
        print(f"❌ Fehler beim Import: {e}")
        import traceback
        traceback.print_exc()
        print()
        print("💡 Tipp: Stelle sicher dass:")
        print("   - Migrations ausgeführt wurden (python3 manage.py migrate)")
        print("   - Übungen geladen wurden (python3 manage.py add_new_exercises)")
        print("   - Datenbank-Verbindung funktioniert")
        return 1


def main():
    """Hauptfunktion - Export oder Import."""
    
    if len(sys.argv) == 1:
        # Kein Argument = Export-Modus
        return export_data()
    
    elif len(sys.argv) == 2:
        # Dateiname gegeben = Import-Modus
        filename = sys.argv[1]
        return import_data(filename)
    
    else:
        print("Verwendung:")
        print("  Export: python export_db.py")
        print("  Import: python import_db.py <backup-datei.json>")
        return 1


if __name__ == "__main__":
    exit(main())
