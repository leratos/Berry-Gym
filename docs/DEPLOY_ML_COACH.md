# 🤖 ML Coach - Server Deployment Guide

**Stand:** 05.02.2026  
**Komponente:** ML-basiertes Vorhersagesystem (scikit-learn)

---

## 📋 Übersicht

Das ML-System ist **CPU-only** und benötigt **keine GPU**. Es läuft komplett lokal auf dem Server ohne externe API-Calls.

### Was macht das ML-System?

Das System erstellt **intelligente Gewichtsvorhersagen** basierend auf deiner Trainingshistorie:

1. **Beim Training:** Zeigt "ML-Empfehlung: X kg × Y Wdh" für jeden Satz
2. **Lernt von dir:** Analysiert deine letzten Trainingseinheiten (Gewicht, Wdh, RPE)
3. **Wird präziser:** Je mehr du trainierst, desto besser die Vorhersagen
4. **Spart Zeit:** Kein Raten mehr beim Gewicht - das Modell kennt dein Level

### Wo finde ich es?

- **Dashboard:** Button "ML Vorhersage-Modelle" (blaue Card)
- **Beim Training:** "ML-Empfehlung" wird über jeder Übung angezeigt
- **ML Dashboard:** Zeigt alle trainierten Modelle mit Genauigkeit (R² Score, MAE)

### Komponenten
- **Model:** Random Forest Regressor (scikit-learn 1.6.1)
- **Storage:** Pickle-Files in `MEDIA_ROOT/ml_models/`
- **Database:** MLPredictionModel (Django Model)
- **Dependencies:** scikit-learn 1.6.1, joblib 1.5.0

### Performance
- **Training:** <5 Sekunden pro User-Modell
- **Inferenz:** <10ms mit 1h Cache
- **RAM:** ~50-100MB pro aktives Modell
- **CPU:** 1-2 Cores für Training ausreichend

---

## 🚀 Deployment-Schritte

### 1. Code auf Server hochladen

```bash
# Via Git (empfohlen)
cd /var/www/vhosts/deine-domain.de/homegym
git pull origin main

# Oder via SCP
scp -r ml_coach/ user@server:/var/www/vhosts/deine-domain.de/homegym/
scp core/models.py user@server:/var/www/vhosts/deine-domain.de/homegym/core/
```

### 2. Virtual Environment aktivieren

```bash
cd /var/www/vhosts/deine-domain.de/homegym
source venv/bin/activate
```

### 3. Dependencies installieren

```bash
# ML-Pakete installieren (CPU-only)
pip install scikit-learn==1.6.1 joblib==1.5.0

# Verify Installation
python -c "import sklearn; print('scikit-learn:', sklearn.__version__)"
python -c "import joblib; print('joblib:', joblib.__version__)"
```

**Erwartete Ausgabe:**
```
scikit-learn: 1.6.1
joblib: 1.5.0
```

### 4. Migration ausführen

```bash
# Django Migrationen anwenden
python manage.py migrate

# Verify MLPredictionModel existiert
python manage.py shell -c "from core.models import MLPredictionModel; print('✅ Model OK')"
```

### 5. Media-Ordner für ML-Modelle erstellen

```bash
# Ordner für Pickle-Files erstellen
mkdir -p media/ml_models

# Permissions setzen (wichtig für Plesk)
chmod 755 media/ml_models
chown www-data:www-data media/ml_models  # oder entsprechender Web-User
```

### 6. Service neu starten

```bash
# Via Plesk: Python-App neu starten
# Oder manuell:
sudo systemctl restart homegym.service  # falls systemd verwendet wird
```

### 7. ML-System testen

```bash
# Test 1: Command ausführen
python manage.py train_ml_models

# Erwartete Ausgabe:
# 🤖 ML Training Service gestartet
# Minimale Samples: 10
# Trainiere Modelle für X User...
# ✅ Training abgeschlossen!

# Test 2: Python Shell Test
python manage.py shell
```

**In der Shell:**
```python
from ml_coach.ml_trainer import MLTrainer
from ml_coach.prediction_service import MLPredictor
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.first()

# Test Training
print("🔄 Teste ML-Training...")
results = MLTrainer.train_all_user_models(user=user, min_samples=10)
print(f"✅ Training OK: {len(results)} Modelle trainiert")

# Test Prediction (falls Modelle existieren)
if results:
    uebung, metrics = results[0]
    print(f"🔮 Teste Vorhersage für {uebung.name}...")
    predictor = MLPredictor(user_id=user.id)
    prediction = predictor.predict_next_weight(
        uebung_id=uebung.id,
        last_weight=50,
        last_reps=10,
        rpe=7
    )
    print(f"✅ Vorhersage: {prediction}")
else:
    print("⚠️ Keine Modelle trainiert (zu wenig Daten)")

exit()
```

### 8. API-Endpoints testen

```bash
# Test Dashboard (sollte 200 zurückgeben)
curl http://deine-domain.de/ml/dashboard/

# Test Model-Training API
curl -X POST http://deine-domain.de/api/ml/train/ \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1}'

# Test Vorhersage (wenn Modell existiert)
curl http://deine-domain.de/api/ml/predict/1/
```

---

## 📊 Monitoring & Wartung

