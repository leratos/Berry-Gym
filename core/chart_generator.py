"""Generiert Charts und Visualisierungen für PDF-Reports.

Optimierung (2026-01-11):
- Rendert die echte SVG-Muscle-Map (muscle_map.svg) via cairosvg in ein PNG für xhtml2pdf.
- Hervorhebung erfolgt durch Setzen von "fill" pro SVG-Pfad-ID (keine PIL-"Oval/Box"-Ersatzgrafik).
- Fallback: Wenn SVG nicht gefunden/parsebar ist, nutzt die bisherige PIL-Variante (kompatibel).
"""

import base64
import io
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # Non-GUI backend
from django.conf import settings

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from PIL import Image, ImageDraw, ImageFont

# -----------------------------
# Helpers
# -----------------------------


def _rgba_to_hex(color):
    """(r,g,b[,a]) -> '#RRGGBB'"""
    if color is None:
        return "#D9D9D9"
    r, g, b = color[0], color[1], color[2]
    return f"#{int(r):02X}{int(g):02X}{int(b):02X}"


def _status_to_rgba(status: str):
    """Mapping: Status -> RGBA Farbe."""
    if status == "optimal":
        return (40, 167, 69, 255)  # Grün
    if status == "untertrainiert":
        return (255, 193, 7, 255)  # Gelb
    if status == "uebertrainiert":
        return (220, 53, 69, 255)  # Rot
    return (217, 217, 217, 255)  # Grau


def _find_muscle_svg_path() -> Path | None:
    """Sucht muscle_map.svg.
    Priorität:
    1) settings.MUSCLE_MAP_SVG_PATH (wenn gesetzt)
    2) static/core/images/muscle_map.svg (Standard-Location)
    3) gleiche Directory wie diese Datei
    """
    # 1) Django settings
    p = getattr(settings, "MUSCLE_MAP_SVG_PATH", None)
    if p:
        pp = Path(p)
        if pp.exists():
            return pp

    # 2) Standard-Location: static/core/images/
    base = Path(getattr(settings, "BASE_DIR", Path(__file__).resolve().parent.parent)).resolve()
    for rel in [
        "core/static/core/images/muscle_map.svg",
        "static/core/images/muscle_map.svg",
        "staticfiles/core/images/muscle_map.svg",
    ]:
        cand = base / rel
        if cand.exists():
            return cand

    # 3) neben dieser Datei
    here = Path(__file__).resolve().parent
    cand = here / "muscle_map.svg"
    if cand.exists():
        return cand

    return None


# -----------------------------
# SVG Rendering (neu)
# -----------------------------


