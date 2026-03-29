"""
CSV and PDF export functionality for training data and plans.

This module handles the generation and export of training session data and
workout plans in CSV and PDF formats. It provides utilities for creating
downloadable reports of training history, statistics, and plan documentation.
"""

import base64
import csv
import io
import logging
from datetime import datetime, timedelta
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone

try:
    from xhtml2pdf import pisa
except ImportError:
    pisa = None

try:
    import qrcode
except ImportError:
    qrcode = None

from core.chart_generator import generate_body_trend_chart, generate_rpe_donut

from ..export.chart_orchestrator import generate_pdf_charts
from ..export.pdf_renderer import render_training_pdf_response
from ..export.stats_collector import calc_volume_trend_weekly, collect_pdf_stats
from ..export.weight_analysis import analyze_weight_loss_context
from ..models import MUSKELGRUPPEN, Plan, PlanUebung, Satz, Trainingseinheit, Uebung

logger = logging.getLogger(__name__)

# Backward-compatible aliases for tests that import private names
_analyze_weight_loss_context = analyze_weight_loss_context
_calc_volume_trend_weekly = calc_volume_trend_weekly


@login_required
def export_training_csv(request: HttpRequest) -> HttpResponse:
    """Export all training data as CSV.

    Exports all training sessions and sets for the current user in CSV format,
    including exercise details, weights, reps, RPE, and volume calculations.

    Args:
        request: Django request object

    Returns:
        HttpResponse: CSV file download with training data
    """
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="training_export.csv"'
    response.write("\ufeff")  # UTF-8 BOM for Excel

    writer = csv.writer(response)
    writer.writerow(
        [
            "Datum",
            "Übung",
            "Muskelgruppe",
            "Satz Nr.",
            "Gewicht (kg)",
            "Wiederholungen",
            "RPE",
            "Volumen (kg)",
            "Aufwärmsatz",
            "Notiz",
        ]
    )

    trainings = (
        Trainingseinheit.objects.filter(user=request.user)
        .prefetch_related("saetze__uebung")
        .order_by("-datum")
    )

    for training in trainings:
        for satz in training.saetze.all():
            volumen = float(satz.gewicht) * satz.wiederholungen if satz.gewicht else 0
            writer.writerow(
                [
                    training.datum.strftime("%d.%m.%Y"),
                    satz.uebung.bezeichnung,
                    satz.uebung.get_muskelgruppe_display(),
                    satz.satz_nr,
                    float(satz.gewicht) if satz.gewicht else "",
                    satz.wiederholungen,
                    satz.rpe if satz.rpe else "",
                    round(volumen, 1),
                    "Ja" if satz.ist_aufwaermsatz else "Nein",
                    satz.notiz or "",
                ]
            )

    return response


@login_required
def export_training_pdf(request: HttpRequest) -> HttpResponse:
    """Export training statistics as PDF.

    Generates a comprehensive PDF report of training statistics including
    volume progression, muscle group balance, push/pull analysis, and
    strength development using xhtml2pdf.

    Args:
        request: Django request object

    Returns:
        HttpResponse: PDF file download with training report
    """
    if not pisa:
        messages.error(request, "PDF Export nicht verfügbar - xhtml2pdf fehlt")
        logger.error("xhtml2pdf import failed")
        return redirect("training_stats")

    heute = timezone.now()
    letzte_30_tage = heute - timedelta(days=30)
    stats = collect_pdf_stats(request.user, letzte_30_tage, heute)

    # Abhängige Analysen – benötigen den vollständigen stats-Dict
    volumen_trend_weekly = calc_volume_trend_weekly(
        stats.get("volumen_wochen", []), heute=stats.get("current_date")
    )
    stats["volumen_trend_weekly"] = volumen_trend_weekly
    weight_loss_analysis = analyze_weight_loss_context(stats)
    stats["weight_loss_analysis"] = weight_loss_analysis

    muskelgruppen_stats = stats["muskelgruppen_stats"]
    volumen_wochen = stats["volumen_wochen"]
    push_saetze = stats["push_saetze"]
    pull_saetze = stats["pull_saetze"]
    muscle_heatmap, volume_chart, push_pull_chart, body_map_image = generate_pdf_charts(
        muskelgruppen_stats, volumen_wochen, push_saetze, pull_saetze
    )
    body_trend_chart = generate_body_trend_chart(stats.get("koerperwerte_chart", []))
    rpe_donut_chart = generate_rpe_donut(stats.get("rpe_verteilung", {}), stats.get("avg_rpe", 0.0))

    context = {
        "user": request.user,
        "datum": heute,
        "muscle_heatmap": muscle_heatmap,
        "volume_chart": volume_chart,
        "push_pull_chart": push_pull_chart,
        "body_map_image": body_map_image,
        "body_trend_chart": body_trend_chart,
        "rpe_donut_chart": rpe_donut_chart,
        **stats,
    }

    return render_training_pdf_response(request, context, heute)


