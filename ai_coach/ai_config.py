"""
Konfiguration für AI Coach
Lädt Environment-Variablen aus .env Datei
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# .env Datei laden (im ai_coach/ Ordner)
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# SSH Tunnel Configuration (nur für lokale Entwicklung)
USE_SSH_TUNNEL = os.getenv("USE_SSH_TUNNEL", "True").lower() == "true"
SSH_HOST = os.getenv("SSH_HOST", "gym.last-strawberry.com")
SSH_PORT = int(os.getenv("SSH_PORT", 22))
SSH_USERNAME = os.getenv("SSH_USERNAME")
SSH_PASSWORD = os.getenv("SSH_PASSWORD")
SSH_KEY_PATH = os.getenv("SSH_KEY_PATH")

# Database Configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# Local SSH Tunnel Binding
LOCAL_BIND_PORT = int(os.getenv("LOCAL_BIND_PORT", 3307))

# Django Settings
DJANGO_SETTINGS_MODULE = os.getenv("DJANGO_SETTINGS_MODULE", "config.settings")

# Default User ID
DEFAULT_USER_ID = int(os.getenv("DEFAULT_USER_ID", 1))

# Ollama Configuration
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")


def validate_config():
    """
    Validiert ob alle notwendigen Konfigurationen gesetzt sind
    """
    errors = []

    # SSH-Validierung nur wenn Tunnel verwendet wird
    if USE_SSH_TUNNEL:
        if not SSH_USERNAME:
            errors.append("SSH_USERNAME nicht gesetzt in .env")

        if not SSH_PASSWORD and not SSH_KEY_PATH:
            errors.append("Weder SSH_PASSWORD noch SSH_KEY_PATH gesetzt in .env")

    # DB-Validierung immer
    if not DB_NAME:
        errors.append("DB_NAME nicht gesetzt in .env")

    if not DB_USER:
        errors.append("DB_USER nicht gesetzt in .env")

    if not DB_PASSWORD:
        errors.append("DB_PASSWORD nicht gesetzt in .env")

    if errors:
        raise ValueError("Konfigurationsfehler:\n" + "\n".join(f"  - {e}" for e in errors))

    return True


if __name__ == "__main__":
    # Test: Konfiguration ausgeben (ohne Passwörter)
    print("=== AI Coach Configuration ===")
    print(f"SSH Host: {SSH_HOST}:{SSH_PORT}")
    print(f"SSH User: {SSH_USERNAME}")
    print(f"SSH Auth: {'Key' if SSH_KEY_PATH else 'Password'}")
    print(f"DB Name: {DB_NAME}")
    print(f"DB User: {DB_USER}")
    print(f"Local Port: {LOCAL_BIND_PORT}")
    print(f"Ollama Model: {OLLAMA_MODEL}")
    print("\nValidating...")
    try:
        validate_config()
        print("✓ Configuration valid!")
    except ValueError as e:
        print(f"✗ {e}")
