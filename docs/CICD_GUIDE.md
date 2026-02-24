# 🚀 CI/CD Pipeline Documentation

## Übersicht

HomeGym verwendet GitHub Actions für automatisierte Tests, Code Quality Checks und optionales Deployment.

## 📊 Pipeline Architektur

```
┌─────────────┐
│  Git Push   │
└──────┬──────┘
       │
       ├──────────────────┬──────────────────┬──────────────────┐
       │                  │                  │                  │
       ▼                  ▼                  ▼                  ▼
┌────────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐
│   Tests    │    │   Lint     │    │  Security  │    │   Deploy   │
│ + Coverage │    │  (Black,   │    │  (Safety,  │    │ (Manual)   │
│            │    │   isort,   │    │  Bandit)   │    │            │
│            │    │   flake8)  │    │            │    │            │
└────────────┘    └────────────┘    └────────────┘    └────────────┘
```

## 🔧 Workflows

### 1. CI Pipeline (`ci.yml`)

**Trigger:** Automatisch bei Push/PR
**Branches:**
- Push: `main`, `feature/**`, `hotfix/**`
- Pull Request: `main`

#### Jobs:

**a) Tests & Coverage**
- Läuft auf Ubuntu Latest
- Python 3.12
- Matrix Strategy (einfach erweiterbar)

**Steps:**
1. Code auschecken
2. Python Setup mit Pip Cache
3. Dependencies installieren
4. Migrations ausführen
5. Tests mit Coverage laufen lassen
6. Coverage zu Codecov uploaden
7. HTML Coverage Report als Artifact speichern

**Environment Variables:**
```yaml
DJANGO_SETTINGS_MODULE: config.settings
SECRET_KEY: Test-Key (wenn nicht als Secret gesetzt)
DEBUG: True
ALLOWED_HOSTS: localhost,127.0.0.1
```

**b) Code Quality Checks**
- Black Format Check
- isort Import Order Check
- flake8 Linting (hard fail)

**c) Security Scans**
- Safety: Dependency Vulnerability Scan
- Bandit: Python Security Linter

**Artifacts:**
- Coverage HTML Report (14 Tage)
- Bandit Security Report (14 Tage)

### 2. Deploy Pipeline (`deploy.yml`)

**Trigger:**
- automatisch via `workflow_run`, wenn die CI auf `main` erfolgreich war
- manuell via `workflow_dispatch`

**Input (manuell):** Environment `production`

**Steps:**
1. Code auschecken
2. Via SSH zum Server verbinden
3. Database Backup erstellen
4. Code pullen
5. Dependencies installieren
6. Migrations ausführen
7. Static files sammeln
8. Gunicorn + Nginx neustarten

**Benötigte Secrets:**
- SSH_HOST
- SSH_USERNAME
- SSH_PRIVATE_KEY
- PROJECT_PATH
- Optional: SSH_PORT

## 📈 Status Badges

Füge diese Badges zu deinem README.md hinzu:

```markdown
# HomeGym

![CI/CD Pipeline](https://github.com/USERNAME/REPO/actions/workflows/ci.yml/badge.svg)
![Tests](https://img.shields.io/badge/tests-passing-brightgreen)
![Coverage](https://codecov.io/gh/USERNAME/REPO/branch/main/graph/badge.svg)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Django](https://img.shields.io/badge/django-5.0-green)
```

**Ersetze:**
- `USERNAME` mit deinem GitHub Username
- `REPO` mit dem Repository Namen

## 🔐 Secrets Management

### Minimal Setup (keine Secrets nötig):
CI läuft mit Test-Defaults für:
- SECRET_KEY (test key)
- Database (SQLite in memory)

### Mit Coverage Reporting:
```
CODECOV_TOKEN=your-token-from-codecov.io
```

### Mit Auto-Deploy:
```
SSH_HOST=123.45.67.89
SSH_USERNAME=appuser
SSH_PRIVATE_KEY=-----BEGIN RSA PRIVATE KEY-----...
PROJECT_PATH=/var/www/homegym
SSH_PORT=22 (optional)
```

## 🚦 Quality Gates