def _generate_qr_code_base64(url: str) -> str:
    """Generiert einen QR-Code für die angegebene URL und gibt ihn als Base64-PNG zurück."""
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    qr_img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def _group_exercises_by_day(plan) -> dict:
    """Gruppiert PlanUebung-Objekte eines Plans nach Trainingstag."""
    planuebungen = (
        PlanUebung.objects.filter(plan=plan)
        .select_related("uebung")
        .order_by("trainingstag", "reihenfolge")
    )
    tage: dict = {}
    for pu in planuebungen:
        tag = pu.trainingstag or "Tag 1"
        tage.setdefault(tag, []).append(pu)
    return tage


def _generate_and_return_pdf(
    request: HttpRequest, html: str, filename: str, redirect_on_error: str
) -> HttpResponse:
    """Rendert HTML zu PDF und gibt eine Download-Response zurück.

    Bei Fehler: messages.error + redirect zu redirect_on_error.
    """
    try:
        result = BytesIO()
        pdf = pisa.pisaDocument(BytesIO(html.encode("utf-8")), result)
        if pdf.err:
            logger.error(f"PDF generation errors: {pdf.err}")
            messages.error(request, "Fehler bei PDF-Generierung")
            return redirect(redirect_on_error)
        response = HttpResponse(result.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        logger.error(f"PDF export failed: {str(e)}", exc_info=True)
        messages.error(request, "PDF-Generierung fehlgeschlagen. Bitte später erneut versuchen.")
        return redirect(redirect_on_error)


_PLAN_PDF_CSS = """
    @page { size: A4; margin: 2cm; }
    body { font-family: Arial, sans-serif; font-size: 10pt; line-height: 1.4; }
    h1 { color: #198754; font-size: 24pt; margin-bottom: 10px;
         border-bottom: 3px solid #198754; padding-bottom: 5px; }
    h2 { color: #0dcaf0; font-size: 14pt; margin-top: 20px; margin-bottom: 10px;
         border-left: 4px solid #0dcaf0; padding-left: 10px; }
    .header { display: flex; justify-content: space-between; align-items: start; margin-bottom: 20px; }
    .plan-info { flex: 1; }
    .qr-code { text-align: right; }
    .qr-code img { width: 120px; height: 120px; }
    table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
    th { background-color: #198754; color: white; padding: 8px; text-align: left; font-size: 9pt; }
    td { padding: 6px 8px; border-bottom: 1px solid #ddd; font-size: 9pt; }
    tr:nth-child(even) { background-color: #f8f9fa; }
    .badge { display: inline-block; padding: 3px 8px; border-radius: 3px;
             font-size: 8pt; font-weight: bold; }
    .badge-primary { background-color: #198754; color: white; }
    .badge-secondary { background-color: #6c757d; color: white; }
    .footer { position: fixed; bottom: 1cm; left: 2cm; right: 2cm; text-align: center;
              font-size: 8pt; color: #6c757d; border-top: 1px solid #ddd; padding-top: 5px; }
    .page-break { page-break-after: always; }
"""


def _build_plan_pdf_html(
    plan,
    tage: dict,
    qr_base64: str,
    muskelgruppen_dict: dict,
    beschreibung_html: str,
    plan_url: str,
) -> str:
    """Baut das vollständige HTML-Dokument für den Einzel-Plan-PDF-Export."""
    parts = [
        f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>{_PLAN_PDF_CSS}</style></head><body>',
        '<div class="header"><div class="plan-info">',
        f"<h1>{plan.name}</h1>",
        f"<p><strong>Beschreibung:</strong><br>{beschreibung_html}</p>",
        f'<p><strong>Erstellt:</strong> {plan.erstellt_am.strftime("%d.%m.%Y")}</p>',
        '</div><div class="qr-code">',
        f'<img src="data:image/png;base64,{qr_base64}" alt="QR Code">',
        '<p style="font-size: 8pt; color: #6c757d;">Scan für Details</p>',
        "</div></div>",
    ]
    for tag_nummer, uebungen in sorted(tage.items()):
        parts.append(
            f"<h2>{tag_nummer}</h2>"
            "<table><thead><tr>"
            "<th>#</th><th>Übung</th><th>Muskelgruppe</th><th>Sätze</th><th>Wiederholungen</th>"
            "</tr></thead><tbody>"
        )
        for idx, pu in enumerate(uebungen, 1):
            mg = muskelgruppen_dict.get(pu.uebung.muskelgruppe, pu.uebung.muskelgruppe)
            parts.append(
                f"<tr><td>{idx}</td><td><strong>{pu.uebung.bezeichnung}</strong></td>"
                f'<td><span class="badge badge-primary">{mg}</span></td>'
                f"<td>{pu.saetze_ziel or '-'}</td><td>{pu.wiederholungen_ziel or '-'}</td></tr>"
            )
        parts.append("</tbody></table>")
    parts.append(
        f'<div class="footer">HomeGym Trainingsplan | '
        f'Erstellt: {timezone.now().strftime("%d.%m.%Y %H:%M")} | {plan_url}</div>'
        "</body></html>"
    )
    return "".join(parts)


@login_required
def export_plan_pdf(request: HttpRequest, plan_id: int) -> HttpResponse:
    """Export a training plan as PDF with QR code.

    Generates a PDF document for a single training plan including all exercises
    grouped by training day, with muscle group information and a QR code for
    easy sharing.

    Args:
        request: Django request object
        plan_id: ID of the plan to export

    Returns:
        HttpResponse: PDF file download with training plan
    """
    if not pisa or not qrcode:
        messages.error(request, "PDF Export nicht verfügbar - Pakete fehlen")
        return redirect("plan_details", plan_id=plan_id)

    plan = get_object_or_404(Plan, id=plan_id, user=request.user)

    # Generate QR code + group exercises by day using helpers
    plan_url = request.build_absolute_uri(f"/plan/{plan.id}/")
    qr_base64 = _generate_qr_code_base64(plan_url)
    tage = _group_exercises_by_day(plan)
    muskelgruppen_dict = dict(MUSKELGRUPPEN)
    beschreibung_html = (plan.beschreibung or "Keine Beschreibung").replace("\n", "<br>")

    html_template = _build_plan_pdf_html(
        plan, tage, qr_base64, muskelgruppen_dict, beschreibung_html, plan_url
    )
    filename = f"plan_{plan.name.replace(' ', '_')}_{timezone.now().strftime('%Y%m%d')}.pdf"
    redirect_url = reverse("plan_details", kwargs={"plan_id": plan_id})
    return _generate_and_return_pdf(request, html_template, filename, redirect_url)


_PLAN_GROUP_PDF_CSS = """
    @page { size: A4; margin: 2cm; }
    body { font-family: Arial, sans-serif; font-size: 10pt; line-height: 1.4; }
    h1 { color: #198754; font-size: 24pt; margin-bottom: 10px;
         border-bottom: 3px solid #198754; padding-bottom: 5px; }
    h2 { color: #0dcaf0; font-size: 16pt; margin-top: 25px; margin-bottom: 10px;
         border-left: 4px solid #0dcaf0; padding-left: 10px; page-break-before: auto; }
    .header { display: flex; justify-content: space-between; align-items: start; margin-bottom: 30px; }
    .plan-info { flex: 1; }
    .qr-code { text-align: right; }
    .qr-code img { width: 120px; height: 120px; }
    .group-overview { background-color: #f8f9fa; border-left: 4px solid #198754;
                      padding: 15px; margin-bottom: 20px; }
    table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
    th { background-color: #198754; color: white; padding: 8px; text-align: left; font-size: 9pt; }
    td { padding: 6px 8px; border-bottom: 1px solid #ddd; font-size: 9pt; }
    tr:nth-child(even) { background-color: #f8f9fa; }
    .badge { display: inline-block; padding: 3px 8px; border-radius: 3px;
             font-size: 8pt; font-weight: bold; }
    .badge-primary { background-color: #198754; color: white; }
    .footer { position: fixed; bottom: 1cm; left: 2cm; right: 2cm; text-align: center;
              font-size: 8pt; color: #6c757d; border-top: 1px solid #ddd; padding-top: 5px; }
"""


def _build_group_pdf_html(
    gruppe_name: str,
    plaene,
    qr_base64: str,
    muskelgruppen_dict: dict,
    beschreibung_html: str,
    erster_plan,
    plans_url: str,
) -> str:
    """Baut das vollständige HTML-Dokument für den Gruppen-PDF-Export."""
    parts = [
        f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>{_PLAN_GROUP_PDF_CSS}</style></head><body>',
        '<div class="header"><div class="plan-info">',
        f"<h1>{gruppe_name}</h1>",
        '<div class="group-overview">',
        f"<p><strong>Trainingsgruppe:</strong> {plaene.count()} Trainingstage</p>",
        f"<p><strong>Beschreibung:</strong><br>{beschreibung_html}</p>",
        f'<p><strong>Erstellt:</strong> {erster_plan.erstellt_am.strftime("%d.%m.%Y")}</p>',
        "</div></div>",
        '<div class="qr-code">',
        f'<img src="data:image/png;base64,{qr_base64}" alt="QR Code">',
        '<p style="font-size: 8pt; color: #6c757d;">Scan für Details</p>',
        "</div></div>",
    ]
    for idx_plan, plan in enumerate(plaene, 1):
        planuebungen = (
            PlanUebung.objects.filter(plan=plan).select_related("uebung").order_by("reihenfolge")
        )
        tag_name = f"Tag {idx_plan}: {plan.name}"
        parts.append(
            f"<h2>{tag_name}</h2>"
            "<table><thead><tr>"
            '<th style="width:25px;">#</th>'
            '<th style="width:30%;">Übung</th>'
            '<th style="width:25%;">Muskelgruppe</th>'
            '<th style="width:50px;">Sätze</th>'
            '<th style="width:15%;">Wdh.</th>'
            '<th style="width:50px;">Pause</th>'
            "</tr></thead><tbody>"
        )
        for idx, pu in enumerate(planuebungen, 1):
            mg = muskelgruppen_dict.get(pu.uebung.muskelgruppe, pu.uebung.muskelgruppe)
            pause = f"{pu.pausenzeit}s" if pu.pausenzeit else "-"
            parts.append(
                f"<tr><td>{idx}</td><td><strong>{pu.uebung.bezeichnung}</strong></td>"
                f'<td><span class="badge badge-primary">{mg}</span></td>'
                f"<td>{pu.saetze_ziel or '-'}</td><td>{pu.wiederholungen_ziel or '-'}</td>"
                f'<td style="font-size:8pt;color:#6c757d;">{pause}</td></tr>'
            )
        parts.append("</tbody></table>")
    parts.append(
        f'<div class="footer">HomeGym Trainingsgruppe | '
        f'Erstellt: {timezone.now().strftime("%d.%m.%Y %H:%M")} | {plans_url}</div>'
        "</body></html>"
    )
    return "".join(parts)


@login_required
def export_plan_group_pdf(request: HttpRequest, gruppe_id: int) -> HttpResponse:
    """Export a complete training plan group as PDF.

    Generates a comprehensive PDF document for an entire training plan group,
    combining all training days into a single document with proper formatting
    and QR codes for easy sharing.

    Args:
        request: Django request object
        gruppe_id: ID of the plan group to export

    Returns:
        HttpResponse: PDF file download with complete training group
    """
    if not pisa or not qrcode:
        messages.error(request, "PDF Export nicht verfügbar - Pakete fehlen")
        return redirect("training_select_plan")

    plaene = Plan.objects.filter(user=request.user, gruppe_id=gruppe_id).order_by(
        "gruppe_reihenfolge", "name"
    )
    if not plaene.exists():
        messages.error(request, "Keine Pläne in dieser Gruppe gefunden")
        return redirect("training_select_plan")

    erster_plan = plaene.first()
    gruppe_name = erster_plan.gruppe_name or "Trainingsgruppe"
    gruppen_beschreibung = erster_plan.beschreibung or f"{gruppe_name} - Wochenplan"
    beschreibung_html = gruppen_beschreibung.replace("\n", "<br>")
    muskelgruppen_dict = dict(MUSKELGRUPPEN)

    plans_url = request.build_absolute_uri("/training/select/")
    qr_base64 = _generate_qr_code_base64(plans_url)
    html_template = _build_group_pdf_html(
        gruppe_name,
        plaene,
        qr_base64,
        muskelgruppen_dict,
        beschreibung_html,
        erster_plan,
        plans_url,
    )
    filename = f"gruppe_{gruppe_name.replace(' ', '_')}_{timezone.now().strftime('%Y%m%d')}.pdf"
    return _generate_and_return_pdf(request, html_template, filename, "training_select_plan")


# ---------------------------------------------------------------------------
# Hevy-Format Export
# ---------------------------------------------------------------------------

# Hevy CSV column order (official Hevy export format)
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

_HEVY_DATETIME_FMT = "%Y-%m-%d %H:%M:%S"


@login_required
def export_hevy_csv(request: HttpRequest) -> HttpResponse:
    """Export all training data in Hevy-compatible CSV format.

    Produces a CSV that can be imported into Hevy (and similar apps like
    Strong). Each row represents one set. Workout title falls back to the
    date string when no plan name is set.

    Args:
        request: Django request object

    Returns:
        HttpResponse: CSV file download
    """
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="homegym_hevy_export.csv"'
    response.write("\ufeff")  # UTF-8 BOM for Excel / Hevy importer

    writer = csv.writer(response)
    writer.writerow(_HEVY_HEADERS)

    trainings = (
        Trainingseinheit.objects.filter(user=request.user, abgeschlossen=True)
        .select_related("plan")
        .prefetch_related("saetze__uebung")
        .order_by("datum")
    )

    for training in trainings:
        title = training.plan.name if training.plan else training.datum.strftime("%d.%m.%Y")
        start_time = training.datum.strftime(_HEVY_DATETIME_FMT)
        # Hevy needs an end_time; estimate from dauer_minuten or start + 60 min
        if training.dauer_minuten:
            from datetime import timedelta as _td

            end_dt = training.datum + _td(minutes=training.dauer_minuten)
        else:
            end_dt = training.datum + timedelta(hours=1)
        end_time = end_dt.strftime(_HEVY_DATETIME_FMT)
        description = training.kommentar or ""

        # Group sets by exercise to build set_index per exercise within workout
        sets_by_exercise: dict = {}
        for satz in training.saetze.all():
            key = satz.uebung.bezeichnung
            sets_by_exercise.setdefault(key, []).append(satz)

        for exercise_name, saetze in sets_by_exercise.items():
            for idx, satz in enumerate(saetze):
                superset_id = f"S{satz.superset_gruppe}" if satz.superset_gruppe else ""
                set_type = "warmup" if satz.ist_aufwaermsatz else "normal"
                weight = float(satz.gewicht) if satz.gewicht else ""
                rpe = float(satz.rpe) if satz.rpe else ""
                writer.writerow(
                    [
                        title,
                        start_time,
                        end_time,
                        description,
                        exercise_name,
                        superset_id,
                        satz.notiz or "",
                        idx,  # set_index (0-based within exercise)
                        set_type,
                        weight,
                        satz.wiederholungen,
                        "",  # distance_km – not tracked
                        "",  # duration_seconds – not tracked
                        rpe,
                    ]
                )

    return response


# ---------------------------------------------------------------------------
# Hevy-Format Import
# ---------------------------------------------------------------------------

_REQUIRED_HEVY_COLS = {"title", "start_time", "exercise_title", "set_type", "weight_kg", "reps"}


def _parse_hevy_datetime(raw: str) -> datetime | None:
    """Parse Hevy datetime string. Hevy uses 'YYYY-MM-DD HH:MM:SS' or ISO."""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw.strip(), fmt)
        except ValueError:
            continue
    return None