def _render_svg_muscle_map_png_base64(muskelgruppen_stats):
    """Rendert die SVG-Muscle-Map als PNG (base64), mit farbiger Hervorhebung per IDs.

    Erwartet muskelgruppen_stats als Liste von Dicts, z.B.:
      [{"key": "BRUST", "status": "optimal"}, ...]
    """
    if not muskelgruppen_stats:
        return None

    svg_path = _find_muscle_svg_path()
    if not svg_path:
        raise FileNotFoundError(
            "muscle_map.svg nicht gefunden (setze settings.MUSCLE_MAP_SVG_PATH oder lege Datei in static/core/images/ ab)."
        )

    # Import hier, damit das Modul auch ohne cairosvg/cairo-library funktioniert
    try:
        import cairosvg
    except (ImportError, OSError) as e:
        # cairosvg nicht installiert ODER Cairo-C-Library fehlt (Windows)
        raise ImportError(f"cairosvg/cairo nicht verfügbar: {e}")

    import xml.etree.ElementTree as ET

    svg_text = svg_path.read_text(encoding="utf-8")

    # Parse SVG
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as e:
        raise ValueError(f"SVG ParseError: {e}") from e

    # Namespace ermitteln (typisch '{http://www.w3.org/2000/svg}')
    ns = ""
    if root.tag.startswith("{") and "}" in root.tag:
        ns = root.tag.split("}")[0] + "}"

    def find_by_id(el_id: str):
        # ElementTree unterstützt XPath mit @id nur eingeschränkt; wir iterieren.
        for el in root.iter():
            if el.get("id") == el_id:
                return el
        return None

    # Mapping: Muskelgruppen-Key -> SVG IDs (angepasst an deine Keys)
    KEY_TO_IDS = {
        "BRUST": ["front_chest_left", "front_chest_right"],
        "SCHULTER_VORD": ["front_delt_left", "front_delt_right"],
        "SCHULTER_SEIT": [
            "front_delt_left",
            "front_delt_right",
            "back_delt_left",
            "back_delt_right",
        ],
        "SCHULTER_HINT": ["back_delt_left", "back_delt_right"],
        "TRIZEPS": ["back_triceps_left", "back_triceps_right"],
        "BIZEPS": ["front_biceps_left", "front_biceps_right"],
        "UNTERARME": [
            "front_forearm_left",
            "front_forearm_right",
            "back_forearm_left",
            "back_forearm_right",
        ],
        "RUECKEN_LAT": ["back_lat_left", "back_lat_right"],
        "RUECKEN_TRAPEZ": [
            "front_traps_left",
            "front_traps_right",
            "back_traps_left",
            "back_traps_right",
            "back_midback",
        ],
        "RUECKEN_OBERER": ["back_midback"],
        "RUECKEN_UNTER": ["back_erectors_left", "back_erectors_right"],
        "BAUCH": [
            "front_abs_upper",
            "front_abs_mid",
            "front_abs_lower",
            "front_oblique_left",
            "front_oblique_right",
        ],
        "BEINE_QUAD": ["front_quad_left", "front_quad_right"],
        "BEINE_ADDUKTOREN": ["front_adductor_left", "front_adductor_right"],
        "BEINE_HAM": ["back_hamstring_left", "back_hamstring_right"],
        "BEINE_GESAESS": ["back_glute_left", "back_glute_right"],
        "BEINE_WADEN": ["front_calf_left", "front_calf_right", "back_calf_left", "back_calf_right"],
    }

    # Farben aus Statusdaten ableiten
    key_to_hex = {}
    for mg in muskelgruppen_stats:
        key = mg.get("key")
        status = mg.get("status")
        key_to_hex[key] = _rgba_to_hex(_status_to_rgba(status))

    # Setze Fill-Override pro ID
    for key, ids in KEY_TO_IDS.items():
        if key not in key_to_hex:
            continue
        fill_hex = key_to_hex[key]
        for el_id in ids:
            el = find_by_id(el_id)
            if el is not None:
                # WICHTIG: CSS-Klasse entfernen, sonst überschreibt sie das fill-Attribut
                if "class" in el.attrib:
                    del el.attrib["class"]
                # Style-Attribut entfernen falls vorhanden
                if "style" in el.attrib:
                    del el.attrib["style"]
                # Jetzt fill setzen
                el.set("fill", fill_hex)
                # Optional: kräftigere Kontur
                el.set("stroke", "#333333")
                el.set("stroke-width", "3")

    # SVG wieder serialisieren
    svg_bytes = ET.tostring(root, encoding="utf-8", method="xml")

    # Render to PNG
    # background_color: leicht grau wie im alten PNG (sonst transparent)
    png_bytes = cairosvg.svg2png(
        bytestring=svg_bytes, output_width=1100, output_height=1024, background_color="#F5F5F5"
    )

    return base64.b64encode(png_bytes).decode("utf-8")


# -----------------------------
# PIL Fallback (alt, kompakt)
# -----------------------------