### Tests Job:
- ✅ MUSS erfolgreich sein
- ❌ Schlägt fehl bei Test-Errors
- ⚠️ Coverage Upload optional (fail_ci_if_error: false)

### Lint Job:
- ✅ Black/isort Check MUSS passen
- ✅ flake8 MUSS passen (kein `--exit-zero`)

### Security Job:
- ⚠️ Safety läuft als Hinweis (`continue-on-error: true`)
- ✅ Bandit ist blockierend bei Medium+ Severity (`-ll`)
- 📊 Bandit-Report als Artifact

## 📊 Monitoring & Reports

### Wo finde ich was?

**Test Results:**
```
GitHub → Actions → CI/CD Pipeline → Job "Tests & Coverage"
```

**Coverage Report:**
```
GitHub → Actions → Workflow → Artifacts → coverage-report
(Download & entpacken → htmlcov/index.html öffnen)
```

**Security Reports:**
```
GitHub → Actions → Workflow → Artifacts → bandit-security-report
```

**Codecov Dashboard:**
```
https://codecov.io/gh/USERNAME/REPO
```

## 🐛 Troubleshooting

### Tests schlagen fehl

**Symptom:** "Tests & Coverage" Job rot
**Debug:**
1. Actions → Failed Job → Logs erweitern
2. Scrolle zu "Run tests with coverage"
3. Lies den Error

**Häufige Ursachen:**
```python
# Import Error
→ Check requirements.txt

# Migration Error
→ Committen: python manage.py makemigrations

# Test Failure
→ Lokal fixen: pytest

# Environment Variable fehlt
→ Secret in GitHub setzen
```

### Black/isort Check schlägt fehl

**Symptom:** "Code Quality" Job rot
**Fix:**
```bash
# Lokal formatieren
black core/ config/ ai_coach/
isort core/ config/ ai_coach/

# Committen
git add .
git commit -m "Format code"
git push
```

### Deploy schlägt fehl

**Symptom:** "Deploy to Production" Job rot
**Debug:**
1. Check SSH Secrets (korrekt gesetzt?)
2. Teste SSH Connection manuell:
```bash
ssh -i ~/.ssh/key user@host "cd /path && ls"
```

3. Check Logs auf Server:
```bash
tail -f /var/log/gunicorn/error.log
tail -f /var/log/nginx/error.log
```

### Coverage Upload schlägt fehl

**Symptom:** Warning bei Codecov Upload
**Grund:** CODECOV_TOKEN nicht gesetzt
**Fix:** Entweder Secret setzen ODER ignorieren (fail_ci_if_error: false)

## 🔄 Workflow Customization

### Matrix Testing erweitern

```yaml
strategy:
  matrix:
    python-version: ['3.11', '3.12']
    django-version: ['4.2', '5.0']
```

### Mehr Branches überwachen

```yaml
on:
  push:
      branches: [ main, feature/**, hotfix/** ]
```

### Slack Notifications hinzufügen

```yaml
- name: Notify Slack
  if: failure()
  uses: 8398a7/action-slack@v3
  with:
    status: ${{ job.status }}
    webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

### Caching optimieren

```yaml
- name: Cache pip packages
  uses: actions/cache@v3
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
```

## 📝 Best Practices

### DO ✅

1. **Committen vor Push testen:**
```bash
pytest
black --check core/
isort --check core/
```

2. **Kleine, fokussierte Commits:**
```bash
git commit -m "Add user authentication tests"
# Besser als:
git commit -m "Update stuff"
```

3. **Branch Protection Rules:**
- Require Status Checks (CI muss grün sein)
- Require Reviews vor Merge
- Require up-to-date branches

4. **Secrets niemals committen:**
```bash
# .gitignore:
.env
*.key
secrets.yml
```

5. **Artifacts für Debugging nutzen:**
- Coverage Reports runterladen
- Security Reports checken
- Bei Failures Logs speichern

### DON'T ❌

1. **Nicht Production-Secrets in GitHub:**
```
❌ SSH_PRIVATE_KEY für Production Server
✅ Nur für Deployment-User mit minimalen Rechten
```

2. **Nicht flake8/mypy ohne exit-zero:**
```yaml
❌ flake8 core/ --exit-zero  # Versteckt echte Probleme
✅ flake8 core/  # Build bricht bei Lint-Fehlern bewusst ab
```

3. **Nicht Auto-Deploy ohne Tests:**
```yaml
❌ on: push: → deploy  # GEFÄHRLICH!
✅ on: workflow_run (CI success) + workflow_dispatch
```

4. **Nicht zu viele Matrix-Kombinationen:**
```yaml
❌ python: [3.9, 3.10, 3.11, 3.12] × django: [3.2, 4.0, 4.1, 4.2, 5.0]
   = 20 Jobs!
