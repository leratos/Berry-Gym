"""
Module for core training session execution and set management.

Handles training session workflows including:
- Selection and display of training plans
- Starting training sessions with pre-configured exercises
- Managing individual sets during training (add, update, delete)
- Finishing training sessions with summary statistics and AI suggestions
"""

import re
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Count, Max, Sum, Avg, F, Q
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods

from ..models import (
    Trainingseinheit, Uebung, Satz, Plan, PlanUebung, UserProfile
)

logger = logging.getLogger(__name__)


@login_required
def training_select_plan(request):
    """Zeigt alle verfügbaren Pläne zur Auswahl an. Priorisiert aktive Plan-Gruppe."""
    from collections import OrderedDict

    # Filter-Parameter (eigene, public oder shared)
    filter_type = request.GET.get('filter', 'eigene')

    if filter_type == 'public':
        # Öffentliche Pläne von allen Usern (außer eigene)
        plaene = Plan.objects.filter(is_public=True).exclude(user=request.user).order_by('gruppe_name', 'gruppe_reihenfolge', 'name')
    elif filter_type == 'shared':
        # Mit mir geteilte Pläne (von Trainingspartnern)
        plaene = request.user.shared_plans.all().order_by('gruppe_name', 'gruppe_reihenfolge', 'name')
    else:
        # Eigene Pläne (Standard) - sortiert nach Reihenfolge innerhalb Gruppe
        plaene = Plan.objects.filter(user=request.user).order_by('gruppe_name', 'gruppe_reihenfolge', 'name')

    # Aktive Plan-Gruppe ermitteln
    active_group_id = None
    active_group_name = None
    try:
        profile = request.user.profile
        if profile.active_plan_group:
            active_group_id = str(profile.active_plan_group)
            # Prüfe ob Gruppe noch existiert
            active_group_plan = Plan.objects.filter(
                user=request.user, gruppe_id=profile.active_plan_group
            ).first()
            if active_group_plan:
                active_group_name = active_group_plan.gruppe_name or 'Unbenannte Gruppe'
            else:
                active_group_id = None
    except UserProfile.DoesNotExist:
        pass

    # Gruppiere Pläne nach gruppe_id (echte Datenbankbeziehung)
    # Aktive Gruppe zuerst, dann Rest
    active_plan_gruppen = OrderedDict()
    plan_gruppen = OrderedDict()
    einzelne_plaene = []

    for plan in plaene:
        if plan.gruppe_id:
            gruppe_key = str(plan.gruppe_id)
            # Entscheide ob aktiv oder normal
            target = active_plan_gruppen if gruppe_key == active_group_id else plan_gruppen
            if gruppe_key not in target:
                target[gruppe_key] = {
                    'name': plan.gruppe_name or 'Unbenannte Gruppe',
                    'plaene': []
                }
            target[gruppe_key]['plaene'].append(plan)
        else:
            einzelne_plaene.append(plan)

    # Zähle geteilte Pläne für Badge
    shared_count = request.user.shared_plans.count()

    context = {
        'plaene': plaene,  # Für Fallback
        'active_plan_gruppen': active_plan_gruppen,  # Aktive Gruppe (priorisiert)
        'active_group_name': active_group_name,
        'plan_gruppen': plan_gruppen,  # Andere gruppierte Pläne
        'einzelne_plaene': einzelne_plaene,  # Nicht gruppierte Pläne
        'filter_type': filter_type,
        'shared_count': shared_count
    }
    return render(request, 'core/training_select_plan.html', context)


def plan_details(request, plan_id):
    """Zeigt Details eines Trainingsplans mit allen Übungen."""
    # Zugriff auf: eigene Pläne, öffentliche Pläne, oder mit mir geteilte Pläne
    plan = get_object_or_404(
        Plan,
        Q(user=request.user) | Q(is_public=True) | Q(shared_with=request.user),
        id=plan_id
    )

    # Prüfe ob User der Owner ist
    is_owner = plan.user == request.user
    plan_uebungen = plan.uebungen.all().order_by('reihenfolge')

    # Für jede Übung das letzte verwendete Gewicht holen (für Vorschau)
    uebungen_mit_historie = []
    for plan_uebung in plan_uebungen:
        letzter_satz = Satz.objects.filter(
            uebung=plan_uebung.uebung,
            ist_aufwaermsatz=False
        ).order_by('-einheit__datum').first()

        uebungen_mit_historie.append({
            'plan_uebung': plan_uebung,
            'letztes_gewicht': letzter_satz.gewicht if letzter_satz else None,
            'letzte_wdh': letzter_satz.wiederholungen if letzter_satz else None,
        })

    context = {
        'plan': plan,
        'uebungen_mit_historie': uebungen_mit_historie,
        'is_owner': is_owner,
    }
    return render(request, 'core/plan_details.html', context)


