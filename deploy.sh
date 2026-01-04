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

# 12. Datenbank-Import (User, Pläne, Training)
if ls homegym_backup_*.json 1> /dev/null 2>&1; then
    echo ""
    echo -e "${YELLOW}📥 Backup-Datei gefunden!${NC}"
    BACKUP_FILE=$(ls -t homegym_backup_*.json | head -1)
    echo "Neueste Datei: $BACKUP_FILE"
    echo ""
    read -p "Datenbank importieren? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}⏳ Importiere Benutzerdaten...${NC}"
        python import_db.py "$BACKUP_FILE"
        echo -e "${GREEN}✅ Datenbank-Import abgeschlossen!${NC}"
        echo ""
        echo "ℹ️  Du kannst dich mit deinen lokalen Login-Daten einloggen!"
    fi
else
    echo -e "${YELLOW}ℹ️  Kein Backup gefunden - überspringe Import${NC}"
fi

# 13. Superuser erstellen (optional - nur wenn kein Import)
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    read -p "Superuser erstellen? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        python manage.py createsuperuser
    fi
# 13. Superuser erstellen (optional - nur wenn kein Import)
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
   4. Gunicorn prüfen
if ! command -v gunicorn &> /dev/null; then
    echo -e "${RED}❌ Gunicorn nicht gefunden!${NC}"
    echo "Installiere gunicorn..."
    pip install gunicorn
fi

# 15
# 14. Gunicorn prüfen
if ! command -v gunicorn &> /dev/null; then
    echo -e "${RED}❌ Gunicorn nicht gefunden!${NC}"
    echo "Installiere gunicorn..."
    pip install gunicorn
fi

# 15. Gunicorn starten
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

# 16. Prüfen ob läuft
if curl -s http://127.0.0.1:$PORT > /dev/null; then
    echo -e "${GREEN}✅ App läuft erfolgreich auf Port $PORT!${NC}"
else
    echo -e "${RED}❌ App konnte nicht gestartet werden!${NC}"
    echo "Prüfe Logs:"
    echo "  tail -f $LOG_DIR/gunicorn-error.log"
    exit 1
fi

# 17. Zusammenfassung
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
echo "  - Neustart: sudo systemctl restart homegym"
echo "  - Status: sudo systemctl status homegym"
echo ""
echo "📚 Nächste Schritte für Production:"
echo "  1. Systemd Service einrichten:"
echo "     sudo cp homegym.service /etc/systemd/system/"
echo "     sudo systemctl daemon-reload"
echo "     sudo systemctl enable homegym"
echo "     sudo systemctl start homegym"
echo ""
echo "  2. Nginx-Konfiguration:"
echo "     sudo cp homegym.nginx /etc/nginx/sites-available/homegym"
echo "     sudo ln -s /etc/nginx/sites-available/homegym /etc/nginx/sites-enabled/"
echo "     sudo nginx -t && sudo systemctl reload nginx"
echo ""
echo "  3. SSL/HTTPS mit Let's Encrypt:"
echo "     sudo certbot --nginx -d DEINE-DOMAIN.de"
echo ""
echo "🎉 Viel Erfolg mit der HomeGym App!"
