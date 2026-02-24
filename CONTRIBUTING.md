# Contributing to HomeGym

Vielen Dank für dein Interesse an HomeGym! 🏋️

Wir freuen uns über Contributions aller Art - ob Bugfixes, neue Features, Dokumentation oder Übersetzungen.

## 🚀 Quick Start für Contributors

### 1. Repository forken & klonen

```bash
# Fork auf GitHub erstellen (Button oben rechts)

# Dein Fork klonen
git clone https://github.com/DEIN-USERNAME/Berry-Gym.git
cd Berry-Gym

# Upstream Remote hinzufügen
git remote add upstream https://github.com/leratos/Berry-Gym.git
```

### 2. Development Environment setup

```bash
# Virtual Environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Dependencies installieren
pip install -r requirements.txt

# .env erstellen
cp .env.example .env

# Datenbank setup
python manage.py migrate
python manage.py loaddata core/fixtures/initial_exercises.json
python manage.py createsuperuser

# Server starten
python manage.py runserver
```

### 3. Branch erstellen

```bash
# Immer von main abzweigen
git checkout main
git pull upstream main

# Feature Branch erstellen
git checkout -b feature/deine-neue-funktion
# oder
git checkout -b fix/bug-beschreibung
```

## 📝 Commit Conventions

Wir nutzen [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: Neue Funktion hinzufügen
fix: Bug beheben
docs: Dokumentation ändern
style: Code-Formatierung (keine Logic-Änderung)
refactor: Code umstrukturieren ohne Verhalten zu ändern
test: Tests hinzufügen oder ändern
chore: Build-Process, Dependencies, etc.
```

**Beispiele:**
```bash
git commit -m "feat: AI Coach live guidance während Training"
git commit -m "fix: 1RM Berechnung bei Körpergewichtsübungen"
git commit -m "docs: AI setup guide aktualisieren"
```

## 🎯 Contribution Bereiche

### 🐛 Bugs melden

1. **GitHub Issues** → "New Issue" → "Bug Report"
2. **Informationen:**
   - Beschreibung des Problems
   - Schritte zur Reproduktion
   - Erwartetes vs. tatsächliches Verhalten
   - Screenshots (falls hilfreich)
   - Python Version, OS, Browser

### ✨ Feature Requests

1. **GitHub Issues** → "New Issue" → "Feature Request"
2. **Informationen:**
   - Use Case: Warum ist dieses Feature nützlich?
   - Vorgeschlagene Implementierung (optional)
   - Mockups/Wireframes (optional)

### 💻 Code Contributions

**Gute erste Issues:**
- Issues mit Label `good first issue`
- Dokumentations-Verbesserungen
- Übersetzungen
- UI/UX Verbesserungen

**Workflow:**
1. Issue auswählen oder erstellen
2. Branch erstellen (`feature/...` oder `fix/...`)
3. Code schreiben + Tests
4. Commit mit Conventional Commit Message
5. Push zu deinem Fork
6. Pull Request öffnen

## 🧪 Testing

```bash
# Projektstandard: pytest
pytest

# Spezifischer Testlauf
pytest core/tests/test_training_views.py -v

# Mit Coverage (wie in CI)
pytest --cov=core --cov=ai_coach --cov-report=term-missing
```

**Test-Erwartungen:**
- Alle existierenden Tests müssen weiterhin laufen
- Neue Features sollten Tests haben
- Bugfixes sollten Regression-Tests haben

## 📚 Code Style

### Python
- **PEP 8** Konventionen
- **Type Hints** für Function Signatures
- **Docstrings** für komplexe Funktionen
- **Max Line Length:** 100 Zeichen

```python
from typing import List, Optional

def calculate_one_rm(gewicht: float, wiederholungen: int) -> float:
    """
    Berechnet 1RM nach Epley-Formel.
    
    Args:
        gewicht: Gewicht in kg
        wiederholungen: Anzahl Wiederholungen (1-10)
        
    Returns:
        Geschätztes 1RM in kg
    """
    return gewicht * (1 + wiederholungen / 30)
```

### Django
- **Class-based Views** für komplexe Logic
- **Function-based Views** für einfache Endpoints
- **Model Validators** für Business Logic
- **Signals** sparsam einsetzen

### JavaScript
- **ES6+** Features nutzen
- **Vanilla JS** (kein jQuery/Framework)
- **Async/Await** statt Callbacks
- **Template Literals** für HTML-Strings

```javascript
async function loadTrainingData(trainingId) {
    try {
        const response = await fetch(`/api/training/${trainingId}/`);
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Fehler beim Laden:', error);
        showErrorToast('Training konnte nicht geladen werden');
    }
}
```

### HTML/CSS
- **Bootstrap 5** Komponenten nutzen
- **Semantic HTML** (`<section>`, `<article>`, `<nav>`)
- **BEM Naming** für Custom CSS
- **Mobile First** Responsive Design

## 🔍 Pull Request Process

### 1. PR erstellen

**Titel:** Nutze Conventional Commit Format
```
feat: AI Coach live guidance
fix: 1RM calculation for bodyweight exercises
docs: update AI setup instructions
```

**Beschreibung:**
```markdown
## Beschreibung
Kurze Zusammenfassung der Änderungen

## Motivation
Warum ist diese Änderung nötig?

## Änderungen
- Liste der Änderungen
- Datei 1: Was wurde geändert
- Datei 2: Was wurde geändert

## Testing
- [ ] Manuell getestet
- [ ] Unit Tests hinzugefügt
- [ ] Existierende Tests laufen

## Screenshots (optional)
Vor/Nachher Bilder bei UI-Änderungen

## Closes
Closes #123 (Issue Nummer)
```

### 2. Review-Prozess

- Maintainer reviewen deinen Code
- Möglicherweise wird um Änderungen gebeten
- Diskussion über Design-Entscheidungen
- Nach Approval: Merge durch Maintainer

### 3. Nach dem Merge

- Branch löschen (lokal + remote)
- Upstream pullen für nächstes Feature

```bash
# Lokal aufräumen
git checkout main
git pull upstream main
git branch -d feature/deine-funktion

# Remote Branch löschen
git push origin --delete feature/deine-funktion
```

## 🏗️ Architektur-Guidelines

### Backend (Django)
- **Models:** Datenbank-Schema, keine Business Logic
- **Views:** Request-Handling, ruft Services auf
- **Services:** Business Logic (z.B. `ai_coach/`)
- **Serializers:** API Response Formatting

### Frontend
- **Templates:** Server-Side Rendering (Django Templates)
- **Static JS:** Progressive Enhancement, kein SPA
- **AJAX:** Nur für interaktive Features (AI Coach Chat)
- **PWA:** Service Worker für Offline-Support

### AI Coach
- **LLM Integration:** OpenRouter-basierte AI-Flows mit Kosten-/Rate-Limit-Tracking
- **Prompt Engineering:** `ai_coach/prompt_builder.py`
- **Cost Tracking:** Jeder LLM-Call logged Kosten
- **Caching:** Vermeidet redundante API-Calls

## 🌍 Internationalization (i18n)

Die App unterstützt Deutsch und Englisch (vollständig integriert). Weitere
Übersetzungen und Qualitätsverbesserungen sind willkommen.

**Vorschlag:**
1. Django i18n Framework nutzen
2. Sprachdateien in `locale/de/` und `locale/en/`
3. `{% trans %}` Tags in Templates
4. `gettext()` in Python Code

## 📖 Dokumentation

**Was dokumentieren:**
- Neue Features in README.md
- API Endpoints in Docstrings
- Komplexe Algorithmen (z.B. RPE-Analyse)
- Deployment-Änderungen in DEPLOYMENT.md

**Wo dokumentieren:**
- Code: Docstrings + Inline-Kommentare
- Features: README.md
- Roadmap: docs/PROJECT_ROADMAP.md
- AI Coach: AI_COACH_CONCEPT.md

## 🚫 Was wir NICHT akzeptieren

- Code ohne Tests (für kritische Features)
- Breaking Changes ohne Migration-Path
- Dependencies ohne Begründung
- Secrets oder API Keys im Code
- Unformatierter Code (PEP 8 Violations)

## 🙋 Fragen?

- **GitHub Discussions:** Für allgemeine Fragen
- **GitHub Issues:** Für konkrete Bugs/Features
- **Discord/Matrix:** (optional, falls Community-Server existiert)

## 📜 Code of Conduct

Wir erwarten respektvolles Verhalten:
- **Hilfsbereit** sein bei Fragen
- **Konstruktive** Kritik statt Flames
- **Geduldig** mit neuen Contributors
- **Inklusiv** gegenüber allen Skill-Levels

---

**Vielen Dank für deine Contribution! 💪**

Jede Zeile Code, jeder Bugfix, jede Dokumentations-Verbesserung macht HomeGym besser für alle.
