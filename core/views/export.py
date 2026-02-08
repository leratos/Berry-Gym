"""
CSV and PDF export functionality for training data and plans.

This module handles the generation and export of training session data and
workout plans in CSV and PDF formats. It provides utilities for creating
downloadable reports of training history, statistics, and plan documentation.
"""

import csv
import json
import logging
import base64
from io import BytesIO
from collections import defaultdict
from datetime import timedelta

from django.shortcuts import redirect, get_object_or_404
from django.http import HttpResponse
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.db.models import Count, Max, Sum, Avg, F
from django.db import models

try:
    from xhtml2pdf import pisa
except ImportError:
    pisa = None

try:
    import qrcode
except ImportError:
    qrcode = None

from ..models import (
    Trainingseinheit, KoerperWerte, Satz, Plan, PlanUebung, MUSKELGRUPPEN
)
from core.chart_generator import (
    generate_muscle_heatmap, generate_volume_chart, generate_push_pull_pie,
    generate_body_map_with_data
)

logger = logging.getLogger(__name__)


def export_training_csv(request):
    """Export all training data as CSV.

    Exports all training sessions and sets for the current user in CSV format,
    including exercise details, weights, reps, RPE, and volume calculations.

    Args:
        request: Django request object

    Returns:
        HttpResponse: CSV file download with training data
    """
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="training_export.csv"'
    response.write('\ufeff')  # UTF-8 BOM for Excel

    writer = csv.writer(response)
    writer.writerow(['Datum', 'Übung', 'Muskelgruppe', 'Satz Nr.', 'Gewicht (kg)', 'Wiederholungen', 'RPE', 'Volumen (kg)', 'Aufwärmsatz', 'Notiz'])

    trainings = Trainingseinheit.objects.filter(user=request.user).prefetch_related('saetze__uebung').order_by('-datum')

    for training in trainings:
        for satz in training.saetze.all():
            volumen = float(satz.gewicht) * satz.wiederholungen if satz.gewicht else 0
            writer.writerow([
                training.datum.strftime('%d.%m.%Y'),
                satz.uebung.bezeichnung,
                satz.uebung.get_muskelgruppe_display(),
                satz.satznummer,
                float(satz.gewicht) if satz.gewicht else '',
                satz.wiederholungen,
                satz.rpe if satz.rpe else '',
                round(volumen, 1),
                'Ja' if satz.ist_aufwaermsatz else 'Nein',
                satz.notiz or ''
            ])

    return response