### Modelle überprüfen

```bash
# Django Admin öffnen
# → Core → ML Prediction Models
# oder via Shell:
python manage.py shell -c "from core.models import MLPredictionModel; print(MLPredictionModel.objects.all())"
```

### Automatisches Training einrichten (optional)

```bash
# Cron-Job für tägliches Training
# Via Plesk: Scheduled Tasks oder /etc/cron.d/

# Beispiel: Täglich um 3:00 Uhr
0 3 * * * cd /var/www/vhosts/deine-domain.de/homegym && source venv/bin/activate && python manage.py train_ml_models --min-samples 10
```

### Alte Modelle löschen

```bash
# Modelle älter als 30 Tage löschen
python manage.py shell
```

**In der Shell:**
```python
from core.models import MLPredictionModel
from datetime import datetime, timedelta

old_models = MLPredictionModel.objects.filter(
    trained_at__lt=datetime.now() - timedelta(days=30),
    status='OUTDATED'
)
print(f"Lösche {old_models.count()} alte Modelle...")
old_models.delete()
```

---

## 🐛 Troubleshooting

### Problem: ModuleNotFoundError: No module named 'sklearn'

**Lösung:**
```bash
source venv/bin/activate
pip install scikit-learn==1.6.1 joblib==1.5.0
```

### Problem: PermissionError beim Speichern von Modellen

**Lösung:**
```bash
# Permissions für media/ml_models/ anpassen
chmod 755 media/ml_models
chown www-data:www-data media/ml_models
```

### Problem: "Keine Übungen mit genug Daten gefunden"

**Das ist normal!** User brauchen mind. 10 Sätze pro Übung für ML-Training.

**Lösung:** Warten bis User trainiert haben, oder Test-Daten generieren:
```python
# Test-Daten generieren (nur für Entwicklung)
python manage.py shell
from core.models import Trainingseinheit, Satz, Uebung
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta
import random

User = get_user_model()
user = User.objects.first()
uebung = Uebung.objects.filter(name__icontains='bench').first()

# 15 Test-Einheiten erstellen
for i in range(15):
    einheit = Trainingseinheit.objects.create(
        user=user,
        datum=datetime.now() - timedelta(days=i*2)
    )
    for s in range(3):
        Satz.objects.create(
            einheit=einheit,
            uebung=uebung,
            gewicht=60 + random.randint(-5, 10),
            wiederholungen=8 + random.randint(-2, 4),
            rpe=7 + random.random() * 2
        )

print("✅ Test-Daten erstellt!")
```

### Problem: Training dauert sehr lange

**CPU-Optimierung:**
```python
# In ml_coach/ml_trainer.py die n_jobs Parameter anpassen:
# RandomForestRegressor(n_estimators=50, max_depth=10, n_jobs=2)
```

### Problem: Pickle-Files werden zu groß

**Modellgröße reduzieren:**
```python
# In ml_coach/ml_trainer.py:
# n_estimators=50 → 30 (weniger Bäume)
# max_depth=10 → 8 (flachere Bäume)
```

### Problem: TemplateDoesNotExist at /ml/dashboard/

**Fehler:** `core/base.html` wird nicht gefunden

**Lösung:**
Dies wurde bereits gefixt. Falls der Fehler noch auftritt:
```bash
# Code neu pullen
git pull origin main

# Sicherstellen dass ml_dashboard.html das standalone Template ist
cat core/templates/core/ml_dashboard.html | head -n 5
# Sollte mit "{% load static %}" und "<!doctype html>" starten
```

---

## 📈 Performance-Metriken

### Erwartete Werte
- **R² Score:** >0.7 (gut), >0.85 (excellent)
- **MAE:** <5kg (gut), <2.5kg (excellent)
- **Modellgröße:** 50-200KB pro Model
- **Training-Zeit:** 2-5 Sekunden
- **Inferenz-Zeit:** <10ms

### Monitoring Dashboard

**Dashboard URL:** `https://deine-domain.de/ml/dashboard/`

**Metriken:**
- Anzahl trainierte Modelle
- Modelle die Retraining brauchen
- Durchschnittlicher R² Score
- Durchschnittlicher MAE

---

## ✅ Deployment-Checkliste

- [ ] Code auf Server hochgeladen
- [ ] Virtual Environment aktiviert
- [ ] `pip install scikit-learn==1.6.1 joblib==1.5.0` ausgeführt
- [ ] `python manage.py migrate` ausgeführt
- [ ] `media/ml_models/` Ordner erstellt mit korrekten Permissions
- [ ] Service neu gestartet
- [ ] `python manage.py train_ml_models` getestet
- [ ] Dashboard `/ml/dashboard/` erreichbar
- [ ] API-Endpoints getestet

---

## 🎯 Next Steps

1. **Warten auf Trainingsdaten:** User müssen ≥10 Sätze pro Übung absolvieren
2. **Erstes Training:** Nach 2-3 Wochen erstes `train_ml_models` ausführen
3. **Monitoring:** Dashboard regelmäßig checken
4. **Optional:** Cron-Job für automatisches Training einrichten

---

**Bei Fragen:** Siehe [DEPLOYMENT.md](DEPLOYMENT.md) für allgemeine Server-Fragen
