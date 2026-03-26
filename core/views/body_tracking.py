import json
from statistics import median

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from ..models import KoerperWerte, ProgressPhoto

# Schwellenwerte für Ausreißer-Erkennung (pro Woche / 7 Tage)
OUTLIER_THRESHOLDS = {
    "ffmi": 0.5,
    "kfa": 2.0,
    "muskelmasse": 1.0,
}


def detect_outliers(werte_list: list) -> set[int]:
    """Erkennt BIA-Ausreißer über Median-Filter und harte Wochendelta-Schwellenwerte.

    Zwei Kriterien – ein Punkt wird geflaggt wenn mindestens eines zutrifft:

    1. **3-Punkt-Median-Filter**: Für Punkte i (1..n-2): Wenn |v[i] - median(v[i-1], v[i], v[i+1])|
       die absolute Schwelle überschreitet → Flag.
    2. **Harte Wochendelta-Schwellenwerte**: Zwischen aufeinanderfolgenden Messungen,
       normalisiert auf 7 Tage. Der *neuere* Punkt wird geflaggt.

    Geprüfte Metriken: FFMI, KFA (koerperfett_prozent), Muskelmasse (muskelmasse_kg).

    Args:
        werte_list: Chronologisch sortierte Liste von KoerperWerte-Objekten.

    Returns:
        Set von KoerperWerte-IDs die als mögliche Messfehler geflaggt sind.
    """
    if len(werte_list) < 2:
        return set()

    outlier_ids: set[int] = set()

    # Extrahiere Serien: (index, id, datum, value) – nur Punkte mit Wert
    def _extract_series(werte, attr_name, is_property=False):
        series = []
        for idx, w in enumerate(werte):
            val = getattr(w, attr_name, None) if is_property else getattr(w, attr_name, None)
            if val is not None:
                series.append((idx, w.id, w.datum, float(val)))
        return series

    metrics = [
        ("ffmi", "ffmi", True),
        ("kfa", "koerperfett_prozent", False),
        ("muskelmasse", "muskelmasse_kg", False),
    ]

    for threshold_key, attr_name, is_property in metrics:
        threshold = OUTLIER_THRESHOLDS[threshold_key]
        series = _extract_series(werte_list, attr_name, is_property)

        if len(series) < 2:
            continue

        # --- 3-Punkt-Median-Filter (Index 1..n-2 der Serie) ---
        for i in range(1, len(series) - 1):
            _, wid, _, val = series[i]
            med = median([series[i - 1][3], val, series[i + 1][3]])
            if abs(val - med) > threshold:
                outlier_ids.add(wid)

        # --- Harte Wochendelta-Schwellenwerte ---
        for i in range(1, len(series)):
            _, prev_id, prev_datum, prev_val = series[i - 1]
            _, curr_id, curr_datum, curr_val = series[i]
            tage = (curr_datum - prev_datum).days
            if tage <= 0:
                continue
            delta_per_week = abs(curr_val - prev_val) / tage * 7
            if delta_per_week > threshold:
                outlier_ids.add(curr_id)

    return outlier_ids


def _linear_forecast(dates_values: list, forecast_days: int) -> float | None:
    """Lineare Regression auf (date, value)-Paaren → Prognose für forecast_days in der Zukunft.

    Benötigt mindestens 5 Datenpunkte. Gibt None zurück wenn zu wenig Daten.
    """
    if len(dates_values) < 5:
        return None
    t0 = dates_values[0][0]
    xs = [(d - t0).days for d, _ in dates_values]
    ys = [float(v) for _, v in dates_values]
    n = len(xs)
    s_x = sum(xs)
    s_y = sum(ys)
    s_xy = sum(x * y for x, y in zip(xs, ys))
    s_xx = sum(x * x for x in xs)
    denom = n * s_xx - s_x**2
    if denom == 0:
        return None
    slope = (n * s_xy - s_x * s_y) / denom
    intercept = (s_y - slope * s_x) / n
    return slope * (xs[-1] + forecast_days) + intercept