def _generate_body_map_with_data_pil_fallback(muskelgruppen_stats):
    """
    Alter Ansatz: schematische Bodymap via PIL Shapes.
    Behalten als Fallback, falls SVG nicht verfügbar ist.
    """
    try:
        muskel_colors = {}
        for mg in muskelgruppen_stats:
            key = mg.get("key")
            muskel_colors[key] = _status_to_rgba(mg.get("status"))

        default_color = (217, 217, 217, 160)

        width, height = 1100, 1024
        img = Image.new("RGBA", (width, height), (245, 245, 245, 255))
        draw = ImageDraw.Draw(img)

        # Titel
        try:
            font_label = ImageFont.truetype("arial.ttf", 28)
        except Exception:
            font_label = ImageFont.load_default()

        # === FRONT (links) ===
        fx, fy = 170, 80

        # Label
        draw.text((fx + 140, 20), "Vorne", fill=(0, 0, 0, 255), font=font_label, anchor="mm")

        # Kopf
        draw.ellipse(
            [fx + 120, fy + 30, fx + 160, fy + 70],
            fill=default_color,
            outline=(0, 0, 0, 255),
            width=2,
        )

        # Schultern (SCHULTER_VORD)
        color_delt = muskel_colors.get(
            "SCHULTER_VORD", muskel_colors.get("SCHULTER_SEIT", default_color)
        )
        draw.ellipse(
            [fx + 60, fy + 90, fx + 110, fy + 160], fill=color_delt, outline=(0, 0, 0, 255), width=2
        )
        draw.ellipse(
            [fx + 170, fy + 90, fx + 220, fy + 160],
            fill=color_delt,
            outline=(0, 0, 0, 255),
            width=2,
        )

        # Brust
        color_chest = muskel_colors.get("BRUST", default_color)
        draw.ellipse(
            [fx + 100, fy + 110, fx + 140, fy + 180],
            fill=color_chest,
            outline=(0, 0, 0, 255),
            width=2,
        )
        draw.ellipse(
            [fx + 140, fy + 110, fx + 180, fy + 180],
            fill=color_chest,
            outline=(0, 0, 0, 255),
            width=2,
        )

        # Bizeps
        color_biceps = muskel_colors.get("BIZEPS", default_color)
        draw.ellipse(
            [fx + 45, fy + 140, fx + 75, fy + 210],
            fill=color_biceps,
            outline=(0, 0, 0, 255),
            width=2,
        )
        draw.ellipse(
            [fx + 205, fy + 140, fx + 235, fy + 210],
            fill=color_biceps,
            outline=(0, 0, 0, 255),
            width=2,
        )

        # Unterarme
        draw.rectangle(
            [fx + 40, fy + 215, fx + 60, fy + 300],
            fill=default_color,
            outline=(0, 0, 0, 255),
            width=1,
        )
        draw.rectangle(
            [fx + 220, fy + 215, fx + 240, fy + 300],
            fill=default_color,
            outline=(0, 0, 0, 255),
            width=1,
        )

        # Bauch
        color_abs = muskel_colors.get("BAUCH", default_color)
        draw.rectangle(
            [fx + 110, fy + 185, fx + 170, fy + 300],
            fill=color_abs,
            outline=(0, 0, 0, 255),
            width=2,
        )

        # Oberschenkel (BEINE_QUAD)
        color_quad = muskel_colors.get("BEINE_QUAD", default_color)
        draw.ellipse(
            [fx + 90, fy + 305, fx + 130, fy + 460],
            fill=color_quad,
            outline=(0, 0, 0, 255),
            width=2,
        )
        draw.ellipse(
            [fx + 150, fy + 305, fx + 190, fy + 460],
            fill=color_quad,
            outline=(0, 0, 0, 255),
            width=2,
        )

        # Waden
        color_calf = muskel_colors.get("BEINE_WADEN", default_color)
        draw.ellipse(
            [fx + 90, fy + 465, fx + 120, fy + 580],
            fill=color_calf,
            outline=(0, 0, 0, 255),
            width=2,
        )
        draw.ellipse(
            [fx + 160, fy + 465, fx + 190, fy + 580],
            fill=color_calf,
            outline=(0, 0, 0, 255),
            width=2,
        )

        # === BACK (rechts) ===
        bx, by = 650, 80

        # Label
        draw.text((bx + 140, 20), "Hinten", fill=(0, 0, 0, 255), font=font_label, anchor="mm")

        # Kopf
        draw.ellipse(
            [bx + 120, by + 30, bx + 160, by + 70],
            fill=default_color,
            outline=(0, 0, 0, 255),
            width=2,
        )

        # Schultern hinten (SCHULTER_HINT)
        color_delt_back = muskel_colors.get("SCHULTER_HINT", default_color)
        draw.ellipse(
            [bx + 60, by + 90, bx + 110, by + 160],
            fill=color_delt_back,
            outline=(0, 0, 0, 255),
            width=2,
        )
        draw.ellipse(
            [bx + 170, by + 90, bx + 220, by + 160],
            fill=color_delt_back,
            outline=(0, 0, 0, 255),
            width=2,
        )

        # Latissimus
        color_lat = muskel_colors.get("RUECKEN_LAT", default_color)
        draw.polygon(
            [
                (bx + 70, by + 150),
                (bx + 80, by + 200),
                (bx + 100, by + 260),
                (bx + 120, by + 290),
                (bx + 130, by + 250),
                (bx + 130, by + 180),
                (bx + 110, by + 160),
            ],
            fill=color_lat,
            outline=(0, 0, 0, 255),
            width=2,
        )
        draw.polygon(
            [
                (bx + 210, by + 150),
                (bx + 200, by + 200),
                (bx + 180, by + 260),
                (bx + 160, by + 290),
                (bx + 150, by + 250),
                (bx + 150, by + 180),
                (bx + 170, by + 160),
            ],
            fill=color_lat,
            outline=(0, 0, 0, 255),
            width=2,
        )

        # Unterer Rücken (RUECKEN_UNTER)
        color_lower_back = muskel_colors.get("RUECKEN_UNTER", default_color)
        draw.rectangle(
            [bx + 110, by + 240, bx + 170, by + 340],
            fill=color_lower_back,
            outline=(0, 0, 0, 255),
            width=2,
        )

        # Trizeps
        color_triceps = muskel_colors.get("TRIZEPS", default_color)
        draw.ellipse(
            [bx + 45, by + 140, bx + 75, by + 210],
            fill=color_triceps,
            outline=(0, 0, 0, 255),
            width=2,
        )
        draw.ellipse(
            [bx + 205, by + 140, bx + 235, by + 210],
            fill=color_triceps,
            outline=(0, 0, 0, 255),
            width=2,
        )

        # Unterarme hinten
        draw.rectangle(
            [bx + 40, by + 215, bx + 60, by + 300],
            fill=default_color,
            outline=(0, 0, 0, 255),
            width=1,
        )
        draw.rectangle(
            [bx + 220, by + 215, bx + 240, by + 300],
            fill=default_color,
            outline=(0, 0, 0, 255),
            width=1,
        )

        # Gesäß (BEINE_GESAESS)
        color_glutes = muskel_colors.get("BEINE_GESAESS", default_color)
        draw.ellipse(
            [bx + 90, by + 340, bx + 140, by + 420],
            fill=color_glutes,
            outline=(0, 0, 0, 255),
            width=2,
        )
        draw.ellipse(
            [bx + 140, by + 340, bx + 190, by + 420],
            fill=color_glutes,
            outline=(0, 0, 0, 255),
            width=2,
        )

        # Hamstrings (BEINE_HAM)
        color_ham = muskel_colors.get("BEINE_HAM", default_color)
        draw.ellipse(
            [bx + 95, by + 410, bx + 130, by + 540], fill=color_ham, outline=(0, 0, 0, 255), width=2
        )
        draw.ellipse(
            [bx + 150, by + 410, bx + 185, by + 540],
            fill=color_ham,
            outline=(0, 0, 0, 255),
            width=2,
        )

        # Waden hinten
        draw.ellipse(
            [bx + 90, by + 545, bx + 120, by + 660],
            fill=color_calf,
            outline=(0, 0, 0, 255),
            width=2,
        )
        draw.ellipse(
            [bx + 160, by + 545, bx + 190, by + 660],
            fill=color_calf,
            outline=(0, 0, 0, 255),
            width=2,
        )

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception:
        return None


