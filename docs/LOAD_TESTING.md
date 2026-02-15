# Load Testing – Berry-Gym

**Tool:** Locust  
**Ziel:** P95 < 500ms, P99 < 1000ms, Fehlerrate < 1% @ 100 concurrent users

---

## Voraussetzungen

### 1. Locust installieren

```bash
pip install locust
```

Ist bereits in `requirements.txt` enthalten.

### 2. Test-User anlegen

Load Tests brauchen echte Django-User. Das Management-Command erstellt sie:

```bash
# Lokale Entwicklung
python manage.py create_load_test_users

# Oder manuell via Django Shell
python manage.py shell
>>> from django.contrib.auth.models import User
>>> for i in range(1, 6):
...     User.objects.create_user(f"loadtest_user{i}", password="LoadTest2024!")
```

**Wichtig:** Die User-Credentials müssen mit `LOAD_TEST_USERS` in `locustfile.py` übereinstimmen.

### 3. Django-Server starten

```bash
# Entwicklung (SQLite – Trendanalyse)
python manage.py runserver

# Produktionsnäher (Gunicorn + SQLite)
gunicorn config.wsgi:application --workers 4 --bind 0.0.0.0:8000
```

---

## Ausführung

### Web-UI (empfohlen für manuelle Tests)

```bash
locust --config tests/load/locust.conf
```

Dann Browser öffnen: http://localhost:8089

Im Web-UI:
1. Host bestätigen (default: `http://localhost:8000`)
2. User-Anzahl und Spawn-Rate einstellen
3. „Start swarming" klicken
4. Nach 60s „Stop" klicken

### Headless (für Automatisierung / CI-ähnlich)

```bash
locust --config tests/load/locust.conf --headless
```

Ergebnis-Report wird nach `tests/load/results/report.html` geschrieben.

### Nur ein Szenario testen

```bash
# Nur typische User-Sessions
locust -f tests/load/locustfile.py --class-picker

# Oder direkt angeben
locust -f tests/load/locustfile.py BerryGymUser --users 50 --spawn-rate 5 --run-time 30s --headless
```

---

## Szenarien

| Klasse | Beschreibung | Tasks |
|---|---|---|
| `BerryGymUser` | Typische authentifizierte Session | Dashboard, Übungen, Historie, Stats, Body-Stats, Profil |
| `CachedEndpointUser` | Fokus auf gecachte Endpoints | plan-templates API, Dashboard, Übungsliste |
| `ApiUser` | AJAX-typische Requests | last-set, exercise-detail, ml-model-info |

---

## SLO-Ziele

| Metrik | Ziel | Kritisch |
|---|---|---|
| P95 Latenz | < 500ms | > 1000ms |
| P99 Latenz | < 1000ms | > 2000ms |
| Fehlerrate | < 1% | > 5% |
| Throughput | > 50 RPS | < 20 RPS |

---

## Ergebnisse interpretieren

Nach dem Test gibt Locust eine Zusammenfassung aus:

```
============================== LOAD TEST ERGEBNIS ==============================
  Requests gesamt:  6240
  Fehlerrate:       0.08%  (Ziel: < 1%)
  P95 Latenz:       312ms  (Ziel: < 500ms)
  P99 Latenz:       487ms  (Ziel: < 1000ms)
  ✅ P95 OK
  ✅ P99 OK
  ✅ Fehlerrate OK
  GESAMT: ✅ ALLE SLOs ERFÜLLT
```

Der HTML-Report unter `tests/load/results/report.html` enthält:
- Zeitverlauf der Response Times
- Requests/s über Zeit
- Fehler-Liste mit Details

---

## Einschränkungen

### Lokaler Test ≠ Produktion

| Aspekt | Lokal | Produktion |
|---|---|---|
| Server | Django `runserver` (single-threaded) | Gunicorn (4 Workers) |
| Datenbank | SQLite | MariaDB |
| Cache | LocMemCache | FileBasedCache |
| Netzwerk | Localhost (0ms Latenz) | Internet (~50-100ms) |

**Fazit:** Lokale Zahlen sind nicht direkt mit Produktions-SLOs vergleichbar. Load Tests lokal sind sinnvoll für:
- Regressions-Erkennung (wurde es langsamer als vorher?)
- Bottleneck-Suche (welcher Endpoint ist der Ausreißer?)
- Cache-Verifikation (hält der Cache unter Last?)

Für absolute SLO-Validierung: Test gegen Staging/Produktion mit Gunicorn.

### Nicht getestete Endpoints

Folgende Endpoints sind absichtlich ausgelassen:

| Endpoint | Grund |
|---|---|
| `/api/generate-plan/` | Ollama-Dependency, blockierender LLM-Call |
| `/api/analyze-plan/` | Ollama-Dependency |
| `/api/ml/train/` | Blockierender scikit-learn-Fit, verfälscht Messungen |
| `/export/training-pdf/` | WeasyPrint ist langsam by design (kein SLO-Problem) |
| `/api/push/subscribe/` | Benötigt VAPID-Keys im Request |

---

## Test-User aufräumen

```bash
python manage.py shell
>>> from django.contrib.auth.models import User
>>> User.objects.filter(username__startswith="loadtest_user").delete()
```

Oder via Management-Command:

```bash
python manage.py create_load_test_users --delete
```
