"""
Secrets Manager - Sichere Verwaltung von API Keys
Nutzt OS Keyring (Windows Credential Manager, macOS Keychain)
"""

import os
import sys
from typing import Optional


class SecretsManager:
    """
    Verwaltet API Keys sicher ohne Klartext-Speicherung
    
    Priority:
    1. OS Keyring (Windows Credential Manager, macOS Keychain, Linux Secret Service)
    2. Environment Variables (zur Laufzeit gesetzt)
    3. .env Datei (nur als Fallback, nicht empfohlen für Production)
    """
    
    SERVICE_NAME = "HomeGym_AI_Coach"
    
    def __init__(self):
        self.keyring_available = False
        self._init_keyring()
    
    def _init_keyring(self):
        """Prüft ob keyring verfügbar ist"""
        try:
            import keyring
            self.keyring = keyring
            self.keyring_available = True
        except ImportError:
            print("⚠️ keyring nicht installiert - nutze Environment Variables")
            print("   Installiere mit: pip install keyring")
            self.keyring = None
    
    def get_secret(self, key_name: str, allow_env_fallback: bool = True) -> Optional[str]:
        """
        Holt Secret aus sicherer Quelle
        
        Args:
            key_name: Name des Secrets (z.B. 'OPENROUTER_API_KEY')
            allow_env_fallback: Erlaube .env Fallback (nicht empfohlen für Production)
        
        Returns:
            Secret-Wert oder None
        """
        
        # 1. Versuche OS Keyring (sicherste Methode)
        if self.keyring_available:
            try:
                value = self.keyring.get_password(self.SERVICE_NAME, key_name)
                if value:
                    return value
            except Exception as e:
                print(f"⚠️ Keyring Fehler: {e}")
        
        # 2. Environment Variable (zur Laufzeit, nicht in .env!)
        value = os.environ.get(key_name)
        if value and value != f"your_{key_name.lower()}_here":
            return value
        
        # 3. Fallback: .env Datei (nur wenn explizit erlaubt)
        if allow_env_fallback:
            from dotenv import load_dotenv
            load_dotenv()
            value = os.getenv(key_name)
            if value and value != f"your_{key_name.lower()}_here":
                print(f"⚠️ '{key_name}' aus .env geladen - nicht sicher!")
                print(f"   Setze mit: python ai_coach/secrets_manager.py set {key_name}")
                return value
        
        return None
    
    def set_secret(self, key_name: str, value: str) -> bool:
        """
        Speichert Secret sicher im OS Keyring
        
        Args:
            key_name: Name des Secrets
            value: Secret-Wert
        
        Returns:
            True bei Erfolg
        """
        
        if not self.keyring_available:
            print("❌ keyring nicht verfügbar!")
            print("   Installiere mit: pip install keyring")
            return False
        
        try:
            self.keyring.set_password(self.SERVICE_NAME, key_name, value)
            print(f"✅ '{key_name}' sicher in OS Keyring gespeichert")
            
            # Zeige wo gespeichert (OS-spezifisch)
            if sys.platform == "win32":
                print("   → Windows Credential Manager")
                print("   → Sichtbar in: Systemsteuerung → Anmeldeinformationsverwaltung")
            elif sys.platform == "darwin":
                print("   → macOS Keychain")
                print("   → Sichtbar in: Keychain Access App")
            else:
                print("   → Linux Secret Service")
            
            return True
        
        except Exception as e:
            print(f"❌ Fehler beim Speichern: {e}")
            return False
    
    def delete_secret(self, key_name: str) -> bool:
        """Löscht Secret aus OS Keyring"""
        
        if not self.keyring_available:
            return False
        
        try:
            self.keyring.delete_password(self.SERVICE_NAME, key_name)
            print(f"✅ '{key_name}' aus OS Keyring gelöscht")
            return True
        except Exception as e:
            print(f"⚠️ Konnte nicht löschen: {e}")
            return False
    
    def list_secrets(self) -> list:
        """Listet alle gespeicherten Secret-Namen"""
        
        # keyring hat keine list() Funktion, also zeigen wir bekannte Keys
        known_keys = [
            'OPENROUTER_API_KEY',
            'GROQ_API_KEY',
            'DB_PASSWORD'
        ]
        
        found = []
        for key in known_keys:
            if self.get_secret(key, allow_env_fallback=False):
                found.append(key)
        
        return found


