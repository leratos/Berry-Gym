"""
PDF rendering for training reports.

Engine-Auswahl (Phase „WeasyPrint-Engine"):
- ``settings.PDF_ENGINE`` (env ``PDF_ENGINE``) wählt die primäre Engine.
  Default ``xhtml2pdf`` (Bestand). ``weasyprint`` aktiviert die CSS-Engine
  mit echtem ``@font-face`` (Source-Fonts + Status-Glyphen).
- WeasyPrint-Fehler/-Nichtverfügbarkeit → automatischer Fallback auf
  xhtml2pdf (Template wird dafür mit ``pdf_engine='xhtml2pdf'`` neu gerendert,
  damit der xhtml2pdf-inkompatible ``@font-face``-Block ausgeblendet bleibt).
"""

import logging
import os
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.conf import settings
from django.contrib import messages
from django.contrib.staticfiles import finders
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.template.loader import render_to_string

try:
    from xhtml2pdf import pisa
except ImportError:
    pisa = None

try:
    import weasyprint
except Exception:  # ImportError ODER fehlende native Libs (Pango/GLib)
    weasyprint = None

logger = logging.getLogger(__name__)


def _weasyprint_url_fetcher(url: str):
    """Löst Django-Static-URLs (die Font-TTFs) für WeasyPrint auf das
    Dateisystem auf – ohne HTTP-Round-Trip. base64-``data:``-URIs (Charts,
    Body-Map) gehen unverändert an den Default-Fetcher."""
    from weasyprint import default_url_fetcher

    try:
        path = unquote(urlparse(url).path or "")
        marker = (settings.STATIC_URL or "static/").strip("/")  # "static"
        idx = path.find(marker + "/")
        if idx != -1:
            rel = path[idx + len(marker) + 1 :]
            fs = finders.find(rel)
            if not fs and getattr(settings, "STATIC_ROOT", None):
                candidate = os.path.join(settings.STATIC_ROOT, rel)
                if os.path.exists(candidate):
                    fs = candidate
            if fs and os.path.exists(fs):
                return default_url_fetcher(Path(fs).as_uri())
    except Exception:
        pass
    return default_url_fetcher(url)


def _render_pdf_bytes(request: HttpRequest, context: dict) -> bytes:
    """Rendert das Report-Template zu PDF-Bytes. WeasyPrint primär (falls
    konfiguriert + verfügbar), sonst/­bei Fehler xhtml2pdf. Wirft bei totalem
    Fehlschlag, der Aufrufer fängt das ab."""
    engine = str(getattr(settings, "PDF_ENGINE", "xhtml2pdf")).lower()

    def _html(engine_name: str) -> str:
        return render_to_string(
            "core/training_pdf_simple.html", {**context, "pdf_engine": engine_name}
        )

    if engine == "weasyprint" and weasyprint is not None:
        try:
            html_string = _html("weasyprint")
            return weasyprint.HTML(
                string=html_string,
                base_url=request.build_absolute_uri("/"),
                url_fetcher=_weasyprint_url_fetcher,
            ).write_pdf()
        except Exception as e:
            logger.warning(
                "WeasyPrint-PDF fehlgeschlagen, Fallback auf xhtml2pdf: %s", e, exc_info=True
            )

    if pisa is None:
        raise RuntimeError("Keine PDF-Engine verfügbar (xhtml2pdf nicht importierbar).")
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(_html("xhtml2pdf").encode("UTF-8")), result)
    if pdf.err:
        raise RuntimeError(f"xhtml2pdf pisaDocument meldete {pdf.err} Fehler.")
    return result.getvalue()


def render_training_pdf_response(request: HttpRequest, context: dict, heute) -> HttpResponse:
    """Render training PDF template and return PDF download response.

    Handles both template rendering errors and PDF-engine errors, returning a
    redirect to training_stats with an error message on failure.
    """
    try:
        pdf_bytes = _render_pdf_bytes(request, context)
    except Exception as e:
        logger.error(f"PDF export failed: {str(e)}", exc_info=True)
        messages.error(request, "PDF-Generierung fehlgeschlagen. Bitte später erneut versuchen.")
        return redirect("training_stats")

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    username = request.user.username
    start = context.get("start_datum")
    end = context.get("end_datum")
    if start and end:
        filename = (
            f"TrainingReport_{username}_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}.pdf"
        )
    else:
        filename = f"TrainingReport_{username}_{heute.strftime('%Y%m%d')}.pdf"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
