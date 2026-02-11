# 🎨 Code Quality - Quick Reference

## Täglicher Workflow

```bash
# Windows
format.bat

# Git Commit (pre-commit hooks laufen automatisch)
git add .
git commit -m "Your message"
```

## Manuelle Commands

```bash
# Code formatieren
black core/ config/

# Imports sortieren
isort core/ config/

# Linting
flake8 core/ config/

# Type Checking
mypy core/ config/

# Alle Pre-commit Hooks
pre-commit run --all-files
```

## Konfiguration

- **Black:** `pyproject.toml`
- **isort:** `pyproject.toml`
- **flake8:** `.flake8`
- **mypy:** `pyproject.toml`
- **pre-commit:** `.pre-commit-config.yaml`

## Standards

- **Line Length:** 100 Zeichen
- **Python Version:** 3.12
- **Max Complexity:** 15
- **Import Order:** stdlib → django → thirdparty → firstparty → local

## Dokumentation

Siehe `docs/CODE_QUALITY.md` für Details.
