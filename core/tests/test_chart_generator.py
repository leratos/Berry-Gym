"""
Tests für core/chart_generator.py

Abgedeckte Funktionen:
- _rgba_to_hex
- _status_to_rgba
- generate_body_map_with_data (mit PIL-Fallback, da Cairo auf Windows nicht verfügbar)
- generate_muscle_heatmap
- generate_volume_chart
- generate_push_pull_pie

Edge Cases:
- Leere Eingaben
- Einzeldatenpunkte
- Alle Status-Typen (optimal, untertrainiert, uebertrainiert, unbekannt)
- generate_volume_chart mit < 2 Punkten (laut Code: gibt None zurück)

Nicht getestet:
- _render_svg_muscle_map_png_base64: erfordert Cairo-C-Library (auf Windows nicht vorhanden)
  → wird via monkeypatch ausgelöst, um den PIL-Fallback zu verifizieren
"""

import base64


# ---------------------------------------------------------------------------
# Hilfsfunktion: ist Rückgabewert ein valides base64-PNG?
# ---------------------------------------------------------------------------


def _is_base64_png(value: str) -> bool:
    """Prüft ob ein String ein base64-kodiertes PNG ist."""
    if not value or not isinstance(value, str):
        return False
    try:
        decoded = base64.b64decode(value)
        # PNG Magic Bytes: \x89PNG
        return decoded[:4] == b"\x89PNG"
    except Exception:
        return False


# ---------------------------------------------------------------------------
# _rgba_to_hex
# ---------------------------------------------------------------------------


class TestRgbaToHex:
    """Tests für die interne Hilfsfunktion _rgba_to_hex."""

    def test_bekannte_farbe(self):
        from core.chart_generator import _rgba_to_hex

        assert _rgba_to_hex((255, 0, 0)) == "#FF0000"

    def test_gruen(self):
        from core.chart_generator import _rgba_to_hex

        assert _rgba_to_hex((40, 167, 69)) == "#28A745"

    def test_none_gibt_grau_zurueck(self):
        from core.chart_generator import _rgba_to_hex

        assert _rgba_to_hex(None) == "#D9D9D9"

    def test_rgba_mit_alpha_wird_ignoriert(self):
        """Alpha-Kanal wird ignoriert – nur RGB relevant."""
        from core.chart_generator import _rgba_to_hex

        assert _rgba_to_hex((40, 167, 69, 255)) == "#28A745"

    def test_schwarz(self):
        from core.chart_generator import _rgba_to_hex

        assert _rgba_to_hex((0, 0, 0)) == "#000000"

    def test_weiss(self):
        from core.chart_generator import _rgba_to_hex

        assert _rgba_to_hex((255, 255, 255)) == "#FFFFFF"


# ---------------------------------------------------------------------------
# _status_to_rgba
# ---------------------------------------------------------------------------


class TestStatusToRgba:
    """Tests für das Status → RGBA Mapping."""

    def test_optimal_ist_gruen(self):
        from core.chart_generator import _status_to_rgba

        r, g, b, a = _status_to_rgba("optimal")
        assert g > r and g > b  # Grün dominiert

    def test_untertrainiert_ist_gelb(self):
        from core.chart_generator import _status_to_rgba

        r, g, b, a = _status_to_rgba("untertrainiert")
        assert r > 200 and g > 150 and b < 50  # Gelb

    def test_uebertrainiert_ist_rot(self):
        from core.chart_generator import _status_to_rgba

        r, g, b, a = _status_to_rgba("uebertrainiert")
        assert r > 200 and g < 100  # Rot dominiert

    def test_unbekannter_status_ist_grau(self):
        from core.chart_generator import _status_to_rgba

        r, g, b, a = _status_to_rgba("irgendwas_unbekanntes")
        # Grau: R=G=B=217
        assert r == g == b == 217

    def test_alle_status_geben_4_tuple_zurueck(self):
        from core.chart_generator import _status_to_rgba

        for status in ["optimal", "untertrainiert", "uebertrainiert", "unbekannt"]:
            result = _status_to_rgba(status)
            assert len(result) == 4, f"Status '{status}' gibt kein 4-Tuple zurück"


# ---------------------------------------------------------------------------
# generate_muscle_heatmap
# ---------------------------------------------------------------------------


