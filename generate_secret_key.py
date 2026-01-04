#!/usr/bin/env python
"""
HomeGym - Django SECRET_KEY Generator
======================================
Generiert einen sicheren SECRET_KEY für Django Production.

Verwendung:
    python generate_secret_key.py

Features:
    - 50 Zeichen lang (Django Standard)
    - Enthält Groß-/Kleinbuchstaben, Zahlen und Sonderzeichen
    - Kryptographisch sicher (secrets Modul)
    - Keine mehrdeutigen Zeichen (0/O, 1/l/I)
    - Shell-sicher (keine Probleme mit Bash/Zsh)
"""

import secrets
import string

def generate_secret_key(length=50):
    """
    Generiert einen sicheren Django SECRET_KEY.
    
    Args:
        length: Länge des Keys (Standard: 50)
    
    Returns:
        Sicherer, zufälliger String
    """
    # Zeichen-Pool (ohne mehrdeutige Zeichen)
    # Keine: 0, O, 1, l, I (Verwechslungsgefahr)
    # Keine: Backtick, Dollar, Backslash (Shell-Probleme)
    chars = string.ascii_letters + string.digits
    # Sichere Sonderzeichen hinzufügen
    safe_punctuation = '!@#%^&*(-_=+)'
    chars += safe_punctuation
    
    # Entferne mehrdeutige Zeichen
    chars = chars.replace('0', '').replace('O', '')
    chars = chars.replace('1', '').replace('l', '').replace('I', '')
    
    # Generiere sicheren Key
    key = ''.join(secrets.choice(chars) for _ in range(length))
    
    return key


def validate_key(key):
    """
    Prüft ob Key alle Anforderungen erfüllt.
    
    Args:
        key: Zu prüfender Secret Key
    
    Returns:
        bool: True wenn valide, sonst False
    """
    # Mindestlänge 50 Zeichen
    if len(key) < 50:
        return False
    
    # Muss verschiedene Zeichentypen enthalten
    has_upper = any(c.isupper() for c in key)
    has_lower = any(c.islower() for c in key)
    has_digit = any(c.isdigit() for c in key)
    has_special = any(c in '!@#%^&*(-_=+)' for c in key)
    
    return all([has_upper, has_lower, has_digit, has_special])


def main():
    """Hauptfunktion - Generiert und zeigt Secret Key."""
    print("=" * 60)
    print("🔐 Django SECRET_KEY Generator")
    print("=" * 60)
    print()
    
    # Generiere Key
    key = generate_secret_key()
    
    # Validierung
    if validate_key(key):
        print("✅ Sicherer SECRET_KEY generiert!")
        print()
        print("-" * 60)
        print(key)
        print("-" * 60)
        print()
        print("📋 Kopiere diesen Key und füge ihn ein in:")
        print("   1. .env Datei (Zeile: SECRET_KEY=...)")
        print("   2. homegym.service (Environment: DJANGO_SECRET_KEY=...)")
        print()
        print("⚠️  WICHTIG:")
        print("   - Niemals in Git committen!")
        print("   - Niemals öffentlich teilen!")
        print("   - Für jeden Server eigenen Key generieren!")
        print()
        print("🔒 Key-Eigenschaften:")
        print(f"   - Länge: {len(key)} Zeichen")
        print(f"   - Großbuchstaben: {sum(1 for c in key if c.isupper())}")
        print(f"   - Kleinbuchstaben: {sum(1 for c in key if c.islower())}")
        print(f"   - Zahlen: {sum(1 for c in key if c.isdigit())}")
        print(f"   - Sonderzeichen: {sum(1 for c in key if c in '!@#%^&*(-_=+)')}")
        print()
        
        # Weitere Keys generieren?
        print("💡 Tipp: Führe das Script nochmal aus für einen anderen Key")
        print()
        
        return 0
    else:
        print("❌ Fehler: Generierter Key erfüllt nicht alle Anforderungen!")
        return 1


if __name__ == "__main__":
    exit(main())