def training_start(request, plan_id=None):
    """Startet Training. Wenn plan_id da ist, werden Übungen vor-angelegt."""
    training = Trainingseinheit.objects.create(user=request.user)

    # Deload-Erkennung mit konfigurierbaren Parametern
    is_deload = False
    deload_vol_factor = 0.8
    deload_weight_factor = 0.9
    deload_rpe_target = 7.0

    if plan_id:
        plan = get_object_or_404(Plan, id=plan_id, user=request.user)
        training.plan = plan
        training.save()

        # Zyklus-Tracking: cycle_start_date setzen beim ersten Training mit aktiver Gruppe
        try:
            profile = request.user.profile
            if (profile.active_plan_group
                    and plan.gruppe_id
                    and str(plan.gruppe_id) == str(profile.active_plan_group)):
                if not profile.cycle_start_date:
                    profile.cycle_start_date = timezone.now().date()
                    profile.save()
                is_deload = profile.is_deload_week()
                deload_vol_factor = profile.deload_volume_factor
                deload_weight_factor = profile.deload_weight_factor
                deload_rpe_target = profile.deload_rpe_target
        except UserProfile.DoesNotExist:
            pass

        # Wir gehen alle Übungen im Plan durch
        for plan_uebung in plan.uebungen.all().order_by('reihenfolge'):
            uebung = plan_uebung.uebung

            # SMART GHOSTING: Wir schauen, was du letztes Mal gemacht hast
            letzter_satz = Satz.objects.filter(einheit__user=request.user, uebung=uebung, ist_aufwaermsatz=False).order_by('-einheit__datum', '-satz_nr').first()

            # Gewicht: Historie gewinnt (Ghosting), da im Plan oft kein kg steht
            start_gewicht = letzter_satz.gewicht if letzter_satz else 0

            # Wiederholungen: PLAN gewinnt vor Historie!
            start_wdh = 0

            # Versuch 1: Wir lesen die Zahl aus dem Plan (z.B. "12" oder "8-12")
            ziel_text = plan_uebung.wiederholungen_ziel
            # re.search sucht die erste Zahl im Text (bounded for safety)
            match = re.search(r'\d{1,4}', str(ziel_text)) if ziel_text else None

            if match:
                start_wdh = int(match.group())
            # Versuch 2: Wenn im Plan nix steht, nehmen wir die Historie
            elif letzter_satz:
                start_wdh = letzter_satz.wiederholungen

            # Anzahl der Sätze aus dem Plan holen
            anzahl_saetze = plan_uebung.saetze_ziel

            # DELOAD-ANPASSUNGEN: Volumen & Gewicht gemäß Profil-Einstellungen reduzieren
            if is_deload:
                # Sätze reduzieren (z.B. Faktor 0.8: 4 -> 3, mindestens 2)
                anzahl_saetze = max(2, int(anzahl_saetze * deload_vol_factor))
                # Gewicht reduzieren (z.B. Faktor 0.9 = -10%)
                start_gewicht = round(float(start_gewicht) * deload_weight_factor, 1)

            # Superset-Gruppe aus dem Plan übernehmen
            superset_gruppe = plan_uebung.superset_gruppe

            # Wir erstellen so viele Platzhalter-Sätze, wie im Plan stehen
            for i in range(1, anzahl_saetze + 1):
                Satz.objects.create(
                    einheit=training,
                    uebung=uebung,
                    satz_nr=i,
                    gewicht=start_gewicht,
                    wiederholungen=start_wdh,
                    ist_aufwaermsatz=False,
                    superset_gruppe=superset_gruppe
                )

        if is_deload:
            vol_pct = int((1 - deload_vol_factor) * 100)
            weight_pct = int((1 - deload_weight_factor) * 100)
            messages.info(request, f'Deload-Woche: Volumen -{vol_pct}%, Gewicht -{weight_pct}% automatisch reduziert. Ziel-RPE: {deload_rpe_target}')

    return redirect('training_session', training_id=training.id)


