# AI Coach - Personalisierte Trainingsplanung mit Llama 3.1

AI-gestützte Trainingsplan-Generierung basierend auf historischen Trainingsdaten und Equipment-Verfügbarkeit.

## 🏗️ Architektur

```
User Data → Data Analyzer → Prompt Builder → Llama 3.1 → Plan Validator → Django DB
```

## ✨ Features

- **Trainingshistorie-Analyse**: RPE-gewichtetes Volumen, 1RM Berechnung, Schwachstellen-Erkennung
- **Equipment-Filtering**: Nur Übungen mit verfügbarem Equipment
- **Push/Pull Balance**: Automatische Balance-Optimierung
- **Progressive Overload**: Intelligente Steigerungsvorschläge
- **Flexible Plan-Typen**: 3er-Split, PPL, Upper/Lower, Fullbody

## 🚀 Quick Start

```bash
# 1. Ollama Server starten (falls nicht läuft)
ollama serve

# 2. Trainingsplan generieren
python ai_coach/plan_generator.py --user-id 1 --plan-type 3er-split
```

## 📦 Setup

### 1. Ollama Installation
```bash
# Ollama installieren
winget install ollama

# Llama 3.1 8B Model pullen
ollama pull llama3.1:8b

# Server starten
ollama serve
```

### 2. Python Dependencies
```bash
pip install ollama python-dotenv mysqlclient
```

### 3. Environment Config
- Config: `ai_coach/.env` (bereits konfiguriert)
- SSH Key: `C:/Users/lerat/.ssh/id_rsa`
- DB Host: `gym.last-strawberry.com:3306` (via SSH Tunnel)

## 📖 Usage

### Trainingsplan generieren

```bash
# 3er-Split für User 1 (speichert in DB)
python ai_coach/plan_generator.py --user-id 1 --plan-type 3er-split

# Preview ohne DB speichern
python ai_coach/plan_generator.py --user-id 1 --plan-type ppl --no-save

# Mit JSON Export
python ai_coach/plan_generator.py --user-id 1 --plan-type upper-lower --output plan.json

# Höhere Kreativität (0.0-1.0)
python ai_coach/plan_generator.py --user-id 1 --temperature 0.9

# Längere Analyse (60 Tage statt 30)
python ai_coach/plan_generator.py --user-id 1 --analysis-days 60
```

### Plan-Typen

| Plan Type | Beschreibung | Frequenz |
|-----------|-------------|----------|
| **3er-split** | Push/Pull/Legs oder Ober/Unter/Ganz | 3x/Woche |
| **4er-split** | Brust+Tri, Rücken+Bi, Schultern+Bauch, Beine | 4x/Woche |
| **ppl** | Push/Pull/Legs | 6x/Woche |
| **upper-lower** | Oberkörper/Unterkörper | 4x/Woche |
| **fullbody** | Ganzkörper | 3x/Woche |

## 🧩 Module

### `data_analyzer.py`
Analysiert Trainingshistorie der letzten 30 Tage:
- **RPE-weighted Volume**: `effective_reps = reps × (RPE/10)`
- **1RM Berechnung**: Epley Formula `weight × (1 + reps/30)`
- **Push/Pull Balance**: Basierend auf Muskelgruppen
- **Schwachstellen**: Muskelgruppen mit <60% durchschnittlichem Volumen

```python
from data_analyzer import TrainingAnalyzer

with DatabaseClient() as db:
    analyzer = TrainingAnalyzer(user_id=1, days=30)
    analysis = analyzer.analyze()
    analyzer.print_summary()
```

### `prompt_builder.py`
Erstellt strukturierte Prompts für Llama:
- **System Prompt**: Fitness Coach Persona mit 15 Jahren Erfahrung
- **User Prompt**: Trainingsdaten + verfügbare Übungen
- **Equipment-Filtering**: Nur Übungen die User ausführen kann

```python
from prompt_builder import PromptBuilder

builder = PromptBuilder()
available_exercises = builder.get_available_exercises_for_user(user_id=1)
messages = builder.build_messages(analysis, available_exercises, "3er-split")
```

### `llm_client.py`
Ollama API Wrapper:
- **Llama 3.1 Integration**: Lokales LLM (8GB VRAM)
- **JSON Parsing**: Mit Fallback für ```json code blocks```
- **Plan Validation**: Prüft Übungen und Required Fields

```python
from llm_client import LLMClient

client = LLMClient(temperature=0.7)
plan = client.generate_training_plan(messages, max_tokens=4000)
valid, errors = client.validate_plan(plan, available_exercises)
```

### `plan_generator.py`
Hauptskript - kombiniert alle Module:
1. ✅ Trainingshistorie analysieren
2. ✅ Verfügbare Übungen ermitteln (Equipment-Filter)
3. ✅ Prompts erstellen (System + User)
4. ✅ LLM aufrufen (Llama 3.1)
5. ✅ Plan validieren
6. ✅ In Django DB speichern (Plan + Plan_Uebung)