class TestGenerateMuscleHeatmap:
    """Tests für generate_muscle_heatmap."""

    def test_leere_liste_gibt_none_zurueck(self):
        from core.chart_generator import generate_muscle_heatmap

        assert generate_muscle_heatmap([]) is None

    def test_none_gibt_none_zurueck(self):
        from core.chart_generator import generate_muscle_heatmap

        assert generate_muscle_heatmap(None) is None

    def test_normaler_aufruf_gibt_base64_png_zurueck(self):
        from core.chart_generator import generate_muscle_heatmap

        daten = [
            {"name": "Brust", "saetze": 15, "status": "optimal"},
            {"name": "Rücken", "saetze": 12, "status": "untertrainiert"},
            {"name": "Beine", "saetze": 5, "status": "uebertrainiert"},
        ]
        result = generate_muscle_heatmap(daten)
        assert _is_base64_png(result), "Ergebnis ist kein valides base64-PNG"

    def test_einzelner_eintrag(self):
        """Einzelner Eintrag darf nicht crashen."""
        from core.chart_generator import generate_muscle_heatmap

        daten = [{"name": "Brust", "saetze": 10, "status": "optimal"}]
        result = generate_muscle_heatmap(daten)
        assert _is_base64_png(result)

    def test_alle_status_typen(self):
        """Alle vier Status-Typen auf einmal – kein Crash."""
        from core.chart_generator import generate_muscle_heatmap

        daten = [
            {"name": "A", "saetze": 10, "status": "optimal"},
            {"name": "B", "saetze": 5, "status": "untertrainiert"},
            {"name": "C", "saetze": 25, "status": "uebertrainiert"},
            {"name": "D", "saetze": 0, "status": "unbekannt"},
        ]
        result = generate_muscle_heatmap(daten)
        assert _is_base64_png(result)

    def test_null_saetze(self):
        """Muskelgruppen mit 0 Sätzen dürfen keinen Crash verursachen."""
        from core.chart_generator import generate_muscle_heatmap

        daten = [
            {"name": "Brust", "saetze": 0, "status": "untertrainiert"},
            {"name": "Rücken", "saetze": 0, "status": "untertrainiert"},
        ]
        result = generate_muscle_heatmap(daten)
        assert _is_base64_png(result)


# ---------------------------------------------------------------------------
# generate_volume_chart
# ---------------------------------------------------------------------------


class TestGenerateVolumeChart:
    """Tests für generate_volume_chart."""

    def test_leere_liste_gibt_none_zurueck(self):
        from core.chart_generator import generate_volume_chart

        assert generate_volume_chart([]) is None

    def test_none_gibt_none_zurueck(self):
        from core.chart_generator import generate_volume_chart

        assert generate_volume_chart(None) is None

    def test_ein_eintrag_gibt_none_zurueck(self):
        """Laut Code: len < 2 → None. Das ist ein bewusstes Design."""
        from core.chart_generator import generate_volume_chart

        daten = [{"woche": "2026-W01", "volumen": 5000.0}]
        result = generate_volume_chart(daten)
        assert result is None, (
            "ACHTUNG: generate_volume_chart gibt bei < 2 Einträgen None zurück. "
            "Ein Einzelpunkt kann nicht als Linie dargestellt werden – das ist korrekt."
        )

    def test_zwei_eintraege_minimale_darstellung(self):
        """Zwei Einträge sind das Minimum für einen Linienchart."""
        from core.chart_generator import generate_volume_chart

        daten = [
            {"woche": "2026-W01", "volumen": 4000.0},
            {"woche": "2026-W02", "volumen": 5000.0},
        ]
        result = generate_volume_chart(daten)
        assert _is_base64_png(result)

    def test_normaler_verlauf(self):
        from core.chart_generator import generate_volume_chart

        daten = [
            {"woche": "2026-W01", "volumen": 3000.0},
            {"woche": "2026-W02", "volumen": 4500.0},
            {"woche": "2026-W03", "volumen": 5200.0},
            {"woche": "2026-W04", "volumen": 4800.0},
        ]
        result = generate_volume_chart(daten)
        assert _is_base64_png(result)

    def test_alle_volumen_null(self):
        """Volumen = 0 überall: kein Crash, valides PNG erwartet."""
        from core.chart_generator import generate_volume_chart

        daten = [
            {"woche": "2026-W01", "volumen": 0.0},
            {"woche": "2026-W02", "volumen": 0.0},
        ]
        result = generate_volume_chart(daten)
        assert _is_base64_png(result)

    def test_grosses_volumen(self):
        """Sehr hohe Volumenwerte dürfen kein Overflow-Problem verursachen."""
        from core.chart_generator import generate_volume_chart

        daten = [{"woche": f"2026-W{i:02d}", "volumen": float(i * 100000)} for i in range(1, 13)]
        result = generate_volume_chart(daten)
        assert _is_base64_png(result)