✅ python: [3.12] × django: [5.0]
   = 1 Job (erweitern bei Bedarf)
```

## 🚀 Deployment Workflow

### Manuelles Deployment (sicher):

1. **GitHub → Actions**
2. **Deploy to Production → Run workflow**
3. **Environment: production**
4. **Run workflow Button**
5. **Warten (Status checken)**
6. **Bei Erfolg: Website testen**

### Deployment Checklist:

**VOR Deployment:**
- [ ] Tests laufen lokal: `pytest`
- [ ] Migrations erstellt: `python manage.py makemigrations --check`
- [ ] Code formatiert: `black . && isort .`
- [ ] Backup vorhanden
- [ ] Maintenance Mode aktiviert (optional)

**NACH Deployment:**
- [ ] Website erreichbar
- [ ] Login funktioniert
- [ ] Critical Features testen
- [ ] Error Logs checken
- [ ] Sentry Errors checken
- [ ] Maintenance Mode deaktiviert

## 📊 Metriken & KPIs

### Was tracken?

**Build Metriken:**
- ✅ Build Success Rate (Ziel: >95%)
- ⏱️ Build Duration (Ziel: <5 Min)
- 📈 Test Coverage (Ziel: >80%)

**Quality Metriken:**
- 🐛 Flake8 Violations (Ziel: <50)
- 🔒 Security Issues (Ziel: 0 Critical)
- 📝 Code Smells (Ziel: minimize)

**Deployment Metriken:**
- 🚀 Deploy Frequency (wie oft?)
- ⏱️ Lead Time (Commit → Production)
- 🔴 Rollback Rate (Ziel: <5%)
- ⏰ Mean Time to Recovery (MTTR)

### Wo sehe ich das?

**GitHub Actions:**
```
Repository → Insights → Actions
```

**Codecov:**
```
codecov.io/gh/USERNAME/REPO → Trends
```

**Sentry:**
```
sentry.io → Issues Dashboard
```

## 🎯 Next Steps

### Phase 2: Erweiterte CI/CD

1. **Container Support:**
   - Docker Build & Push
   - Docker Compose Tests
   - Container Registry

2. **E2E Tests:**
   - Playwright/Selenium
   - Visual Regression Tests
   - Performance Tests

3. **Advanced Deployment:**
   - Blue-Green Deployment
   - Canary Releases
   - Rollback Automation

4. **Monitoring Integration:**
   - Deployment Notifications
   - Performance Tracking
   - Error Rate Monitoring

## 📞 Support

**Probleme mit CI/CD?**
1. Check GitHub Actions Logs
2. Check Dokumentation: docs/GITHUB_SECRETS_SETUP.md
3. Lokal testen: pytest, black, flake8
4. Google den Error
5. GitHub Issues durchsuchen

**Deploy Probleme?**
1. Check SSH Connection
2. Check Server Logs
3. Check Gunicorn/Nginx Status
4. Rollback wenn nötig

## ✅ Summary

**Was läuft automatisch:**
- ✅ Tests bei jedem Push/PR
- ✅ Code Quality Checks
- ✅ Security Scans
- ✅ Coverage Reporting

**Was ist manuell:**
- 🎯 Deployment (nur per Button)
- 🎯 Environment Rollbacks
- 🎯 Database Migrations (in Deploy)

**Keine Secrets nötig für:**
- Tests
- Linting
- Security Scans

**Secrets nur für:**
- Coverage Badge (optional)
- Auto-Deploy (optional)
