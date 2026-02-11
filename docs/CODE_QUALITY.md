# 🎨 Code Quality & Formatting Guide

## Übersicht

HomeGym nutzt ein automatisiertes Code-Quality-System:
- **Black** - Code Formatter
- **isort** - Import Sorter
- **flake8** - Linter
- **mypy** - Type Checker
- **pre-commit** - Git Hooks

## Quick Start

```bash
# Code formatieren (automatisch)
black core/ config/

# Imports sortieren
isort core/ config/

# Linting prüfen
flake8 core/ config/

# Type-Checking
mypy core/ config/

# Alle Checks auf einmal (wie Git Hook)
pre-commit run --all-files
```

## Black - Code Formatter

**Automatisch angewendet beim Git Commit!**

### Manuell ausführen:

```bash
# Gesamtes Projekt
black .

# Nur core/
black core/

# Nur checken, ohne zu ändern
black --check core/
```

### Konfiguration

Siehe `pyproject.toml`:
- **Line Length:** 100 Zeichen
- **Target:** Python 3.12
- **Excludes:** migrations, venv, staticfiles

### Black Regeln

```python
# ✅ RICHTIG (nach Black)
def my_function(arg1: str, arg2: int) -> bool:
    return True

# ❌ FALSCH (wird formatiert)
def my_function(arg1:str,arg2:int)->bool:
    return True
```

## isort - Import Sorter

**Sortiert Imports automatisch!**

### Sections (Reihenfolge):

1. **FUTURE** - `from __future__ import ...`
2. **STDLIB** - Python Standard Library
3. **DJANGO** - Django Framework
4. **THIRDPARTY** - Externe Packages
5. **FIRSTPARTY** - Eigener Code (core, ai_coach, config)
6. **LOCALFOLDER** - Relative Imports

### Beispiel:

```python
# ✅ RICHTIG (nach isort)
from datetime import datetime  # STDLIB

from django.db import models  # DJANGO

import pytest  # THIRDPARTY
from faker import Faker

from core.models import Uebung  # FIRSTPARTY
from ai_coach.llm_client import LLMClient

from .helpers import calculate_1rm  # LOCALFOLDER


# ❌ FALSCH (durcheinander)
from .helpers import calculate_1rm
import pytest
from django.db import models
from core.models import Uebung
from datetime import datetime
```

### Manuell ausführen:

```bash
# Gesamtes Projekt
isort .

# Nur core/
isort core/

# Nur checken
isort --check core/
```

## flake8 - Linter

**Findet Code-Smells und Style-Violations!**

### Konfiguration

Siehe `.flake8`:
- **Max Line Length:** 100
- **Max Complexity:** 15
- **Ignored Errors:** E203, E501, W503 (Black-kompatibel)

### Manuell ausführen:

```bash
# Gesamtes Projekt mit Stats
flake8 core/ config/ --count --statistics

# Nur eine Datei
flake8 core/models.py

# Mit Source-Code-Anzeige
flake8 core/ --show-source
```

### Häufige Errors:

| Code | Bedeutung | Fix |
|------|-----------|-----|
| **F401** | Unused import | Import entfernen oder mit `# noqa: F401` markieren |
| **F841** | Unused variable | Variable nutzen oder `_` prefix |
| **E722** | Bare except | `except Exception:` statt `except:` |
| **N802** | Function name should be lowercase | `my_function` statt `myFunction` |
| **C901** | Too complex (>15) | Funktion aufteilen |

### Errors ignorieren:

```python
# Einzelne Zeile
from .models import *  # noqa: F403

# Gesamte Datei
# flake8: noqa

# Spezifischer Error
import something  # noqa: F401
```

## mypy - Type Checker

**Prüft Type Hints!**

### Konfiguration

Siehe `pyproject.toml`:
- **Python Version:** 3.12
- **Strict:** Teilweise (check_untyped_defs=True)
- **Ignored Packages:** factory, faker, qrcode, ollama, etc.

### Manuell ausführen:

```bash
# Gesamtes Projekt
mypy core/ config/

# Einzelne Datei
mypy core/models.py

# Nur checken, keine Errors
mypy --no-error-summary core/
```

### Type Hints Beispiele:

```python
# ✅ RICHTIG
def calculate_1rm(weight: Decimal, reps: int) -> Decimal:
    return weight * (Decimal('1') + Decimal(reps) / Decimal('30'))

# Type Hints für komplexere Types
from typing import List, Optional, Dict, Any

def get_trainings(user_id: int) -> List[Trainingseinheit]:
    return Trainingseinheit.objects.filter(user_id=user_id)

def get_user_stats(user: User) -> Optional[Dict[str, Any]]:
    if not user.is_authenticated:
        return None
    return {'total_volume': 1000, 'best_1rm': 150}


# ❌ FALSCH (keine Type Hints)
def calculate_1rm(weight, reps):
    return weight * (1 + reps/30)
```

