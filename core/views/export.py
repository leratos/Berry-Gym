"""
CSV and PDF export functionality for training data and plans.

This module handles the generation and export of training session data and
workout plans in CSV and PDF formats. It provides utilities for creating
downloadable reports of training history, statistics, and plan documentation.
"""

import base64
import csv
import logging
from collections import defaultdict
from datetime import timedelta
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from django.db.models import Avg, Count, F, Max, Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
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

from core.chart_generator import (
    generate_body_map_with_data,
    generate_muscle_heatmap,
    generate_push_pull_pie,
    generate_volume_chart,
)

from ..models import MUSKELGRUPPEN, KoerperWerte, Plan, PlanUebung, Satz, Trainingseinheit
from ..utils.advanced_stats import (
    calculate_1rm_standards,
    calculate_consistency_metrics,
    calculate_fatigue_index,
    calculate_plateau_analysis,
    calculate_rpe_quality_analysis,
)

logger = logging.getLogger(__name__)


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


_EMPFOHLENE_SAETZE: dict[str, tuple[int, int]] = {
    "brust": (12, 20),
    "ruecken_breiter": (15, 25),
    "ruecken_unterer": (10, 18),
    "schulter_vordere": (8, 15),
    "schulter_seitliche": (12, 20),
    "schulter_hintere": (12, 20),
    "bizeps": (10, 18),
    "trizeps": (10, 18),
    "quadrizeps": (15, 25),
    "hamstrings": (12, 20),
    "glutaeus": (10, 18),
    "waden": (12, 20),
    "bauch": (12, 25),
    "unterer_ruecken": (8, 15),
}

_PUSH_GROUPS = ["BRUST", "SCHULTER_VORN", "SCHULTER_SEIT", "TRIZEPS"]
_PULL_GROUPS = [
    "RUECKEN_LAT",
    "RUECKEN_TRAPEZ",
    "RUECKEN_UNTEN",
    "RUECKEN_OBERER",
    "SCHULTER_HINT",
    "BIZEPS",
]


def _muscle_status(anzahl: int, min_s: int, max_s: int, wenig_daten: bool) -> tuple[str, str, str]:
    """Return (status_key, status_label, erklaerung) for one muscle group."""
    if anzahl == 0:
        expl = (
            f"Noch keine Sätze erfasst. Empfehlung: {min_s}-{max_s} Sätze/Monat"
            if wenig_daten
            else f"Diese Muskelgruppe wurde nicht trainiert. Empfehlung: {min_s}-{max_s} Sätze/Monat"
        )
        return "nicht_trainiert", "Nicht trainiert", expl
    if anzahl < min_s:
        if wenig_daten:
            return (
                "untertrainiert",
                "Wenig trainiert",
                f"{anzahl} Sätze in 30 Tagen. Empfehlung: {min_s}-{max_s} Sätze/Monat "
                "(mehr Daten für genauere Analyse)",
            )
        return (
            "untertrainiert",
            "Untertrainiert",
            f"Nur {anzahl} Sätze in 30 Tagen. Empfehlung: {min_s}-{max_s} Sätze für optimales Wachstum",
        )
    if anzahl > max_s:
        if wenig_daten:
            return (
                "uebertrainiert",
                "Viel trainiert",
                f"{anzahl} Sätze - intensiver Start! Beobachte Regeneration. "
                f"Empfehlung: {min_s}-{max_s} Sätze/Monat",
            )
        return (
            "uebertrainiert",
            "Mögl. Übertraining",
            f"{anzahl} Sätze könnten zu viel sein. Empfehlung: {min_s}-{max_s} Sätze. Regeneration prüfen!",
        )
    return "optimal", "Optimal", f"{anzahl} Sätze liegen im optimalen Bereich ({min_s}-{max_s})"


