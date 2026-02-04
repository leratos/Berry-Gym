# 🤖 AI Coach - Konzept & Implementierungsplan

**Stand:** 09.01.2026  
**Status:** 🔄 In Planung  
**Hardware:** Laptop RTX 4070 (8GB VRAM), Tower RTX 4070 Ti Super (16GB VRAM)

---

## 🎯 Ziel

Intelligente Trainingsplan-Generierung basierend auf:
- Trainingshistorie (letzte 30 Tage)
- Muskelgruppen-Balance
- Progressive Overload Daten
- RPE-Trends
- Individuelle Präferenzen

---

## 🏗️ Architektur

### Komponenten-Übersicht

```
┌─────────────────────────────────────────────────────────────┐
│                     HomeGym Web App                         │
│                  (gym.last-strawberry.com)                  │
│                MariaDB localhost:3306 (Plesk)               │
│              🔒 Firewall: Nur lokale Verbindungen           │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      │ SSH Tunnel (sshtunnel Paket)
                      │ localhost:3307 → server localhost:3306
                      │ Automatisch im Script gestartet
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                   AI Coach Script (Lokal)                   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  1. Django ORM Setup                                 │  │
│  │     - SSH Tunnel zu Production DB (auto-start)       │  │
│  │     - Verbindung: localhost:3307 → server:3306      │  │
│  │     - Models: Trainingseinheit, Satz, Plan, Uebung  │  │
│  └──────────────────────────────────────────────────────┘  │
│                            │                                │
│  ┌─────────────────────────▼────────────────────────────┐  │
│  │  2. Datenanalyse                                     │  │
│  │     - Letzte 30 Tage Training laden                  │  │
│  │     - Muskelgruppen-Volumen berechnen                │  │
│  │     - RPE-Trends analysieren                         │  │
│  │     - Schwachstellen identifizieren                  │  │
│  └──────────────────────────────────────────────────────┘  │
│                            │                                │
│  ┌─────────────────────────▼────────────────────────────┐  │
│  │  3. Prompt Engineering                               │  │
│  │     - System Prompt: Fitness Coach Persona           │  │
│  │     - Context: Trainingshistorie als JSON            │  │
│  │     - Instruktionen: Plan-Struktur vorgeben          │  │
│  └──────────────────────────────────────────────────────┘  │
│                            │                                │
│  ┌─────────────────────────▼────────────────────────────┐  │
│  │  4. Ollama LLM Call                                  │  │
│  │     - Model: llama3.1:8b (Laptop)                    │  │
│  │     - Model: llama3.1:13b (Tower, später)            │  │
│  │     - Output: JSON mit Trainingsplan                 │  │
│  └──────────────────────────────────────────────────────┘  │
│                            │                                │
│  ┌─────────────────────────▼────────────────────────────┐  │
│  │  5. Plan Persistierung                               │  │
│  │     - Plan.objects.create()                          │  │
│  │     - PlanUebung.objects.bulk_create()               │  │
│  │     - Validierung & Error Handling                   │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 📊 Datenfluss

### Input (Training History Analysis)

```python
{
    "user_id": 1,
    "analysis_period": "30 days",
    "training_stats": {
        "total_sessions": 12,
        "avg_duration_minutes": 75,
        "frequency_per_week": 3.5,
        "muscle_groups": {
            "Brust": {
                "effective_reps": 240,  # Wdh × (RPE/10)
                "avg_rpe": 7.8,
                "last_trained": "2026-01-07"
            },
            "Rücken": {
                "effective_reps": 280,
                "avg_rpe": 8.2,
                "last_trained": "2026-01-08"
            },
            "Beine": {
                "effective_reps": 180,
                "avg_rpe": 7.5,
                "last_trained": "2026-01-05"
            }
            // ... weitere Muskelgruppen
        },
        "exercise_performance": [
            {
                "exercise": "Bankdrücken",
                "last_1rm": 85.0,
                "trend": "+2.5kg (vs. 4 weeks ago)",
                "avg_rpe": 7.5
            }
            // ... weitere Übungen
        ],
        "weaknesses": ["Beine untertrainiert", "Schultern: Seitheben fehlt"],
        "form_index": 78
    }
}
```

### Output (Generated Plan)

```python
{
    "plan_name": "3er-Split: Push/Pull/Legs (Woche 1-4)",
    "plan_description": "Fokus auf Beinaufbau und Schulter-Hypertrophie",
    "sessions": [
        {
            "day": "Push (Brust/Schultern/Trizeps)",
            "exercises": [
                {
                    "exercise_id": 1,  # Bankdrücken
                    "sets": 4,
                    "reps": "8-10",
                    "order": 1,
                    "notes": "Hauptübung, progressive Overload"
                },
                {
                    "exercise_id": 15,  # Seitheben
                    "sets": 4,
                    "reps": "12-15",
                    "order": 2,
                    "notes": "Schwachstelle, langsame Ausführung"
                }
                // ... weitere Übungen
            ]
        },
        // ... weitere Trainingstage
    ],
    "periodization": {
        "week_1_4": "Hypertrophie (8-12 Wdh, RPE 7-8)",
        "week_5": "Deload (6 Wdh, RPE 5-6)"
    }
}
```

---

## 🛠️ Technologie-Stack

| Komponente | Technologie | Zweck |
|------------|------------|-------|
| **LLM Runtime** | Ollama | Lokale Modell-Ausführung |
| **Model** | Llama 3.1 8B/13B | Plan-Generierung |
| **DB Access** | Django ORM + mysqlclient | Production DB via SSH Tunnel |
| **SSH Tunnel** | sshtunnel (Python) | Automatischer Tunnel-Start im Script |
| **Connection** | localhost:3307 → server:3306 | Sichere verschlüsselte Verbindung |
| **Prompt Management** | Python Strings | System/User Prompts |
| **Error Handling** | Try/Except + Logging | Robustheit |

---

## 📂 Projekt-Struktur

```
Fitness/
├── ai_coach/                        # Neuer Ordner
│   ├── __init__.py                  # Paket-Initialisierung
│   ├── plan_generator.py            # Hauptskript (Entry Point)
│   ├── data_analyzer.py             # Trainingshistorie-Analyse
│   ├── prompt_builder.py            # Prompt Engineering
│   ├── llm_client.py                # Ollama API Wrapper
│   ├── db_client.py                 # Django ORM Setup + SSH Tunnel
│   ├── config.py                    # Konfiguration (SSH, DB, User ID)
│   ├── .env.example                 # Environment Template
│   ├── requirements.txt             # Dependencies (ollama, sshtunnel, mysqlclient)
│   └── README.md                    # Usage Dokumentation
│
└── (bestehende Struktur)
```

---

## 🔧 Implementierungsphasen

### Phase 1: Setup & Basic Integration ✅
- [x] Ollama installiert (Laptop + GPU configured)
- [x] llama3.1:8b heruntergeladen
- [x] Test erfolgreich

### Phase 2: Django ORM Integration (Aktuell)
- [ ] `ai_coach/` Ordner erstellen
- [ ] `db_client.py`: Django Setup + SSH Tunnel (sshtunnel Paket)
- [ ] `.env.example`: SSH + DB Credentials Template
- [ ] `data_analyzer.py`: Basic Training History Query
- [ ] Test: SSH Tunnel + Daten aus Production DB laden

### Phase 3: Datenanalyse
- [ ] Muskelgruppen-Volumen berechnen (RPE-weighted)
- [ ] 1RM Trends pro Übung
- [ ] Schwachstellen identifizieren
- [ ] JSON Context für LLM aufbereiten

### Phase 4: Prompt Engineering
- [ ] System Prompt: Fitness Coach Persona
- [ ] User Prompt: Trainingshistorie + Anforderungen
- [ ] JSON Schema für Output definieren
- [ ] Few-Shot Examples (optional)

### Phase 5: LLM Integration
- [ ] `llm_client.py`: Ollama API Wrapper
- [ ] Prompt → Ollama → JSON Response
- [ ] Error Handling (Timeouts, Invalid JSON)
- [ ] Response Validation

### Phase 6: Plan Persistierung
- [ ] JSON → Django Models (Plan, PlanUebung)
- [ ] Übungs-IDs validieren (existieren in DB?)
- [ ] Plan speichern & User zuweisen
- [ ] Success/Error Logging

### Phase 7: Testing & Refinement
- [ ] End-to-End Test mit echten Daten
- [ ] Plan-Qualität bewerten
- [ ] Prompt iterieren basierend auf Outputs
- [ ] Performance messen (Zeit, VRAM)

### Phase 8: Automation (Optional)
- [ ] CLI Arguments (user_id, plan_type)
- [ ] Windows Task Scheduler Integration
- [ ] Wöchentliche automatische Generierung

---

## 🎯 MVP (Minimum Viable Product)

**Ziel:** Einfacher funktionierender Prototyp

**Features:**
1. User ID als Argument
2. Letzte 30 Tage Training laden
3. Muskelgruppen-Balance berechnen
4. Einfacher Prompt: "Erstelle 3er-Split basierend auf diesen Daten"
5. JSON Output von Ollama
6. Plan in DB speichern

**Nicht im MVP:**
- UI/Web-Integration
- Mehrere Plan-Typen (nur 3er-Split)
- Periodisierung (kommt später)
- Deload-Wochen

---

## 📋 Success Criteria

**Technisch:**
- ✅ Script läuft ohne Errors
- ✅ DB-Verbindung funktioniert
- ✅ Ollama antwortet in <20 Sekunden
- ✅ Plan wird in DB gespeichert
- ✅ Plan erscheint in Web App

**Qualitativ:**
- ✅ Plan ist wissenschaftlich fundiert
- ✅ Muskelgruppen ausgewogen
- ✅ Progressive Overload berücksichtigt
- ✅ Übungen existieren in DB
- ✅ Realistische Satz/Wdh-Vorgaben

---

## 🔐 Security Considerations

1. **SSH Tunnel:** ✅ Port 3306 nur lokal (Plesk: "Nur lokale Verbindungen")
2. **Verschlüsselung:** ✅ Komplette DB-Kommunikation SSH-verschlüsselt
3. **Authentifizierung:** SSH Key (empfohlen) oder Passwort via .env
4. **Credentials:** SSH + DB Credentials via .env (nicht im Code)
5. **Read-Only Access:** Script liest nur Training (außer Plan-Speicherung)
6. **User Isolation:** Nur Daten des angegebenen Users
7. **Local Execution:** LLM läuft lokal, keine Daten in Cloud
8. **Attack Surface:** Minimal - nur SSH Port 22 exposed (Standard)

---

## 📊 Performance Targets

| Metrik | Ziel | Begründung |
|--------|------|------------|
| **DB Query Time** | <2s | Optimierte Queries mit select_related |
| **LLM Inference** | <15s | 8B Model auf 4070 |
| **Total Runtime** | <20s | Interaktive Nutzung möglich |
| **VRAM Usage** | <7GB | Laptop 4070 (8GB verfügbar) |

---

## 🚀 Next Steps

1. **Jetzt:** Ordnerstruktur anlegen (`ai_coach/` Folder)
2. **Dann:** `.env.example` mit SSH + DB Credentials Template
3. **Danach:** `db_client.py` mit SSH Tunnel (sshtunnel) + Django Setup
4. **Test:** SSH Tunnel starten → DB Connection testen
5. **Weiter:** `data_analyzer.py` mit Basic Query (letztes Training laden)

---

## 💡 Ideen für Erweiterungen (Später)

- **Plan-Typen:** 2er/3er/4er/5er-Split, PPL, Upper/Lower, Fullbody
- **Periodisierung:** 4-Wochen Zyklen mit Deload
- **Ernährung:** Kalorien/Protein-Empfehlungen
- **Injury Prevention:** Schwachstellen-basierte Prehab
- **Voice Interface:** Alexa/Google Home Integration
- **Auto-Logging:** Vorschläge während Training
- **Competition Prep:** Peak Week Planning

---

**Autor:** lera  
**Review:** Copilot ✅