### mypy Errors ignorieren:

```python
# Einzelne Zeile
result = some_function()  # type: ignore

# Mit Grund
result = legacy_code()  # type: ignore[no-untyped-call]
```

## Pre-commit Hooks

**Automatische Code-Quality-Checks beim Git Commit!**

### Installation

```bash
# Hooks installieren (einmalig)
pre-commit install

# Hooks deinstallieren
pre-commit uninstall
```

### Was passiert beim Commit?

1. **trailing-whitespace** - Entfernt Whitespace am Zeilenende
2. **end-of-file-fixer** - Fügt Newline am Dateiende hinzu
3. **check-yaml** - Prüft YAML-Syntax
4. **check-added-large-files** - Warnt bei Dateien >1MB
5. **debug-statements** - Findet vergessene `print()`, `debugger`
6. **black** - Formatiert Code
7. **isort** - Sortiert Imports
8. **flake8** - Prüft Code-Quality
9. **mypy** - Prüft Type Hints

### Manuell ausführen:

```bash
# Alle Hooks auf alle Dateien
pre-commit run --all-files

# Nur bestimmten Hook
pre-commit run black --all-files

# Nur auf geänderten Dateien
pre-commit run
```

### Hook temporär skippen:

```bash
# Commit ohne Hooks
git commit --no-verify -m "Emergency fix"

# ODER: Einzelne Dateien skippen (in .pre-commit-config.yaml)
# exclude: '^(migrations/|legacy_code\.py)'
```

## Workflow

### 1. Während der Entwicklung

```bash
# Code schreiben...

# Formatieren
black core/models.py
isort core/models.py

# Prüfen
flake8 core/models.py
mypy core/models.py
```

### 2. Vor dem Commit

```bash
# Alle Änderungen formatieren
black .
isort .

# Prüfen
flake8 core/ config/
pytest
```

### 3. Git Commit (automatisch!)

```bash
git add .
git commit -m "Add new feature"

# Pre-commit Hooks laufen automatisch!
# Falls Fehler: Dateien wurden geändert, erneut committen
```

## CI/CD Integration (Später)

```yaml
# .github/workflows/code-quality.yml
name: Code Quality

on: [push, pull_request]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install black isort flake8 mypy
      - run: black --check .
      - run: isort --check .
      - run: flake8 .
      - run: mypy core/ config/
```

## Troubleshooting

### Problem: Black und flake8 widersprechen sich

**Lösung:** Unsere `.flake8` ist bereits Black-kompatibel (E203, W503 ignoriert)

### Problem: Pre-commit Hook schlägt fehl

**Lösung:**
```bash
# Dateien wurden geändert - erneut stagen
git add .
git commit -m "Your message"

# Oder Hook-Output lesen und Fehler fixen
```

### Problem: mypy zu strikt

**Lösung:** Type Hints schrittweise hinzufügen:
```python
# Temporär ignorieren
# type: ignore

# Oder in pyproject.toml anpassen
# disallow_untyped_defs = false
```

### Problem: isort bricht Code

**Lösung:** Sehr selten! Falls doch:
```python
# isort: skip_file  # Am Anfang der Datei

# Oder einzelne Imports
import something  # isort: skip
```

## Best Practices

### ✅ DO

- Lass Black **ALLES** formatieren - diskutiere nicht über Style
- Nutze Type Hints bei neuen Funktionen
- Fixe flake8-Warnings sofort
- Pre-commit Hooks aktiv lassen
- Code Quality als Teil von "Done"

### ❌ DON'T

- Black-Formatierung nicht manuell rückgängig machen
- Type Hints nicht überall erzwingen (Legacy-Code OK)
- Pre-commit Hooks nicht dauerhaft --no-verify
- Code-Quality nicht "später" fixen
- Komplexität nicht über 15 steigen lassen

## IDE Integration

### VS Code

```json
// .vscode/settings.json
{
  "python.formatting.provider": "black",
  "python.formatting.blackArgs": ["--config", "pyproject.toml"],
  "python.sortImports.args": ["--profile", "black"],
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "python.linting.mypyEnabled": true,
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  }
}
```

### PyCharm

1. **Settings** → **Tools** → **Black**
2. **Settings** → **Tools** → **File Watchers** → Black
3. **Settings** → **Editor** → **Inspections** → flake8

## Summary

```bash
# Täglicher Workflow
black .           # Formatieren
isort .           # Imports sortieren
flake8 .          # Prüfen
pytest            # Testen
git commit        # Pre-commit läuft automatisch!
```

**Code Quality ist KEINE Option - es ist Standard!** 🎨