@login_required
def export_training_pdf(request):
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
        messages.error(request, 'PDF Export nicht verfügbar - xhtml2pdf fehlt')
        logger.error('xhtml2pdf import failed')
        return redirect('training_stats')

    # Helper function: muscle group key to display name
    muskelgruppen_dict = dict(MUSKELGRUPPEN)

    # Collect data
    heute = timezone.now()
    letzte_30_tage = heute - timedelta(days=30)
    letzte_90_tage = heute - timedelta(days=90)

    # Training sessions
    trainings = Trainingseinheit.objects.filter(
        user=request.user,
        datum__gte=letzte_30_tage
    ).order_by('-datum')[:20]

    # Statistics
    alle_trainings = Trainingseinheit.objects.filter(user=request.user)
    gesamt_trainings = alle_trainings.count()
    trainings_30_tage = alle_trainings.filter(datum__gte=letzte_30_tage).count()

    alle_saetze = Satz.objects.filter(
        einheit__user=request.user,
        ist_aufwaermsatz=False
    )
    gesamt_saetze = alle_saetze.count()
    saetze_30_tage = alle_saetze.filter(einheit__datum__gte=letzte_30_tage).count()

    # Volume
    gesamt_volumen = sum(
        float(s.gewicht) * s.wiederholungen
        for s in alle_saetze if s.gewicht and s.wiederholungen
    )
    volumen_30_tage = sum(
        float(s.gewicht) * s.wiederholungen
        for s in alle_saetze.filter(einheit__datum__gte=letzte_30_tage)
        if s.gewicht and s.wiederholungen
    )

    # Average training frequency
    if gesamt_trainings > 0:
        erste_training = alle_trainings.order_by('datum').first()
        if erste_training:
            tage_aktiv = max(1, (heute - erste_training.datum).days)
            trainings_pro_woche = round((gesamt_trainings / tage_aktiv) * 7, 1)
        else:
            trainings_pro_woche = 0
    else:
        trainings_pro_woche = 0

    # Top exercises with more details
    top_uebungen_raw = alle_saetze.values(
        'uebung__bezeichnung',
        'uebung__muskelgruppe'
    ).annotate(
        anzahl=Count('id'),
        max_gewicht=Max('gewicht'),
        avg_gewicht=Avg('gewicht'),
        total_volumen=Sum(
            F('gewicht') * F('wiederholungen'),
            output_field=models.FloatField()
        )
    ).order_by('-anzahl')[:10]

    # Convert muscle group keys to display names
    top_uebungen = []
    for uebung in top_uebungen_raw:
        uebung_dict = dict(uebung)
        uebung_dict['muskelgruppe_display'] = muskelgruppen_dict.get(
            uebung['uebung__muskelgruppe'],
            uebung['uebung__muskelgruppe']
        )
        top_uebungen.append(uebung_dict)

    # Strength development: Top 5 exercises with measurable progression
    kraft_progression = []
    for uebung in top_uebungen[:5]:
        uebung_name = uebung['uebung__bezeichnung']
        uebung_saetze = alle_saetze.filter(
            uebung__bezeichnung=uebung_name
        ).order_by('einheit__datum')

        if uebung_saetze.count() >= 3:
            # Compare first 3 sets with last 3 sets
            erste_saetze = uebung_saetze[:3]
            letzte_saetze = list(uebung_saetze)[-3:]

            erstes_max = max((s.gewicht or 0) for s in erste_saetze)
            letztes_max = max((s.gewicht or 0) for s in letzte_saetze)

            if erstes_max > 0:
                progression_prozent = round(((float(letztes_max) - float(erstes_max)) / float(erstes_max)) * 100, 1)
                kraft_progression.append({
                    'uebung': uebung_name,
                    'start_gewicht': float(erstes_max),
                    'aktuell_gewicht': float(letztes_max),
                    'progression': float(progression_prozent),
                    'muskelgruppe': muskelgruppen_dict.get(uebung['uebung__muskelgruppe'], uebung['uebung__muskelgruppe'])
                })

    kraft_progression = sorted(kraft_progression, key=lambda x: x['progression'], reverse=True)[:5]

    # Muscle group balance with intelligent assessment
    muskelgruppen_stats = []

    # Recommended sets per muscle group per month (evidence-based)
    empfohlene_saetze = {
        'brust': (12, 20),
        'ruecken_breiter': (15, 25),
        'ruecken_unterer': (10, 18),
        'schulter_vordere': (8, 15),
        'schulter_seitliche': (12, 20),
        'schulter_hintere': (12, 20),
        'bizeps': (10, 18),
        'trizeps': (10, 18),
        'quadrizeps': (15, 25),
        'hamstrings': (12, 20),
        'glutaeus': (10, 18),
        'waden': (12, 20),
        'bauch': (12, 25),
        'unterer_ruecken': (8, 15),
    }

    for gruppe_key, gruppe_name in MUSKELGRUPPEN:
        gruppe_saetze = alle_saetze.filter(
            uebung__muskelgruppe=gruppe_key,
            einheit__datum__gte=letzte_30_tage
        )
        anzahl = gruppe_saetze.count()

        # Calculate recommendation and status
        empfehlung = empfohlene_saetze.get(gruppe_key, (12, 20))
        min_saetze, max_saetze = empfehlung

        # Data quality check: softer wording for few training sessions
        wenig_daten = trainings_30_tage < 8

        if anzahl == 0:
            status = 'nicht_trainiert'
            status_label = 'Nicht trainiert'
            if wenig_daten:
                erklaerung = f'Noch keine Sätze erfasst. Empfehlung: {min_saetze}-{max_saetze} Sätze/Monat'
            else:
                erklaerung = f'Diese Muskelgruppe wurde nicht trainiert. Empfehlung: {min_saetze}-{max_saetze} Sätze/Monat'
        elif anzahl < min_saetze:
            status = 'untertrainiert'
            if wenig_daten:
                status_label = 'Wenig trainiert'
                erklaerung = f'{anzahl} Sätze in 30 Tagen. Empfehlung: {min_saetze}-{max_saetze} Sätze/Monat (mehr Daten für genauere Analyse)'
            else:
                status_label = 'Untertrainiert'
                erklaerung = f'Nur {anzahl} Sätze in 30 Tagen. Empfehlung: {min_saetze}-{max_saetze} Sätze für optimales Wachstum'
        elif anzahl > max_saetze:
            status = 'uebertrainiert'
            if wenig_daten:
                status_label = 'Viel trainiert'
                erklaerung = f'{anzahl} Sätze - intensiver Start! Beobachte Regeneration. Empfehlung: {min_saetze}-{max_saetze} Sätze/Monat'
            else:
                status_label = 'Mögl. Übertraining'
                erklaerung = f'{anzahl} Sätze könnten zu viel sein. Empfehlung: {min_saetze}-{max_saetze} Sätze. Regeneration prüfen!'
        else:
            status = 'optimal'
            status_label = 'Optimal'
            erklaerung = f'{anzahl} Sätze liegen im optimalen Bereich ({min_saetze}-{max_saetze})'

        if anzahl > 0:
            volumen = sum(
                float(s.gewicht) * s.wiederholungen
                for s in gruppe_saetze
                if s.gewicht and s.wiederholungen
            )
            avg_rpe_result = gruppe_saetze.aggregate(Avg('rpe'))['rpe__avg']
            avg_rpe = float(avg_rpe_result) if avg_rpe_result else 0.0
            muskelgruppen_stats.append({
                'key': gruppe_key,
                'name': gruppe_name,
                'saetze': anzahl,
                'volumen': float(round(volumen, 0)),
                'avg_rpe': float(round(avg_rpe, 1)),
                'status': status,
                'status_label': status_label,
                'erklaerung': erklaerung,
                'empfehlung_min': min_saetze,
                'empfehlung_max': max_saetze,
                'prozent_von_optimal': float(round((anzahl / ((min_saetze + max_saetze) / 2)) * 100, 0))
            })

    muskelgruppen_stats = sorted(muskelgruppen_stats, key=lambda x: x['saetze'], reverse=True)

    # Push/Pull balance analysis
    push_groups = ['BRUST', 'SCHULTER_VORN', 'SCHULTER_SEIT', 'TRIZEPS']
    pull_groups = ['RUECKEN_LAT', 'RUECKEN_TRAPEZ', 'RUECKEN_UNTEN', 'RUECKEN_OBERER', 'SCHULTER_HINT', 'BIZEPS']

    push_saetze = sum(mg['saetze'] for mg in muskelgruppen_stats if mg['key'] in push_groups)
    pull_saetze = sum(mg['saetze'] for mg in muskelgruppen_stats if mg['key'] in pull_groups)

    # Balance assessment
    if push_saetze == 0 and pull_saetze == 0:
        push_pull_ratio = 0
        push_pull_bewertung = 'Keine Daten'
        push_pull_empfehlung = 'Beginne mit ausgewogenem Push- und Pull-Training für optimale Muskelentwicklung.'
    elif pull_saetze > 0:
        push_pull_ratio = round(push_saetze / pull_saetze, 2)
        if 0.9 <= push_pull_ratio <= 1.1:
            push_pull_bewertung = 'Ausgewogen'
            push_pull_empfehlung = 'Perfekt! Push/Pull-Verhältnis ist ausgeglichen.'
        elif push_pull_ratio > 1.1:
            push_pull_bewertung = 'Zu viel Push'
            push_pull_empfehlung = f'Ratio {push_pull_ratio}:1 - Mehr Pull-Training (Rücken, Bizeps) für Schultergesundheit!'
        else:
            push_pull_bewertung = 'Zu viel Pull'
            push_pull_empfehlung = f'Ratio {push_pull_ratio}:1 - Mehr Push-Training (Brust, Schultern) für Balance!'
    else:
        push_pull_ratio = 0
        push_pull_bewertung = 'Nur Push'
        push_pull_empfehlung = 'Füge Pull-Training (Rücken, Bizeps) hinzu für ausgeglichene Entwicklung!'

    push_pull_balance = {
        'push_saetze': push_saetze,
        'pull_saetze': pull_saetze,
        'ratio': push_pull_ratio,
        'bewertung': push_pull_bewertung,
        'empfehlung': push_pull_empfehlung
    }

    # Identify weaknesses (undertrained muscle groups)
    schwachstellen = [mg for mg in muskelgruppen_stats if mg['status'] in ['untertrainiert', 'nicht_trainiert']]
    schwachstellen = sorted(schwachstellen, key=lambda x: x['saetze'])[:5]

    # Intensity analysis (RPE-based)
    rpe_saetze = alle_saetze.filter(
        rpe__isnull=False,
        einheit__datum__gte=letzte_30_tage
    )
    if rpe_saetze.exists():
        avg_rpe_val = rpe_saetze.aggregate(Avg('rpe'))['rpe__avg']
        avg_rpe = float(round(avg_rpe_val, 1)) if avg_rpe_val else 0.0
        rpe_verteilung = {
            'leicht': int(rpe_saetze.filter(rpe__lte=6).count()),
            'mittel': int(rpe_saetze.filter(rpe__gt=6, rpe__lte=8).count()),
            'schwer': int(rpe_saetze.filter(rpe__gt=8).count())
        }
    else:
        avg_rpe = 0
        rpe_verteilung = {'leicht': 0, 'mittel': 0, 'schwer': 0}

    # Volume progression over last 12 weeks
    weekly_volume_pdf = defaultdict(float)

    for satz in alle_saetze.filter(ist_aufwaermsatz=False):
        if satz.gewicht and satz.wiederholungen:
            iso_year, iso_week, _ = satz.einheit.datum.isocalendar()
            week_key = f"{iso_year}-W{iso_week:02d}"
            volumen = float(satz.gewicht) * satz.wiederholungen
            weekly_volume_pdf[week_key] += volumen

    # Last 12 weeks sorted
    weekly_labels_pdf = sorted(weekly_volume_pdf.keys())[-12:]
    volumen_wochen = [
        {
            'woche': f"KW{label.split('-W')[1]}",
            'volumen': round(weekly_volume_pdf[label], 0)
        }
        for label in weekly_labels_pdf
    ]

    # Body measurements with trend
    koerperwerte_qs = KoerperWerte.objects.filter(
        user=request.user
    ).order_by('-datum')

    koerperwerte = list(koerperwerte_qs[:5])
    letzter_koerperwert = koerperwerte[0] if koerperwerte else None

    # Weight trend calculation
    gewichts_trend = None
    if len(koerperwerte) >= 2:
        neueste = koerperwerte[0]
        aelteste = koerperwerte[-1]
        gewichts_diff = neueste.gewicht - aelteste.gewicht
        gewichts_trend = {
            'diff': round(gewichts_diff, 1),
            'richtung': 'zugenommen' if gewichts_diff > 0 else 'abgenommen'
        }

    # Push/Pull balance data for template
    push_saetze = int(push_pull_balance.get('push_saetze', 0))
    pull_saetze = int(push_pull_balance.get('pull_saetze', 0))
    push_pull_ratio = float(push_pull_balance.get('ratio', 0))
    push_pull_bewertung = str(push_pull_balance.get('bewertung', ''))
    push_pull_empfehlung = str(push_pull_balance.get('empfehlung', ''))

    # Identify strengths (optimal muscle groups)
    staerken = [mg for mg in muskelgruppen_stats if mg['status'] == 'optimal']

    # Generate charts
    try:
        muscle_heatmap = generate_muscle_heatmap(muskelgruppen_stats)
        volume_chart = generate_volume_chart(volumen_wochen[-8:])
        push_pull_chart = generate_push_pull_pie(push_saetze, pull_saetze)
        body_map_image = generate_body_map_with_data(muskelgruppen_stats)
        logger.info('Charts successfully generated')
    except Exception as e:
        logger.warning(f'Chart generation failed: {str(e)}')
        muscle_heatmap = None
        volume_chart = None
        push_pull_chart = None
        body_map_image = None

    context = {
        'user': request.user,
        'datum': heute,
        'current_date': heute,
        'start_datum': letzte_30_tage,
        'end_datum': heute,
        'trainings': trainings,
        'gesamt_trainings': gesamt_trainings,
        'gesamt_saetze': gesamt_saetze,
        'gesamt_volumen': round(gesamt_volumen, 0),
        'trainings_30_tage': trainings_30_tage,
        'saetze_30_tage': saetze_30_tage,
        'volumen_30_tage': round(volumen_30_tage, 0),
        'trainings_pro_woche': trainings_pro_woche,
        'top_uebungen': top_uebungen,
        'kraft_progression': kraft_progression,
        'kraftentwicklung': kraft_progression,
        'muskelgruppen_stats': muskelgruppen_stats,
        'push_pull_balance': push_pull_balance,
        'push_saetze': push_saetze,
        'pull_saetze': pull_saetze,
        'push_pull_ratio': push_pull_ratio,
        'push_pull_bewertung': push_pull_bewertung,
        'push_pull_empfehlung': push_pull_empfehlung,
        'schwachstellen': schwachstellen,
        'staerken': staerken,
        'total_einheiten': gesamt_trainings,
        'total_saetze': gesamt_saetze,
        'total_volumen': round(gesamt_volumen, 0),
        'avg_rpe': avg_rpe,
        'rpe_verteilung': rpe_verteilung,
        'volumen_wochen': volumen_wochen[-8:],
        'muscle_heatmap': muscle_heatmap,
        'volume_chart': volume_chart,
        'push_pull_chart': push_pull_chart,
        'body_map_image': body_map_image,
        'koerperwerte': koerperwerte,
        'letzter_koerperwert': letzter_koerperwert,
        'gewichts_trend': gewichts_trend,
    }

    # Render HTML
    try:
        html_string = render_to_string('core/training_pdf_simple.html', context)
    except Exception as e:
        logger.error(f'Template rendering failed: {str(e)}', exc_info=True)
        messages.error(request, 'Template-Fehler: PDF konnte nicht erstellt werden.')
        return redirect('training_stats')

    # Generate PDF with xhtml2pdf
    try:
        result = BytesIO()
        pdf = pisa.pisaDocument(BytesIO(html_string.encode("UTF-8")), result)

        if pdf.err:
            logger.error(f'PDF generation failed with {pdf.err} errors')
            messages.error(request, 'Fehler beim PDF-Export (pisaDocument failed)')
            return redirect('training_stats')

        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="homegym_report_{heute.strftime("%Y%m%d")}.pdf"'
        return response

    except Exception as e:
        logger.error(f'PDF export failed: {str(e)}', exc_info=True)
        messages.error(request, 'PDF-Generierung fehlgeschlagen. Bitte später erneut versuchen.')
        return redirect('training_stats')