# -----------------------------
# Public API
# -----------------------------


def generate_body_map_with_data(muskelgruppen_stats):
    """
    Generiert eine Body-Map mit farblicher Hervorhebung basierend auf Trainingsdaten.
    Versucht zuerst SVG-Rendering, nutzt PIL-Fallback bei Problemen.

    Returns:
        str: Base64-encoded PNG image
    """
    if not muskelgruppen_stats:
        return None

    # 1) Versuche SVG-Rendering (professionell) - nur wenn Cairo verfügbar
    try:
        # Test ob cairosvg importierbar ist (inkl. Cairo-C-Library)
        import cairosvg

        return _render_svg_muscle_map_png_base64(muskelgruppen_stats)
    except (ImportError, OSError, FileNotFoundError) as e:
        # cairosvg nicht verfügbar ODER Cairo-Library fehlt (Windows) ODER SVG nicht gefunden
        print(f"SVG rendering nicht verfügbar, nutze PIL-Fallback: {type(e).__name__}: {e}")
        pass
    except Exception as e:
        # Andere Fehler (Parsing, etc.)
        print(f"SVG rendering fehlgeschlagen, nutze PIL-Fallback: {e}")
        import traceback

        traceback.print_exc()
        pass

    # 2) Fallback: PIL-Variante (immer verfügbar)
    return _generate_body_map_with_data_pil_fallback(muskelgruppen_stats)


