"""
Fix hilfsmuskeln field - convert strings to lists
Läuft einmalig um fehlerhafte Daten zu korrigieren
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.models import Uebung, MUSKELGRUPPEN

def fix_hilfsmuskeln():
    """Konvertiert String-Werte in hilfsmuskeln zu Listen."""
    fixed = 0
    errors = 0
    
    # Mapping: Label → Key (case-insensitive)
    label_to_key = {label.lower(): key for key, label in MUSKELGRUPPEN}
    
    # Aliases für häufige Varianten
    aliases = {
        'po': 'PO',
        'gesäß': 'PO',
        'glutes': 'PO',
        'beine - quadrizeps': 'BEINE_QUAD',
        'quadrizeps': 'BEINE_QUAD',
        'quads': 'BEINE_QUAD',
        'beine - hamstrings': 'BEINE_HAM',
        'hamstrings': 'BEINE_HAM',
    }
    
    for uebung in Uebung.objects.all():
        try:
            if uebung.hilfsmuskeln:
                # Wenn es ein String ist, parse ihn
                if isinstance(uebung.hilfsmuskeln, str):
                    print(f"🔧 {uebung.bezeichnung}: hilfsmuskeln ist String: '{uebung.hilfsmuskeln}'")
                    
                    # String splitten bei Komma
                    parts = [p.strip() for p in uebung.hilfsmuskeln.split(',')]
                    
                    # Labels zu Keys konvertieren
                    keys = []
                    for part in parts:
                        # Klammern entfernen (z.B. "(gering)" oder "(Stabilisierung)")
                        part_clean = part.split('(')[0].strip()
                        part_lower = part_clean.lower()
                        
                        # 1. Alias-Suche
                        if part_lower in aliases:
                            keys.append(aliases[part_lower])
                            print(f"   🔍 '{part}' → '{aliases[part_lower]}' (Alias)")
                        # 2. Exakte Übereinstimmung mit Label
                        elif part_lower in label_to_key:
                            keys.append(label_to_key[part_lower])
                        # 3. Exakte Übereinstimmung mit Key
                        elif part_lower in dict(MUSKELGRUPPEN).keys():
                            keys.append(part_lower)
                        # 4. Teilstring-Suche (z.B. "Schulter - Seitliche" → "schulter")
                        else:
                            found = False
                            for label, key in label_to_key.items():
                                if label in part_lower or part_lower in label:
                                    keys.append(key)
                                    found = True
                                    print(f"   🔍 '{part}' → '{key}' (Teilstring-Match)")
                                    break
                            if not found:
                                print(f"   ⚠️  Unbekannter Muskel: '{part}'")
                    
                    uebung.hilfsmuskeln = keys
                    uebung.save()
                    fixed += 1
                    print(f"   ✅ Korrigiert zu Liste: {keys}")
                    
                elif not isinstance(uebung.hilfsmuskeln, list):
                    print(f"⚠️  {uebung.bezeichnung}: Unbekannter Typ: {type(uebung.hilfsmuskeln)}")
                    uebung.hilfsmuskeln = []
                    uebung.save()
                    fixed += 1
        except Exception as e:
            print(f"❌ Fehler bei {uebung.bezeichnung}: {e}")
            errors += 1
    
    print(f"\n{'='*50}")
    print(f"✅ {fixed} Übungen korrigiert")
    print(f"❌ {errors} Fehler")
    print(f"{'='*50}")

if __name__ == '__main__':
    fix_hilfsmuskeln()