@login_required
def training_session(request, training_id):
    training = get_object_or_404(Trainingseinheit, id=training_id, user=request.user)

    # Sortieren für Gruppierung: Erst Muskelgruppe, dann Übungsname
    uebungen = Uebung.objects.filter(
        Q(is_custom=False) | Q(created_by=request.user)
    ).order_by('muskelgruppe', 'bezeichnung')

    # Sortierung nach Plan-Reihenfolge wenn Training aus Plan gestartet wurde
    if training.plan:
        # Erstelle eine Map von uebung_id zu reihenfolge aus dem Plan
        plan_reihenfolge = {pu.uebung_id: pu.reihenfolge for pu in training.plan.uebungen.all()}
        # Hole alle Sätze und sortiere nach Plan-Reihenfolge, dann Satz-Nummer
        saetze = sorted(
            training.saetze.all(),
            key=lambda s: (plan_reihenfolge.get(s.uebung_id, 999), s.satz_nr)
        )
    else:
        # Fallback: alphabetisch nach Übungsname
        saetze = training.saetze.all().order_by('uebung__bezeichnung', 'satz_nr')

    # Volumen berechnen (nur Arbeitssätze, keine Warmups)
    total_volume = 0
    arbeitssaetze = training.saetze.filter(ist_aufwaermsatz=False)
    for satz in arbeitssaetze:
        total_volume += float(satz.gewicht) * satz.wiederholungen

    # Zielwerte aus dem Plan laden (wenn vorhanden)
    plan_ziele = {}
    if training.plan:
        for pu in training.plan.uebungen.all():
            plan_ziele[pu.uebung_id] = {
                'saetze_ziel': pu.saetze_ziel,
                'wiederholungen_ziel': pu.wiederholungen_ziel
            }

    # Gewichtsempfehlungen für alle Übungen berechnen (auch ohne Plan!)
    gewichts_empfehlungen = {}

    # Übungen im aktuellen Training sammeln (aus QuerySet, nicht aus sortierter Liste)
    uebungen_im_training = set(training.saetze.values_list('uebung_id', flat=True).distinct())

    # Wenn Plan vorhanden, auch Plan-Übungen einschließen
    if training.plan:
        uebungen_im_training.update(training.plan.uebungen.values_list('uebung_id', flat=True))

    for uebung_id in uebungen_im_training:
        # Letzten echten Satz dieser Übung finden (aus vorherigen Trainings)
        letzter_satz = Satz.objects.filter(
            einheit__user=request.user,
            uebung_id=uebung_id,
            ist_aufwaermsatz=False,
            einheit__ist_deload=False,
        ).exclude(einheit=training).order_by('-einheit__datum', '-satz_nr').first()

        if letzter_satz:
            empfohlenes_gewicht = float(letzter_satz.gewicht)
            empfohlene_wdh = letzter_satz.wiederholungen

            # Ziel-Wiederholungen: Aus Plan falls vorhanden, sonst Standard 8-12
            ziel_wdh_str = "8-12"  # Standard
            plan_pausenzeit = None
            if training.plan:
                pu = training.plan.uebungen.filter(uebung_id=uebung_id).first()
                if pu and pu.wiederholungen_ziel:
                    ziel_wdh_str = pu.wiederholungen_ziel
                if pu and hasattr(pu, 'pausenzeit') and pu.pausenzeit:
                    plan_pausenzeit = pu.pausenzeit

            try:
                if '-' in ziel_wdh_str:
                    ziel_wdh_max = int(ziel_wdh_str.split('-')[1])
                    ziel_wdh_min = int(ziel_wdh_str.split('-')[0])
                else:
                    ziel_wdh_max = int(ziel_wdh_str)
                    ziel_wdh_min = int(ziel_wdh_str)
            except ValueError:
                ziel_wdh_max = 12
                ziel_wdh_min = 8

            # Progressive Overload Logik - berücksichtigt Planziel
            if letzter_satz.rpe and float(letzter_satz.rpe) < 7:
                # RPE zu leicht → mehr Gewicht
                empfohlenes_gewicht += 2.5
                hint = f"RPE {letzter_satz.rpe} → +2.5kg"
            elif letzter_satz.wiederholungen >= ziel_wdh_max:
                # Obere Grenze erreicht → mehr Gewicht, Wdh zurück auf Minimum
                empfohlenes_gewicht += 2.5
                empfohlene_wdh = ziel_wdh_min
                hint = f"{ziel_wdh_max}+ Wdh → +2.5kg"
            elif letzter_satz.rpe and float(letzter_satz.rpe) >= 9:
                # RPE hoch aber noch im Wdh-Bereich → Wdh erhöhen (max bis Ziel)
                empfohlene_wdh = min(empfohlene_wdh + 1, ziel_wdh_max)
                hint = f"RPE {letzter_satz.rpe} → mehr Wdh"
            else:
                hint = "Niveau halten"

            # Pausenempfehlung: Aus Plan nehmen falls vorhanden, sonst berechnen
            if plan_pausenzeit:
                # Plan hat Pausenzeit definiert → nutze diese
                empfohlene_pause = plan_pausenzeit
            elif '+2.5kg' in hint:
                empfohlene_pause = 180  # 3 Min für Kraftsteigerung
            elif 'mehr Wdh' in hint:
                empfohlene_pause = 90   # 90s für Volumen/Ausdauer
            else:
                empfohlene_pause = 120  # 2 Min Standard

            gewichts_empfehlungen[uebung_id] = {
                'gewicht': empfohlenes_gewicht,
                'wdh': empfohlene_wdh,
                'letztes_gewicht': float(letzter_satz.gewicht),
                'letzte_wdh': letzter_satz.wiederholungen,
                'hint': hint,
                'pause': empfohlene_pause,
                'pause_from_plan': bool(plan_pausenzeit),
            }

    # Deload-Status: Checkbox-Default basierend auf Zyklus
    is_deload_week = False
    try:
        profile = request.user.profile
        is_deload_week = profile.is_deload_week()
    except UserProfile.DoesNotExist:
        pass

    context = {
        'training': training,
        'uebungen': uebungen,
        'saetze': saetze,
        'total_volume': round(total_volume, 1),
        'arbeitssaetze_count': arbeitssaetze.count(),
        'plan_ziele': plan_ziele,
        'gewichts_empfehlungen': gewichts_empfehlungen,
        'is_deload_week': is_deload_week,
    }
    return render(request, 'core/training_session.html', context)


