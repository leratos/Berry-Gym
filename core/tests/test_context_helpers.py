"""
Tests für context_processors, custom_filters und helpers.exercises.

Abgedeckt:
- global_context: current_year
- disclaimers: globale und pfadabhängige Disclaimers
- get_item template filter
- find_substitute_exercise: alle Prioritätspfade
"""

from django.test import RequestFactory

import pytest

from core.context_processors import disclaimers, global_context
from core.templatetags.custom_filters import get_item

# ===========================================================================
# context_processors.py
# ===========================================================================


@pytest.mark.django_db
class TestGlobalContext:
    def test_returns_current_year(self):
        """current_year wird zurückgegeben."""
        factory = RequestFactory()
        request = factory.get("/")
        ctx = global_context(request)
        from datetime import datetime

        assert ctx["current_year"] == datetime.now().year

    def test_returns_dict(self):
        factory = RequestFactory()
        request = factory.get("/")
        ctx = global_context(request)
        assert isinstance(ctx, dict)


@pytest.mark.django_db
class TestDisclaimersContextProcessor:
    """
    ScientificDisclaimer Model Felder:
      - category (CharField, required, unique=True, choices)
      - title (CharField)
      - message (TextField) ← nicht 'content'!
      - severity (CharField, default="INFO")
      - show_on_pages (JSONField, default=list)
      - is_active (BooleanField)
    """

    def _request(self, path="/"):
        factory = RequestFactory()
        return factory.get(path)

    def test_no_disclaimers_returns_empty(self):
        """Keine Disclaimers in DB → leere Liste."""
        ctx = disclaimers(self._request())
        assert ctx["active_disclaimers"] == []

    def test_global_disclaimer_shown_everywhere(self):
        """Disclaimer ohne show_on_pages wird überall angezeigt."""
        from core.models_disclaimer import ScientificDisclaimer

        d = ScientificDisclaimer.objects.create(
            category="GENERAL",
            title="Global",
            message="Test-Nachricht",
            is_active=True,
            show_on_pages=[],
        )
        ctx = disclaimers(self._request("/irgendwo/"))
        assert d in ctx["active_disclaimers"]
        d.delete()

    def test_path_specific_disclaimer_matches(self):
        """Disclaimer mit show_on_pages wird nur auf passenden Pfaden angezeigt."""
        from core.models_disclaimer import ScientificDisclaimer

        d = ScientificDisclaimer.objects.create(
            category="TRAINING_VOLUME",
            title="Stats-only",
            message="Nur auf Stats-Seiten",
            is_active=True,
            show_on_pages=["stats/"],
        )
        ctx_match = disclaimers(self._request("/stats/"))
        ctx_no_match = disclaimers(self._request("/dashboard/"))
        assert d in ctx_match["active_disclaimers"]
        assert d not in ctx_no_match["active_disclaimers"]
        d.delete()

    def test_inactive_disclaimer_not_shown(self):
        """Inaktive Disclaimers werden nicht angezeigt."""
        from core.models_disclaimer import ScientificDisclaimer

        d = ScientificDisclaimer.objects.create(
            category="FATIGUE_INDEX",
            title="Inaktiv",
            message="Wird nicht angezeigt",
            is_active=False,
            show_on_pages=[],
        )
        ctx = disclaimers(self._request())
        assert d not in ctx["active_disclaimers"]
        d.delete()

    def test_multiple_patterns_first_match_wins(self):
        """Disclaimer mit mehreren Patterns: erster Treffer reicht."""
        from core.models_disclaimer import ScientificDisclaimer

        d = ScientificDisclaimer.objects.create(
            category="1RM_STANDARDS",
            title="Multi",
            message="Auf Stats und Training sichtbar",
            is_active=True,
            show_on_pages=["stats/", "training/"],
        )
        ctx = disclaimers(self._request("/training/session/"))
        assert d in ctx["active_disclaimers"]
        d.delete()


# ===========================================================================
# templatetags/custom_filters.py
# ===========================================================================