def _match_or_create_uebung(name: str, user) -> Uebung:
    """Find an exercise by name (case-insensitive). Create a custom one if not found."""
    # Exact match first (global)
    uebung = Uebung.objects.filter(bezeichnung__iexact=name, created_by__isnull=True).first()
    if uebung:
        return uebung
    # User's own custom exercises
    uebung = Uebung.objects.filter(bezeichnung__iexact=name, created_by=user).first()
    if uebung:
        return uebung
    # Create as custom exercise
    uebung = Uebung.objects.create(
        bezeichnung=name,
        muskelgruppe="sonstige",
        created_by=user,
        is_custom=True,
    )
    logger.info("Hevy import: created custom exercise '%s' for user %s", name, user)
    return uebung


@login_required
def import_hevy_csv(request: HttpRequest) -> HttpResponse:
    """Import training data from a Hevy-compatible CSV file.

    Supports GET (show form) and POST (process file).
    POST with dry_run=1 returns a JSON preview without writing to the DB.

    Args:
        request: Django request object

    Returns:
        Rendered import form (GET) or redirect after successful import (POST)
    """
    from django.contrib import messages as django_messages
    from django.shortcuts import render

    if request.method == "GET":
        return render(request, "core/hevy_import.html")

    uploaded_file = request.FILES.get("hevy_csv")
    if not uploaded_file:
        django_messages.error(request, "Bitte eine CSV-Datei auswählen.")
        return render(request, "core/hevy_import.html")

    # Security: max 10 MB
    if uploaded_file.size > 10 * 1024 * 1024:
        django_messages.error(request, "Datei zu groß (max. 10 MB).")
        return render(request, "core/hevy_import.html")

    # Parse CSV
    try:
        raw = uploaded_file.read().decode("utf-8-sig")  # strip BOM if present
        reader = csv.DictReader(io.StringIO(raw))
        rows = list(reader)
    except Exception as exc:
        logger.warning("Hevy import CSV parse error: %s", exc)
        django_messages.error(request, f"CSV konnte nicht gelesen werden: {exc}")
        return render(request, "core/hevy_import.html")

    if not rows:
        django_messages.error(request, "Die CSV-Datei enthält keine Daten.")
        return render(request, "core/hevy_import.html")

    # Validate required columns
    actual_cols = set(rows[0].keys())
    missing = _REQUIRED_HEVY_COLS - actual_cols
    if missing:
        django_messages.error(request, f"Fehlende Spalten: {', '.join(sorted(missing))}")
        return render(request, "core/hevy_import.html")

    dry_run = request.POST.get("dry_run") == "1"

    # Group rows by (title, start_time) → one Trainingseinheit per workout
    workouts: dict[tuple, list] = {}
    for row in rows:
        key = (row["title"].strip(), row["start_time"].strip())
        workouts.setdefault(key, []).append(row)

    preview = []  # for dry-run display
    errors = []
    imported_count = 0
    set_count = 0
    new_exercises: set[str] = set()

    for (title, start_str), workout_rows in workouts.items():
        start_dt = _parse_hevy_datetime(start_str)
        if not start_dt:
            errors.append(f"Ungültiges Datum '{start_str}' – Workout '{title}' übersprungen.")
            continue

        # Make datetime timezone-aware (use server default timezone)
        from django.utils.timezone import is_aware, make_aware

        if not is_aware(start_dt):
            try:
                start_dt = make_aware(start_dt)
            except Exception:
                pass  # naive datetime is fine for older Django setups

        # Dry-run: collect preview info only
        exercises_in_workout = sorted({r["exercise_title"].strip() for r in workout_rows})
        preview.append(
            {
                "title": title,
                "date": start_dt.strftime("%d.%m.%Y %H:%M"),
                "sets": len(workout_rows),
                "exercises": exercises_in_workout,
            }
        )

        if dry_run:
            continue

        # Check for duplicate (same user + same datetime within 5 min)
        existing = Trainingseinheit.objects.filter(
            user=request.user,
            datum__range=(
                start_dt - timedelta(minutes=5),
                start_dt + timedelta(minutes=5),
            ),
        ).first()
        if existing:
            errors.append(
                f"Workout '{title}' ({start_dt.strftime('%d.%m.%Y %H:%M')}) "
                "existiert bereits – übersprungen."
            )
            continue

        # Create Trainingseinheit
        end_str = workout_rows[0].get("end_time", "").strip()
        end_dt = _parse_hevy_datetime(end_str) if end_str else None
        if end_dt and not is_aware(end_dt):
            try:
                end_dt = make_aware(end_dt)
            except Exception:
                pass
        dauer = None
        if end_dt and end_dt > start_dt:
            dauer = int((end_dt - start_dt).total_seconds() / 60)

        description = workout_rows[0].get("description", "").strip()

        training = Trainingseinheit.objects.create(
            user=request.user,
            dauer_minuten=dauer,
            kommentar=description or None,
            abgeschlossen=True,
        )
        # auto_now_add ignores explicit values -> update datum separately
        Trainingseinheit.objects.filter(pk=training.pk).update(datum=start_dt)
        training.datum = start_dt

        # Create Sätze grouped per exercise (to track satz_nr)
        exercise_satz_counter: dict[str, int] = {}
        for row in workout_rows:
            ex_name = row["exercise_title"].strip()
            if not ex_name:
                continue

            uebung = _match_or_create_uebung(ex_name, request.user)
            if uebung.is_custom and ex_name not in new_exercises:
                new_exercises.add(ex_name)

            exercise_satz_counter[ex_name] = exercise_satz_counter.get(ex_name, 0) + 1
            satz_nr = exercise_satz_counter[ex_name]

            try:
                gewicht = float(row.get("weight_kg") or 0)
            except ValueError:
                gewicht = 0.0
            try:
                wdh = int(float(row.get("reps") or 0))
            except ValueError:
                wdh = 0
            if wdh == 0:
                continue  # skip empty rows

            set_type = row.get("set_type", "normal").strip().lower()
            ist_warmup = set_type in ("warmup", "warm_up", "warm up")

            rpe_raw = row.get("rpe", "").strip()
            rpe = None
            if rpe_raw:
                try:
                    rpe_val = float(rpe_raw)
                    if 1.0 <= rpe_val <= 10.0:
                        rpe = rpe_val
                except ValueError:
                    pass

            superset_raw = row.get("superset_id", "").strip()
            superset_gruppe = 0
            if superset_raw.startswith("S") and superset_raw[1:].isdigit():
                superset_gruppe = int(superset_raw[1:])

            Satz.objects.create(
                einheit=training,
                uebung=uebung,
                satz_nr=satz_nr,
                gewicht=gewicht,
                wiederholungen=wdh,
                ist_aufwaermsatz=ist_warmup,
                rpe=rpe,
                notiz=row.get("exercise_notes", "").strip() or None,
                superset_gruppe=superset_gruppe,
            )
            set_count += 1

        imported_count += 1

    if dry_run:
        return render(
            request,
            "core/hevy_import.html",
            {
                "preview": preview,
                "preview_count": len(preview),
                "dry_run": True,
            },
        )

    if imported_count:
        msg = f"{imported_count} Training(s) mit {set_count} Sätzen importiert."
        if new_exercises:
            msg += f" {len(new_exercises)} neue Übung(en) angelegt: {', '.join(sorted(new_exercises))}."
        django_messages.success(request, msg)
    else:
        django_messages.warning(request, "Keine neuen Trainings importiert.")

    for err in errors:
        django_messages.warning(request, err)

    return redirect("dashboard")