@login_required
def add_set(request, training_id):
    training = get_object_or_404(Trainingseinheit, id=training_id, user=request.user)

    if request.method == 'POST':
        uebung_id = request.POST.get('uebung')
        gewicht = request.POST.get('gewicht')
        wdh = request.POST.get('wiederholungen')
        rpe = request.POST.get('rpe')
        is_warmup = request.POST.get('ist_aufwaermsatz') == 'on'
        notiz = request.POST.get('notiz', '').strip()
        superset_gruppe = request.POST.get('superset_gruppe', 0)

        uebung = get_object_or_404(Uebung, id=uebung_id)

        # Automatische Satz-Nummerierung
        max_satz = training.saetze.filter(uebung=uebung).aggregate(Max('satz_nr'))['satz_nr__max']
        neue_nr = (max_satz or 0) + 1

        # Neuen Satz erstellen
        neuer_satz = Satz.objects.create(
            einheit=training,
            uebung=uebung,
            satz_nr=neue_nr,
            gewicht=gewicht,
            wiederholungen=wdh,
            ist_aufwaermsatz=is_warmup,
            rpe=rpe if rpe else None,
            notiz=notiz if notiz else None,
            superset_gruppe=int(superset_gruppe)
        )

        # PR-Check (nur für Arbeitssätze)
        pr_message = None
        if not is_warmup and gewicht and wdh:
            # Berechne 1RM für diesen Satz (Epley-Formel)
            gewicht_float = float(gewicht)
            wdh_int = int(wdh)
            current_1rm = gewicht_float * (1 + wdh_int / 30)

            # Hole bisheriges Maximum für diese Übung
            alte_saetze = Satz.objects.filter(
                uebung=uebung,
                ist_aufwaermsatz=False,
                einheit__user=request.user,
                einheit__ist_deload=False,
            ).exclude(id=neuer_satz.id)

            if alte_saetze.exists():
                max_alter_satz = max(
                    [float(s.gewicht) * (1 + int(s.wiederholungen) / 30) for s in alte_saetze]
                )

                # Neuer PR?
                if current_1rm > max_alter_satz:
                    verbesserung = round(current_1rm - max_alter_satz, 1)
                    pr_message = f'🎉 NEUER REKORD! {uebung.bezeichnung}: {round(current_1rm, 1)} kg (1RM) - +{verbesserung} kg!'
                    messages.success(request, pr_message)
            else:
                # Erster Satz für diese Übung = automatisch PR
                pr_message = f'🏆 Erster Rekord gesetzt! {uebung.bezeichnung}: {round(current_1rm, 1)} kg (1RM)'
                messages.success(request, pr_message)

        # AJAX Request? Sende JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'satz_id': neuer_satz.id,
                'pr_message': pr_message  # Neu: PR-Message für Toast
            })

        return redirect('training_session', training_id=training_id)