@login_required
def export_plan_pdf(request, plan_id):
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
        messages.error(request, 'PDF Export nicht verfügbar - Pakete fehlen')
        return redirect('plan_details', plan_id=plan_id)

    plan = get_object_or_404(Plan, id=plan_id, user=request.user)

    # Generate QR code (link to plan)
    plan_url = request.build_absolute_uri(f'/plan/{plan.id}/')
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(plan_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")

    # Convert QR to Base64
    buffer = BytesIO()
    qr_img.save(buffer, format='PNG')
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()

    # Group exercises by training day
    planuebungen = PlanUebung.objects.filter(plan=plan).select_related('uebung').order_by('trainingstag', 'reihenfolge')

    # Group by day
    tage = {}
    for planuebung in planuebungen:
        tag = planuebung.trainingstag or 'Tag 1'
        if tag not in tage:
            tage[tag] = []
        tage[tag].append(planuebung)

    # Muscle groups for icon mapping
    muskelgruppen_dict = dict(MUSKELGRUPPEN)

    # Format description with line breaks
    beschreibung_html = (plan.beschreibung or 'Keine Beschreibung').replace('\n', '<br>')

    # HTML template for PDF
    html_template = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{
                size: A4;
                margin: 2cm;
            }}
            body {{
                font-family: Arial, sans-serif;
                font-size: 10pt;
                line-height: 1.4;
            }}
            h1 {{
                color: #198754;
                font-size: 24pt;
                margin-bottom: 10px;
                border-bottom: 3px solid #198754;
                padding-bottom: 5px;
            }}
            h2 {{
                color: #0dcaf0;
                font-size: 14pt;
                margin-top: 20px;
                margin-bottom: 10px;
                border-left: 4px solid #0dcaf0;
                padding-left: 10px;
            }}
            .header {{
                display: flex;
                justify-content: space-between;
                align-items: start;
                margin-bottom: 20px;
            }}
            .plan-info {{
                flex: 1;
            }}
            .qr-code {{
                text-align: right;
            }}
            .qr-code img {{
                width: 120px;
                height: 120px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 20px;
            }}
            th {{
                background-color: #198754;
                color: white;
                padding: 8px;
                text-align: left;
                font-size: 9pt;
            }}
            td {{
                padding: 6px 8px;
                border-bottom: 1px solid #ddd;
                font-size: 9pt;
            }}
            tr:nth-child(even) {{
                background-color: #f8f9fa;
            }}
            .badge {{
                display: inline-block;
                padding: 3px 8px;
                border-radius: 3px;
                font-size: 8pt;
                font-weight: bold;
            }}
            .badge-primary {{
                background-color: #198754;
                color: white;
            }}
            .badge-secondary {{
                background-color: #6c757d;
                color: white;
            }}
            .footer {{
                position: fixed;
                bottom: 1cm;
                left: 2cm;
                right: 2cm;
                text-align: center;
                font-size: 8pt;
                color: #6c757d;
                border-top: 1px solid #ddd;
                padding-top: 5px;
            }}
            .page-break {{
                page-break-after: always;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="plan-info">
                <h1>{plan.name}</h1>
                <p><strong>Beschreibung:</strong><br>{beschreibung_html}</p>
                <p><strong>Erstellt:</strong> {plan.erstellt_am.strftime("%d.%m.%Y")}</p>
            </div>
            <div class="qr-code">
                <img src="data:image/png;base64,{qr_base64}" alt="QR Code">
                <p style="font-size: 8pt; color: #6c757d;">Scan für Details</p>
            </div>
        </div>
    '''

    # Add each training day
    for tag_nummer, uebungen in sorted(tage.items()):
        html_template += f'''
        <h2>{tag_nummer}</h2>
        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>Übung</th>
                    <th>Muskelgruppe</th>
                    <th>Sätze</th>
                    <th>Wiederholungen</th>
                </tr>
            </thead>
            <tbody>
        '''

        for idx, pu in enumerate(uebungen, 1):
            muskelgruppe = muskelgruppen_dict.get(pu.uebung.muskelgruppe, pu.uebung.muskelgruppe)

            html_template += f'''
                <tr>
                    <td>{idx}</td>
                    <td><strong>{pu.uebung.bezeichnung}</strong></td>
                    <td><span class="badge badge-primary">{muskelgruppe}</span></td>
                    <td>{pu.saetze_ziel or "-"}</td>
                    <td>{pu.wiederholungen_ziel or "-"}</td>
                </tr>
            '''

        html_template += '''
            </tbody>
        </table>
        '''

    # Footer
    html_template += f'''
        <div class="footer">
            HomeGym Trainingsplan | Erstellt: {timezone.now().strftime("%d.%m.%Y %H:%M")} | {plan_url}
        </div>
    </body>
    </html>
    '''

    # Generate PDF
    try:
        result = BytesIO()
        pdf = pisa.pisaDocument(BytesIO(html_template.encode('utf-8')), result)

        if pdf.err:
            logger.error(f'PDF generation errors: {pdf.err}')
            messages.error(request, 'Fehler bei PDF-Generierung')
            return redirect('plan_details', plan_id=plan_id)

        # Response with PDF
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        filename = f"plan_{plan.name.replace(' ', '_')}_{timezone.now().strftime('%Y%m%d')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        logger.error(f'Plan PDF export failed: {str(e)}', exc_info=True)
        messages.error(request, 'PDF-Generierung fehlgeschlagen. Bitte später erneut versuchen.')
        return redirect('plan_details', plan_id=plan_id)


@login_required
def export_plan_group_pdf(request, gruppe_id):
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
        messages.error(request, 'PDF Export nicht verfügbar - Pakete fehlen')
        return redirect('training_select_plan')

    # Get all plans in this group
    plaene = Plan.objects.filter(user=request.user, gruppe_id=gruppe_id).order_by('gruppe_reihenfolge', 'name')

    if not plaene.exists():
        messages.error(request, 'Keine Pläne in dieser Gruppe gefunden')
        return redirect('training_select_plan')

    # Generate QR code for plans overview
    plans_url = request.build_absolute_uri('/training/select/')
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(plans_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    qr_img.save(buffer, format='PNG')
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()

    # Group description (from first plan)
    erster_plan = plaene.first()
    gruppe_name = erster_plan.gruppe_name or 'Trainingsgruppe'
    gruppen_beschreibung = erster_plan.beschreibung or f'{gruppe_name} - Wochenplan'
    beschreibung_html = gruppen_beschreibung.replace('\n', '<br>')

    muskelgruppen_dict = dict(MUSKELGRUPPEN)

    # HTML template
    html_template = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{
                size: A4;
                margin: 2cm;
            }}
            body {{
                font-family: Arial, sans-serif;
                font-size: 10pt;
                line-height: 1.4;
            }}
            h1 {{
                color: #198754;
                font-size: 24pt;
                margin-bottom: 10px;
                border-bottom: 3px solid #198754;
                padding-bottom: 5px;
            }}
            h2 {{
                color: #0dcaf0;
                font-size: 16pt;
                margin-top: 25px;
                margin-bottom: 10px;
                border-left: 4px solid #0dcaf0;
                padding-left: 10px;
                page-break-before: auto;
            }}
            .header {{
                display: flex;
                justify-content: space-between;
                align-items: start;
                margin-bottom: 30px;
            }}
            .plan-info {{
                flex: 1;
            }}
            .qr-code {{
                text-align: right;
            }}
            .qr-code img {{
                width: 120px;
                height: 120px;
            }}
            .group-overview {{
                background-color: #f8f9fa;
                border-left: 4px solid #198754;
                padding: 15px;
                margin-bottom: 20px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 20px;
            }}
            th {{
                background-color: #198754;
                color: white;
                padding: 8px;
                text-align: left;
                font-size: 9pt;
            }}
            td {{
                padding: 6px 8px;
                border-bottom: 1px solid #ddd;
                font-size: 9pt;
            }}
            tr:nth-child(even) {{
                background-color: #f8f9fa;
            }}
            .badge {{
                display: inline-block;
                padding: 3px 8px;
                border-radius: 3px;
                font-size: 8pt;
                font-weight: bold;
            }}
            .badge-primary {{
                background-color: #198754;
                color: white;
            }}
            .footer {{
                position: fixed;
                bottom: 1cm;
                left: 2cm;
                right: 2cm;
                text-align: center;
                font-size: 8pt;
                color: #6c757d;
                border-top: 1px solid #ddd;
                padding-top: 5px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="plan-info">
                <h1>{gruppe_name}</h1>
                <div class="group-overview">
                    <p><strong>Trainingsgruppe:</strong> {plaene.count()} Trainingstage</p>
                    <p><strong>Beschreibung:</strong><br>{beschreibung_html}</p>
                    <p><strong>Erstellt:</strong> {erster_plan.erstellt_am.strftime("%d.%m.%Y")}</p>
                </div>
            </div>
            <div class="qr-code">
                <img src="data:image/png;base64,{qr_base64}" alt="QR Code">
                <p style="font-size: 8pt; color: #6c757d;">Scan für Details</p>
            </div>
        </div>
    '''

    # Add each plan (training day)
    for idx_plan, plan in enumerate(plaene, 1):
        planuebungen = PlanUebung.objects.filter(plan=plan).select_related('uebung').order_by('reihenfolge')

        tag_name = f"Tag {idx_plan}: {plan.name}"

        html_template += f'''
        <h2>{tag_name}</h2>
        <table>
            <thead>
                <tr>
                    <th style="width: 25px;">#</th>
                    <th style="width: 30%;">Übung</th>
                    <th style="width: 25%;">Muskelgruppe</th>
                    <th style="width: 50px;">Sätze</th>
                    <th style="width: 15%;">Wdh.</th>
                    <th style="width: 50px;">Pause</th>
                </tr>
            </thead>
            <tbody>
        '''

        for idx, pu in enumerate(planuebungen, 1):
            muskelgruppe = muskelgruppen_dict.get(pu.uebung.muskelgruppe, pu.uebung.muskelgruppe)
            pause = f"{pu.pausenzeit}s" if pu.pausenzeit else "-"

            html_template += f'''
                <tr>
                    <td>{idx}</td>
                    <td><strong>{pu.uebung.bezeichnung}</strong></td>
                    <td><span class="badge badge-primary">{muskelgruppe}</span></td>
                    <td>{pu.saetze_ziel or "-"}</td>
                    <td>{pu.wiederholungen_ziel or "-"}</td>
                    <td style="font-size: 8pt; color: #6c757d;">{pause}</td>
                </tr>
            '''

        html_template += '''
            </tbody>
        </table>
        '''

    # Footer
    html_template += f'''
        <div class="footer">
            HomeGym Trainingsgruppe | Erstellt: {timezone.now().strftime("%d.%m.%Y %H:%M")} | {plans_url}
        </div>
    </body>
    </html>
    '''

    # Generate PDF
    try:
        result = BytesIO()
        pdf = pisa.pisaDocument(BytesIO(html_template.encode('utf-8')), result)

        if pdf.err:
            logger.error(f'PDF generation errors: {pdf.err}')
            messages.error(request, 'Fehler bei PDF-Generierung')
            return redirect('training_select_plan')

        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        filename = f"gruppe_{gruppe_name.replace(' ', '_')}_{timezone.now().strftime('%Y%m%d')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        logger.error(f'Group PDF export failed: {str(e)}', exc_info=True)
        messages.error(request, 'PDF-Generierung fehlgeschlagen. Bitte später erneut versuchen.')
        return redirect('training_select_plan')