@login_required
def add_koerperwert(request: HttpRequest) -> HttpResponse:
    """Formular zum Eintragen der erweiterten Watch-Daten"""

    # Neuesten Eintrag holen: ordering=["-datum"] → .first() = neuester
    # (nicht .last() – das wäre der älteste!)
    letzter_wert = KoerperWerte.objects.filter(user=request.user).first()

    # Körpergröße: primär aus Profil, Fallback aus letzter Messung
    try:
        profil_groesse = request.user.profile.groesse_cm
    except Exception:
        profil_groesse = None
    standard_groesse = profil_groesse or (letzter_wert.groesse_cm if letzter_wert else None)

    if request.method == "POST":
        # Pflichtfelder
        groesse = request.POST.get("groesse") or None
        gewicht = request.POST.get("gewicht")

        # Optionale Watch-Daten
        fett_kg = request.POST.get("fett_kg")
        kfa = request.POST.get("kfa")
        wasser = request.POST.get("wasser")
        wasser_prozent = request.POST.get("wasser_prozent")
        muskel = request.POST.get("muskel")
        muskel_prozent = request.POST.get("muskel_prozent")
        knochen = request.POST.get("knochen")
        viszeralfett = request.POST.get("viszeralfett")
        grundumsatz = request.POST.get("grundumsatz")
        notiz = request.POST.get("notiz")

        # Wenn Größe angegeben: Profil aktualisieren damit sie konsistent bleibt
        if groesse:
            try:
                request.user.profile.groesse_cm = int(groesse)
                request.user.profile.save(update_fields=["groesse_cm"])
            except Exception:
                pass

        # Speichern – groesse_cm leer lassen, bmi/ffmi nutzen Profil-Wert
        KoerperWerte.objects.create(
            user=request.user,
            groesse_cm=groesse if groesse else None,
            gewicht=gewicht,
            fettmasse_kg=fett_kg if fett_kg else None,
            koerperfett_prozent=kfa if kfa else None,
            koerperwasser_kg=wasser if wasser else None,
            koerperwasser_prozent=wasser_prozent if wasser_prozent else None,
            muskelmasse_kg=muskel if muskel else None,
            muskelmasse_prozent=muskel_prozent if muskel_prozent else None,
            knochenmasse_kg=knochen if knochen else None,
            viszeralfett=viszeralfett if viszeralfett else None,
            grundumsatz_kcal=grundumsatz if grundumsatz else None,
            notiz=notiz,
        )
        return redirect("dashboard")

    context = {"standard_groesse": standard_groesse, "profil_groesse": profil_groesse}
    return render(request, "core/add_koerperwert.html", context)


def _val_or_none(val):
    """Gibt val zurück oder None wenn val falsy."""
    return val or None


def _float_or_none(val) -> float | None:
    """Gibt float(val) zurück oder None wenn val falsy."""
    return float(val) if val else None


def _compute_weight_change(werte) -> float:
    """Berechnet Gewichtsveränderung zwischen erstem und letztem Eintrag."""
    if werte.count() <= 1:
        return 0
    return round(float(werte.last().gewicht - werte.first().gewicht), 1)


def _prepare_body_chart_data(werte, outlier_ids: set[int] | None = None) -> dict:
    """Baut alle Chart-Datenserien aus einem KoerperWerte-QuerySet auf.

    Args:
        werte: KoerperWerte QuerySet oder Liste (chronologisch sortiert).
        outlier_ids: Set von IDs die als mögliche Messfehler geflaggt sind.

    Returns:
        Dict mit labels_json, gewicht_json, bmi_json, ffmi_json,
        kfa_json, muskel_json, outlier_flags_json, aktuelles_gewicht, aenderung.
    """
    if outlier_ids is None:
        outlier_ids = set()

    labels = [w.datum.strftime("%d.%m.%y") for w in werte]
    gewicht_data = [float(w.gewicht) for w in werte]
    bmi_data = [_val_or_none(w.bmi) for w in werte]
    ffmi_data = [_val_or_none(w.ffmi) for w in werte]
    kfa_data = [_float_or_none(w.koerperfett_prozent) for w in werte]
    muskel_data = [_float_or_none(w.muskelmasse_kg) for w in werte]
    outlier_flags = [w.id in outlier_ids for w in werte]

    return {
        "aktuelles_gewicht": werte.last().gewicht if hasattr(werte, "last") else werte[-1].gewicht,
        "aenderung": _compute_weight_change(werte),
        "labels_json": json.dumps(labels),
        "gewicht_json": json.dumps(gewicht_data),
        "bmi_json": json.dumps(bmi_data),
        "ffmi_json": json.dumps(ffmi_data),
        "kfa_json": json.dumps(kfa_data),
        "muskel_json": json.dumps(muskel_data),
        "outlier_flags_json": json.dumps(outlier_flags),
    }


