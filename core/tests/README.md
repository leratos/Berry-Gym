# 🧪 HomeGym Test Suite

## 🎯 Quick Start

```bash
# Alle Tests laufen lassen
pytest

# Mit Coverage Report
pytest --cov=core --cov-report=html

# Spezifische Test-Datei
pytest core/tests/test_plan.py -v

# Mit detailliertem Output
pytest -vv --tb=short
```

## 📊 Coverage Status (Stand: 10.02.2026)

**Gesamtcoverage: 20%** (66/68 Tests passing)

### 🏆 High Coverage Modules:
- **body_tracking.py:** 92% ✨
- **models.py:** 75%
- **training_session.py:** 41%
- **plan_management.py:** 36%

### 📁 Test Struktur

```
core/tests/
├── conftest.py                  # Shared fixtures
├── factories.py                 # Factory Boy factories (97% coverage)
│
├── test_models.py              # Model tests (TODO)
├── test_plan.py                # Plan & PlanUebung CRUD (13 tests) ✅
├── test_training_views.py      # Training session workflow (18 tests) ✅
├── test_body_tracking.py       # Body stats & photos (17 tests) ✅
├── test_plan_management.py     # Plan management (16 tests) ✅
└── test_integration.py         # E2E workflows (4 tests, 2 passing) 🔄
```

## 📈 Coverage Roadmap

### ✅ Phase 2.2 - Basic Views (COMPLETE)
**Target:** 14% → 19% (+5%)  
**Achieved:** 14% → 19%

**Tests Added:**
- test_plan.py: 13 tests (Plan CRUD, sharing, equipment)
- test_training_views.py: 18 tests (training sessions, sets)
- test_body_tracking.py: 17 tests (body tracking, photos)

**Coverage Gains:**
- body_tracking.py: 21% → 92% (+71%) 🚀🚀🚀
- training_session.py: 8% → 41% (+33%) 🚀
- models.py: 70% → 81% (+11%)

### ✅ Phase 2.3 - Plan Management (COMPLETE)
**Target:** 19% → 22% (+3%)  
**Achieved:** 19% → 21% (+2%)

**Tests Added:**
- test_plan_management.py: 16 tests

**Coverage Gains:**
- plan_management.py: 12% → 36% (+24%) 🚀

### 🔄 Phase 2.4 - Integration Tests (IN PROGRESS)
**Target:** 21% → 25% (+4%)  
**Status:** 20% (2/4 tests passing)

**Tests Added:**
- test_integration.py: 4 E2E workflow tests
  * ✅ Plan Sharing Workflow
  * ✅ Equipment-Based Planning
  * ⏸️ Complete Training Cycle (2 skipped)

**Next Steps:**
- Fix 2 skipped integration tests
- Add more E2E scenarios
- Target 25%+ coverage

### 🔜 Phase 2.5 - Export & Auth Tests
**Target:** 25% → 30% (+5%)

**Planned:**
- export.py: 10% → 30% (~10 tests)
- auth.py: 14% → 35% (~8 tests)
- exercise_library.py: 13% → 30% (~12 tests)

### 🔜 Phase 3 - Code Quality (Week 3-4)
**Target:** Refactoring, type hints, complexity reduction

### 🔜 Phase 4 - Performance (Week 5-6)
**Target:** Query optimization, N+1 elimination

## 🏃 Test Examples

### Running Specific Test Classes
```bash
# Alle Plan Tests
pytest core/tests/test_plan.py -v

# Nur Body Tracking Tests
pytest core/tests/test_body_tracking.py::TestAddKoerperwert -v

# Integration Tests
pytest core/tests/test_integration.py -v
```

### Coverage für spezifisches Modul
```bash
# Nur body_tracking.py Coverage
pytest --cov=core.views.body_tracking --cov-report=term-missing

# Plan management Coverage
pytest --cov=core.views.plan_management --cov-report=html
```

## 🔧 Fixtures & Factories

### Available Factories
- `UserFactory` - User mit Profil
- `UebungFactory` - Übung mit Equipment
- `PlanFactory` - Trainingsplan
- `PlanUebungFactory` - Plan↔Übung Verknüpfung
- `TrainingseinheitFactory` - Training Session
- `SatzFactory` - Satz mit Gewicht/Wdh
- `KoerperWerteFactory` - Körperwerte
- `EquipmentFactory` - Equipment

### Fixture Usage
```python
@pytest.mark.django_db
def test_example(client):
    user = UserFactory()
    client.force_login(user)
    
    plan = PlanFactory(user=user)
    response = client.get(reverse("plan_detail", args=[plan.id]))
    
    assert response.status_code == 200
```

## 📝 Test Conventions

### Naming
- Test files: `test_*.py`
- Test classes: `TestXxx`
- Test methods: `test_xxx`

### Structure
```python
def test_description(self, client):
    """Test: What this test verifies."""
    # STEP 1: Setup
    user = UserFactory()
    
    # STEP 2: Action
    response = client.post(url, data=data)
    
    # STEP 3: Assert
    assert response.status_code == 200
```

## 🐛 Known Issues

### Skipped Tests
- `test_full_training_cycle` - URL pattern missing
- `test_body_tracking_with_training_progress` - Aggregate issue

### Bugs Found (Not Fixed)
1. `body_tracking.py:97` - Empty string → NULL IntegrityError
2. Field name inconsistency: `groesse` vs `groesse_cm`
3. `share_plan` - Missing `@login_required` decorator

## 🎯 Next Session Tasks

1. **Fix skipped integration tests** (30 min)
2. **Add export.py tests** (45 min)
3. **Add auth.py tests** (45 min)
4. **Target: 25-30% coverage**

## 💡 Tips

- Always use factories instead of manual model creation
- Use `client.force_login(user)` for authenticated tests
- Check both success (200/302) and failure (404/403) cases
- Test user isolation (can't access other users' data)
- Use descriptive test names and docstrings

## 📚 Resources

- [Django Testing Docs](https://docs.djangoproject.com/en/5.0/topics/testing/)
- [pytest-django](https://pytest-django.readthedocs.io/)
- [Factory Boy](https://factoryboy.readthedocs.io/)
