"""
Tests für core/chart_generator.py

Abdeckung:
- _rgba_to_hex(): pure mapping function
- _status_to_rgba(): pure mapping function
- generate_body_map_with_data(): PIL-Fallback (cairosvg nicht verfügbar auf CI/Windows)
- generate_muscle_heatmap(): matplotlib bar chart
- generate_volume_chart(): matplotlib line chart
- generate_push_pull_pie(): matplotlib pie chart
"""

import base64

from django.test import TestCase

from core.chart_generator import (
    _rgba_to_hex,
    _status_to_rgba,
    generate_body_map_with_data,
    generate_muscle_heatmap,
    generate_push_pull_pie,
    generate_volume_chart,
)


class TestRgbaToHex(TestCase):
    def test_none_gibt_grau(self):
        self.assertEqual(_rgba_to_hex(None), "#D9D9D9")

    def test_rot(self):
        self.assertEqual(_rgba_to_hex((255, 0, 0)), "#FF0000")

    def test_gruen(self):
        self.assertEqual(_rgba_to_hex((0, 128, 0)), "#008000")

    def test_schwarz(self):
        self.assertEqual(_rgba_to_hex((0, 0, 0)), "#000000")

    def test_weiss(self):
        self.assertEqual(_rgba_to_hex((255, 255, 255)), "#FFFFFF")

    def test_rgba_tuple_ignoriert_alpha(self):
        # Alpha-Kanal wird ignoriert, nur RGB relevant
        self.assertEqual(_rgba_to_hex((40, 167, 69, 255)), "#28A745")


class TestStatusToRgba(TestCase):
    def test_optimal_ist_gruen(self):
        r, g, b, a = _status_to_rgba("optimal")
        self.assertGreater(g, r)
        self.assertGreater(g, b)

    def test_untertrainiert_ist_gelb(self):
        r, g, b, a = _status_to_rgba("untertrainiert")
        # Gelb = hoher R + G, niedriges B
        self.assertGreater(r, 200)
        self.assertGreater(g, 150)
        self.assertLess(b, 50)

    def test_uebertrainiert_ist_rot(self):
        r, g, b, a = _status_to_rgba("uebertrainiert")
        self.assertGreater(r, g)
        self.assertGreater(r, b)

    def test_unbekannter_status_gibt_grau(self):
        r, g, b, a = _status_to_rgba("UNBEKANNT")
        # Grau: R ≈ G ≈ B
        self.assertAlmostEqual(r, g, delta=20)
        self.assertAlmostEqual(r, b, delta=20)

    def test_alle_werte_als_tuple_mit_4_elementen(self):
        result = _status_to_rgba("optimal")
        self.assertEqual(len(result), 4)


MINIMAL_MG_STATS = [
    {"key": "BRUST", "name": "Brust", "saetze": 12, "status": "optimal"},
    {"key": "RUECKEN_LAT", "name": "Rücken", "saetze": 8, "status": "untertrainiert"},
    {"key": "BEINE_QUAD", "name": "Beine", "saetze": 20, "status": "uebertrainiert"},
]


class TestGenerateBodyMapWithData(TestCase):
    def test_keine_daten_gibt_none(self):
        result = generate_body_map_with_data([])
        self.assertIsNone(result)

    def test_gibt_base64_string_zurueck(self):
        result = generate_body_map_with_data(MINIMAL_MG_STATS)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, str)
        # Muss valides base64 sein
        decoded = base64.b64decode(result)
        self.assertGreater(len(decoded), 0)

    def test_ergebnis_ist_png(self):
        result = generate_body_map_with_data(MINIMAL_MG_STATS)
        decoded = base64.b64decode(result)
        # PNG magic bytes: \x89PNG
        self.assertEqual(decoded[:4], b"\x89PNG")

    def test_einzelne_muskelgruppe(self):
        stats = [{"key": "BRUST", "name": "Brust", "saetze": 10, "status": "optimal"}]
        result = generate_body_map_with_data(stats)
        self.assertIsNotNone(result)


class TestGenerateMuscleHeatmap(TestCase):
    def test_keine_daten_gibt_none(self):
        result = generate_muscle_heatmap([])
        self.assertIsNone(result)

    def test_gibt_base64_string_zurueck(self):
        result = generate_muscle_heatmap(MINIMAL_MG_STATS)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, str)
        decoded = base64.b64decode(result)
        self.assertGreater(len(decoded), 100)

    def test_ergebnis_ist_png(self):
        result = generate_muscle_heatmap(MINIMAL_MG_STATS)
        decoded = base64.b64decode(result)
        self.assertEqual(decoded[:4], b"\x89PNG")

    def test_mit_allen_status_werten(self):
        stats = [
            {"key": "BRUST", "name": "Brust", "saetze": 15, "status": "optimal"},
            {"key": "BAUCH", "name": "Bauch", "saetze": 4, "status": "untertrainiert"},
            {"key": "RUECKEN_LAT", "name": "Lat", "saetze": 30, "status": "uebertrainiert"},
            {"key": "BEINE_QUAD", "name": "Quad", "saetze": 0, "status": "untrainiert"},
        ]
        result = generate_muscle_heatmap(stats)
        self.assertIsNotNone(result)


class TestGenerateVolumeChart(TestCase):
    VOLUME_DATA = [
        {"woche": "KW1", "volumen": 5000},
        {"woche": "KW2", "volumen": 6000},
        {"woche": "KW3", "volumen": 5500},
        {"woche": "KW4", "volumen": 7000},
    ]

    def test_keine_daten_gibt_none(self):
        result = generate_volume_chart([])
        self.assertIsNone(result)

    def test_gibt_base64_string_zurueck(self):
        result = generate_volume_chart(self.VOLUME_DATA)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, str)
        decoded = base64.b64decode(result)
        self.assertGreater(len(decoded), 100)

    def test_ergebnis_ist_png(self):
        result = generate_volume_chart(self.VOLUME_DATA)
        decoded = base64.b64decode(result)
        self.assertEqual(decoded[:4], b"\x89PNG")

    def test_einzelner_datenpunkt_gibt_none(self):
        # Design-Entscheidung: Liniendiagramm braucht mind. 2 Punkte
        result = generate_volume_chart([{"woche": "KW1", "volumen": 3000}])
        self.assertIsNone(result)

    def test_zwei_datenpunkte_reichen(self):
        result = generate_volume_chart(
            [
                {"woche": "KW1", "volumen": 3000},
                {"woche": "KW2", "volumen": 4000},
            ]
        )
        self.assertIsNotNone(result)


class TestGeneratePushPullPie(TestCase):
    def test_gibt_base64_string_zurueck(self):
        result = generate_push_pull_pie(push_saetze=30, pull_saetze=25)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, str)
        decoded = base64.b64decode(result)
        self.assertGreater(len(decoded), 100)

    def test_ergebnis_ist_png(self):
        result = generate_push_pull_pie(push_saetze=30, pull_saetze=25)
        decoded = base64.b64decode(result)
        self.assertEqual(decoded[:4], b"\x89PNG")

    def test_nur_push(self):
        result = generate_push_pull_pie(push_saetze=20, pull_saetze=0)
        self.assertIsNotNone(result)

    def test_nur_pull(self):
        result = generate_push_pull_pie(push_saetze=0, pull_saetze=20)
        self.assertIsNotNone(result)

    def test_gleich_viel_push_und_pull(self):
        result = generate_push_pull_pie(push_saetze=15, pull_saetze=15)
        self.assertIsNotNone(result)
