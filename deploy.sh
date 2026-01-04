#!/bin/bash
# HomeGym App - Quick Deployment Script für Linux Server

set -e  # Exit bei Fehler

echo "🏋️ HomeGym App - Server Deployment"
echo "===================================="
echo ""

# 1. Farben für Output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 2. Konfiguration
APP_DIR="/var/www/vhosts/last-strawberry.com/gym"
VENV_DIR="$APP_DIR/venv"
LOG_DIR="$APP_DIR/logs"
STATIC_DIR="$APP_DIR/staticfiles"
MEDIA_DIR="$APP_DIR/media"
PORT=8002

echo -e "${YELLOW}📁 App-Verzeichnis: $APP_DIR${NC}"
echo ""

# 3. Prüfen ob im richtigen Verzeichnis
if [ ! -f "manage.py" ]; then
    echo -e "${RED}❌ Fehler: manage.py nicht gefunden!${NC}"
    echo "Bitte im Projekt-Root-Verzeichnis ausführen."
    exit 1
fi

# 4. Virtual Environment prüfen/erstellen
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}📦 Erstelle Virtual Environment...${NC}"
    python3 -m venv venv
fi

# 5. Virtual Environment aktivieren
echo -e "${YELLOW}🔧 Aktiviere Virtual Environment...${NC}"
source venv/bin/activate

# 6. Dependencies installieren
echo -e "${YELLOW}📥 Installiere Dependencies...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

# 7. Verzeichnisse erstellen
echo -e "${YELLOW}📂 Erstelle Verzeichnisse...${NC}"
mkdir -p "$LOG_DIR"
mkdir -p "$STATIC_DIR"
mkdir -p "$MEDIA_DIR"

# 8. .env prüfen
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  Keine .env Datei gefunden!${NC}"
    echo "Erstelle .env aus .env.example..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${RED}⚠️  WICHTIG: .env Datei anpassen!${NC}"
        echo "  - SECRET_KEY generieren"
        echo "  - DB_PASSWORD setzen"
        echo "  - ALLOWED_HOSTS anpassen"
        read -p "Drücke Enter wenn fertig..."
    else
        echo -e "${RED}❌ .env.example nicht gefunden!${NC}"
        exit 1
    fi
fi

# 9. Migrations
echo -e "${YELLOW}🔄 Führe Migrations aus...${NC}"
python manage.py makemigrations
python manage.py migrate

# 10. Übungen hinzufügen
echo -e "${YELLOW}💪 Füge Übungen hinzu...${NC}"
python manage.py add_new_exercises

# 11. Static Files sammeln
echo -e "${YELLOW}📦 Sammle Static Files...${NC}"
python manage.py collectstatic --noinput

# 12. Superuser erstellen (optional)
read -p "Superuser erstellen? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python manage.py createsuperuser
fi

# 13. Gunicorn prüfen
if ! command -v gunicorn &> /dev/null; then
    echo -e "${RED}❌ Gunicorn nicht gefunden!${NC}"
    echo "Installiere gunicorn..."
    pip install gunicorn
fi

# 14. Gunicorn starten
echo -e "${YELLOW}🚀 Starte Gunicorn auf Port $PORT...${NC}"

# Alte Prozesse killen
pkill -f "gunicorn.*config.wsgi" || true

# Gunicorn im Daemon-Mode starten
gunicorn --bind 127.0.0.1:$PORT \
         --workers 3 \
         --timeout 60 \
         --access-logfile "$LOG_DIR/gunicorn-access.log" \
         --error-logfile "$LOG_DIR/gunicorn-error.log" \
         --daemon \
         config.wsgi:application

sleep 2

# 15. Prüfen ob läuft
if curl -s http://127.0.0.1:$PORT > /dev/null; then
    echo -e "${GREEN}✅ App läuft erfolgreich auf Port $PORT!${NC}"
else
    echo -e "${RED}❌ App konnte nicht gestartet werden!${NC}"
    echo "Prüfe Logs:"
    echo "  tail -f $LOG_DIR/gunicorn-error.log"
    exit 1
fi

# 16. Zusammenfassung
echo ""
echo -e "${GREEN}===================================="
echo "✅ Deployment erfolgreich!"
echo "====================================${NC}"
echo ""
echo "📍 App läuft auf: http://127.0.0.1:$PORT"
echo "📁 Logs: $LOG_DIR"
echo ""
echo "🔧 Nützliche Befehle:"
echo "  - Logs: tail -f $LOG_DIR/gunicorn-error.log"
echo "  - Neustart: pkill -f 'gunicorn.*config.wsgi' && gunicorn ..."
echo "  - Status: curl http://127.0.0.1:$PORT"
echo ""
echo "📚 Nächste Schritte:"
echo "  1. Nginx-Konfiguration anpassen (siehe DEPLOYMENT.md)"
echo "  2. SSL/HTTPS einrichten"
echo "  3. Systemd Service erstellen (optional)"
echo ""
echo "🎉 Viel Erfolg mit der HomeGym App!"