def generate_muscle_heatmap(muskelgruppen_stats):
    """
    Generiert eine Heatmap-Visualisierung der Muskelgruppen-Balance.

    Returns:
        str: Base64-encoded PNG image
    """
    if not muskelgruppen_stats:
        return None

    # Daten vorbereiten
    gruppen = []
    werte = []
    colors = []

    for mg in muskelgruppen_stats:
        gruppen.append(mg["name"].split("(")[0].strip())  # Nur Name ohne (Latein)
        werte.append(mg["saetze"])

        # Farbe basierend auf Status
        if mg["status"] == "optimal":
            colors.append("#28a745")  # Grün
        elif mg["status"] == "untertrainiert":
            colors.append("#ffc107")  # Gelb
        elif mg["status"] == "uebertrainiert":
            colors.append("#dc3545")  # Rot
        else:
            colors.append("#6c757d")  # Grau

    # Chart erstellen
    fig, ax = plt.subplots(figsize=(10, 6))

    # Horizontale Bar Chart
    y_pos = np.arange(len(gruppen))
    bars = ax.barh(y_pos, werte, color=colors, edgecolor="black", linewidth=0.5)

    # Achsen beschriftung
    ax.set_yticks(y_pos)
    ax.set_yticklabels(gruppen, fontsize=9)
    ax.set_xlabel("Sätze (30 Tage)", fontsize=10, fontweight="bold")
    ax.set_title("Muskelgruppen-Balance Visualisierung", fontsize=12, fontweight="bold", pad=20)

    # Werte auf Balken anzeigen
    for i, (bar, wert) in enumerate(zip(bars, werte)):
        width = bar.get_width()
        ax.text(
            width + 0.5,
            bar.get_y() + bar.get_height() / 2,
            f"{wert}",
            ha="left",
            va="center",
            fontsize=8,
            fontweight="bold",
        )

    # Referenzlinien für optimalen Bereich (12-20 Sätze für die meisten Muskelgruppen)
    ax.axvline(
        x=12, color="green", linestyle="--", linewidth=1, alpha=0.5, label="Min. Optimal (12)"
    )
    ax.axvline(
        x=20, color="green", linestyle="--", linewidth=1, alpha=0.5, label="Max. Optimal (20)"
    )

    # Legende
    legend_elements = [
        mpatches.Patch(color="#28a745", label="Optimal"),
        mpatches.Patch(color="#ffc107", label="Untertrainiert"),
        mpatches.Patch(color="#dc3545", label="Übertrainiert"),
        mpatches.Patch(color="#6c757d", label="Nicht trainiert"),
    ]
    ax.legend(handles=legend_elements, loc="lower right", fontsize=8)

    # Grid
    ax.grid(axis="x", alpha=0.3, linestyle=":", linewidth=0.5)
    ax.set_axisbelow(True)

    # Layout optimieren
    plt.tight_layout()

    # Als PNG in Base64 konvertieren
    buffer = io.BytesIO()
    plt.savefig(buffer, format="png", dpi=150, bbox_inches="tight")
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.read()).decode("utf-8")
    plt.close(fig)

    return image_base64