# ---------------------------------------------------------------------------
# generate_push_pull_pie
# ---------------------------------------------------------------------------


class TestGeneratePushPullPie:
    """Tests für generate_push_pull_pie."""

    def test_beide_null_gibt_none_zurueck(self):
        from core.chart_generator import generate_push_pull_pie

        assert generate_push_pull_pie(0, 0) is None

    def test_nur_push(self):
        """Nur Push-Sätze: Pie sollte trotzdem rendern (ein Sektor)."""
        from core.chart_generator import generate_push_pull_pie

        result = generate_push_pull_pie(20, 0)
        assert _is_base64_png(result)

    def test_nur_pull(self):
        """Nur Pull-Sätze: Pie sollte trotzdem rendern (ein Sektor)."""
        from core.chart_generator import generate_push_pull_pie

        result = generate_push_pull_pie(0, 15)
        assert _is_base64_png(result)

    def test_ausgeglichene_balance(self):
        from core.chart_generator import generate_push_pull_pie

        result = generate_push_pull_pie(20, 20)
        assert _is_base64_png(result)

    def test_unausgeglichene_balance(self):
        from core.chart_generator import generate_push_pull_pie

        result = generate_push_pull_pie(30, 10)
        assert _is_base64_png(result)

    def test_sehr_grosse_werte(self):
        """Keine Darstellungsprobleme bei hohen Satz-Zahlen."""
        from core.chart_generator import generate_push_pull_pie

        result = generate_push_pull_pie(500, 300)
        assert _is_base64_png(result)


# ---------------------------------------------------------------------------
# generate_body_map_with_data (PIL-Fallback Pfad)
# ---------------------------------------------------------------------------


class TestGenerateBodyMapWithData:
    """
    Tests für generate_body_map_with_data.

    Wichtig: Auf Windows ist Cairo nicht verfügbar, daher wird automatisch
    der PIL-Fallback genutzt. Wir testen diesen Pfad direkt.
    """

    def test_leere_liste_gibt_none_zurueck(self):
        from core.chart_generator import generate_body_map_with_data

        assert generate_body_map_with_data([]) is None

    def test_none_gibt_none_zurueck(self):
        from core.chart_generator import generate_body_map_with_data

        assert generate_body_map_with_data(None) is None

    def test_pil_fallback_gibt_base64_png_zurueck(self, monkeypatch):
        """
        Erzwingt den PIL-Fallback indem cairosvg als nicht importierbar simuliert wird.
        Verifiziert dass der Fallback stabil ist und ein valides PNG liefert.
        """
        import builtins

        import core.chart_generator as cg

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "cairosvg":
                raise ImportError("Cairo nicht verfügbar (Test-Mock)")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        daten = [
            {"key": "BRUST", "status": "optimal"},
            {"key": "RUECKEN_LAT", "status": "untertrainiert"},
            {"key": "BEINE_QUAD", "status": "uebertrainiert"},
        ]
        result = cg.generate_body_map_with_data(daten)
        assert _is_base64_png(result), "PIL-Fallback liefert kein valides base64-PNG"

    def test_alle_bekannten_muskelgruppen_kein_crash(self, monkeypatch):
        """Alle definierten Muskelgruppen-Keys auf einmal – kein KeyError."""
        import builtins
        import core.chart_generator as cg

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "cairosvg":
                raise ImportError("Mock")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        alle_keys = [
            "BRUST",
            "SCHULTER_VORD",
            "SCHULTER_SEIT",
            "SCHULTER_HINT",
            "TRIZEPS",
            "BIZEPS",
            "UNTERARME",
            "RUECKEN_LAT",
            "RUECKEN_TRAPEZ",
            "RUECKEN_OBERER",
            "RUECKEN_UNTER",
            "BAUCH",
            "BEINE_QUAD",
            "BEINE_ADDUKTOREN",
            "BEINE_HAM",
            "BEINE_GESAESS",
            "BEINE_WADEN",
        ]
        daten = [{"key": k, "status": "optimal"} for k in alle_keys]
        result = cg.generate_body_map_with_data(daten)
        assert _is_base64_png(result)

    def test_unbekannte_muskelgruppe_kein_crash(self, monkeypatch):
        """Unbekannte Keys dürfen keinen KeyError auslösen."""
        import builtins
        import core.chart_generator as cg

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "cairosvg":
                raise ImportError("Mock")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        daten = [
            {"key": "UNBEKANNTE_GRUPPE", "status": "optimal"},
            {"key": "BRUST", "status": "optimal"},
        ]
        result = cg.generate_body_map_with_data(daten)
        assert _is_base64_png(result)