def _collect_muscle_balance(alle_saetze, letzte_30_tage, trainings_30_tage: int) -> list[dict]:
    """Build muscle group balance stats with evidence-based set recommendations."""
    wenig_daten = trainings_30_tage < 8
    result = []
    for gruppe_key, gruppe_name in MUSKELGRUPPEN:
        gruppe_saetze = alle_saetze.filter(
            uebung__muskelgruppe=gruppe_key, einheit__datum__gte=letzte_30_tage
        )
        anzahl = gruppe_saetze.count()
        min_s, max_s = _EMPFOHLENE_SAETZE.get(gruppe_key, (12, 20))
        status, status_label, erklaerung = _muscle_status(anzahl, min_s, max_s, wenig_daten)
        if anzahl > 0:
            volumen = sum(
                float(s.gewicht) * s.wiederholungen
                for s in gruppe_saetze
                if s.gewicht and s.wiederholungen
            )
            avg_rpe_r = gruppe_saetze.aggregate(Avg("rpe"))["rpe__avg"]
            result.append(
                {
                    "key": gruppe_key,
                    "name": gruppe_name,
                    "saetze": anzahl,
                    "volumen": float(round(volumen, 0)),
                    "avg_rpe": float(round(avg_rpe_r, 1)) if avg_rpe_r else 0.0,
                    "status": status,
                    "status_label": status_label,
                    "erklaerung": erklaerung,
                    "empfehlung_min": min_s,
                    "empfehlung_max": max_s,
                    "prozent_von_optimal": float(round((anzahl / ((min_s + max_s) / 2)) * 100, 0)),
                }
            )
    return sorted(result, key=lambda x: x["saetze"], reverse=True)


def _collect_push_pull(muskelgruppen_stats: list[dict]) -> dict:
    """Compute push/pull balance and return analysis dict."""
    push = sum(mg["saetze"] for mg in muskelgruppen_stats if mg["key"] in _PUSH_GROUPS)
    pull = sum(mg["saetze"] for mg in muskelgruppen_stats if mg["key"] in _PULL_GROUPS)
    if push == 0 and pull == 0:
        ratio, bewertung, empfehlung = (
            0,
            "Keine Daten",
            "Beginne mit ausgewogenem Push- und Pull-Training für optimale Muskelentwicklung.",
        )
    elif pull > 0:
        ratio = round(push / pull, 2)
        if 0.9 <= ratio <= 1.1:
            bewertung, empfehlung = "Ausgewogen", "Perfekt! Push/Pull-Verhältnis ist ausgeglichen."
        elif ratio > 1.1:
            bewertung = "Zu viel Push"
            empfehlung = (
                f"Ratio {ratio}:1 - Mehr Pull-Training (Rücken, Bizeps) für Schultergesundheit!"
            )
        else:
            bewertung = "Zu viel Pull"
            empfehlung = f"Ratio {ratio}:1 - Mehr Push-Training (Brust, Schultern) für Balance!"
    else:
        ratio, bewertung, empfehlung = (
            0,
            "Nur Push",
            "Füge Pull-Training (Rücken, Bizeps) hinzu für ausgeglichene Entwicklung!",
        )
    return {
        "push_saetze": push,
        "pull_saetze": pull,
        "ratio": ratio,
        "bewertung": bewertung,
        "empfehlung": empfehlung,
    }


def _collect_strength_progression(
    alle_saetze, top_uebungen: list, muskelgruppen_dict: dict
) -> list[dict]:
    """Extract top-5 exercises with measurable strength progression (first vs last 3 sets)."""
    result = []
    for uebung in top_uebungen[:5]:
        uebung_name = uebung["uebung__bezeichnung"]
        uebung_saetze = alle_saetze.filter(uebung__bezeichnung=uebung_name).order_by(
            "einheit__datum"
        )
        if uebung_saetze.count() < 3:
            continue
        erste_saetze = uebung_saetze[:3]
        letzte_saetze = list(uebung_saetze)[-3:]
        erstes_max = max((s.gewicht or 0) for s in erste_saetze)
        letztes_max = max((s.gewicht or 0) for s in letzte_saetze)
        if erstes_max > 0:
            progression_prozent = round(
                ((float(letztes_max) - float(erstes_max)) / float(erstes_max)) * 100, 1
            )
            result.append(
                {
                    "uebung": uebung_name,
                    "start_gewicht": float(erstes_max),
                    "aktuell_gewicht": float(letztes_max),
                    "progression": float(progression_prozent),
                    "muskelgruppe": muskelgruppen_dict.get(
                        uebung["uebung__muskelgruppe"], uebung["uebung__muskelgruppe"]
                    ),
                }
            )
    return sorted(result, key=lambda x: x["progression"], reverse=True)[:5]


