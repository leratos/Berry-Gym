# 🚀 HomeGym – Launch-Checkliste (DE)

**Zieldomain:** gym.last-strawberry.com  
**Zieldatum:** Week 8 (nach Roadmap)  
**Letzte Aktualisierung:** 23.02.2026

---

## Legende
- ✅ Erledigt / im Code verankert
- 🔲 Manuell auf dem Server zu prüfen/erledigen
- ⚠️  Bekanntes Risiko, bewusst akzeptiert

---

## 1. Code & Tests

| # | Prüfpunkt | Status | Notiz |
|---|-----------|--------|-------|
| 1.1 | Alle Tests grün | ✅ | 1104 passed, 5 skipped, 0 failed (23.02.2026) |
| 1.2 | Keine ausstehenden Migrationen | ✅ | test_keine_ausstehenden_migrationen grün |
| 1.3 | Django System Check fehlerfrei | ✅ | test_django_system_check_keine_errors grün |
| 1.4 | DEBUG=False per Default | ✅ | settings.py Zeile 50 |
| 1.5 | SECRET_KEY aus Umgebungsvariable | ✅ | Kein Fallback in Production |
| 1.6 | main-Branch sauber, kein WIP | 🔲 | Vor Deploy prüfen: `git status` |

---

## 2. Server-Konfiguration

| # | Prüfpunkt | Status | Notiz |
|---|-----------|--------|-------|
| 2.1 | `.env` auf Server vorhanden | 🔲 | Alle Pflichtfelder aus `.env.example` befüllt |
| 2.2 | `SECRET_KEY` ist zufällig & lang | 🔲 | `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| 2.3 | `ALLOWED_HOSTS` enthält Domain | 🔲 | `gym.last-strawberry.com,www.gym.last-strawberry.com` |
| 2.4 | Datenbank: MariaDB läuft | 🔲 | `DB_ENGINE=django.db.backends.mysql` |
| 2.5 | Gunicorn-Service aktiv | 🔲 | `systemctl status homegym` |
| 2.6 | Nginx-Config geladen | 🔲 | `nginx -t && systemctl reload nginx` |
| 2.7 | Gunicorn timeout 180s | ✅ | deployment/homegym.service – wegen LLM-Calls |
| 2.8 | Nginx proxy_read_timeout 180s | 🔲 | deployment/homegym.nginx prüfen |
| 2.9 | Statische Dateien gesammelt | 🔲 | `python manage.py collectstatic --noinput` |
| 2.10 | Migrations eingespielt | 🔲 | `python manage.py migrate` |

---

## 3. HTTPS & Sicherheit

| # | Prüfpunkt | Status | Notiz |
|---|-----------|--------|-------|
| 3.1 | SSL-Zertifikat gültig | 🔲 | Let's Encrypt via Certbot |
| 3.2 | HTTPS-Redirect aktiv | ✅ | `SECURE_SSL_REDIRECT=True` bei DEBUG=False |
| 3.3 | HSTS gesetzt (1 Jahr) | ✅ | `SECURE_HSTS_SECONDS=31536000` |
| 3.4 | HSTS Subdomains + Preload | ✅ | settings.py Zeile 457–458 |
| 3.5 | Session-Cookie Secure | ✅ | `SESSION_COOKIE_SECURE=True` |
| 3.6 | CSRF-Cookie Secure | ✅ | `CSRF_COOKIE_SECURE=True` |
| 3.7 | X-Frame-Options: DENY | ✅ | settings.py Zeile 472 |
| 3.8 | Content-Type Nosniff | ✅ | settings.py Zeile 475 |
| 3.9 | Login-Brute-Force-Schutz | ✅ | django-axes installiert & konfiguriert |
| 3.10 | Rate-Limiting KI-Endpoints | ✅ | Phase 7.1 abgeschlossen |
| 3.11 | `DEBUG=True` in Production ausgeschlossen | ✅ | Automatisch durch .env |

---

## 4. Monitoring & Fehlertracking

| # | Prüfpunkt | Status | Notiz |
|---|-----------|--------|-------|
| 4.1 | Sentry-DSN in `.env` gesetzt | 🔲 | `SENTRY_DSN=https://...@sentry.io/...` |
| 4.2 | Sentry-Umgebung korrekt | 🔲 | `SENTRY_ENVIRONMENT=production` |
| 4.3 | Test-Exception auslösen | 🔲 | Nach Deploy: Sentry-Dashboard prüfen ob Error ankommt |
| 4.4 | Log-Level auf INFO | 🔲 | `LOG_LEVEL=INFO` in `.env` |
| 4.5 | Gunicorn-Logs schreibbar | 🔲 | `logs/` Verzeichnis existiert & hat Schreibrechte |