@login_required
@require_http_methods(["POST"])
def delete_set(request, set_id):
    """Löscht einen Satz und kehrt zur Liste zurück"""
    # Wir holen den Satz des eingeloggten Nutzers. Wenn er nicht existiert oder nicht dem Nutzer gehört, gibt's einen 404 Fehler.
    satz = get_object_or_404(Satz, id=set_id, einheit__user=request.user)

    # Wir merken uns die Training-ID, bevor wir löschen, damit wir zurückspringen können
    training_id = satz.einheit.id

    satz.delete()

    return redirect('training_session', training_id=training_id)


def update_set(request, set_id):
    """Speichert Änderungen an einem existierenden Satz."""
    try:
        logger.info(f"update_set called for set_id={set_id}, method={request.method}")
        satz = get_object_or_404(Satz, id=set_id)
        training_id = satz.einheit.id

        if request.method == 'POST':
            logger.info(f"POST data: {request.POST.dict()}")

            # Parse und validiere Eingaben
            try:
                gewicht_raw = request.POST.get('gewicht', '').strip()
                wiederholungen_raw = request.POST.get('wiederholungen', '').strip()
                rpe_raw = request.POST.get('rpe', '').strip()

                logger.info(f"Raw values - gewicht: '{gewicht_raw}', wdh: '{wiederholungen_raw}', rpe: '{rpe_raw}'")

                # Gewicht validieren
                gewicht = None
                if gewicht_raw:
                    # Ersetze Komma durch Punkt (deutsche Eingabe)
                    gewicht_raw = gewicht_raw.replace(',', '.')
                    gewicht = float(gewicht_raw)
                    if gewicht < 0 or gewicht > 1000:
                        raise ValueError("Gewicht außerhalb gültiger Bereich (0-1000)")

                # Wiederholungen validieren
                wiederholungen = None
                if wiederholungen_raw:
                    wiederholungen = int(wiederholungen_raw)
                    if wiederholungen < 0 or wiederholungen > 999:
                        raise ValueError("Wiederholungen außerhalb gültiger Bereich (0-999)")

                # RPE validieren
                rpe = None
                if rpe_raw:
                    rpe_raw = rpe_raw.replace(',', '.')
                    rpe = float(rpe_raw)
                    if rpe < 0 or rpe > 10:
                        raise ValueError("RPE muss zwischen 0 und 10 sein")

                logger.info(f"Validated values - gewicht: {gewicht}, wdh: {wiederholungen}, rpe: {rpe}")

                # Speichere validierte Werte
                satz.gewicht = gewicht
                satz.wiederholungen = wiederholungen
                satz.rpe = rpe
                satz.ist_aufwaermsatz = request.POST.get('ist_aufwaermsatz') == 'on'
                notiz = request.POST.get('notiz', '').strip()
                satz.notiz = notiz if notiz else None
                superset_gruppe = request.POST.get('superset_gruppe', '0').strip()
                satz.superset_gruppe = int(superset_gruppe) if superset_gruppe else 0

                logger.info(f"Saving satz {set_id}...")
                satz.save()
                logger.info(f"Satz {set_id} saved successfully")

                # AJAX Request? Sende JSON
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': True})

                return redirect('training_session', training_id=training_id)

            except (ValueError, TypeError) as e:
                logger.error(f"Validation error in update_set: {e}", exc_info=True)
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': 'Ungültige Eingabe'
                    }, status=400)
                return redirect('training_session', training_id=training_id)

        # GET Request - redirect to session
        return redirect('training_session', training_id=training_id)

    except Exception as e:
        logger.exception(f"Unexpected error in update_set for set_id={set_id}: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': 'Ein unerwarteter Serverfehler ist aufgetreten. Bitte versuchen Sie es später erneut.'
            }, status=500)
        return redirect('dashboard')


