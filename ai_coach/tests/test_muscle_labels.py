"""Tests für die gemeinsame Muskelgruppen-Label-Zuordnung (Phase 29.3)."""

from ai_coach.muscle_labels import KEY_TO_DISPLAY, MIN_SETS_PER_WEAKNESS, resolve_weakness_keys


def test_resolve_db_constant_label():
    """data_analyzer liefert DB-Konstanten als Label – müssen aufgelöst werden."""
    assert resolve_weakness_keys("BEINE_HAM") == ["BEINE_HAM"]
    assert resolve_weakness_keys("HUEFTBEUGER") == ["HUEFTBEUGER"]
    assert resolve_weakness_keys("SCHULTER_HINT") == ["SCHULTER_HINT"]


def test_resolve_human_label():
    assert resolve_weakness_keys("Hintere Schulter") == ["SCHULTER_HINT"]
    assert resolve_weakness_keys("hamstrings") == ["BEINE_HAM"]
    assert resolve_weakness_keys("Bauch") == ["BAUCH"]


def test_resolve_group_aggregation():
    keys = resolve_weakness_keys("beine")
    assert "BEINE_QUAD" in keys and "BEINE_HAM" in keys
    assert len(keys) == 7


def test_resolve_unknown_returns_empty():
    assert resolve_weakness_keys("Griffkraft") == []
    assert resolve_weakness_keys("") == []
    assert resolve_weakness_keys(None) == []


def test_every_db_constant_resolves_to_itself():
    """Jede DB-Konstante (= was data_analyzer als muskelgruppe liefert) muss
    erkannt werden – das war der F3-Bug."""
    for key in KEY_TO_DISPLAY:
        assert resolve_weakness_keys(key) == [key], f"{key} nicht auflösbar"


def test_min_sets_within_session_cap():
    """N muss <= 7 bleiben (_MAX_SETS_PER_MUSCLE_GROUP des Validators), sonst
    erzeugt die Volumen-Vorgabe einen Overrep-Konflikt."""
    assert 1 <= MIN_SETS_PER_WEAKNESS <= 7
