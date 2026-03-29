"""
Weight-loss context analysis for PDF export.

Evaluates muscle-loss risk based on training volume trend, FFMI progression,
and BIA volatility when weight loss exceeds 1 kg/week.
"""


def analyze_weight_loss_context(stats: dict) -> dict | None:
    """Kontextbasierte Analyse bei Gewichtsverlust > 1 kg/Woche.

    Zieht Trainingsvolumen-Trend, FFMI-Verlauf und BIA-Volatilität heran
    um das Muskelabbau-Risiko realistisch einzuschätzen. Gibt None zurück
    wenn die Rate kein Risiko darstellt (> -1.0 kg/Woche oder unbekannt).

    Args:
        stats: Vollständiger Stats-Dict aus _collect_pdf_stats inkl.
               volumen_trend_weekly.

    Returns:
        dict mit risk_level, erklaerung, faktoren_dagegen, faktoren_dafuer,
        bia_warnung, referenz_info – oder None.
    """
    gewichts_rate = stats.get("gewichts_rate")
    if gewichts_rate is None or gewichts_rate > -1.0:
        return None

    faktoren_dagegen: list[str] = []
    faktoren_dafuer: list[str] = []

    # 1. Trainingsvolumen-Trend (letzte 2 Wochen)
    volumen_trend = stats.get("volumen_trend_weekly")
    if volumen_trend:
        if volumen_trend["trend"] == "steigt":
            faktoren_dagegen.append(
                f"Trainingsvolumen steigt ({volumen_trend['veraenderung_prozent']:+.1f}% "
                f"vs. Vorwoche: {volumen_trend['letzte_woche']:,.0f} kg → "
                f"{volumen_trend['diese_woche']:,.0f} kg)"
            )
        elif volumen_trend["trend"] == "fällt":
            faktoren_dafuer.append(
                f"Trainingsvolumen sinkt ({volumen_trend['veraenderung_prozent']:+.1f}% vs. Vorwoche)"
            )

    # 2. FFMI-Trend (letzten 2 Körpermessungen)
    koerperwerte = stats.get("koerperwerte", [])
    ffmi_aktuell = koerperwerte[0].ffmi if koerperwerte else None
    ffmi_vorherig = koerperwerte[1].ffmi if len(koerperwerte) > 1 else None
    if ffmi_aktuell is not None and ffmi_vorherig is not None:
        ffmi_diff = round(ffmi_aktuell - ffmi_vorherig, 1)
        if ffmi_diff >= 0:
            faktoren_dagegen.append(
                f"FFMI stabil / steigend ({ffmi_vorherig} → {ffmi_aktuell}, Δ{ffmi_diff:+.1f})"
            )
        else:
            faktoren_dafuer.append(
                f"FFMI leicht gesunken ({ffmi_vorherig} → {ffmi_aktuell}, Δ{ffmi_diff:+.1f}) "
                "– kann auch Messschwankung sein"
            )

    # 3. Muskelmasse-% Trend + BIA-Volatilität
    bia_warnung = False
    muskelmasse_werte = [
        float(kw.muskelmasse_prozent)
        for kw in koerperwerte[:4]
        if kw.muskelmasse_prozent is not None
    ]
    if len(muskelmasse_werte) >= 2:
        schwankung = max(muskelmasse_werte) - min(muskelmasse_werte)
        if schwankung > 4.0:
            bia_warnung = True
        if muskelmasse_werte[0] > muskelmasse_werte[1]:
            hinweis = (
                " (BIA-Werte schwanken stark – mit Vorsicht interpretieren)" if bia_warnung else ""
            )
            faktoren_dagegen.append(
                f"Muskelmasse% zuletzt steigend "
                f"({muskelmasse_werte[1]:.1f}% → {muskelmasse_werte[0]:.1f}%){hinweis}"
            )

    # 4. Referenzzeitraum bestimmen
    letzter_kw = koerperwerte[0] if koerperwerte else None
    referenz_info = None
    if letzter_kw and hasattr(letzter_kw, "get_rate_mit_info"):
        rate_info = letzter_kw.get_rate_mit_info()
        if rate_info:
            referenz_info = (
                f"{rate_info['referenz_datum'].strftime('%d.%m.%Y')} → "
                f"{letzter_kw.datum.strftime('%d.%m.%Y')} ({rate_info['tage']} Tage)"
            )

    # 5. Risk Level + Erklärungstext
    # Steigendes Trainingsvolumen ist das direkteste Signal gegen Muskelabbau –
    # es überstimmt schwache FFMI-Schwankungen (BIA-Rauschen).
    volumen_steigt = volumen_trend is not None and volumen_trend.get("trend") == "steigt"
    if len(faktoren_dagegen) >= 2:
        risk_level = "gering"
        erklaerung = (
            "Mehrere Indikatoren sprechen gegen Muskelabbau. "
            "Der Gewichtsverlust ist am wahrscheinlichsten auf ein Kaloriendefizit zurückzuführen."
        )
    elif volumen_steigt and len(faktoren_dafuer) <= 1:
        # Steigendes Volumen + maximal 1 schwaches Gegenargument → kein echtes Risiko
        risk_level = "gering"
        erklaerung = (
            "Hohe Verlustrate – bei steigendem Trainingsvolumen "
            "ist reiner Fett- bzw. Wasserverlust wahrscheinlicher als Muskelabbau."
        )
    elif faktoren_dafuer and not faktoren_dagegen:
        risk_level = "mittel"
        erklaerung = (
            "Einige Indikatoren deuten auf möglichen Muskelabbau hin. "
            "Proteinzufuhr prüfen und Volumen-Entwicklung beobachten."
        )
    else:
        risk_level = "beobachten"
        erklaerung = (
            "Verlustrate liegt über 1 kg/Woche. "
            "Weitere Messungen nötig für gesicherte Einschätzung."
        )

    return {
        "rate": gewichts_rate,
        "referenz_info": referenz_info,
        "risk_level": risk_level,
        "erklaerung": erklaerung,
        "faktoren_dagegen": faktoren_dagegen,
        "faktoren_dafuer": faktoren_dafuer,
        "bia_warnung": bia_warnung,
    }
