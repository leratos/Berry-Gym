"""
Tests für Phase 4.3 – Caching Strategy.

Testet:
- _load_templates(): Cache-Hit nach erstem Aufruf (kein File-I/O mehr)
- Dashboard: Cache wird befüllt beim ersten Request
- Dashboard: Cache wird invalidiert wenn User ein Training speichert
- Cache-Key-Isolation: User A sieht nicht den Cache von User B
"""

from django.core.cache import cache
from django.urls import reverse

import pytest


@pytest.fixture(autouse=True)
def clear_cache():
    """Cache vor und nach jedem Test leeren."""
    cache.clear()
    yield
    cache.clear()


# ---------------------------------------------------------------------------
# Plan Templates Cache
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPlanTemplatesCache:
    def test_load_templates_populates_cache(self):
        """_load_templates() setzt den Cache beim ersten Aufruf."""
        from core.views.plan_templates import _PLAN_TEMPLATES_CACHE_KEY, _load_templates

        assert cache.get(_PLAN_TEMPLATES_CACHE_KEY) is None
        result = _load_templates()
        assert result is not None
        cached = cache.get(_PLAN_TEMPLATES_CACHE_KEY)
        assert cached is not None
        assert cached == result

    def test_load_templates_uses_cache_on_second_call(self):
        """_load_templates() liest beim zweiten Aufruf aus dem Cache, nicht von Disk."""
        from core.views.plan_templates import _PLAN_TEMPLATES_CACHE_KEY, _load_templates

        # Erster Aufruf: befüllt den Cache
        _load_templates()

        # Cache manipulieren: prüfen ob zweiter Aufruf tatsächlich den Cache nutzt
        cache.set(_PLAN_TEMPLATES_CACHE_KEY, {"__test__": True}, timeout=None)
        second = _load_templates()

        assert second == {
            "__test__": True
        }, "_load_templates() liest nicht aus dem Cache – File-I/O bei jedem Aufruf!"
        # Aufräumen für andere Tests
        cache.delete(_PLAN_TEMPLATES_CACHE_KEY)
        _load_templates()  # Original-Daten wieder laden


# ---------------------------------------------------------------------------
# Dashboard Cache
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDashboardCache:
    def test_dashboard_populates_cache(self, client, django_user_model):
        """Erster Dashboard-Request befüllt den Cache."""
        user = django_user_model.objects.create_user(
            username="cache_test_user", password="testpass123"
        )
        cache_key = f"dashboard_computed_{user.id}"
        assert cache.get(cache_key) is None

        client.force_login(user)
        response = client.get(reverse("dashboard"))

        assert response.status_code == 200
        cached = cache.get(cache_key)
        assert cached is not None, "Dashboard-Cache wurde nach dem ersten Request nicht befüllt."

    def test_dashboard_cache_contains_expected_keys(self, client, django_user_model):
        """Der Cache-Eintrag enthält alle erwarteten Keys."""
        user = django_user_model.objects.create_user(
            username="cache_keys_user", password="testpass123"
        )
        cache_key = f"dashboard_computed_{user.id}"

        client.force_login(user)
        client.get(reverse("dashboard"))

        cached = cache.get(cache_key)
        expected_keys = {
            "streak",
            "gesamt_trainings",
            "gesamt_saetze",
            "form_index",
            "form_rating",
            "form_color",
            "weekly_volumes",
            "motivation_quote",
            "training_heatmap_json",
            "performance_warnings",
            "fatigue_index",
            "trainings_diese_woche",
        }
        missing = expected_keys - set(cached.keys())
        assert not missing, f"Cache-Eintrag fehlt Keys: {missing}"

    def test_dashboard_cache_invalidated_on_new_training(self, client, django_user_model, db):
        """Wenn ein Training gespeichert wird, wird der Dashboard-Cache invalidiert."""
        from core.models import Trainingseinheit

        user = django_user_model.objects.create_user(
            username="invalidation_user", password="testpass123"
        )
        cache_key = f"dashboard_computed_{user.id}"

        # Cache befüllen
        client.force_login(user)
        client.get(reverse("dashboard"))
        assert cache.get(cache_key) is not None

        # Neues Training speichern → Signal soll Cache löschen
        Trainingseinheit.objects.create(user=user)
        assert cache.get(cache_key) is None, (
            "Dashboard-Cache wurde nach neuem Training NICHT invalidiert. "
            "Signal in signals.py prüfen."
        )

    def test_dashboard_cache_key_isolated_per_user(self, client, django_user_model):
        """User A und User B haben voneinander isolierte Cache-Einträge."""
        user_a = django_user_model.objects.create_user(
            username="user_a_cache", password="testpass123"
        )
        user_b = django_user_model.objects.create_user(
            username="user_b_cache", password="testpass123"
        )

        # User A Dashboard laden
        client.force_login(user_a)
        client.get(reverse("dashboard"))

        key_a = f"dashboard_computed_{user_a.id}"
        key_b = f"dashboard_computed_{user_b.id}"

        assert cache.get(key_a) is not None
        assert (
            cache.get(key_b) is None
        ), "User B hat einen Cache-Eintrag obwohl er nie das Dashboard aufgerufen hat."


# ---------------------------------------------------------------------------
# Global Exercise List Cache
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGlobalUebungenCache:
    def test_first_call_populates_cache(self):
        """_get_global_uebungen() befüllt den Cache beim ersten Aufruf."""
        from core.views.exercise_library import (
            _GLOBAL_UEBUNGEN_CACHE_KEY,
            _get_global_uebungen,
        )

        assert cache.get(_GLOBAL_UEBUNGEN_CACHE_KEY) is None
        result = _get_global_uebungen()
        assert isinstance(result, list)
        cached = cache.get(_GLOBAL_UEBUNGEN_CACHE_KEY)
        assert cached is not None, "Cache wurde nach erstem Aufruf nicht befüllt."
        assert cached == result

    def test_second_call_uses_cache_not_db(self):
        """_get_global_uebungen() trifft beim zweiten Aufruf den Cache."""
        from core.views.exercise_library import (
            _GLOBAL_UEBUNGEN_CACHE_KEY,
            _get_global_uebungen,
        )

        # Erster Aufruf: befüllt den Cache
        _get_global_uebungen()

        # Sentinel einsetzen: wenn Cache genutzt wird, kommt dieser zurück
        sentinel = ["__sentinel__"]
        cache.set(_GLOBAL_UEBUNGEN_CACHE_KEY, sentinel, timeout=60)
        result = _get_global_uebungen()

        assert result == sentinel, (
            "_get_global_uebungen() liest nicht aus dem Cache – " "DB-Query bei jedem Aufruf!"
        )