@login_required
@require_http_methods(["POST"])
def toggle_deload(request, training_id):
    """Setzt oder entfernt den Deload-Status eines Trainings via AJAX."""
    training = get_object_or_404(Trainingseinheit, id=training_id, user=request.user)
    try:
        data = json.loads(request.body)
        training.ist_deload = bool(data.get('ist_deload', False))
        training.save(update_fields=['ist_deload'])
        return JsonResponse({'success': True, 'ist_deload': training.ist_deload})
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"toggle_deload error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
def finish_training(request, training_id):
    """Zeigt Zusammenfassung und ermöglicht Speichern von Dauer/Kommentar."""
    training = get_object_or_404(Trainingseinheit, id=training_id, user=request.user)

    if request.method == 'POST':
        # Dauer und Kommentar speichern
        dauer_raw = request.POST.get('dauer_minuten')
        kommentar = request.POST.get('kommentar')

        has_error = False

        if dauer_raw:
            try:
                dauer = int(dauer_raw)
            except (TypeError, ValueError):
                messages.error(request, "Bitte eine gültige Trainingsdauer in Minuten angeben.")
                has_error = True
            else:
                # Plausibilitätsprüfung: Dauer muss positiv und realistisch sein
                if dauer <= 0 or dauer > 1440:
                    messages.error(request, "Die Trainingsdauer muss zwischen 1 und 1440 Minuten liegen.")
                    has_error = True
                else:
                    training.dauer_minuten = dauer

        if kommentar:
            training.kommentar = kommentar

        if not has_error:
            training.save()
            return redirect('dashboard')

    # Statistiken für die Zusammenfassung berechnen
    arbeitssaetze = training.saetze.filter(ist_aufwaermsatz=False)
    warmup_saetze = training.saetze.filter(ist_aufwaermsatz=True)

    # Volumen berechnen
    total_volume = sum(float(s.gewicht) * s.wiederholungen for s in arbeitssaetze)

    # Anzahl Übungen
    uebungen_count = training.saetze.values('uebung').distinct().count()

    # Trainingsdauer schätzen (falls nicht manuell eingegeben)
    if training.datum:
        dauer_geschaetzt = int((timezone.now() - training.datum).total_seconds() / 60)
    else:
        dauer_geschaetzt = 60

    # AI Auto-Suggest: Optimierungsvorschlag nach jedem 3. Training
    ai_suggestion = None
    training_count = Trainingseinheit.objects.filter(user=request.user).count()

    if training_count > 0 and training_count % 3 == 0:
        # Analysiere die letzten 3 Trainings
        # Liste von IDs verwenden statt Subquery (MariaDB LIMIT-Kompatibilität)
        recent_training_ids = list(
            Trainingseinheit.objects.filter(user=request.user, ist_deload=False)
            .order_by('-datum').values_list('id', flat=True)[:3]
        )
        recent_trainings = Trainingseinheit.objects.filter(id__in=recent_training_ids)

        # Berechne durchschnittlichen RPE der letzten 3 Trainings
        recent_sets = Satz.objects.filter(
            einheit_id__in=recent_training_ids,
            ist_aufwaermsatz=False,
            einheit__ist_deload=False,
            rpe__isnull=False
        )

        if recent_sets.exists():
            avg_rpe = recent_sets.aggregate(Avg('rpe'))['rpe__avg']

            # Volumen-Analyse der letzten 3 vs. vorherige 3 Trainings
            previous_training_ids = list(
                Trainingseinheit.objects.filter(user=request.user, ist_deload=False)
                .order_by('-datum').values_list('id', flat=True)[3:6]
            )
            previous_trainings = Trainingseinheit.objects.filter(id__in=previous_training_ids)

            recent_volume = sum(
                float(s.gewicht or 0) * int(s.wiederholungen or 0)
                for t in recent_trainings
                for s in t.saetze.filter(ist_aufwaermsatz=False)
            )

            previous_volume = sum(
                float(s.gewicht or 0) * int(s.wiederholungen or 0)
                for t in previous_trainings
                for s in t.saetze.filter(ist_aufwaermsatz=False)
            ) if previous_trainings.exists() else 0

            # Generiere intelligente Vorschläge basierend auf Daten
            suggestions = []

            # Vorschlag 1: Intensität anpassen
            if avg_rpe < 6.5:
                suggestions.append({
                    'type': 'intensity',
                    'title': 'Intensität erhöhen',
                    'message': f'Dein durchschnittlicher RPE liegt bei {avg_rpe:.1f}/10',
                    'action': 'Steigere das Gewicht um 5-10% oder reduziere die Pausenzeit',
                    'icon': 'bi-arrow-up-circle',
                    'color': 'info'
                })
            elif avg_rpe > 8.5:
                suggestions.append({
                    'type': 'intensity',
                    'title': 'Regeneration priorisieren',
                    'message': f'Dein durchschnittlicher RPE liegt bei {avg_rpe:.1f}/10',
                    'action': 'Reduziere die Intensität oder plane einen Deload',
                    'icon': 'bi-shield-check',
                    'color': 'warning'
                })

            # Vorschlag 2: Volumen anpassen
            if previous_volume > 0:
                volume_change = ((recent_volume - previous_volume) / previous_volume) * 100

                if volume_change < -15:
                    suggestions.append({
                        'type': 'volume',
                        'title': 'Volumen gesunken',
                        'message': f'Dein Volumen ist um {abs(volume_change):.0f}% gefallen',
                        'action': 'Füge 1-2 Sätze pro Übung hinzu oder trainiere häufiger',
                        'icon': 'bi-graph-down',
                        'color': 'danger'
                    })
                elif volume_change > 30:
                    suggestions.append({
                        'type': 'volume',
                        'title': 'Volumen stark gestiegen',
                        'message': f'Dein Volumen ist um {volume_change:.0f}% gestiegen',
                        'action': 'Achte auf ausreichend Regeneration zwischen Trainings',
                        'icon': 'bi-graph-up',
                        'color': 'warning'
                    })

            # Vorschlag 3: Übungsvariation
            trained_exercises = set(
                recent_sets.values_list('uebung_id', flat=True).distinct()
            )

            if len(trained_exercises) < 5:
                suggestions.append({
                    'type': 'variety',
                    'title': 'Mehr Übungsvielfalt',
                    'message': f'Du hast nur {len(trained_exercises)} verschiedene Übungen gemacht',
                    'action': 'Integriere neue Übungen für besseres Muskelwachstum',
                    'icon': 'bi-shuffle',
                    'color': 'info'
                })

            # Wähle den wichtigsten Vorschlag (höchste Priorität)
            priority_order = {'danger': 0, 'warning': 1, 'info': 2}
            if suggestions:
                ai_suggestion = sorted(suggestions, key=lambda x: priority_order[x['color']])[0]

    context = {
        'training': training,
        'arbeitssaetze_count': arbeitssaetze.count(),
        'warmup_saetze_count': warmup_saetze.count(),
        'total_volume': round(total_volume, 1),
        'uebungen_count': uebungen_count,
        'dauer_geschaetzt': dauer_geschaetzt,
        'training_count': training_count,
        'ai_suggestion': ai_suggestion,
    }
    return render(request, 'core/training_finish.html', context)
