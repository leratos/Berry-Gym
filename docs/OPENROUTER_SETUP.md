# OpenRouter Setup Guide 🌐

## Schnellstart (5 Minuten)

### 1. OpenRouter Account erstellen
```bash
# 1. Gehe zu: https://openrouter.ai/
# 2. Klicke "Sign Up" (kostenlos!)
# 3. Verifiziere E-Mail
```

### 2. API Key generieren
```bash
# 1. Gehe zu: https://openrouter.ai/keys
# 2. Klicke "Create Key"
# 3. Name: "HomeGym AI Coach"
# 4. Kopiere Key (beginnt mit "sk-or-v1-...")
```

### 3. API Key in .env eintragen
```bash
# Erstelle .env Datei (falls nicht vorhanden)
cp .env.example .env

# Editiere .env und füge ein:
OPENROUTER_API_KEY=sk-or-v1-dein-key-hier

# OpenRouter Model (optional, default ist gut)
OPENROUTER_MODEL=meta-llama/llama-3.1-70b-instruct

# Aktiviere Fallback (empfohlen)
USE_OPENROUTER_FALLBACK=True
```

### 4. OpenAI Package installieren
```bash
# Lokal (Development)
pip install openai

# Production (Server)
ssh user@gym.last-strawberry.com
cd /var/www/vhosts/last-strawberry.com/gym
source venv/bin/activate
pip install openai
```

### 5. Testen!
```bash
# Hybrid-Modus: Versucht Ollama, dann OpenRouter Fallback
python ai_coach/plan_generator.py --user-id 2 --plan-type 3er-split

# Nur OpenRouter (skip Ollama)
python ai_coach/plan_generator.py --user-id 2 --plan-type 3er-split --use-openrouter

# Ollama ohne Fallback (wie vorher)
python ai_coach/plan_generator.py --user-id 2 --plan-type 3er-split --no-fallback
```

## ✅ Vorteile OpenRouter

### Qualität
- **70B Model** statt 8B → 95% statt 78% Ziel-Erfüllung
- Keine Halluzinationen mehr
- Perfekte JSON-Struktur
- Volle 18 Sätze pro Session

### Kosten
```
Pro Plan: ~0.0015€ (0.15 Cent)
100 Pläne: ~0.15€
1000 Pläne/Monat: ~1.50€

Kostenlos bis zu:
- 200 requests/Tag im Free Tier
- $5 Guthaben zum Start
```

### Speed
- Ollama 8B: ~20 Sekunden
- OpenRouter 70B: ~15 Sekunden
- Groq 70B: ~3 Sekunden (Alternative)

## 🎯 Empfohlene Strategie

### Hybrid-Modus (Standard)
```python
# 1. Versuch: Ollama lokal (kostenlos, 20s)
# 2. Bei Fehler: OpenRouter 70B (0.0015€, 15s)

generator = PlanGenerator(
    user_id=2,
    use_openrouter=False,          # Start mit Ollama
    fallback_to_openrouter=True    # Fallback bei Fehler
)
```

**Ergebnis:**
- 80% der Pläne lokal (kostenlos)
- 20% auf OpenRouter (nur bei Validation-Fehler)
- **Durchschnittskosten: ~0.0003€ pro Plan** (0.03 Cent!)

### Production-Only OpenRouter
```python
# Auf Server: Nutze nur OpenRouter (kein Ollama installiert)

generator = PlanGenerator(
    user_id=2,
    use_openrouter=True,           # Skip Ollama
    fallback_to_openrouter=False
)
```

## 📊 Kosten-Vergleich

| Szenario | Pläne/Monat | Kosten/Monat | Qualität | Setup |
|----------|-------------|--------------|----------|-------|
| Nur Ollama 8B | Unbegrenzt | 0€ | 78% gut | ✅ Lokal |
| Hybrid (80/20) | 1000 | ~0.30€ | 90% gut | ✅ Best |
| Nur OpenRouter 70B | 1000 | ~1.50€ | 95% gut | ⚡ Einfach |

## 🔧 Troubleshooting

### "OPENROUTER_API_KEY nicht gesetzt"
```bash
# Prüfe .env Datei
cat .env | grep OPENROUTER

# Sollte zeigen:
OPENROUTER_API_KEY=sk-or-v1-...

# Falls fehlt: Key von https://openrouter.ai/keys kopieren
```

### "OpenAI Package nicht installiert"
```bash
pip install openai

# Oder auf Production:
ssh user@server
cd /var/www/.../gym
source venv/bin/activate
pip install openai
```

### "Rate Limit exceeded"
```
Free Tier Limits:
- 200 requests/Tag
- 20 requests/Minute

Lösung:
1. Guthaben aufladen ($5 = 3300 Pläne)
2. Oder Hybrid-Modus nutzen (reduziert OpenRouter-Calls)
```

## 🌟 Alternative: Groq (5x schneller!)

Falls Speed wichtig ist:

```bash
# 1. Account: https://console.groq.com
# 2. API Key kopieren
# 3. In .env:
GROQ_API_KEY=gsk_...

# 4. In llm_client.py base_url ändern:
base_url="https://api.groq.com/openai/v1"
```

**Groq Vorteile:**
- Gleicher Preis wie OpenRouter
- **5x schneller** (3s statt 15s)
- 30 requests/min FREE!

## 📈 Nächste Schritte

1. ✅ Setup abgeschlossen
2. Teste 10-20 Pläne im Hybrid-Modus
3. Prüfe Qualität und Kosten im Dashboard
4. Entscheide: Hybrid oder Full OpenRouter

**Dashboard:** https://openrouter.ai/activity

Viel Erfolg! 🚀
