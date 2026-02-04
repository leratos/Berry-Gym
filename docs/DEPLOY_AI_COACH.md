# AI Coach Deployment auf Production Server

## 📋 Deployment Checkliste

### 1️⃣ Dateien auf Server kopieren

```bash
# Von lokalem PC aus (PowerShell/Terminal)
cd C:\Users\lerat\OneDrive\Projekt\App\Fitness

# ai_coach Ordner via SCP hochladen
scp -r ai_coach/ dein-user@gym.last-strawberry.com:/var/www/vhosts/last-strawberry.com/gym/
```

**Oder manuell via FTP/SFTP:**
- Kompletter `ai_coach/` Ordner → `/var/www/vhosts/last-strawberry.com/gym/ai_coach/`

### 2️⃣ Dependencies auf Server installieren

```bash
# SSH auf Server
ssh dein-user@gym.last-strawberry.com

# Ins Projekt
cd /var/www/vhosts/last-strawberry.com/gym

# Virtual Environment aktivieren
source venv/bin/activate

# AI Coach Dependencies installieren
pip install openai==1.58.1 keyring==25.5.0

# NICHT installieren auf Server (kein Ollama, kein SSH-Tunnel nötig):
# - ollama (braucht GPU, nicht verfügbar)
# - sshtunnel (Server verbindet direkt zu localhost MariaDB)
```

### 3️⃣ OpenRouter API Key sicher speichern

```bash
# Auf Server (im venv)
python ai_coach/secrets_manager.py set OPENROUTER_API_KEY

# Eingabe: sk-or-v1-... (dein OpenRouter Key)
# Key wird verschlüsselt im Linux Secret Service gespeichert
```

### 4️⃣ Server .env konfigurieren

In `/var/www/vhosts/last-strawberry.com/gym/.env` hinzufügen:

```bash
# OpenRouter (Remote 70B - Primary LLM)
OPENROUTER_MODEL=meta-llama/llama-3.1-70b-instruct
USE_OPENROUTER_FALLBACK=False  # Primary, nicht Fallback

# KEIN Ollama (Server hat keine GPU):
# OLLAMA_BASE_URL=...  ← NICHT setzen
# OLLAMA_MODEL=...     ← NICHT setzen
```

### 5️⃣ Test: Plan generieren auf Server

```bash
# Test-Run (im venv)
python ai_coach/plan_generator.py --user-id 2 --plan-type 3er-split --use-openrouter

# Sollte ausgeben:
# ✅ "Verwende OpenRouter (remote 70B): meta-llama/llama-3.1-70b-instruct"
# ✅ "Kosten: 0.0028€ (~0.28 Cent)"
# ✅ "Plan erstellt: [Plan-Details]"
```

### 6️⃣ Django Service neu starten

```bash
# Django neu starten damit .env geladen wird
sudo systemctl restart homegym.service

# Status prüfen
sudo systemctl status homegym.service
```

---

## ✅ Erfolgs-Check

Nach Deployment sollte funktionieren:

1. **Plan-Generierung via CLI:**
   ```bash
   python ai_coach/plan_generator.py --user-id 2 --plan-type 3er-split --use-openrouter
   ```

2. **Future Features (nach Implementation):**
   - Live-Guidance während Training
   - Proaktive Anpassungen basierend auf Performance

---

## 🔐 Sicherheit

- ✅ API Key verschlüsselt in Linux Secret Service (nicht in .env)
- ✅ SSH-Tunnel nicht nötig (Server → localhost:3306)
- ✅ Keine Ollama-Installation (keine GPU)

---

## 💰 Kosten-Übersicht

- **Plan-Generierung:** ~0.0015€ (~0.15 Cent)
- **Live-Guidance Session:** ~0.0020€ (~0.20 Cent)
- **Monatlich bei 50 Plänen:** ~0.75€

---

## 🚨 Troubleshooting

### "ModuleNotFoundError: No module named 'openai'"
```bash
source venv/bin/activate
pip install openai==1.58.1 keyring==25.5.0
```

### "OpenRouter API Key nicht gefunden"
```bash
python ai_coach/secrets_manager.py set OPENROUTER_API_KEY
# Key eingeben: sk-or-v1-...
```

### "Ollama connection refused"
→ Normal! Server soll **nur OpenRouter** nutzen (kein Ollama)
→ Prüfe: `USE_OPENROUTER_FALLBACK=False` in `.env`

---

## 📝 Dateien die auf Server müssen

```
ai_coach/
├── __init__.py
├── ai_config.py
├── data_analyzer.py
├── db_client.py
├── llm_client.py
├── plan_generator.py
├── prompt_builder.py
├── secrets_manager.py
├── README.md
└── requirements.txt (Referenz)
```

**NICHT hochladen:**
- `.env` (lokale Config)
- `__pycache__/` (Auto-generiert)
- `test_*.py` (Development)
- `*_prod.py` (waren für Migration, nicht mehr nötig)
