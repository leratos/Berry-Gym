"""
Pytest Configuration und Shared Fixtures.

Diese Datei definiert Fixtures die in allen Tests verfügbar sind.
"""

from django.core.cache import cache

import pytest


@pytest.fixture
def user():
    """Standard User für Tests."""
    from core.tests.factories import UserFactory

    return UserFactory()


@pytest.fixture
def admin_user():
    """Admin User für Tests."""
    from core.tests.factories import UserFactory

    return UserFactory(is_staff=True, is_superuser=True)


@pytest.fixture
def uebung_bankdruecken():
    """Standard Bankdrücken Übung."""
    from core.tests.factories import UebungFactory

    return UebungFactory(
        bezeichnung="Bankdrücken",
        muskelgruppe="BRUST",
        bewegungstyp="DRUECKEN",
        gewichts_typ="GESAMT",
    )


@pytest.fixture
def uebung_kniebeugen():
    """Standard Kniebeugen Übung."""
    from core.tests.factories import UebungFactory

    return UebungFactory(
        bezeichnung="Kniebeugen",
        muskelgruppe="BEINE_QUAD",
        bewegungstyp="BEUGEN",
        gewichts_typ="GESAMT",
    )


@pytest.fixture
def training_session(user):
    """Standard Trainingseinheit für einen User."""
    from core.tests.factories import TrainingseinheitFactory

    return TrainingseinheitFactory(user=user)


@pytest.fixture
def koerperwerte(user):
    """Standard Körperwerte für einen User."""
    from core.tests.factories import KoerperWerteFactory

    return KoerperWerteFactory(user=user, groesse_cm=180, gewicht=80.0)


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """
    Aktiviert DB-Zugriff für alle Tests automatisch.
    Spart @pytest.mark.django_db Dekorator.
    """
    pass


@pytest.fixture(autouse=True)
def clear_cache_between_tests():
    """Cache vor und nach jedem Test leeren.

    Verhindert Cache-Pollution zwischen Tests: SQLite recycelt IDs nach
    DB-Rollback, sodass neue Test-Objekte dieselbe ID wie vorherige bekommen
    können – ohne dieses Fixture würden gecachte Werte vom Vorgänger-Test
    fälschlicherweise zurückgegeben.
    """
    cache.clear()
    yield
    cache.clear()
