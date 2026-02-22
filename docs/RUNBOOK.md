# HomeGym – Operations Runbook

**Letzte Aktualisierung:** 2026-02-22  
**Zielgruppe:** Betreiber (aktuell: Alleinentwickler)

---

## 1. Schnellreferenz

| Was                        | Wo / Wie                                              |
|----------------------------|-------------------------------------------------------|
| Produktions-Server         | Plesk / Hoster-Panel                                  |
| Fehler-Monitoring          | Sentry (Link im .env: SENTRY_DSN)                     |
| Logs                       | `logs/django.log`, `logs/errors.log` auf dem Server   |
| Datenbank                  | MariaDB, Zugangsdaten in `.env`                       |
| Backup                     | Täglich via Hoster-Automatik + manuell vor Deploys    |
| Python-Venv                | `/home/.../homegym/.venv`                             |
| Static Files               | `python manage.py collectstatic --no-input`           |

---

## 2. Standard-Deployment

```bash
# 1. Code holen
git pull origin main

# 2. Abhängigkeiten aktualisieren
.venv/bin/pip install -r requirements.txt

# 3. Migrationen anwenden
.venv/bin/python manage.py migrate --no-input

# 4. Static Files sammeln
.venv/bin/python manage.py collectstatic --no-input

# 5. System-Checks
.venv/bin/python manage.py check --deploy

# 6. Gunicorn neu starten (Plesk: über Prozess-Manager oder Touch der WSGI-Datei)
touch config/wsgi.py
```

**Rollback (wenn etwas schiefläuft):**
```bash
git revert HEAD --no-edit
git push origin main
# Dann Deployment-Schritte 2-6 wiederholen
```

---

## 3. Incident Response

### 3.1 Sentry meldet Fehler

1. Sentry-Alert öffnen → Stack Trace analysieren
2. Ist es ein einzelner User oder systemweit?
3. Ist es eine neue Funktion? → Ggf. Feature-Flag deaktivieren oder Revert
4. Fix → PR → Deploy (s. Abschnitt 2)
5. Sentry-Issue als "Resolved" markieren

### 3.2 Site nicht erreichbar (5xx)

```bash
# Logs prüfen
tail -100 logs/errors.log

# Gunicorn-Prozess prüfen (Plesk: Prozess-Manager)
# Datenbank erreichbar?
.venv/bin/python manage.py dbshell
# > SELECT 1;

# Migrations-Status
.venv/bin/python manage.py showmigrations | grep "\[ \]"
```

Häufige Ursachen:
- Migration nicht angewendet → `python manage.py migrate`
- `.env` fehlt oder hat falschen Wert → prüfen
- Disk voll (Logs, Medien) → aufräumen

### 3.3 Datenbank-Fehler / Korruption

1. **Sofort:** Schreibzugriff sperren (Maintenance-Mode via `DEBUG_MAINTENANCE=True` in .env)
2. Letztes Backup einspielen (Hoster-Panel → Datenbank-Backups)
3. Migrationen prüfen: `python manage.py showmigrations`
4. Ursache analysieren, bevor Maintenance-Mode deaktiviert wird

### 3.4 Sicherheitsvorfall (gehackter Account / Datenleck)

1. Betroffene Accounts sofort sperren:
   ```bash
   .venv/bin/python manage.py shell
   >>> from django.contrib.auth.models import User
   >>> User.objects.filter(username="betroffen").update(is_active=False)
   ```
2. Alle Sessions löschen:
   ```bash
   .venv/bin/python manage.py clearsessions
   ```
3. django-axes Login-Versuche prüfen:
   ```bash
   .venv/bin/python manage.py shell
   >>> from axes.models import AccessAttempt
   >>> AccessAttempt.objects.all().order_by('-attempt_time')[:20]
   ```
4. Sentry auf anomale Fehler prüfen
5. Ggf. Nutzer benachrichtigen (E-Mail)

---

## 4. Routine-Aufgaben

### Wöchentlich
- [ ] Sentry: Offene Issues prüfen
- [ ] Logs: `errors.log` auf Anomalien scannen
- [ ] `python manage.py check` ausführen

### Monatlich
- [ ] `pip list --outdated` prüfen
- [ ] `python -m safety check` ausführen
- [ ] Backup-Restore testweise durchführen (stichprobenartig)
- [ ] Sentry: gelöste Issues bereinigen

### Bei jedem Release
- [ ] `python manage.py check --deploy` ausführen
- [ ] Tests grün: `pytest --no-header -q`
- [ ] requirements.txt mit `pip freeze` abgleichen
- [ ] Datenbank-Backup VOR dem Deploy

---

## 5. Nützliche Management Commands

```bash
# Sentry-Verbindung testen
.venv/bin/python -c "import sentry_sdk; sentry_sdk.capture_message('test')"

# Cache leeren
.venv/bin/python manage.py shell -c "from django.core.cache import cache; cache.clear()"

# Alle User anzeigen
.venv/bin/python manage.py shell -c "from django.contrib.auth.models import User; print(list(User.objects.values('username','email','is_active')))"

# Wissenschaftliche Quellen neu laden
.venv/bin/python manage.py load_training_sources

# Alte Sessions löschen (regelmäßig)
.venv/bin/python manage.py clearsessions

# Axes-Sperren zurücksetzen (bei falsch-positiven)
.venv/bin/python manage.py axes_reset
```

---

## 6. Bekannte Limits & Schwellenwerte

| Metrik                     | Wert / Limit                        |
|----------------------------|-------------------------------------|
| AI Plan-Generierung        | 3 / User / Tag                      |
| AI Live Guidance           | 50 / User / Tag                     |
| AI Analyse                 | 10 / User / Tag                     |
| Max Upload (Hevy-CSV)      | 10 MB                               |
| Max Upload (Foto)          | via Pillow, kein explizites Limit   |
| Session-Timeout            | Django-Default (2 Wochen bei "Login merken") |
| Log-Rotation               | RotatingFileHandler, 10 MB, 5 Backups |

---

## 7. Kontakt & Eskalation

- **Betreiber:** Entwickler (du)  
- **Hoster-Support:** Hoster-Panel → Support-Ticket  
- **Sentry:** alerts@last-strawberry.com (konfigurieren)  
- **Security:** security@last-strawberry.com (s. SECURITY.md)