@login_required
def body_stats(request: HttpRequest) -> HttpResponse:
    """Zeigt Körperwerte-Verlauf mit Graphen."""
    werte = KoerperWerte.objects.filter(user=request.user).order_by("datum")

    if not werte.exists():
        return render(request, "core/body_stats.html", {"no_data": True})

    werte_list = list(werte)

    # Ausreißer erkennen
    outlier_ids = detect_outliers(werte_list)

    # Prognose (6 Wochen = 42 Tage)
    # Gewicht ist unabhängig von BIA-Impedanz → keine Ausreißer-Filterung
    weight_pairs = [(w.datum, float(w.gewicht)) for w in werte_list]
    gewicht_forecast_raw = _linear_forecast(weight_pairs, 42)
    gewicht_forecast = round(gewicht_forecast_raw, 1) if gewicht_forecast_raw else None

    # KFA-Forecast: Ausreißer ausschließen (BIA-Impedanz-Fehler verzerren Regression)
    kfa_pairs = [
        (w.datum, float(w.koerperfett_prozent))
        for w in werte_list
        if w.koerperfett_prozent is not None and w.id not in outlier_ids
    ]
    kfa_forecast_raw = _linear_forecast(kfa_pairs, 42)
    kfa_forecast = round(kfa_forecast_raw, 1) if kfa_forecast_raw else None

    context = {
        "werte": werte,
        **_prepare_body_chart_data(werte, outlier_ids),
        "gewicht_forecast": gewicht_forecast,
        "kfa_forecast": kfa_forecast,
        "outlier_ids": outlier_ids,
    }
    return render(request, "core/body_stats.html", context)


@login_required
def edit_koerperwert(request: HttpRequest, wert_id: int) -> HttpResponse:
    """Körperwert bearbeiten."""
    wert = get_object_or_404(KoerperWerte, id=wert_id, user=request.user)

    if request.method == "POST":
        # Update fields
        wert.gewicht = request.POST.get("gewicht")
        wert.groesse_cm = request.POST.get("groesse_cm") or None
        wert.koerperfett_prozent = request.POST.get("koerperfett_prozent") or None
        wert.fettmasse_kg = request.POST.get("fettmasse_kg") or None
        wert.koerperwasser_kg = request.POST.get("koerperwasser_kg") or None
        wert.koerperwasser_prozent = request.POST.get("koerperwasser_prozent") or None
        wert.muskelmasse_kg = request.POST.get("muskelmasse_kg") or None
        wert.muskelmasse_prozent = request.POST.get("muskelmasse_prozent") or None
        wert.viszeralfett = request.POST.get("viszeralfett") or None
        wert.grundumsatz_kcal = request.POST.get("grundumsatz_kcal") or None
        wert.save()
        messages.success(request, "Körperwert erfolgreich aktualisiert!")
        return redirect("body_stats")

    context = {
        "wert": wert,
    }
    return render(request, "core/edit_koerperwert.html", context)


@login_required
def delete_koerperwert(request: HttpRequest, wert_id: int) -> HttpResponse:
    """Körperwert löschen – nur per POST."""
    wert = get_object_or_404(KoerperWerte, id=wert_id, user=request.user)
    if request.method == "POST":
        wert.delete()
        messages.success(request, "Körperwert erfolgreich gelöscht!")
    return redirect("body_stats")


@login_required
def progress_photos(request: HttpRequest) -> HttpResponse:
    """Zeigt alle Fortschrittsfotos des Users in einer Timeline."""
    photos = ProgressPhoto.objects.filter(user=request.user).order_by("-datum")

    # Gewichtsverlauf für Timeline
    koerperwerte = KoerperWerte.objects.filter(user=request.user).order_by("-datum")[:30]

    context = {
        "photos": photos,
        "koerperwerte": koerperwerte,
    }
    return render(request, "core/progress_photos.html", context)


@login_required
def upload_progress_photo(request: HttpRequest) -> HttpResponse:
    """Upload eines neuen Fortschrittsfotos."""
    if request.method == "POST":
        foto = request.FILES.get("foto")
        gewicht_kg = request.POST.get("gewicht_kg", "").strip()
        notiz = request.POST.get("notiz", "").strip()

        if not foto:
            messages.error(request, "Bitte wähle ein Foto aus.")
            return redirect("progress_photos")

        # Foto speichern
        ProgressPhoto.objects.create(
            user=request.user,
            foto=foto,
            gewicht_kg=gewicht_kg if gewicht_kg else None,
            notiz=notiz if notiz else None,
        )

        messages.success(request, "Foto erfolgreich hochgeladen!")
        return redirect("progress_photos")

    return redirect("progress_photos")


@login_required
def delete_progress_photo(request: HttpRequest, photo_id: int) -> HttpResponse:
    """Löscht ein Fortschrittsfoto."""
    photo = get_object_or_404(ProgressPhoto, id=photo_id, user=request.user)

    if request.method == "POST":
        # Datei löschen
        if photo.foto:
            photo.foto.delete()

        photo.delete()
        messages.success(request, "Foto gelöscht.")
        return redirect("progress_photos")

    return redirect("progress_photos")
