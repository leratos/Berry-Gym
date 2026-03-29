"""
PDF rendering for training reports.

Handles HTML template rendering and xhtml2pdf PDF generation,
including error handling and response construction.
"""

import logging
from io import BytesIO

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.template.loader import render_to_string

try:
    from xhtml2pdf import pisa
except ImportError:
    pisa = None

logger = logging.getLogger(__name__)


def render_training_pdf_response(request: HttpRequest, context: dict, heute) -> HttpResponse:
    """Render training PDF template and return PDF download response.

    Handles both template rendering errors and xhtml2pdf generation errors,
    returning redirect to training_stats with error message on failure.
    """
    try:
        html_string = render_to_string("core/training_pdf_simple.html", context)
    except Exception as e:
        logger.error(f"Template rendering failed: {str(e)}", exc_info=True)
        messages.error(request, "Template-Fehler: PDF konnte nicht erstellt werden.")
        return redirect("training_stats")

    try:
        result = BytesIO()
        pdf = pisa.pisaDocument(BytesIO(html_string.encode("UTF-8")), result)
        if pdf.err:
            logger.error(f"PDF generation failed with {pdf.err} errors")
            messages.error(request, "Fehler beim PDF-Export (pisaDocument failed)")
            return redirect("training_stats")
        response = HttpResponse(result.getvalue(), content_type="application/pdf")
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
    except Exception as e:
        logger.error(f"PDF export failed: {str(e)}", exc_info=True)
        messages.error(request, "PDF-Generierung fehlgeschlagen. Bitte später erneut versuchen.")
        return redirect("training_stats")
