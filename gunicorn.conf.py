# gunicorn.conf.py
# Konfiguration für Berry-Gym auf dem Live-Server
# Verwendung: gunicorn --config gunicorn.conf.py config.wsgi:application

# ──────────────────────────────────────────────
# Timeout – muss länger sein als der längste LLM-Call
# OpenRouter 70B kann 60-120s brauchen → 180s Puffer
# ──────────────────────────────────────────────
timeout = 180  # Worker-Timeout in Sekunden (Standard: 30 – viel zu kurz)
graceful_timeout = 30  # Wie lange ein Worker nach SIGTERM noch antworten darf

# ──────────────────────────────────────────────
# Worker
# ──────────────────────────────────────────────
worker_class = "sync"  # sync bleibt korrekt für Django (kein async)
workers = 2  # Anpassen je nach Server-RAM (Faustregel: 2 * CPU-Kerne + 1)
threads = 2  # Threads pro Worker für parallele Requests

# ──────────────────────────────────────────────
# Keepalive & Verbindungen
# ──────────────────────────────────────────────
keepalive = 5  # Sekunden für Keep-Alive Verbindungen

# ──────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────
accesslog = "-"  # stdout (Plesk/Systemd fängt das ab)
errorlog = "-"  # stdout
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s %(D)s'