### `db_client.py`
SSH Tunnel + Django ORM Setup:
- **SSH Tunnel**: Via subprocess + native OpenSSH
- **Context Manager**: Automatisches Cleanup
- **Django ORM**: Production DB Zugriff

```python
from db_client import DatabaseClient

with DatabaseClient() as db:
    from core.models import User, Trainingseinheit
    # ... Django ORM queries
# SSH Tunnel wird automatisch geschlossen
```

## 📄 Output Format

Llama generiert JSON mit dieser Struktur:

```json
{
  "plan_name": "3er-Split: Push/Pull/Legs - Woche 1-4",
  "plan_description": "Beschreibung und Ziele",
  "duration_weeks": 4,
  "sessions": [
    {
      "day_name": "Push (Brust/Schultern/Trizeps)",
      "exercises": [
        {
          "exercise_name": "Bankdrücken (Langhantel)",
          "sets": 4,
          "reps": "8-10",
          "rpe_target": 8,
          "order": 1,
          "notes": "Hauptübung, progressive Overload"
        }
      ]
    }
  ],
  "weekly_structure": "Beschreibung des Wochenplans",
  "progression_notes": "Steigerungs-Hinweise"
}
```

## ✅ Validation

Der generierte Plan wird automatisch validiert:
- ✅ Required fields vorhanden? (`plan_name`, `sessions`, `exercises`)
- ✅ Alle Übungen existieren in DB?
- ✅ Alle Übungen haben Equipment?
- ✅ Sets/Reps/Order definiert?

❌ Bei Validierungsfehlern wird Plan **NICHT gespeichert**.

## ⚡ Performance

- **Data Analysis**: ~2s (SSH Tunnel + Django Queries)
- **Prompt Building**: <1s
- **LLM Generation**: ~15-45s (Llama 3.1 8B @ RTX 4070)
- **Validation + Save**: ~1s
- **Total**: ~20-50s pro Plan

## 🔧 Troubleshooting

### SSH Tunnel Fehler
```bash
# SSH Key Permissions prüfen
icacls "C:\Users\lerat\.ssh\id_rsa"

# Manuell SSH testen
ssh -i "C:/Users/lerat/.ssh/id_rsa" lerat@gym.last-strawberry.com
```

### Ollama nicht erreichbar
```bash
# Ollama Status prüfen
ollama list

# Ollama Server starten
ollama serve

# Model vorhanden?
ollama pull llama3.1:8b
```

### Equipment nicht gefunden
User muss Equipment im UI auswählen: **`/equipment/`**

⚠️ **Minimum 15-20 Übungen empfohlen** für gute Pläne.

### Plan Generation Fehler
- Prüfe Ollama Logs: `ollama serve` Output
- Validierungsfehler werden im Terminal angezeigt
- JSON Export mit `--output plan.json` für Debugging

## 📊 Example Output

```bash
$ python ai_coach/plan_generator.py --user-id 1 --plan-type 3er-split

============================================================
🏋️ AI COACH - Trainingsplan Generierung
============================================================

📊 SCHRITT 1: Trainingshistorie analysieren
   Sessions: 1 (0.2x/Woche)
   Top Muskelgruppen: BAUCH (31), BRUST (29), BEINE_HAM (26)
   Schwachstellen: BIZEPS (13 eff.Wdh)

🔧 SCHRITT 2: Verfügbare Übungen ermitteln
   ✓ 41 Übungen mit verfügbarem Equipment

🤖 SCHRITT 3: LLM Prompts erstellen
   ✓ System Prompt: 1903 Zeichen
   ✓ User Prompt: 2599 Zeichen

🧠 SCHRITT 4: Trainingsplan mit Llama generieren
   ✓ Response: 15.2s, 648 Tokens

✅ SCHRITT 5: Plan validieren
   ✅ Plan Validation: OK

💾 SCHRITT 6: Plan in Datenbank speichern
   ✓ Plan erstellt: '3er-Split: Push/Pull/Legs' (ID: 42)
   ➤ Session: Push (Brust/Schultern/Trizeps)
      ✓ Bankdrücken (Langhantel): 4x8-10
      ✓ Arnold Press (Kurzhantel): 3x10-12
   ➤ Session: Pull (Rücken/Lat)
      ✓ Kreuzheben (Langhantel): 4x8-10
      ✓ Seal Rows (Bank, Kurzhantel): 3x10-12

🎉 FERTIG! Trainingsplan erfolgreich generiert
```

## 🎯 Next Steps

- [ ] **Web UI Integration**: Plan-Generator Button im Dashboard
- [ ] **Periodisierung**: Multi-Woche Pläne mit automatischen Deload-Wochen
- [ ] **Exercise Variation**: Automatische Rotation alle 4-6 Wochen
- [ ] **Progress Tracking**: Vergleich Plan vs. Actual Performance
- [ ] **Regeneration Score**: Empfehlung basierend auf RPE History