def get_openrouter_key() -> Optional[str]:
    """
    Helper: Holt OpenRouter API Key sicher
    
    Usage:
        from secrets_manager import get_openrouter_key
        api_key = get_openrouter_key()
    """
    manager = SecretsManager()
    return manager.get_secret('OPENROUTER_API_KEY')


def get_db_password() -> Optional[str]:
    """Helper: Holt DB Password sicher"""
    manager = SecretsManager()
    return manager.get_secret('DB_PASSWORD')


if __name__ == "__main__":
    import sys
    
    manager = SecretsManager()
    
    if len(sys.argv) < 2:
        print("=== HomeGym Secrets Manager ===\n")
        print("Sichere Verwaltung von API Keys ohne Klartext-Speicherung\n")
        print("Commands:")
        print("  python secrets_manager.py set <KEY_NAME>     - Speichert Secret sicher")
        print("  python secrets_manager.py get <KEY_NAME>     - Zeigt Secret (maskiert)")
        print("  python secrets_manager.py delete <KEY_NAME>  - Löscht Secret")
        print("  python secrets_manager.py list               - Listet gespeicherte Keys")
        print("\nBeispiel:")
        print("  python secrets_manager.py set OPENROUTER_API_KEY")
        sys.exit(0)
    
    command = sys.argv[1].lower()
    
    if command == "set":
        if len(sys.argv) < 3:
            print("❌ Usage: python secrets_manager.py set <KEY_NAME>")
            sys.exit(1)
        
        key_name = sys.argv[2]
        
        # Key von User abfragen (nicht als CLI Argument!)
        print(f"\n🔐 Setze Secret: {key_name}")
        print("Paste API Key (Eingabe wird versteckt):")
        
        # Nutze getpass für versteckte Eingabe
        import getpass
        value = getpass.getpass("Key: ")
        
        if not value:
            print("❌ Leerer Key - abgebrochen")
            sys.exit(1)
        
        success = manager.set_secret(key_name, value)
        sys.exit(0 if success else 1)
    
    elif command == "get":
        if len(sys.argv) < 3:
            print("❌ Usage: python secrets_manager.py get <KEY_NAME>")
            sys.exit(1)
        
        key_name = sys.argv[2]
        value = manager.get_secret(key_name, allow_env_fallback=False)
        
        if value:
            # Maskiere bis auf letzte 4 Zeichen
            masked = "*" * (len(value) - 4) + value[-4:] if len(value) > 4 else "****"
            print(f"✅ {key_name}: {masked}")
        else:
            print(f"❌ '{key_name}' nicht gefunden")
            sys.exit(1)
    
    elif command == "delete":
        if len(sys.argv) < 3:
            print("❌ Usage: python secrets_manager.py delete <KEY_NAME>")
            sys.exit(1)
        
        key_name = sys.argv[2]
        
        # Bestätigung
        confirm = input(f"⚠️ '{key_name}' wirklich löschen? (yes/no): ")
        if confirm.lower() != "yes":
            print("Abgebrochen")
            sys.exit(0)
        
        success = manager.delete_secret(key_name)
        sys.exit(0 if success else 1)
    
    elif command == "list":
        print("\n🔐 Gespeicherte Secrets:")
        found = manager.list_secrets()
        
        if found:
            for key in found:
                print(f"  ✅ {key}")
        else:
            print("  (keine)")
        
        print("\nUm Secret zu setzen:")
        print("  python secrets_manager.py set OPENROUTER_API_KEY")
    
    else:
        print(f"❌ Unbekannter Command: {command}")
        print("Nutze: set, get, delete, oder list")
        sys.exit(1)
