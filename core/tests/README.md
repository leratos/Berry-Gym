# 🧪 HomeGym Test Suite

## Quick Start

```bash
# Tests installieren
pip install -r requirements.txt

# Alle Tests laufen lassen
pytest

# Mit Coverage Report
pytest --cov --cov-report=html

# Nur schnelle Tests
pytest -m "not slow"

# Nur Unit Tests
pytest -m unit

# Verbose Output
pytest -v
```

## Struktur

```
core/tests/
├── __init__.py          # Package marker
├── conftest.py          # Shared fixtures
├── factories.py         # Factory Boy factories
├── test_models.py       # Model unit tests
├── test_views.py        # View integration tests (TODO)
└── test_utils.py        # Utility function tests (TODO)
```

## Test Markers

- `@pytest.mark.unit` - Unit Tests (schnell, isoliert)
- `@pytest.mark.integration` - Integration Tests (DB, API)
- `@pytest.mark.slow` - Langsame Tests (ML, LLM)
- `@pytest.mark.requires_ollama` - Benötigt Ollama Server

## Coverage Ziele

- **Phase 1 (Woche 1):** 30%+ Coverage
- **Phase 2 (Woche 4):** 60%+ Coverage
- **Phase 3 (Woche 8):** 80%+ Coverage

## Aktuelle Coverage

```bash
# HTML Report anzeigen
pytest --cov --cov-report=html
# Öffne: htmlcov/index.html
```

## Factories verwenden

```python
from core.tests.factories import UserFactory, TrainingseinheitFactory

def test_my_feature():
    user = UserFactory()
    training = TrainingseinheitFactory(user=user)
    assert training.user == user
```

## Best Practices

1. **Arrange-Act-Assert Pattern**
   ```python
   def test_something():
       # Arrange
       user = UserFactory()
       
       # Act
       result = user.do_something()
       
       # Assert
       assert result is True
   ```

2. **Descriptive Test Names**
   ```python
   def test_user_can_create_custom_exercise()  # ✅ Good
   def test_create()  # ❌ Bad
   ```

3. **One Assert per Test** (wenn möglich)

4. **Use Fixtures for Setup**
   ```python
   @pytest.fixture
   def prepared_training(user):
       return TrainingseinheitFactory(user=user, dauer_minuten=60)
   ```

## Troubleshooting

**Problem:** `ImportError: No module named core`
```bash
# Lösung: DJANGO_SETTINGS_MODULE setzen
export DJANGO_SETTINGS_MODULE=config.settings
```

**Problem:** Tests finden keine DB
```bash
# Lösung: pytest.ini prüfen
[pytest]
DJANGO_SETTINGS_MODULE = config.settings
```

**Problem:** Langsame Tests
```bash
# Lösung: Nur schnelle Tests
pytest -m "not slow"
```