def _collect_intensity_data(alle_saetze, letzte_30_tage) -> tuple[float, dict]:
    """Return (avg_rpe, rpe_verteilung) for the last 30 days."""
    rpe_saetze = alle_saetze.filter(rpe__isnull=False, einheit__datum__gte=letzte_30_tage)
    if not rpe_saetze.exists():
        return 0.0, {"leicht": 0, "mittel": 0, "schwer": 0}
    avg_rpe_val = rpe_saetze.aggregate(Avg("rpe"))["rpe__avg"]
    avg_rpe = float(round(avg_rpe_val, 1)) if avg_rpe_val else 0.0
    rpe_verteilung = {
        "leicht": int(rpe_saetze.filter(rpe__lte=6).count()),
        "mittel": int(rpe_saetze.filter(rpe__gt=6, rpe__lte=8).count()),
        "schwer": int(rpe_saetze.filter(rpe__gt=8).count()),
    }
    return avg_rpe, rpe_verteilung


def _collect_weekly_volume_pdf(alle_saetze) -> list[dict]:
    """Build weekly volume progression (last 12 weeks) for PDF report."""
    weekly_volume: dict[str, float] = defaultdict(float)
    for satz in alle_saetze.filter(ist_aufwaermsatz=False):
        if satz.gewicht and satz.wiederholungen:
            iso_year, iso_week, _ = satz.einheit.datum.isocalendar()
            week_key = f"{iso_year}-W{iso_week:02d}"
            weekly_volume[week_key] += float(satz.gewicht) * satz.wiederholungen
    labels = sorted(weekly_volume.keys())[-12:]
    return [
        {"woche": f"KW{label.split('-W')[1]}", "volumen": round(weekly_volume[label], 0)}
        for label in labels
    ]


def _collect_weight_trend(koerperwerte: list) -> dict | None:
    """Return weight trend dict (diff + direction) or None if insufficient data."""
    if len(koerperwerte) < 2:
        return None
    gewichts_diff = koerperwerte[0].gewicht - koerperwerte[-1].gewicht
    return {
        "diff": round(gewichts_diff, 1),
        "richtung": "zugenommen" if gewichts_diff > 0 else "abgenommen",
    }


def _generate_pdf_charts(
    muskelgruppen_stats: list[dict], volumen_wochen: list[dict], push_saetze: int, pull_saetze: int
) -> tuple:
    """Generate chart images for PDF; returns (muscle_heatmap, volume_chart, push_pull_chart, body_map).
    Returns (None, None, None, None) if generation fails."""
    try:
        muscle_heatmap = generate_muscle_heatmap(muskelgruppen_stats)
        volume_chart = generate_volume_chart(volumen_wochen[-8:])
        push_pull_chart = generate_push_pull_pie(push_saetze, pull_saetze)
        body_map_image = generate_body_map_with_data(muskelgruppen_stats)
        logger.info("Charts successfully generated")
        return muscle_heatmap, volume_chart, push_pull_chart, body_map_image
    except Exception as e:
        logger.warning(f"Chart generation failed: {str(e)}")
        return None, None, None, None


