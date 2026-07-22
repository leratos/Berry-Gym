"""#1060 – Harte Regeln für das PDF-Report-Template.

Hintergrund: Djangos ``{# … #}``-Kommentare gelten nur EINZEILIG. Mehrzeilige
Varianten erkennt die Template-Engine nicht – sie wurden wörtlich ins
gerenderte PDF übernommen (Prod-Report 21.07.2026: Phasen-Interna auf den
Seiten 1, 2 und 6 eines als teilbar gedachten Dokuments). Zweiter Befund:
Der Footer nutzte xhtml2pdf-Vendor-Tags (``<pdf:pagenumber/>``), die
WeasyPrint ignoriert → "Seite von" ohne Zahlen.

Regeln im Testcode statt Konvention im Kopf (analog test_empfehlung_textregeln):
1. Kein mehrzeiliger ``{#``-Kommentar im Template-Quelltext.
2. Das gerenderte HTML enthält keine ``{#``/``#}``-Sequenzen (beide Engines).
3. Seitenzahlen je Engine: WeasyPrint via ``@page``-CSS-Counter,
   xhtml2pdf via Vendor-Tags – nie beides, nie keins.
"""

from pathlib import Path
from types import SimpleNamespace

from django.template.loader import render_to_string

BASE_DIR = Path(__file__).resolve().parents[2]
TEMPLATE_PFAD = "core/templates/core/training_pdf_simple.html"


def _render(engine: str) -> str:
    """Minimal-Context-Render – fehlende Variablen rendern in Django leer,
    die Kommentar-/Footer-Regeln sind davon unabhängig prüfbar. Nur ``user``
    braucht einen Stub (Filter-Argumente wie ``default:user.username`` werfen
    bei komplett fehlender Variable)."""
    user_stub = SimpleNamespace(get_full_name=lambda: "Test User", username="test")
    return render_to_string(
        "core/training_pdf_simple.html", {"pdf_engine": engine, "user": user_stub}
    )


def test_kein_mehrzeiliger_template_kommentar_im_quelltext():
    """Regel 1: ``{#`` ohne ``#}`` auf derselben Zeile = mehrzeiliger Kommentar,
    den Django wörtlich rendert. Für Erklärtexte ``{% comment %}`` verwenden."""
    quelle = (BASE_DIR / TEMPLATE_PFAD).read_text(encoding="utf-8")
    verstoesse = [
        f"{TEMPLATE_PFAD}:{nr}: {zeile.strip()}"
        for nr, zeile in enumerate(quelle.splitlines(), start=1)
        if "{#" in zeile and "#}" not in zeile
    ]
    assert (
        not verstoesse
    ), "Mehrzeilige {#-Kommentare gefunden (rendern wörtlich ins PDF!):\n" + "\n".join(verstoesse)


def test_gerendertes_html_ohne_kommentar_sequenzen():
    """Regel 2: egal welche Engine – im Output des Templates darf keine
    Kommentar-Syntax auftauchen (Kernbefund #1060)."""
    for engine in ("weasyprint", "xhtml2pdf"):
        html = _render(engine)
        assert "{#" not in html, f"'{{#' im gerenderten HTML (engine={engine})"
        assert "#}" not in html, f"'#}}' im gerenderten HTML (engine={engine})"


def test_weasyprint_seitenzahlen_via_css_counter():
    """Regel 3a: WeasyPrint bekommt den @page-Counter und KEINE Vendor-Tags
    (die dort ignoriert würden → 'Seite von' ohne Zahlen)."""
    html = _render("weasyprint")
    assert 'counter(page) " von " counter(pages)' in html
    assert "<pdf:pagenumber" not in html
    assert "<pdf:pagecount" not in html


def test_xhtml2pdf_seitenzahlen_via_vendor_tags():
    """Regel 3b: xhtml2pdf behält die Vendor-Tags und bekommt keinen
    @page-Counter (dort unbekannte Margin-Box-Syntax)."""
    html = _render("xhtml2pdf")
    assert "<pdf:pagenumber/>" in html
    assert "<pdf:pagecount/>" in html
    assert "counter(pages)" not in html
