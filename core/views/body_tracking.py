import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from ..models import KoerperWerte, ProgressPhoto


@login_required
def add_koerperwert(request):
    """Formular zum Eintragen der erweiterten Watch-Daten"""

    # Wir holen den letzten Eintrag, um die Größe vorzuschlagen
    letzter_wert = KoerperWerte.objects.first()
    standard_groesse = letzter_wert.groesse_cm if letzter_wert else 180

    if request.method == "POST":
        # Pflichtfelder
        groesse = request.POST.get("groesse")
        gewicht = request.POST.get("gewicht")

        # Optionale Watch-Daten
        fett_kg = request.POST.get("fett_kg")
        kfa = request.POST.get("kfa")
        wasser = request.POST.get("wasser")
        muskel = request.POST.get("muskel")
        knochen = request.POST.get("knochen")
        notiz = request.POST.get("notiz")

        # Speichern
        KoerperWerte.objects.create(
            user=request.user,
            groesse_cm=groesse,
            gewicht=gewicht,
            fettmasse_kg=fett_kg if fett_kg else None,
            koerperfett_prozent=kfa if kfa else None,
            koerperwasser_kg=wasser if wasser else None,
            muskelmasse_kg=muskel if muskel else None,
            knochenmasse_kg=knochen if knochen else None,
            notiz=notiz,
        )
        return redirect("dashboard")

    context = {"standard_groesse": standard_groesse}
    return render(request, "core/add_koerperwert.html", context)


def body_stats(request):
    """Zeigt Körperwerte-Verlauf mit Graphen."""
    werte = KoerperWerte.objects.all().order_by("datum")

    if not werte.exists():
        return render(request, "core/body_stats.html", {"no_data": True})

    # Daten für Charts vorbereiten
    labels = [w.datum.strftime("%d.%m.%y") for w in werte]
    gewicht_data = [float(w.gewicht) for w in werte]

    # BMI & FFMI
    bmi_data = [w.bmi if w.bmi else None for w in werte]
    ffmi_data = [w.ffmi if w.ffmi else None for w in werte]

    # Körperfett
    kfa_data = [float(w.koerperfett_prozent) if w.koerperfett_prozent else None for w in werte]

    # Muskelmasse
    muskel_data = [float(w.muskelmasse_kg) if w.muskelmasse_kg else None for w in werte]

    # Berechne aktuelle Werte und Änderung
    aktuelles_gewicht = werte.last().gewicht if werte else None
    gewicht_aenderung = (
        round(float(werte.last().gewicht - werte.first().gewicht), 1) if werte.count() > 1 else 0
    )

    context = {
        "werte": werte,
        "aktuelles_gewicht": aktuelles_gewicht,
        "aenderung": gewicht_aenderung,
        "labels_json": json.dumps(labels),
        "gewicht_json": json.dumps(gewicht_data),
        "bmi_json": json.dumps(bmi_data),
        "ffmi_json": json.dumps(ffmi_data),
        "kfa_json": json.dumps(kfa_data),
        "muskel_json": json.dumps(muskel_data),
    }
    return render(request, "core/body_stats.html", context)


@login_required
def edit_koerperwert(request, wert_id):
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
def delete_koerperwert(request, wert_id):
    """Körperwert löschen."""
    wert = get_object_or_404(KoerperWerte, id=wert_id, user=request.user)
    wert.delete()
    messages.success(request, "Körperwert erfolgreich gelöscht!")
    return redirect("body_stats")


@login_required
def progress_photos(request):
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
def upload_progress_photo(request):
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
def delete_progress_photo(request, photo_id):
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