def _calc_trainings_per_week(alle_trainings, heute) -> float:
    """Calculate average training frequency per week from all sessions."""
    gesamt = alle_trainings.count()
    if gesamt == 0:
        return 0.0
    erste = alle_trainings.order_by("datum").first()
    if not erste:
        return 0.0
    tage_aktiv = max(1, (heute - erste.datum).days)
    return round((gesamt / tage_aktiv) * 7, 1)


def _build_top_uebungen(alle_saetze, muskelgruppen_dict: dict) -> list[dict]:
    """Query top 10 exercises by set count, annotated with display name."""
    raw = (
        alle_saetze.values("uebung__bezeichnung", "uebung__muskelgruppe")
        .annotate(
            anzahl=Count("id"),
            max_gewicht=Max("gewicht"),
            avg_gewicht=Avg("gewicht"),
            total_volumen=Sum(F("gewicht") * F("wiederholungen"), output_field=models.FloatField()),
        )
        .order_by("-anzahl")[:10]
    )
    result = []
    for uebung in raw:
        uebung_dict = dict(uebung)
        uebung_dict["muskelgruppe_display"] = muskelgruppen_dict.get(
            uebung["uebung__muskelgruppe"], uebung["uebung__muskelgruppe"]
        )
        result.append(uebung_dict)
    return result


def _render_training_pdf_response(request: HttpRequest, context: dict, heute) -> HttpResponse:
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
        response["Content-Disposition"] = (
            f'attachment; filename="homegym_report_{heute.strftime("%Y%m%d")}.pdf"'
        )
        return response
    except Exception as e:
        logger.error(f"PDF export failed: {str(e)}", exc_info=True)
        messages.error(request, "PDF-Generierung fehlgeschlagen. Bitte später erneut versuchen.")
        return redirect("training_stats")


def _sum_volume(saetze_qs) -> float:
    """Summiert Volumen (Gewicht × Wdh) aus einem Satz-QuerySet."""
    return sum(
        float(s.gewicht) * s.wiederholungen for s in saetze_qs if s.gewicht and s.wiederholungen
    )


