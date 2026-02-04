# Sicheres Secrets Management 🔐

## Problem mit Klartext API Keys

**Vorher (.env Datei):**
```bash
OPENROUTER_API_KEY=sk-or-v1-abc123xyz...  # ❌ Klartext!
```

**Risiken:**
- Jeder mit PC/Server-Zugriff kann Key lesen
- Git Commits versehentlich mit Keys
- Backup-Tools speichern Keys
- Logs können Keys enthalten

## Neue sichere Lösung ✅

### Windows: Credential Manager
### macOS: Keychain
### Linux: Secret Service

Keys werden **verschlüsselt** vom Betriebssystem gespeichert!

---

## 🚀 Setup (5 Minuten)

### 1. Package installieren
```bash
pip install keyring
```

### 2. API Key sicher speichern
```bash
python ai_coach/secrets_manager.py set OPENROUTER_API_KEY
# Paste deinen Key (wird versteckt eingegeben)
```

### 3. Fertig! 🎉
```bash
# Ab jetzt automatisch verschlüsselt geladen
python ai_coach/plan_generator.py --user-id 2 --plan-type 3er-split
```

---

## 📋 Secrets Manager Commands

### Secret speichern
```bash
python ai_coach/secrets_manager.py set OPENROUTER_API_KEY
# Eingabeaufforderung erscheint, Key wird nicht angezeigt
```

### Secret prüfen (maskiert)
```bash
python ai_coach/secrets_manager.py get OPENROUTER_API_KEY
# Ausgabe: ✅ OPENROUTER_API_KEY: ********************xyz123
```

### Secret löschen
```bash
python ai_coach/secrets_manager.py delete OPENROUTER_API_KEY
# Bestätigung erforderlich
```

### Alle Secrets auflisten
```bash
python ai_coach/secrets_manager.py list
# Zeigt welche Keys gespeichert sind
```

---

## 🔒 Wo wird gespeichert?

### Windows
```
Windows Credential Manager
→ Systemsteuerung → Anmeldeinformationsverwaltung
→ Windows-Anmeldeinformationen
→ Suche nach "HomeGym_AI_Coach"
```

### macOS
```
Keychain Access App
→ Suche nach "HomeGym_AI_Coach"
```

### Linux
```
Secret Service (GNOME Keyring / KWallet)
→ seahorse (GUI) oder secret-tool (CLI)
```

---

## 🎯 Vorteile

| Feature | .env Klartext | Secrets Manager |
|---------|---------------|-----------------|
| **Verschlüsselung** | ❌ Nein | ✅ OS-Level |
| **Git-sicher** | ❌ Risiko | ✅ Nie committed |
| **Zugriffskontrolle** | ❌ Jeder | ✅ OS-Benutzer |
| **Audit-Log** | ❌ Nein | ✅ OS-Events |
| **Backup-sicher** | ❌ Klartext | ✅ Verschlüsselt |

---

## 🔄 Fallback-Hierarchie

Das System versucht Keys in dieser Reihenfolge:

```python
1. OS Keyring (Windows Credential Manager, etc.)  # Sicherste
   ↓ Falls nicht gefunden
2. Environment Variable (zur Laufzeit gesetzt)     # Gut
   ↓ Falls nicht gefunden  
3. .env Datei (nur Development-Fallback)           # Unsicher!
```

**Empfehlung:**
- **Development (PC)**: OS Keyring
- **Production (Server)**: Environment Variables zur Laufzeit

---

## 🖥️ Production Server Setup

### Option 1: Systemd Service (empfohlen)
```bash
# /etc/systemd/system/homegym.service
[Service]
Environment="OPENROUTER_API_KEY=sk-or-v1-xxx"
# Wird nur zur Laufzeit in RAM gehalten!
```

### Option 2: Secrets Manager auch auf Server
```bash
# Als homegym User einloggen
sudo -u homegym_user bash

# Key setzen (wird im User-Keyring gespeichert)
python ai_coach/secrets_manager.py set OPENROUTER_API_KEY
```

### Option 3: Cloud Secrets Manager
```bash
# AWS Secrets Manager
# Azure Key Vault
# Google Cloud Secret Manager
# → Integration möglich (erfordert SDK)
```

---

## 🛡️ Best Practices

### ✅ DO:
```bash
# Keys über Secrets Manager setzen
python ai_coach/secrets_manager.py set OPENROUTER_API_KEY

# .gitignore für .env
echo ".env" >> .gitignore

# Environment nur zur Laufzeit
export OPENROUTER_API_KEY="sk-or-v1-xxx"
python app.py
unset OPENROUTER_API_KEY
```

### ❌ DON'T:
```bash
# Niemals Keys in Code hardcoden
api_key = "sk-or-v1-abc123"  # ❌

# Niemals Keys in .env committen
git add .env  # ❌

# Niemals Keys in Logs
print(f"API Key: {api_key}")  # ❌
```

---

## 🔧 Troubleshooting

### "keyring nicht installiert"
```bash
pip install keyring
```

### Windows: "Zugriff verweigert"
```powershell
# Als Administrator ausführen
# Oder: Windows Credential Manager manuell öffnen
```

### Linux: "No keyring backend"
```bash
# GNOME Desktop
sudo apt install gnome-keyring python3-secretstorage

# KDE Desktop  
sudo apt install kwalletmanager python3-keyring

# Headless Server (ohne GUI)
# → Nutze Environment Variables stattdessen
```

### macOS: "Keychain locked"
```bash
# Keychain entsperren
security unlock-keychain ~/Library/Keychains/login.keychain-db
```

---

## 🧪 Migration von .env zu Keyring

```bash
# 1. Aktuellen Key aus .env lesen
grep OPENROUTER_API_KEY .env
# OPENROUTER_API_KEY=sk-or-v1-abc123xyz

# 2. Key in Secrets Manager setzen
python ai_coach/secrets_manager.py set OPENROUTER_API_KEY
# Paste: sk-or-v1-abc123xyz

# 3. Key aus .env löschen (wichtig!)
# Editiere .env und entferne die Zeile

# 4. Testen
python ai_coach/plan_generator.py --user-id 2 --plan-type 3er-split
# Sollte jetzt aus Keyring laden: "✓ OpenRouter Client bereit (Key aus sicherer Quelle)"

# 5. .env in .gitignore
echo ".env" >> .gitignore
git add .gitignore
git commit -m "Ignore .env files"
```

---

## 📚 Code-Beispiel

```python
from secrets_manager import get_openrouter_key

# Holt Key automatisch aus sicherer Quelle
api_key = get_openrouter_key()

if api_key:
    print("✅ Key gefunden (aus Keyring)")
else:
    print("❌ Bitte Key setzen:")
    print("   python ai_coach/secrets_manager.py set OPENROUTER_API_KEY")
```

---

## ✅ Zusammenfassung

**Alte Methode (.env Klartext):**
```bash
OPENROUTER_API_KEY=sk-or-v1-abc123  # Jeder kann lesen!
```

**Neue Methode (Encrypted Keyring):**
```bash
python ai_coach/secrets_manager.py set OPENROUTER_API_KEY
# → Verschlüsselt in OS Keyring gespeichert
# → Nur dein OS-User kann darauf zugreifen
# → Niemals in Git committed
# → Automatisch geladen
```

**Deine Daten sind jetzt sicher! 🛡️**