class TestGetItemFilter:
    def test_returns_value_for_existing_key(self):
        d = {"a": 1, "b": 2}
        assert get_item(d, "a") == 1

    def test_returns_none_for_missing_key(self):
        d = {"a": 1}
        assert get_item(d, "x") is None

    def test_returns_none_for_none_dict(self):
        assert get_item(None, "key") is None

    def test_returns_none_for_none_key(self):
        assert get_item({"a": 1}, None) is None

    def test_returns_none_for_empty_dict(self):
        assert get_item({}, "key") is None

    def test_works_with_integer_keys(self):
        d = {1: "eins", 2: "zwei"}
        assert get_item(d, 1) == "eins"


# ===========================================================================
# helpers/exercises.py
# ===========================================================================


@pytest.mark.django_db
class TestFindSubstituteExercise:
    """
    Tests für find_substitute_exercise — alle Prioritätspfade.

    WICHTIG: Uebung.equipment ist ein ManyToManyField → niemals direkt in
    objects.create() übergeben. Erst Objekt anlegen, dann .equipment.set([...]).
    """

    def setup_method(self):
        from core.models import Equipment, Uebung

        # Equipment-Objekte anlegen (name muss ein gültiger EQUIPMENT_CHOICES-Key sein)
        self.koerper_eq, _ = Equipment.objects.get_or_create(name="KOERPER")
        self.hantel_eq, _ = Equipment.objects.get_or_create(name="KURZHANTEL")
        self.langhantel_eq, _ = Equipment.objects.get_or_create(name="LANGHANTEL")

        # Original-Übung: Bankdrücken mit Langhantel
        # Equipment ist M2M → create() OHNE equipment, danach .set()
        self.original = Uebung.objects.create(
            bezeichnung="Bankdrücken",
            muskelgruppe="BRUST",
            bewegungstyp="DRUECKEN",  # Choice-Key, nicht Display-Name
        )
        self.original.equipment.set([self.langhantel_eq])

        # Alternative: Liegestütz mit Körpergewicht
        self.bodyweight_alt = Uebung.objects.create(
            bezeichnung="Liegestütz",
            muskelgruppe="BRUST",
            bewegungstyp="DRUECKEN",
        )
        self.bodyweight_alt.equipment.set([self.koerper_eq])

    def test_no_match_returns_fallback_message(self):
        """Wenn kein Equipment verfügbar → Fallback-Nachricht."""
        from core.helpers.exercises import find_substitute_exercise

        result = find_substitute_exercise("Bankdrücken", "Langhantel", [])
        assert "name" in result

    def test_bodyweight_fallback(self):
        """Wenn nur Körpergewicht verfügbar → Körpergewicht-Alternative."""
        from core.helpers.exercises import find_substitute_exercise

        koerper_display = self.koerper_eq.get_name_display().strip().lower()
        result = find_substitute_exercise(
            "Bankdrücken",
            "Langhantel",
            [koerper_display],
        )
        assert "name" in result

    def test_same_movement_pattern_priority(self):
        """Gleiches Bewegungsmuster + verfügbares Equipment wird bevorzugt."""
        from core.helpers.exercises import find_substitute_exercise
        from core.models import Uebung

        # Kurzhantel-Alternative anlegen, equipment via .set()
        hantel_alt = Uebung.objects.create(
            bezeichnung="Kurzhantel-Bankdrücken",
            muskelgruppe="BRUST",
            bewegungstyp="DRUECKEN",
        )
        hantel_alt.equipment.set([self.hantel_eq])

        hantel_display = self.hantel_eq.get_name_display().strip().lower()
        result = find_substitute_exercise(
            "Bankdrücken",
            "Langhantel",
            [hantel_display],
        )
        assert result["name"] == hantel_alt.bezeichnung
        hantel_alt.delete()

    def test_unknown_exercise_uses_keyword_mapping(self):
        """Unbekannte Übung → Keyword-Mapping für Muskelgruppe."""
        from core.helpers.exercises import find_substitute_exercise

        koerper_display = self.koerper_eq.get_name_display().strip().lower()
        result = find_substitute_exercise(
            "Brust Liegestütz",
            "kein Equipment",
            [koerper_display],
        )
        assert "name" in result

    def test_no_original_no_equipment_returns_fallback(self):
        """Vollständig unbekannte Übung ohne Equipment → kein Crash."""
        from core.helpers.exercises import find_substitute_exercise

        result = find_substitute_exercise("XYZ gibts nicht", "Laser", [])
        assert "name" in result
        assert "equipment" in result
