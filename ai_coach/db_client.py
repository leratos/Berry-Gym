"""
Database Client mit SSH Tunnel und Django ORM Setup
Ermöglicht sicheren Zugriff auf Production Database

HINWEIS: Verwendet subprocess + SSH command wegen sshtunnel/paramiko Kompatibilitätsproblem
"""

import os
import subprocess
import sys
import time
from pathlib import Path

import django

# Import der Config (funktioniert auch bei direktem Ausführen)
try:
    from . import ai_config
except ImportError:
    import ai_config


class DatabaseClient:
    """
    Managed SSH Tunnel und Django ORM Connection zur Production Database
    Verwendet subprocess + native SSH command (Windows/Linux kompatibel)
    """

    def __init__(self):
        self.tunnel_process = None
        self._django_initialized = False

    def start_tunnel(self):
        """
        Startet SSH Tunnel zur Production Database via subprocess
        Überspringt Tunnel auf Production Server (USE_SSH_TUNNEL=False)
        """
        # Auf Production Server: Kein SSH-Tunnel nötig
        if not ai_config.USE_SSH_TUNNEL:
            print(f"ℹ️ Production Mode: Direkte DB-Verbindung (kein SSH-Tunnel)")
            return

        ai_config.validate_config()

        print(f"🔌 Starte SSH Tunnel zu {ai_config.SSH_HOST}...")

        # SSH Command zusammenbauen
        ssh_cmd = [
            "ssh",
            "-N",  # No command execution
            "-L",
            f"{ai_config.LOCAL_BIND_PORT}:{ai_config.DB_HOST}:{ai_config.DB_PORT}",
            f"{ai_config.SSH_USERNAME}@{ai_config.SSH_HOST}",
            "-p",
            str(ai_config.SSH_PORT),
        ]

        # SSH Key Authentication
        if ai_config.SSH_KEY_PATH:
            ssh_cmd.extend(["-i", ai_config.SSH_KEY_PATH])
            print(f"   Auth: SSH Key ({ai_config.SSH_KEY_PATH})")
        else:
            print(f"   Auth: SSH Password (interactive)")

        # Weitere SSH Optionen für nicht-interaktive Nutzung
        ssh_cmd.extend(
            [
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "ServerAliveInterval=60",
                "-o",
                "ServerAliveCountMax=3",
            ]
        )

        # SSH Tunnel als Background Process starten
        try:
            self.tunnel_process = subprocess.Popen(
                ssh_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )

            # Kurz warten bis Tunnel aufgebaut ist
            time.sleep(2)

            # Prüfen ob Prozess noch läuft
            if self.tunnel_process.poll() is not None:
                # Prozess ist beendet - Fehler
                stderr = self.tunnel_process.stderr.read().decode()
                raise RuntimeError(f"SSH Tunnel konnte nicht gestartet werden:\n{stderr}")

            print(
                f"✓ SSH Tunnel aktiv: localhost:{ai_config.LOCAL_BIND_PORT} → {ai_config.SSH_HOST}:{ai_config.DB_PORT}"
            )
            print(f"   PID: {self.tunnel_process.pid}")

        except FileNotFoundError:
            raise RuntimeError(
                "SSH command nicht gefunden. Ist OpenSSH installiert?\n"
                + "Windows: Settings → Apps → Optional Features → OpenSSH Client"
            )
        except Exception as e:
            raise RuntimeError(f"SSH Tunnel Fehler: {e}")

    def stop_tunnel(self):
        """
        Stoppt SSH Tunnel
        """
        if not ai_config.USE_SSH_TUNNEL:
            return  # Kein Tunnel zu stoppen

        if self.tunnel_process:
            self.tunnel_process.terminate()
            try:
                self.tunnel_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.tunnel_process.kill()
            print("✓ SSH Tunnel geschlossen")

    def setup_django(self):
        """
        Initialisiert Django ORM für Production Database
        WICHTIG: Muss nach start_tunnel() aufgerufen werden
        """
        if self._django_initialized:
            return

        # Django Settings überschreiben für AI Coach
        # Wichtig: sys.path ZUERST setzen, damit config.settings gefunden wird
        project_root = Path(__file__).parent.parent
        sys.path.insert(0, str(project_root))

        # Database Settings überschreiben
        # Muss VOR django.setup() passieren
        os.environ["DB_ENGINE"] = "django.db.backends.mysql"  # WICHTIG: MySQL aktivieren!

        # Production: Direkte Verbindung, Development: SSH-Tunnel
        if ai_config.USE_SSH_TUNNEL:
            os.environ["DB_HOST"] = "127.0.0.1"  # Tunnel läuft auf localhost
            os.environ["DB_PORT"] = str(ai_config.LOCAL_BIND_PORT)
        else:
            os.environ["DB_HOST"] = ai_config.DB_HOST  # localhost auf Server
            os.environ["DB_PORT"] = str(ai_config.DB_PORT)  # 3306 direkt

        os.environ["DB_NAME"] = ai_config.DB_NAME
        os.environ["DB_USER"] = ai_config.DB_USER
        os.environ["DB_PASSWORD"] = ai_config.DB_PASSWORD

        # DJANGO_SETTINGS_MODULE NACH sys.path Änderung setzen
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", ai_config.DJANGO_SETTINGS_MODULE)

        django.setup()
        self._django_initialized = True
        print("✓ Django ORM initialisiert")

    def test_connection(self):
        """
        Testet DB-Verbindung durch Abfrage der User-Anzahl
        """
        from django.contrib.auth.models import User

        try:
            user_count = User.objects.count()
            print(f"✓ Database Connection OK - {user_count} User gefunden")
            return True
        except Exception as e:
            print(f"✗ Database Connection Error: {e}")
            return False

    def __enter__(self):
        """
        Context Manager: Start
        Verwendung: with DatabaseClient() as db:
        """
        self.start_tunnel()
        self.setup_django()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Context Manager: Cleanup
        """
        self.stop_tunnel()


def get_db_client():
    """
    Helper Function: Erstellt und konfiguriert DatabaseClient
    """
    return DatabaseClient()


if __name__ == "__main__":
    # Test: SSH Tunnel + Django ORM Connection
    print("=== Database Client Test ===\n")

    try:
        with DatabaseClient() as db:
            print("\n🧪 Teste Database Connection...")
            db.test_connection()

            # Beispiel-Query: Alle User ausgeben
            from django.contrib.auth.models import User

            users = User.objects.all()
            print(f"\n📊 User in Database:")
            for user in users:
                print(f"   - {user.username} (ID: {user.id})")

    except Exception as e:
        print(f"\n❌ Fehler: {e}")
        import traceback

        traceback.print_exc()
