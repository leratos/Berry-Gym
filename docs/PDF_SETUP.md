# PDF Export Setup (Server)

## WeasyPrint auf Linux-Server installieren

```bash
# SSH auf Server
ssh lera@gym.last-strawberry.com

# Wechsle zum Projekt-Verzeichnis
cd /var/www/vhosts/last-strawberry.com/gym.last-strawberry.com

# System-Abhängigkeiten installieren
sudo apt-get update
sudo apt-get install -y \
    python3-cffi \
    python3-brotli \
    python3-dev \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    libcairo2 \
    libcairo2-dev \
    shared-mime-info

# Python-Packages NEU installieren (in venv)
source venv/bin/activate

# Alte Installation entfernen
pip uninstall -y WeasyPrint cairocffi cffi

# Neu installieren mit korrekten Dependencies
pip install --upgrade pip setuptools wheel
pip install cairocffi==1.6.1
pip install WeasyPrint==62.3

# Service neu starten
sudo systemctl restart homegym

# Testen ob WeasyPrint funktioniert
python -c "from weasyprint import HTML; print('WeasyPrint OK')"
```

## Wie es funktioniert

Die App erkennt automatisch die verfügbare PDF-Library:

- **Auf Linux-Server**: Nutzt WeasyPrint (beste Qualität)
- **Auf Windows (lokal)**: Nutzt xhtml2pdf (als Fallback)

Keine Code-Änderungen nötig beim Deployment!

## Testen

Nach der Installation auf Server:
```bash
# Logs prüfen
sudo journalctl -u homegym -f

# PDF-Download testen
curl -I https://gym.last-strawberry.com/export/training-pdf/
```