def generate_volume_chart(volumen_wochen):
    """
    Generiert ein Volumen-Entwicklungs-Chart über Wochen.

    Returns:
        str: Base64-encoded PNG image
    """
    if not volumen_wochen or len(volumen_wochen) < 2:
        return None

    wochen = [w["woche"] for w in volumen_wochen]
    volumen = [w["volumen"] for w in volumen_wochen]

    fig, ax = plt.subplots(figsize=(10, 4))

    # Line chart mit Area fill
    ax.plot(wochen, volumen, marker="o", linewidth=2, color="#0d6efd", markersize=8)
    ax.fill_between(range(len(wochen)), volumen, alpha=0.3, color="#0d6efd")

    # Beschriftung
    ax.set_xlabel("Kalenderwoche", fontsize=10, fontweight="bold")
    ax.set_ylabel("Trainingsvolumen (kg)", fontsize=10, fontweight="bold")
    ax.set_title("Trainingsvolumen-Entwicklung", fontsize=12, fontweight="bold", pad=20)

    # Werte auf Punkten anzeigen
    for i, (woche, vol) in enumerate(zip(wochen, volumen)):
        ax.text(
            i,
            vol + max(volumen) * 0.03,
            f"{int(vol)}kg",
            ha="center",
            va="bottom",
            fontsize=8,
            fontweight="bold",
        )

    # Grid
    ax.grid(True, alpha=0.3, linestyle=":", linewidth=0.5)
    ax.set_axisbelow(True)

    # X-Achse lesbar machen
    plt.xticks(rotation=45, ha="right")

    plt.tight_layout()

    # Als PNG in Base64 konvertieren
    buffer = io.BytesIO()
    plt.savefig(buffer, format="png", dpi=150, bbox_inches="tight")
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.read()).decode("utf-8")
    plt.close(fig)

    return image_base64


def generate_push_pull_pie(push_saetze, pull_saetze):
    """
    Generiert ein Pie Chart für Push/Pull-Balance.

    Returns:
        str: Base64-encoded PNG image
    """
    if push_saetze == 0 and pull_saetze == 0:
        return None

    fig, ax = plt.subplots(figsize=(6, 6))

    labels = ["Push", "Pull"]
    sizes = [push_saetze, pull_saetze]
    colors = ["#ff6b6b", "#4ecdc4"]
    explode = (0.05, 0.05)

    wedges, texts, autotexts = ax.pie(
        sizes,
        explode=explode,
        labels=labels,
        colors=colors,
        autopct="%1.1f%%",
        startangle=90,
        textprops={"fontsize": 12, "fontweight": "bold"},
    )

    # Sätze-Anzahl hinzufügen
    for i, (label, size) in enumerate(zip(labels, sizes)):
        texts[i].set_text(f"{label}\n({size} Sätze)")

    ax.set_title("Push/Pull Balance", fontsize=14, fontweight="bold", pad=20)

    plt.tight_layout()

    # Als PNG in Base64 konvertieren
    buffer = io.BytesIO()
    plt.savefig(buffer, format="png", dpi=150, bbox_inches="tight")
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.read()).decode("utf-8")
    plt.close(fig)

    return image_base64
