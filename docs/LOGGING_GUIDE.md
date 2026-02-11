# 📝 HomeGym Logging & Monitoring Guide

## Übersicht

HomeGym nutzt ein mehrstufiges Logging-System:
- **Console Logging** (Development)
- **File Logging** (Production)
- **Sentry Error Tracking** (Production)
- **Django-Axes** (Brute-Force Protection)

## Log-Dateien

Alle Logs werden in `logs/` gespeichert:

```
logs/
├── django.log        # Alle Logs (INFO+)
├── error.log         # Nur Fehler (ERROR+)
└── security.log      # Security-Events (WARNING+)
```

**Rotation:** 10 MB pro Datei, 5 Backups (außer security.log: 10 Backups)

## Logging in Code verwenden

### 1. Basic Logging

```python
from core.utils.logging_helper import get_logger

logger = get_logger(__name__)

# Info-Level
logger.info("Training created successfully")

# Warning-Level
logger.warning("Unusual training duration detected")

# Error-Level
logger.error("Failed to save training", exc_info=True)
```

### 2. Strukturiertes Logging mit Context

```python
from core.utils.logging_helper import log_user_action

log_user_action(
    logger,
    "Training completed",
    user_id=request.user.id,
    training_id=training.id,
    duration_minutes=training.dauer_minuten,
    volume_kg=total_volume
)
```

### 3. Error Logging mit Context

```python
from core.utils.logging_helper import log_error_with_context

try:
    result = risky_operation()
except Exception as e:
    log_error_with_context(
        logger,
        "Operation failed",
        exception=e,
        user_id=request.user.id,
        operation='training_creation',
        input_data=form.cleaned_data
    )
    # Re-raise oder handle
```

### 4. Performance Monitoring

```python
from core.utils.logging_helper import log_performance

@log_performance
def generate_training_plan(user_id: int):
    # Funktion wird automatisch geloggt mit Ausführungszeit
    plan = create_plan()
    return plan
```

### 5. Security Events

```python
from core.utils.logging_helper import log_security_event

log_security_event(
    'suspicious_api_access',
    severity='WARNING',
    user_id=request.user.id,
    ip_address=request.META.get('REMOTE_ADDR'),
    endpoint=request.path
)
```

## Log-Levels

**Wann welches Level?**

| Level | Verwendung | Beispiel |
|-------|------------|----------|
| **DEBUG** | Development-Details | SQL Queries, Variable-Werte |
| **INFO** | Normale Operationen | "User logged in", "Training created" |
| **WARNING** | Ungewöhnlich, aber nicht kritisch | "Slow query detected (2.5s)" |
| **ERROR** | Fehler, aber App läuft weiter | "Failed to send email" |
| **CRITICAL** | Schwerer Fehler, App unstabil | "Database connection lost" |

## Sentry Error Tracking

### Setup (Production)

1. **Account erstellen:** https://sentry.io/ (kostenlos bis 5k Events/Monat)

2. **DSN in .env:**
```bash
SENTRY_DSN=https://xxx@sentry.io/123456
SENTRY_ENVIRONMENT=production
```

3. **Automatisch aktiv** wenn `DEBUG=False`

### Features

✅ Automatische Error-Erfassung
✅ Stack Traces
✅ Request Context (URL, User, Browser)
✅ Breadcrumbs (letzte Aktionen vor Error)
✅ Release Tracking
✅ Performance Monitoring (10% Sample)

### Custom Sentry Events

```python
import sentry_sdk

# Custom Message
sentry_sdk.capture_message("Something unusual happened")

# Custom Exception
try:
    risky_operation()
except Exception as e:
    sentry_sdk.capture_exception(e)

# Add Context
with sentry_sdk.configure_scope() as scope:
    scope.set_user({"id": user.id, "username": user.username})
    scope.set_tag("training_type", "ai_generated")
    scope.set_extra("plan_id", plan.id)
```

## Django-Axes: Brute-Force Protection

### Konfiguration

