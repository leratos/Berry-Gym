#!/usr/bin/env python
"""
HomeGym - Datenbank Import Tool (Symlink zu export_db.py)
===========================================================
Importiert Benutzerdaten aus JSON-Backup auf dem Server.

Verwendung:
    python3 import_db.py homegym_backup_2026-01-04.json

Hinweis:
    Dieses Script ist ein Wrapper für export_db.py im Import-Modus.
    Die eigentliche Logik befindet sich in export_db.py.
"""

import sys
from pathlib import Path

# Import von export_db.py
try:
    # Versuche export_db zu importieren
    import export_db
    
    # Wenn keine Argumente, zeige Hilfe
    if len(sys.argv) < 2:
        print("❌ Fehler: Bitte Backup-Datei angeben!")
        print()
        print("Verwendung:")
        print(f"  python3 {sys.argv[0]} <backup-datei.json>")
        print()
        print("Beispiel:")
        print(f"  python3 {sys.argv[0]} homegym_backup_2026-01-04.json")
        sys.exit(1)
    
    # Import-Modus
    filename = sys.argv[1]
    sys.exit(export_db.import_data(filename))
    
except ImportError:
    print("❌ Fehler: export_db.py nicht gefunden!")
    print()
    print("Stelle sicher dass beide Dateien im gleichen Verzeichnis sind:")
    print("  - export_db.py")
    print("  - import_db.py")
    sys.exit(1)
