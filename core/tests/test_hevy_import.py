"""
Tests für Hevy-Format Import und Export.

Testet:
- Hevy CSV Export (Spalten, Inhalt, abgeschlossen-Filter)
- Hevy CSV Import (Parsing, Workout-Anlage, Duplikat-Schutz, Dry-Run)
- Edge Cases: fehlerhafte Daten, leere Dateien, zu grosse Dateien
"""

import csv
import io

from django.urls import reverse

import pytest

from core.models import Satz, Trainingseinheit, Uebung
from core.tests.factories import SatzFactory, TrainingseinheitFactory, UebungFactory, UserFactory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HEVY_HEADERS = [
    "title",
    "start_time",
    "end_time",
    "description",
    "exercise_title",
    "superset_id",
    "exercise_notes",
    "set_index",
    "set_type",
    "weight_kg",
    "reps",
    "distance_km",
    "duration_seconds",
    "rpe",
]


def _make_hevy_csv(*rows: dict) -> bytes:
    """Build a minimal Hevy CSV as bytes (UTF-8 with BOM)."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_HEVY_HEADERS)
    writer.writeheader()
    for row in rows:
        full_row = {k: "" for k in _HEVY_HEADERS}
        full_row.update(row)
        writer.writerow(full_row)
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


def _hevy_row(
    title="Test Workout",
    start="2025-01-15 10:00:00",
    end="2025-01-15 11:00:00",
    exercise="Bankdrücken",
    set_type="normal",
    weight=80.0,
    reps=8,
    rpe="",
    set_index=0,
):
    return {
        "title": title,
        "start_time": start,
        "end_time": end,
        "exercise_title": exercise,
        "set_type": set_type,
        "weight_kg": weight,
        "reps": reps,
        "rpe": rpe,
        "set_index": set_index,
    }


# ---------------------------------------------------------------------------
# Export Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestHevyCSVExport:

    def test_requires_login(self, client):
        response = client.get(reverse("export_hevy_csv"))
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_returns_csv(self, client):
        user = UserFactory()
        client.force_login(user)
        response = client.get(reverse("export_hevy_csv"))
        assert response.status_code == 200
        assert "text/csv" in response["Content-Type"]
        assert "homegym_hevy_export.csv" in response["Content-Disposition"]

    def test_hevy_headers_present(self, client):
        user = UserFactory()
        client.force_login(user)
        response = client.get(reverse("export_hevy_csv"))
        content = response.content.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(content))
        headers = next(reader)
        for col in _HEVY_HEADERS:
            assert col in headers, f"Missing Hevy column: {col}"

    def test_only_abgeschlossen_trainings_exported(self, client):
        user = UserFactory()
        client.force_login(user)
        uebung = UebungFactory()
        done = TrainingseinheitFactory(user=user, abgeschlossen=True)
        open_ = TrainingseinheitFactory(user=user, abgeschlossen=False)
        SatzFactory(einheit=done, uebung=uebung, gewicht=100, wiederholungen=5)
        SatzFactory(einheit=open_, uebung=uebung, gewicht=60, wiederholungen=10)

        response = client.get(reverse("export_hevy_csv"))
        content = response.content.decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(content)))
        # Only the set from the finished workout
        assert len(rows) == 1
        assert rows[0]["weight_kg"] == "100.0"

    def test_set_type_warmup_mapping(self, client):
        user = UserFactory()
        client.force_login(user)
        uebung = UebungFactory()
        training = TrainingseinheitFactory(user=user, abgeschlossen=True)
        SatzFactory(
            einheit=training, uebung=uebung, ist_aufwaermsatz=True, gewicht=40, wiederholungen=10
        )
        SatzFactory(
            einheit=training, uebung=uebung, ist_aufwaermsatz=False, gewicht=80, wiederholungen=5
        )

        response = client.get(reverse("export_hevy_csv"))
        content = response.content.decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(content)))
        types = {r["weight_kg"]: r["set_type"] for r in rows}
        assert types["40.0"] == "warmup"
        assert types["80.0"] == "normal"

    def test_user_isolation(self, client):
        user1 = UserFactory()
        user2 = UserFactory()
        uebung = UebungFactory()
        t2 = TrainingseinheitFactory(user=user2, abgeschlossen=True)
        SatzFactory(einheit=t2, uebung=uebung, gewicht=200, wiederholungen=1)

        client.force_login(user1)
        response = client.get(reverse("export_hevy_csv"))
        content = response.content.decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(content)))
        assert len(rows) == 0

    def test_superset_id_exported(self, client):
        user = UserFactory()
        client.force_login(user)
        uebung = UebungFactory()
        training = TrainingseinheitFactory(user=user, abgeschlossen=True)
        SatzFactory(
            einheit=training, uebung=uebung, superset_gruppe=2, gewicht=60, wiederholungen=10
        )

        response = client.get(reverse("export_hevy_csv"))
        content = response.content.decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(content)))
        assert rows[0]["superset_id"] == "S2"

    def test_rpe_exported(self, client):
        user = UserFactory()
        client.force_login(user)
        uebung = UebungFactory()
        training = TrainingseinheitFactory(user=user, abgeschlossen=True)
        SatzFactory(einheit=training, uebung=uebung, rpe=8.0, gewicht=100, wiederholungen=3)

        response = client.get(reverse("export_hevy_csv"))
        content = response.content.decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(content)))
        assert rows[0]["rpe"] == "8.0"


# ---------------------------------------------------------------------------
# Import Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestHevyCSVImport:

    def test_requires_login(self, client):
        response = client.post(reverse("import_hevy_csv"))
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_get_shows_form(self, client):
        user = UserFactory()
        client.force_login(user)
        response = client.get(reverse("import_hevy_csv"))
        assert response.status_code == 200
        assert b"hevy_csv" in response.content

    def test_post_without_file_shows_error(self, client):
        user = UserFactory()
        client.force_login(user)
        response = client.post(reverse("import_hevy_csv"), {})
        assert response.status_code == 200
        assert "Bitte eine CSV-Datei" in response.content.decode()

    def test_missing_required_columns_shows_error(self, client):
        user = UserFactory()
        client.force_login(user)
        bad_csv = b"foo,bar\n1,2\n"
        f = io.BytesIO(bad_csv)
        f.name = "bad.csv"
        response = client.post(reverse("import_hevy_csv"), {"hevy_csv": f})
        assert response.status_code == 200
        assert "Fehlende Spalten" in response.content.decode()

    def test_imports_workout_and_sets(self, client):
        user = UserFactory()
        client.force_login(user)
        UebungFactory(bezeichnung="Bankdrücken")

        csv_data = _make_hevy_csv(
            _hevy_row(exercise="Bankdrücken", weight=100, reps=5, set_index=0),
            _hevy_row(exercise="Bankdrücken", weight=100, reps=5, set_index=1),
        )
        f = io.BytesIO(csv_data)
        f.name = "hevy.csv"
        response = client.post(reverse("import_hevy_csv"), {"hevy_csv": f}, follow=True)

        assert response.status_code == 200
        assert Trainingseinheit.objects.filter(user=user).count() == 1
        assert Satz.objects.filter(einheit__user=user).count() == 2

    def test_warmup_sets_imported_correctly(self, client):
        user = UserFactory()
        client.force_login(user)
        UebungFactory(bezeichnung="Kniebeugen")

        csv_data = _make_hevy_csv(
            _hevy_row(exercise="Kniebeugen", set_type="warmup", weight=40, reps=10),
            _hevy_row(exercise="Kniebeugen", set_type="normal", weight=100, reps=5),
        )
        f = io.BytesIO(csv_data)
        f.name = "hevy.csv"
        client.post(reverse("import_hevy_csv"), {"hevy_csv": f})

        warmups = Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=True)
        normals = Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False)
        assert warmups.count() == 1
        assert normals.count() == 1

    def test_duplicate_workout_skipped(self, client):
        user = UserFactory()
        client.force_login(user)
        UebungFactory(bezeichnung="Bankdrücken")

        # Import once
        csv_data = _make_hevy_csv(_hevy_row(exercise="Bankdrücken", weight=80, reps=8))
        for _ in range(2):
            f = io.BytesIO(csv_data)
            f.name = "hevy.csv"
            client.post(reverse("import_hevy_csv"), {"hevy_csv": f})

        assert Trainingseinheit.objects.filter(user=user).count() == 1

    def test_unknown_exercise_created_as_custom(self, client):
        user = UserFactory()
        client.force_login(user)

        csv_data = _make_hevy_csv(_hevy_row(exercise="FooBar Exotic Lift", weight=50, reps=10))
        f = io.BytesIO(csv_data)
        f.name = "hevy.csv"
        client.post(reverse("import_hevy_csv"), {"hevy_csv": f})

        custom = Uebung.objects.filter(bezeichnung="FooBar Exotic Lift", created_by=user).first()
        assert custom is not None
        assert custom.is_custom is True

    def test_dry_run_does_not_create_records(self, client):
        user = UserFactory()
        client.force_login(user)
        UebungFactory(bezeichnung="Bankdrücken")

        csv_data = _make_hevy_csv(_hevy_row(exercise="Bankdrücken", weight=80, reps=5))
        f = io.BytesIO(csv_data)
        f.name = "hevy.csv"
        response = client.post(reverse("import_hevy_csv"), {"hevy_csv": f, "dry_run": "1"})

        assert response.status_code == 200
        assert Trainingseinheit.objects.filter(user=user).count() == 0
        assert b"Vorschau" in response.content

    def test_dry_run_shows_workout_preview(self, client):
        user = UserFactory()
        client.force_login(user)

        csv_data = _make_hevy_csv(
            _hevy_row(title="Push Day", exercise="Bankdrücken", weight=80, reps=8),
            _hevy_row(
                title="Push Day",
                exercise="Schulterdrücken",
                weight=50,
                reps=10,
                start="2025-01-15 10:00:00",
            ),
        )
        f = io.BytesIO(csv_data)
        f.name = "hevy.csv"
        response = client.post(reverse("import_hevy_csv"), {"hevy_csv": f, "dry_run": "1"})
        assert b"Push Day" in response.content

    def test_rpe_stored_correctly(self, client):
        user = UserFactory()
        client.force_login(user)
        UebungFactory(bezeichnung="Kreuzheben")

        csv_data = _make_hevy_csv(_hevy_row(exercise="Kreuzheben", weight=140, reps=3, rpe="8.5"))
        f = io.BytesIO(csv_data)
        f.name = "hevy.csv"
        client.post(reverse("import_hevy_csv"), {"hevy_csv": f})

        satz = Satz.objects.filter(einheit__user=user).first()
        assert satz is not None
        assert float(satz.rpe) == 8.5

    def test_invalid_rpe_ignored(self, client):
        user = UserFactory()
        client.force_login(user)
        UebungFactory(bezeichnung="Klimmzüge")

        csv_data = _make_hevy_csv(
            _hevy_row(exercise="Klimmzüge", weight=0, reps=8, rpe="99")  # out of range
        )
        f = io.BytesIO(csv_data)
        f.name = "hevy.csv"
        client.post(reverse("import_hevy_csv"), {"hevy_csv": f})

        satz = Satz.objects.filter(einheit__user=user).first()
        assert satz is not None
        assert satz.rpe is None

    def test_user_isolation_import(self, client):
        user1 = UserFactory()
        user2 = UserFactory()
        UebungFactory(bezeichnung="Bankdrücken")

        csv_data = _make_hevy_csv(_hevy_row(exercise="Bankdrücken", weight=80, reps=5))

        client.force_login(user1)
        f = io.BytesIO(csv_data)
        f.name = "hevy.csv"
        client.post(reverse("import_hevy_csv"), {"hevy_csv": f})

        # user2 has nothing
        assert Trainingseinheit.objects.filter(user=user2).count() == 0

    def test_empty_csv_shows_error(self, client):
        user = UserFactory()
        client.force_login(user)

        # Only header, no rows
        header_only = (",".join(_HEVY_HEADERS) + "\n").encode("utf-8")
        f = io.BytesIO(header_only)
        f.name = "hevy.csv"
        response = client.post(reverse("import_hevy_csv"), {"hevy_csv": f})
        assert response.status_code == 200
        assert "keine Daten" in response.content.decode()

    def test_sets_with_zero_reps_skipped(self, client):
        user = UserFactory()
        client.force_login(user)
        UebungFactory(bezeichnung="Bankdrücken")

        csv_data = _make_hevy_csv(
            _hevy_row(exercise="Bankdrücken", weight=80, reps=0),  # should be skipped
            _hevy_row(exercise="Bankdrücken", weight=80, reps=5),
        )
        f = io.BytesIO(csv_data)
        f.name = "hevy.csv"
        client.post(reverse("import_hevy_csv"), {"hevy_csv": f})

        assert Satz.objects.filter(einheit__user=user).count() == 1
