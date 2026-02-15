"""
Tests für Phase 4.2 – Database Indexes.

Strategie: Prüft über Django's connection.introspection ob die definierten
Indexes tatsächlich in der Datenbank angelegt wurden. Das stellt sicher, dass
Migrations nicht vergessen wurden und die Index-Namen stabil bleiben.
"""

from django.db import connection

import pytest


def get_index_names(table_name: str) -> set[str]:
    """Gibt alle Index-Namen für eine Tabelle zurück."""
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, table_name)
    return {
        name
        for name, info in constraints.items()
        if info.get("index") and not info.get("primary_key") and not info.get("unique")
    }


def get_constraint_columns(table_name: str, index_name: str) -> list[str]:
    """Gibt die Spalten eines bestimmten Index zurück."""
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, table_name)
    if index_name in constraints:
        return constraints[index_name].get("columns", [])
    return []


@pytest.mark.django_db
class TestTrainingseinheitIndexes:
    """Indexes auf core_trainingseinheit."""

    def test_user_datum_compound_index_exists(self):
        """Compound Index (user_id, datum) für Stats-Views muss existieren."""
        indexes = get_index_names("core_trainingseinheit")
        assert "training_user_datum_idx" in indexes, (
            "Index training_user_datum_idx fehlt – Stats-Views filtern immer "
            "nach user UND sortieren nach datum."
        )

    def test_user_datum_index_columns(self):
        """Compound Index muss die richtigen Spalten in richtiger Reihenfolge haben."""
        columns = get_constraint_columns("core_trainingseinheit", "training_user_datum_idx")
        assert columns == [
            "user_id",
            "datum",
        ], f"Erwartete Spalten ['user_id', 'datum'], bekam {columns}"

    def test_user_deload_index_exists(self):
        """Index (user_id, ist_deload) für Deload-Filter in Stats muss existieren."""
        indexes = get_index_names("core_trainingseinheit")
        assert (
            "training_user_deload_idx" in indexes
        ), "Index training_user_deload_idx fehlt – Deload-Ausschluss in Stats-Views."

    def test_user_deload_index_columns(self):
        columns = get_constraint_columns("core_trainingseinheit", "training_user_deload_idx")
        assert columns == [
            "user_id",
            "ist_deload",
        ], f"Erwartete Spalten ['user_id', 'ist_deload'], bekam {columns}"

    def test_datum_single_index_still_exists(self):
        """Der ursprüngliche datum-Index darf nicht verschwunden sein."""
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(cursor, "core_trainingseinheit")
        # Suche nach einem Index der nur 'datum' enthält
        datum_only_indexes = [
            name
            for name, info in constraints.items()
            if info.get("index")
            and not info.get("primary_key")
            and info.get("columns") == ["datum"]
        ]
        assert datum_only_indexes, "Ursprünglicher datum-Einzelindex fehlt."


@pytest.mark.django_db
class TestSatzIndexes:
    """Indexes auf core_satz."""

    def test_einheit_warmup_index_exists(self):
        """Index (einheit_id, ist_aufwaermsatz) für Warmup-Filter muss existieren."""
        indexes = get_index_names("core_satz")
        assert "satz_einheit_warmup_idx" in indexes, (
            "Index satz_einheit_warmup_idx fehlt – Warmup-Sätze werden in fast "
            "jeder Auswertung rausgefiltert."
        )

    def test_einheit_warmup_index_columns(self):
        columns = get_constraint_columns("core_satz", "satz_einheit_warmup_idx")
        assert columns == [
            "einheit_id",
            "ist_aufwaermsatz",
        ], f"Erwartete Spalten ['einheit_id', 'ist_aufwaermsatz'], bekam {columns}"

    def test_uebung_einheit_index_still_exists(self):
        """Der ursprüngliche (uebung, einheit)-Index darf nicht verschwunden sein."""
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(cursor, "core_satz")
        uebung_einheit_indexes = [
            name
            for name, info in constraints.items()
            if info.get("index")
            and not info.get("primary_key")
            and set(info.get("columns", [])) == {"uebung_id", "einheit_id"}
        ]
        assert uebung_einheit_indexes, "Ursprünglicher (uebung, einheit)-Index fehlt."


@pytest.mark.django_db
class TestPlanIndexes:
    """Indexes auf core_plan."""

    def test_user_public_index_exists(self):
        """Index (user_id, is_public) für Plan-Library muss existieren."""
        indexes = get_index_names("core_plan")
        assert "plan_user_public_idx" in indexes, (
            "Index plan_user_public_idx fehlt – Plan-Library filtert nach "
            "user ODER is_public=True."
        )

    def test_user_public_index_columns(self):
        columns = get_constraint_columns("core_plan", "plan_user_public_idx")
        assert columns == [
            "user_id",
            "is_public",
        ], f"Erwartete Spalten ['user_id', 'is_public'], bekam {columns}"


@pytest.mark.django_db
class TestPlanUebungIndexes:
    """Indexes auf core_planuebung."""

    def test_plan_trainingstag_index_exists(self):
        """Index (plan_id, trainingstag) für plan_details-View muss existieren."""
        indexes = get_index_names("core_planuebung")
        assert "planuebung_plan_tag_idx" in indexes, (
            "Index planuebung_plan_tag_idx fehlt – plan_details gruppiert "
            "Übungen nach plan_id + trainingstag."
        )

    def test_plan_trainingstag_index_columns(self):
        columns = get_constraint_columns("core_planuebung", "planuebung_plan_tag_idx")
        assert columns == [
            "plan_id",
            "trainingstag",
        ], f"Erwartete Spalten ['plan_id', 'trainingstag'], bekam {columns}"