- **Max Versuche:** 5 fehlgeschlagene Logins
- **Lockout-Zeit:** 1 Stunde
- **Tracking:** Username-basiert
- **Logs:** `security.log`

### Admin-Interface

Gesperrte IPs/Users managen:
```
/admin/axes/accessattempt/
```

### Manuelles Entsperren

```bash
python manage.py axes_reset
# Oder für spezifischen User:
python manage.py axes_reset_username <username>
```

## Log-Files analysieren

### Letzte Errors anzeigen

```bash
# Windows
type logs\error.log | findstr /i "error"

# Linux/Mac
tail -n 50 logs/error.log | grep -i error
```

### Log-Level filtern

```bash
# Nur CRITICAL
findstr "CRITICAL" logs\django.log

# Nur heute
findstr "2026-02-" logs\django.log
```

### Security-Events

```bash
type logs\security.log
```

## Environment Variables

```bash
# Log-Level setzen (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL=INFO

# Sentry
SENTRY_DSN=https://xxx@sentry.io/123456
SENTRY_ENVIRONMENT=production  # oder staging, development
```

## Troubleshooting

### Problem: Logs werden nicht geschrieben

**Lösung:**
```bash
# Prüfe ob logs/ existiert
ls logs/

# Erstelle falls nicht vorhanden
mkdir logs
```

### Problem: Log-Datei wird zu groß

**Lösung:** Rotation ist automatisch (10 MB Limit). Alte Logs:
```bash
# Alte Backups löschen
del logs\django.log.1
del logs\django.log.2
```

### Problem: Sentry Events kommen nicht an

**Prüfen:**
1. `DEBUG=False` in .env?
2. `SENTRY_DSN` korrekt gesetzt?
3. Internet-Verbindung?
4. Sentry-Dashboard checken

**Test:**
```python
import sentry_sdk
sentry_sdk.capture_message("Test Event")
```

## Best Practices

### ✅ DO

- Strukturiertes Logging mit Context-Daten nutzen
- Sensitive Daten NICHT loggen (Passwörter, Tokens, etc.)
- Performance-Decorator für langsame Operationen
- Security-Events immer loggen
- Exceptions mit `exc_info=True` loggen

### ❌ DON'T

- User-Input direkt in Logs (SQL-Injection-Risiko)
- Logs in Hot Loops (Performance)
- Sensitive Daten wie Passwörter loggen
- Zu viel DEBUG-Logging in Production
- Logs ohne Context (schwer zu debuggen)

## Beispiel: Vollständiges Error-Handling

```python
from core.utils.logging_helper import get_logger, log_error_with_context

logger = get_logger(__name__)

def create_training_session(request):
    try:
        # Validierung
        form = TrainingForm(request.POST)
        if not form.is_valid():
            logger.warning(
                "Invalid form submission",
                extra={
                    'user_id': request.user.id,
                    'errors': form.errors.as_json()
                }
            )
            return render(request, 'form.html', {'form': form})
        
        # Speichern
        training = form.save(commit=False)
        training.user = request.user
        training.save()
        
        # Success Logging
        logger.info(
            "Training created",
            extra={
                'user_id': request.user.id,
                'training_id': training.id,
                'duration': training.dauer_minuten
            }
        )
        
        return redirect('training_detail', pk=training.pk)
        
    except Exception as e:
        # Error Logging mit Context
        log_error_with_context(
            logger,
            "Failed to create training",
            exception=e,
            user_id=request.user.id,
            form_data=request.POST.dict()
        )
        
        # User-freundliche Error-Message
        messages.error(request, "Fehler beim Speichern. Bitte versuche es erneut.")
        return render(request, 'error.html')
```

## Monitoring Checkliste

- [ ] Sentry DSN konfiguriert
- [ ] Log-Files werden rotiert
- [ ] Security-Events werden geloggt
- [ ] Axes Brute-Force Protection aktiv
- [ ] Performance-Monitoring für kritische Funktionen
- [ ] Error-Alerts in Sentry konfiguriert
- [ ] Log-Retention Policy definiert (wie lange Logs behalten?)