def _collect_pdf_stats(user, letzte_30_tage, heute) -> dict:
    """Sammelt alle Statistiken für den PDF-Report.

    Returns dict mit allen Daten für den Template-Kontext.
    """
    muskelgruppen_dict = dict(MUSKELGRUPPEN)

    trainings = Trainingseinheit.objects.filter(user=user, datum__gte=letzte_30_tage).order_by(
        "-datum"
    )[:20]

    alle_trainings = Trainingseinheit.objects.filter(user=user)
    gesamt_trainings = alle_trainings.count()
    trainings_30_tage = alle_trainings.filter(datum__gte=letzte_30_tage).count()

    alle_saetze = Satz.objects.filter(
        einheit__user=user,
        ist_aufwaermsatz=False,
        einheit__ist_deload=False,
    )
    gesamt_saetze = alle_saetze.count()
    saetze_30_tage = alle_saetze.filter(einheit__datum__gte=letzte_30_tage).count()

    gesamt_volumen = _sum_volume(alle_saetze)
    volumen_30_tage = _sum_volume(alle_saetze.filter(einheit__datum__gte=letzte_30_tage))

    trainings_pro_woche = _calc_trainings_per_week(alle_trainings, heute)
    consistency_metrics = calculate_consistency_metrics(alle_trainings)
    top_uebungen = _build_top_uebungen(alle_saetze, muskelgruppen_dict)
    plateau_analysis = calculate_plateau_analysis(alle_saetze, top_uebungen)
    kraft_progression = _collect_strength_progression(alle_saetze, top_uebungen, muskelgruppen_dict)
    muskelgruppen_stats = _collect_muscle_balance(alle_saetze, letzte_30_tage, trainings_30_tage)
    push_pull_balance = _collect_push_pull(muskelgruppen_stats)

    schwachstellen_status = {"untertrainiert", "nicht_trainiert"}
    schwachstellen = sorted(
        [mg for mg in muskelgruppen_stats if mg["status"] in schwachstellen_status],
        key=lambda x: x["saetze"],
    )[:5]
    staerken = [mg for mg in muskelgruppen_stats if mg["status"] == "optimal"]

    avg_rpe, rpe_verteilung = _collect_intensity_data(alle_saetze, letzte_30_tage)
    rpe_saetze = alle_saetze.filter(rpe__isnull=False, einheit__datum__gte=letzte_30_tage)
    rpe_quality = calculate_rpe_quality_analysis(alle_saetze)
    volumen_wochen = _collect_weekly_volume_pdf(alle_saetze)
    fatigue_analysis = calculate_fatigue_index(volumen_wochen, rpe_saetze, alle_trainings)

    koerperwerte_qs = KoerperWerte.objects.filter(user=user).order_by("-datum")
    koerperwerte = list(koerperwerte_qs[:5])
    letzter_koerperwert = koerperwerte[0] if koerperwerte else None
    user_gewicht = letzter_koerperwert.gewicht if letzter_koerperwert else None
    rm_standards = calculate_1rm_standards(alle_saetze, top_uebungen, user_gewicht)
    gewichts_trend = _collect_weight_trend(koerperwerte)

    push_saetze = int(push_pull_balance.get("push_saetze", 0))
    pull_saetze = int(push_pull_balance.get("pull_saetze", 0))

    return {
        "start_datum": letzte_30_tage,
        "end_datum": heute,
        "current_date": heute,
        "trainings": trainings,
        "gesamt_trainings": gesamt_trainings,
        "gesamt_saetze": gesamt_saetze,
        "gesamt_volumen": round(gesamt_volumen, 0),
        "trainings_30_tage": trainings_30_tage,
        "saetze_30_tage": saetze_30_tage,
        "volumen_30_tage": round(volumen_30_tage, 0),
        "trainings_pro_woche": trainings_pro_woche,
        "top_uebungen": top_uebungen,
        "kraft_progression": kraft_progression,
        "kraftentwicklung": kraft_progression,
        "muskelgruppen_stats": muskelgruppen_stats,
        "push_pull_balance": push_pull_balance,
        "push_saetze": push_saetze,
        "pull_saetze": pull_saetze,
        "push_pull_ratio": float(push_pull_balance.get("ratio", 0)),
        "push_pull_bewertung": str(push_pull_balance.get("bewertung", "")),
        "push_pull_empfehlung": str(push_pull_balance.get("empfehlung", "")),
        "schwachstellen": schwachstellen,
        "staerken": staerken,
        "total_einheiten": gesamt_trainings,
        "total_saetze": gesamt_saetze,
        "total_volumen": round(gesamt_volumen, 0),
        "avg_rpe": avg_rpe,
        "rpe_verteilung": rpe_verteilung,
        "volumen_wochen": volumen_wochen[-8:],
        "koerperwerte": koerperwerte,
        "letzter_koerperwert": letzter_koerperwert,
        "gewichts_trend": gewichts_trend,
        "plateau_analysis": plateau_analysis,
        "consistency_metrics": consistency_metrics,
        "fatigue_analysis": fatigue_analysis,
        "rm_standards": rm_standards,
        "rpe_quality": rpe_quality,
    }


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
    stats = _collect_pdf_stats(request.user, letzte_30_tage, heute)

    muskelgruppen_stats = stats["muskelgruppen_stats"]
    volumen_wochen = stats["volumen_wochen"]
    push_saetze = stats["push_saetze"]
    pull_saetze = stats["pull_saetze"]
    muscle_heatmap, volume_chart, push_pull_chart, body_map_image = _generate_pdf_charts(
        muskelgruppen_stats, volumen_wochen, push_saetze, pull_saetze
    )

    context = {
        "user": request.user,
        "datum": heute,
        "muscle_heatmap": muscle_heatmap,
        "volume_chart": volume_chart,
        "push_pull_chart": push_pull_chart,
        "body_map_image": body_map_image,
        **stats,
    }

    return _render_training_pdf_response(request, context, heute)


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
