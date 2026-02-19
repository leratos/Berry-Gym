import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from ..models import KoerperWerte, ProgressPhoto


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
        muskel = request.POST.get("muskel")
        knochen = request.POST.get("knochen")
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
            muskelmasse_kg=muskel if muskel else None,
            knochenmasse_kg=knochen if knochen else None,
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


def _prepare_body_chart_data(werte) -> dict:
    """Baut alle Chart-Datenserien aus einem KoerperWerte-QuerySet auf.

    Returns:
        Dict mit labels_json, gewicht_json, bmi_json, ffmi_json,
        kfa_json, muskel_json, aktuelles_gewicht, aenderung.
    """
    labels = [w.datum.strftime("%d.%m.%y") for w in werte]
    gewicht_data = [float(w.gewicht) for w in werte]
    bmi_data = [_val_or_none(w.bmi) for w in werte]
    ffmi_data = [_val_or_none(w.ffmi) for w in werte]
    kfa_data = [_float_or_none(w.koerperfett_prozent) for w in werte]
    muskel_data = [_float_or_none(w.muskelmasse_kg) for w in werte]

    return {
        "aktuelles_gewicht": werte.last().gewicht,
        "aenderung": _compute_weight_change(werte),
        "labels_json": json.dumps(labels),
        "gewicht_json": json.dumps(gewicht_data),
        "bmi_json": json.dumps(bmi_data),
        "ffmi_json": json.dumps(ffmi_data),
        "kfa_json": json.dumps(kfa_data),
        "muskel_json": json.dumps(muskel_data),
    }


@login_required
def body_stats(request: HttpRequest) -> HttpResponse:
    """Zeigt Körperwerte-Verlauf mit Graphen."""
    werte = KoerperWerte.objects.filter(user=request.user).order_by("datum")

    if not werte.exists():
        return render(request, "core/body_stats.html", {"no_data": True})

    context = {"werte": werte, **_prepare_body_chart_data(werte)}
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
        wert.muskelmasse_kg = request.POST.get("muskelmasse_kg") or None
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
