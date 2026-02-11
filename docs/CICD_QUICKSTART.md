# 🚀 CI/CD Quick Start

## Setup in 3 Schritten

### 1. Code zu GitHub pushen
```bash
git add .
git commit -m "Add CI/CD pipeline"
git push origin NewStruc
```

### 2. Erste Pipeline ansehen
1. GitHub → Repository → **Actions**
2. "CI/CD Pipeline" Workflow anklicken
3. Warten bis grün ✅

### 3. Badges zu README hinzufügen
```markdown
![CI/CD](https://github.com/USERNAME/REPO/actions/workflows/ci.yml/badge.svg)
![Tests](https://img.shields.io/badge/tests-passing-brightgreen)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Django](https://img.shields.io/badge/django-5.0-green)
```

**USERNAME und REPO ersetzen!**

## Was läuft automatisch?

✅ **Tests** - Bei jedem Push/PR
✅ **Code Quality** - Black, isort, flake8
✅ **Security Scan** - Safety, Bandit
✅ **Coverage Report** - Als Artifact

## Kein Setup nötig!

Pipeline läuft **sofort** nach Push - keine Secrets nötig!

## Optional: Codecov Badge

1. Gehe zu https://codecov.io
2. Login mit GitHub
3. Aktiviere dein Repo
4. Kopiere Token
5. GitHub → Settings → Secrets → **New secret**
   - Name: `CODECOV_TOKEN`
   - Value: [dein Token]

**Badge:**
```markdown
[![codecov](https://codecov.io/gh/USERNAME/REPO/branch/main/graph/badge.svg)](https://codecov.io/gh/USERNAME/REPO)
```

## Troubleshooting

### Pipeline ist rot 🔴

**Tests failed:**
```bash
# Lokal testen
pytest
```

**Black/isort failed:**
```bash
# Formatieren
black . && isort .
git add . && git commit -m "Format code"
```

### Wo sind die Logs?

```
GitHub → Actions → Failed Workflow → Job anklicken → Logs lesen
```

### Coverage Report runterladen

```
GitHub → Actions → Workflow → Artifacts → coverage-report-3.12
```

## Deploy (Optional - NUR manuell)

1. **Secrets setzen** (siehe docs/GITHUB_SECRETS_SETUP.md)
2. **GitHub → Actions → Deploy to Production**
3. **Run workflow**
4. **Environment wählen**
5. **Confirm**

⚠️ **WICHTIG:** Deploy ist optional! Du kannst weiter manuell deployen.

## Full Documentation

- **Komplette Anleitung:** docs/CICD_GUIDE.md
- **Secrets Setup:** docs/GITHUB_SECRETS_SETUP.md
- **Workflow Files:** .github/workflows/

## Status

✅ CI läuft automatisch
✅ Keine Secrets nötig
✅ Tests + Quality Checks
⚙️ Deploy optional (manuell)

**Ready to push!** 🚀
