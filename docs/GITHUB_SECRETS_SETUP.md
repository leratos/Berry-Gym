# 🔐 GitHub Secrets Setup Guide

## Required Secrets für CI/CD

Nach dem Push musst du diese Secrets in GitHub einstellen:
**Settings → Secrets and variables → Actions → New repository secret**

### Für Tests (Optional, aber empfohlen):

| Secret Name | Description | Example |
|------------|-------------|---------|
| `SECRET_KEY` | Django Secret Key für Tests | `django-insecure-test-key-12345` |
| `CODECOV_TOKEN` | Codecov.io Token für Coverage Reports | `abcd1234-...` |

**Hinweis:** Falls `SECRET_KEY` nicht gesetzt ist, verwendet CI einen Test-Key (nicht sicher, nur für CI!).

### Für Deployment (Nur wenn du Auto-Deploy willst):

| Secret Name | Description | Example |
|------------|-------------|---------|
| `SSH_HOST` | Server IP oder Domain | `123.45.67.89` oder `example.com` |
| `SSH_USERNAME` | SSH Username | `root` oder `appuser` |
| `SSH_PRIVATE_KEY` | SSH Private Key (kompletter Key!) | `-----BEGIN RSA PRIVATE KEY-----...` |
| `SSH_PORT` | SSH Port (optional) | `22` (default) |
| `PROJECT_PATH` | Projektpfad auf Server | `/var/www/homegym` |

## 📊 Codecov Setup (Optional - für schöne Coverage Badges)

1. Geh zu https://codecov.io
2. Login mit GitHub
3. Aktiviere dein Repository
4. Kopiere den Token
5. Füge ihn als `CODECOV_TOKEN` Secret hinzu

**Badge für README:**
```markdown
[![codecov](https://codecov.io/gh/USERNAME/REPO/branch/main/graph/badge.svg)](https://codecov.io/gh/USERNAME/REPO)
```

## 🚀 Workflow Trigger

### CI Pipeline (`ci.yml`):
Läuft automatisch bei:
- Push zu: `main`, `NewStruc`, `develop`
- Pull Requests zu: `main`, `develop`

**Was läuft:**
- ✅ Tests mit Coverage
- ✅ Code Quality Checks (Black, isort, flake8)
- ✅ Security Scans (Safety, Bandit)

### Deploy Pipeline (`deploy.yml`):
**NUR MANUELL** triggerbar:
1. GitHub → Actions → Deploy to Production
2. "Run workflow" klicken
3. Environment wählen (production/staging)
4. Confirm

**⚠️ WICHTIG:** Deploy-Workflow ist optional! Du musst die SSH Secrets NICHT setzen, wenn du manuell deployst.

## 🛡️ Security Best Practices

### SSH Key generieren:
```bash
# Auf deinem lokalen PC:
ssh-keygen -t rsa -b 4096 -C "github-actions-deploy"
# Speichern als: ~/.ssh/github_actions_deploy

# Public Key auf Server:
cat ~/.ssh/github_actions_deploy.pub
# Inhalt zu ~/.ssh/authorized_keys auf Server hinzufügen

# Private Key als Secret:
cat ~/.ssh/github_actions_deploy
# Kompletten Inhalt (inkl. BEGIN/END) als SSH_PRIVATE_KEY Secret speichern
```

### Django SECRET_KEY für Production:
```python
# NIEMALS den Production-Key in GitHub Secrets!
# Production-Key sollte nur auf dem Server in .env sein
# Der CI-Key ist nur für Tests!
```

## ✅ Secrets Checklist

### Minimal (nur CI Tests):
- [ ] Keine Secrets nötig! CI läuft mit Test-Defaults

### Mit Coverage Reporting:
- [ ] `CODECOV_TOKEN` (von codecov.io)

### Mit Auto-Deploy:
- [ ] `SSH_HOST`
- [ ] `SSH_USERNAME`
- [ ] `SSH_PRIVATE_KEY`
- [ ] `PROJECT_PATH`
- [ ] Optional: `SSH_PORT`

## 🚦 Nach dem Setup

### Check CI Status:
1. Push Code zu GitHub
2. Geh zu: Repository → Actions
3. Schau dass "CI/CD Pipeline" läuft
4. Grüner Haken = Alles OK ✅

### Debug bei Fehlern:
1. Actions → Failed Workflow anklicken
2. Job anklicken → Logs lesen
3. Häufige Probleme:
   - Missing dependencies in requirements.txt
   - Migration errors
   - Test failures
   - Secret nicht gesetzt

## 📝 Environment Setup (Optional)

Für bessere Kontrolle kannst du Environments erstellen:
**Settings → Environments → New environment**

### Production Environment:
- Name: `production`
- Protection rules:
  - ✅ Required reviewers (du selbst)
  - ✅ Wait timer (z.B. 5 Minuten)
- Secrets: SSH credentials

### Staging Environment:
- Name: `staging`
- Keine Protection rules
- Andere SSH credentials

## ⚠️ Wichtige Hinweise

1. **Deploy-Workflow ist OPTIONAL**
   - Du kannst weiterhin manuell deployen
   - SSH Secrets nur wenn du Auto-Deploy willst

2. **Test-Secrets sind OPTIONAL**
   - CI läuft auch ohne `SECRET_KEY`
   - Codecov ist nice-to-have, aber nicht nötig

3. **Minimale CI funktioniert out-of-the-box**
   - Tests laufen
   - Code Quality wird geprüft
   - Keine Secrets nötig!

## 🎯 Empfohlenes Setup für den Anfang

**START EINFACH:**
```
✅ CI läuft ohne Secrets (Tests + Quality Checks)
❌ Codecov (später, wenn du Badges willst)
❌ Auto-Deploy (weiter manuell deployen)
```

**SPÄTER UPGRADEN:**
```
✅ Codecov Token hinzufügen (schöne Coverage Badges)
✅ SSH Secrets hinzufügen (Auto-Deploy)
```

## 🐛 Troubleshooting

### "Tests failed":
```bash
# Lokal testen ob Tests laufen:
pytest
```

### "Black/isort check failed":
```bash
# Lokal formatieren:
black core/ config/ ai_coach/
isort core/ config/ ai_coach/
git add .
git commit -m "Format code"
```

### "Migrations failed":
```bash
# Migrations committen:
python manage.py makemigrations
git add .
git commit -m "Add migrations"
```

## 📞 Support

Bei Problemen:
1. GitHub Actions Logs checken
2. Lokale Tests/Checks ausführen
3. Google den Error
4. GitHub Issues durchsuchen