---

## 5. E-Mail

| # | Prüfpunkt | Status | Notiz |
|---|-----------|--------|-------|
| 5.1 | SMTP-Zugangsdaten in `.env` | 🔲 | `EMAIL_HOST_PASSWORD` befüllt |
| 5.2 | Passwort-Reset funktioniert | 🔲 | Manuell testen: /accounts/password_reset/ |
| 5.3 | Absender-Adresse korrekt | ✅ | `noreply@last-strawberry.com` in `.env.example` |

---

## 6. Backup & Rollback

| # | Prüfpunkt | Status | Notiz |
|---|-----------|--------|-------|
| 6.1 | Datenbank-Backup vor Deploy | 🔲 | `mysqldump homegym_db > backup_$(date +%Y%m%d).sql` |
| 6.2 | Media-Backup (Fotos) | 🔲 | `tar czf media_backup_$(date +%Y%m%d).tar.gz media/` |
| 6.3 | Rollback-Plan definiert | 🔲 | Letzten Commit notieren: `git log --oneline -1` |
| 6.4 | Rollback getestet | ⚠️ | Noch nicht getestet – zumindest Theorie dokumentieren |

---

## 7. Funktionstest nach Deploy (Smoke Tests)

Manuell im Browser nach jedem Deploy durchführen:

| # | Test | Erwartetes Ergebnis |
|---|------|---------------------|
| 7.1 | Startseite / aufrufen | 200, kein Fehler |
| 7.2 | Login mit Test-Account | Redirect zu Dashboard |
| 7.3 | Training starten & Satz eintragen | Satz gespeichert |
| 7.4 | Training abschließen | Status „abgeschlossen" |
| 7.5 | KI-Plangenerator aufrufen | Formular sichtbar |
| 7.6 | Hevy-Export herunterladen | CSV-Download startet |
| 7.7 | Hevy-Import (Test-CSV) | Import erfolgreich |
| 7.8 | Sprachumschaltung DE/EN | UI wechselt Sprache |
| 7.9 | Passwort-Reset anfordern | E-Mail kommt an |
| 7.10 | Sentry-Check: bewusst 500 auslösen | Fehler in Sentry sichtbar |
| 7.11 | HTTPS-Redirect: http:// aufrufen | Redirect auf https:// |
| 7.12 | Admin-Bereich `/admin/` | Nur für Staff erreichbar |

---

## 8. Daten & Initialisierung

| # | Prüfpunkt | Status | Notiz |
|---|-----------|--------|-------|
| 8.1 | Übungsdatenbank geladen | 🔲 | `python manage.py loaddata core/fixtures/initial_exercises.json` |
| 8.2 | Wissenschaftliche Quellen geladen | 🔲 | `python manage.py load_training_sources` |
| 8.3 | 1RM-Standards befüllt | 🔲 | Migration 0053 läuft automatisch bei `migrate` |
| 8.4 | Superuser erstellt | 🔲 | `python manage.py createsuperuser` |
| 8.5 | Invite-Codes erstellt (falls Closed Beta) | 🔲 | Über Admin-Interface |

---

## 9. Web Push Notifications

| # | Prüfpunkt | Status | Notiz |
|---|-----------|--------|-------|
| 9.1 | VAPID-Keys generiert | 🔲 | `python manage.py generate_vapid_keys` (falls vorhanden) |
| 9.2 | `.pem`-Dateien auf Server | 🔲 | Pfade in `.env`: `VAPID_PRIVATE_KEY_FILE`, `VAPID_PUBLIC_KEY_FILE` |

---

## Checkliste: Pre-Launch (T-1)

```
[ ] git pull auf Server – aktueller main-Stand
[ ] python manage.py migrate
[ ] python manage.py collectstatic --noinput
[ ] systemctl restart homegym
[ ] Smoke Tests 7.1–7.12 durchführen
[ ] Sentry-Dashboard offen halten
[ ] Backup von Datenbank & Media vorhanden
```

## Checkliste: Post-Launch (T+1)

```
[ ] Sentry: Fehler-Rate in ersten 24h prüfen
[ ] Gunicorn-Logs auf Errors prüfen
[ ] Erste User-Registrierungen prüfen
[ ] Performance: Ladezeiten manuell messen
```
