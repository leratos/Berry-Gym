"""Phase 32.4 – AUDIT/Guard-Test: ALLE benachbarten Wochen-Volumen-Vergleichsstellen.

Dies ist der **Konvergenzgarant** gegen vergessene Pfade (Konzept §32.4, §11.1):
Er zählt die bekannten Vergleichsstellen explizit auf und prüft pro Pfad, dass
eine Wiedereinstiegs-Woche nach einer dokumentierten Pause **keine falsche
Volumen-Anstiegs-Warnung/-Bewertung** erzeugt.

Bekannte Vergleichsstellen (Stand Umsetzung – Liste bewusst als *unvollständig*
behandeln; ein neu entdeckter Pfad gehört hier ergänzt):

| #  | Pfad                          | Funktion                                            |
|----|-------------------------------|-----------------------------------------------------|
| 1  | Export/PDF Fatigue-Spike      | advanced_stats.calculate_fatigue_index              |
| 2  | Dashboard Fatigue-Spike       | training_stats._calculate_fatigue_index             |
| 3  | Dashboard Form-Index Volumen  | training_stats._get_volume_trend_score              |
| 4  | Stats-Seite Volumen-Warnung   | training_stats._detect_volume_warnings              |
| 5  | Export Volumen-Trend          | stats_collector.calc_volume_trend_weekly            |
| 6  | Blockdauer/Phasenwechsel      | periodization.get_block_age_warning (Netto via      |
|    | (Phase 34)                    | week_classification.pausen_ausfall_wochen)          |
| 7  | Rückschritt/Wiederaufbau      | advanced_stats.classify_progression_status          |
|    | (Phase 35.1)                  | (reentry_pause → Status "reentry" statt Bestrafung  |
|    |                               | der eigenen Rampen-Empfehlung)                      |
| 8  | Push/Pull-Balance             | stats_collector.collect_push_pull (PDF) +           |
|    | (Phase 35.2)                  | training_stats._calc_push_pull_ratio (Live) –       |
|    |                               | einseitige Daten → "Nicht bewertbar"                |
| 9  | Schwachstellen/Stärken        | stats_collector.collect_muscle_balance – 0-Satz-    |
|    | (Phase 35.2)                  | Gruppen werden emittiert (keine Inversion)          |
| 10 | RPE-All-Time-Fallback         | advanced_stats.calculate_rpe_quality_analysis_      |
|    | (Phase 35.2)                  | windowed – insufficient_4w gated die Empfehlungen   |
| 11 | Report-Pausen-Banner          | week_classification.pausen_im_zeitraum              |
|    | (Phase 35.3)                  | (Live + PDF, eine Datenquelle)                      |
| 12 | Heatmap-Pausenmarker          | chart_generator.generate_training_heatmap           |
|    | (Phase 35.3)                  | (pause_ranges-Parameter)                            |

``INVENTORY`` unten ist ein Importierbarkeits-Guard: wird eine Vergleichsstelle
umbenannt/entfernt, schlägt der Test fehl und erzwingt ein Review.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

from django.core.cache import cache
from django.db.models import Prefetch
from django.utils import timezone

import pytest

from core.chart_generator import generate_training_heatmap
from core.export.stats_collector import (
    calc_volume_trend_weekly,
    collect_muscle_balance,
    collect_pdf_stats,
    collect_push_pull,
)
from core.models import Satz, Trainingseinheit, TrainingsPause
from core.tests.factories import (
    PlanFactory,
    SatzFactory,
    TrainingsblockFactory,
    TrainingseinheitFactory,
    TrainingsPauseFactory,
    UebungFactory,
    UserFactory,
)
from core.utils.advanced_stats import (
    calculate_fatigue_index,
    calculate_plateau_analysis,
    calculate_rpe_quality_analysis_windowed,
    classify_progression_status,
)
from core.utils.periodization import get_block_age_warning
from core.utils.reentry import get_active_reentry_pause
from core.utils.week_classification import (
    build_weekly_volume_overview,
    pausen_ausfall_wochen,
    pausen_im_zeitraum,
)
from core.views.training_stats import (
    _calc_push_pull_ratio,
    _calc_weekly_volume,
    _calculate_fatigue_index,
    _calculate_weekly_volumes,
    _detect_volume_warnings,
    _get_volume_trend_score,
)


def _mo(iso_year: int, iso_week: int) -> date:
    return date.fromisocalendar(iso_year, iso_week, 1)


def _iso(d: date) -> str:
    iy, iw, _ = d.isocalendar()
    return f"{iy}-W{iw:02d}"


def _session(user, plan, uebung, d: date, n_sets: int, gewicht: int = 100):
    """Session am Tag ``d`` mit ``n_sets`` Arbeitssätzen à gewicht×10 Wdh."""
    dt = datetime.combine(d, datetime.min.time())
    aware = timezone.make_aware(dt) if timezone.is_naive(dt) else dt
    einheit = TrainingseinheitFactory(user=user, plan=plan, ist_deload=False)
    Trainingseinheit.objects.filter(pk=einheit.pk).update(datum=aware)
    einheit.refresh_from_db()
    for _ in range(n_sets):
        SatzFactory(
            einheit=einheit,
            uebung=uebung,
            gewicht=Decimal(gewicht),
            wiederholungen=10,
            rpe=Decimal("8.0"),
            ist_aufwaermsatz=False,
        )
    return einheit


@pytest.fixture
def comeback_szenario(db):
    """Vor-Pause-Volumen ~2000/Woche, 2 Wochen dokumentierte Pause (0 Sessions),
    Comeback-Woche mit ~5000 (= >100 % „Anstieg" gegenüber Vor-Pause).

    heute = Mittwoch der Comeback-Woche (W23/2026).
    """
    user = UserFactory()
    plan = PlanFactory(user=user)
    uebung = UebungFactory()
    # Vor-Pause: W19, W20 je 2 Sätze (2000)
    _session(user, plan, uebung, _mo(2026, 19) + timedelta(days=1), n_sets=2)
    _session(user, plan, uebung, _mo(2026, 20) + timedelta(days=1), n_sets=2)
    # Dokumentierte Pause W21-Mo bis W22-So (2 volle Wochen, 0 Sessions)
    pause = TrainingsPauseFactory(
        user=user, start_datum=_mo(2026, 21), end_datum=_mo(2026, 22) + timedelta(days=6)
    )
    # Comeback W23: 5 Sätze (5000)
    _session(user, plan, uebung, _mo(2026, 23), n_sets=5)
    heute = timezone.make_aware(
        datetime.combine(_mo(2026, 23) + timedelta(days=2), datetime.min.time())
    )
    trainings_prefetched = (
        Trainingseinheit.objects.filter(user=user)
        .prefetch_related(
            Prefetch(
                "saetze",
                queryset=Satz.objects.filter(ist_aufwaermsatz=False).select_related("uebung"),
                to_attr="arbeitssaetze_list",
            )
        )
        .order_by("datum")
    )
    return {
        "user": user,
        "pause": pause,
        "heute": heute,
        "saetze": Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False),
        "trainings": Trainingseinheit.objects.filter(user=user).order_by("datum"),
        "trainings_prefetched": trainings_prefetched,
        "pausen": TrainingsPause.objects.filter(user=user),
    }


def test_inventory_alle_vergleichsstellen_importierbar():
    """Guard: alle bekannten Vergleichsstellen existieren (Umbenennung → Review)."""
    inventory = [
        calculate_fatigue_index,
        _calculate_fatigue_index,
        _get_volume_trend_score,
        _detect_volume_warnings,
        calc_volume_trend_weekly,
        # Pfad 6 (Phase 34): Blockdauer/Phasenwechsel-Empfehlung
        get_block_age_warning,
        pausen_ausfall_wochen,
        # Pfad 7 (Phase 35.1): Status-Klassifikator rampen-aware
        classify_progression_status,
        # Pfad 8 (Phase 35.2): Push/Pull PDF + Live
        collect_push_pull,
        _calc_push_pull_ratio,
        # Pfad 9 (Phase 35.2): Schwachstellen/Stärken-Quelle
        collect_muscle_balance,
        # Pfad 10 (Phase 35.2): RPE-Zeitfenster-Wrapper
        calculate_rpe_quality_analysis_windowed,
        # Pfad 11 (Phase 35.3): Pausen-Banner-Datenquelle
        pausen_im_zeitraum,
        # Pfad 12 (Phase 35.3): Heatmap-Pausenmarker
        generate_training_heatmap,
    ]
    assert all(callable(f) for f in inventory)
    assert len(inventory) == 14


@pytest.mark.django_db
class TestKeineFalscheAnstiegsWarnung:
    """Pro Pfad: Comeback nach Pause erzeugt KEINE falsche Volumen-Anstiegs-Warnung."""

    def _overview(self, ctx):
        return build_weekly_volume_overview(
            ctx["saetze"], ctx["trainings"], heute=ctx["heute"], pausen=list(ctx["pausen"])
        )

    def test_pfad1_pdf_fatigue_spike(self, comeback_szenario):
        ctx = comeback_szenario
        overview = self._overview(ctx)
        rpe_saetze = ctx["saetze"].filter(rpe__isnull=False)
        result = calculate_fatigue_index(overview, rpe_saetze, ctx["trainings"])
        assert not any("Volumen-Anstieg" in w for w in result["warnungen"])

    def test_pfad2_dashboard_fatigue_spike(self, comeback_szenario):
        ctx = comeback_szenario
        weekly_volumes = _calculate_weekly_volumes(ctx["user"], ctx["heute"])
        gesamt = ctx["trainings"].count()
        result = _calculate_fatigue_index(ctx["user"], ctx["heute"], weekly_volumes, gesamt)
        assert not any("Volumen-Anstieg" in w for w in result["fatigue_warnings"])

    def test_pfad3_form_index_volumen_trend(self, comeback_szenario):
        ctx = comeback_szenario
        score = _get_volume_trend_score(ctx["user"], ctx["heute"])
        # 20 = „Volumen gestiegen/gehalten" (= falsche Anstiegs-Bewertung nach Pause)
        assert score != 20

    def test_pfad4_stats_volumen_warnung(self, comeback_szenario):
        from core.utils.week_classification import letzte_iso_wochen_keys, pausen_grenze_keys

        ctx = comeback_szenario
        labels, data, plans = _calc_weekly_volume(list(ctx["trainings_prefetched"]))
        heute_date = ctx["heute"].date()
        aktuelle_kw = f"{heute_date.isocalendar()[0]}-W{heute_date.isocalendar()[1]:02d}"
        grenze = pausen_grenze_keys(
            ctx["pausen"], heute_date, letzte_iso_wochen_keys(heute_date, 14)
        )
        warnings = _detect_volume_warnings(
            labels, data, aktuelle_kw=aktuelle_kw, plans_per_week=plans, grenze_keys=grenze
        )
        assert not any(w.get("type") == "spike" for w in warnings)

    def test_pfad5_export_volumen_trend(self, comeback_szenario):
        ctx = comeback_szenario
        overview = self._overview(ctx)
        result = calc_volume_trend_weekly(overview, heute=ctx["heute"])
        # „steigt" wäre der falsche Comeback-Anstieg über die Pause hinweg.
        assert result is None or result["trend"] != "steigt"


@pytest.mark.django_db
class TestPositivkontrolle:
    """Gegenprobe: OHNE Pause feuert ein echter Volumen-Anstieg weiterhin –
    die Unterdrückung ist also pausen-bedingt, kein blankes Abschalten."""

    def test_pfad3_ohne_pause_bewertet_anstieg(self):
        user = UserFactory()
        plan = PlanFactory(user=user)
        ue = UebungFactory()
        # 3 aufeinanderfolgende Wochen, steigendes Volumen, KEINE Pause.
        _session(user, plan, ue, _mo(2026, 21) + timedelta(days=1), n_sets=2)
        _session(user, plan, ue, _mo(2026, 22) + timedelta(days=1), n_sets=2)
        _session(user, plan, ue, _mo(2026, 23), n_sets=5)
        heute = timezone.make_aware(
            datetime.combine(_mo(2026, 23) + timedelta(days=2), datetime.min.time())
        )
        assert _get_volume_trend_score(user, heute) == 20  # Anstieg wird bewertet

    def test_pfad4_ohne_pause_warnt_spike(self):
        user = UserFactory()
        plan = PlanFactory(user=user)
        ue = UebungFactory()
        # Spike in einer ABGESCHLOSSENEN Woche (W22), W23 = laufend.
        _session(user, plan, ue, _mo(2026, 21) + timedelta(days=1), n_sets=2)
        _session(user, plan, ue, _mo(2026, 22) + timedelta(days=1), n_sets=6)
        _session(user, plan, ue, _mo(2026, 23), n_sets=6)
        heute_date = _mo(2026, 23) + timedelta(days=2)
        labels, data, plans = _calc_weekly_volume(
            list(
                Trainingseinheit.objects.filter(user=user).prefetch_related(
                    Prefetch(
                        "saetze",
                        queryset=Satz.objects.filter(ist_aufwaermsatz=False),
                        to_attr="arbeitssaetze_list",
                    )
                )
            )
        )
        aktuelle_kw = f"{heute_date.isocalendar()[0]}-W{heute_date.isocalendar()[1]:02d}"
        warnings = _detect_volume_warnings(
            labels, data, aktuelle_kw=aktuelle_kw, plans_per_week=plans, grenze_keys=set()
        )
        assert any(w.get("type") == "spike" for w in warnings)


class TestCodexFixesPr201:
    """Regressionen für die 4 Codex-P2-Anmerkungen aus PR #201."""

    def test_pausenbehaftete_vorwoche_mit_restvolumen_blockt(self):
        """P2 (⑱-Ergänzung): Ist die VORWOCHE selbst eine Pausen-Grenze (mit
        Restvolumen), berührt der Vergleich die Pause → keine Spike-Warnung.
        Früher schloss `prev_label < g` die Vorwoche fälschlich aus."""
        labels = ["2026-W18", "2026-W19", "2026-W20"]
        data = [1000, 900, 2000]  # W20 wäre ein Spike vs W19
        warnings = _detect_volume_warnings(
            labels, data, aktuelle_kw=None, plans_per_week=None, grenze_keys={"2026-W19"}
        )
        assert not any(w.get("type") == "spike" for w in warnings)

    @pytest.mark.django_db
    def test_distante_pause_unterdrueckt_aktuellen_vergleich_nicht(self):
        """P2: Eine Pause 3 Wochen zurück darf einen ECHTEN aktuellen Spike nicht
        unterdrücken, wenn die letzten beiden Wochen normal trainiert wurden."""
        from core.views.training_stats import (
            _get_volume_trend_score,
            _pause_blockiert_volumenvergleich,
        )

        user = UserFactory()
        plan = PlanFactory(user=user)
        ue = UebungFactory()
        now = timezone.now()
        heute_d = now.date()

        def _wk_mo(k):
            d = heute_d - timedelta(weeks=k)
            return d - timedelta(days=d.weekday())

        # Normale Trainings in Wochen 0,1,2 (gleiches Volumen → Trend-Score 20).
        for k in (0, 1, 2):
            _session(user, plan, ue, _wk_mo(k), n_sets=2)
        # Dokumentierte Pause 3 Wochen zurück (Woche 3, ausserhalb des 2-Wo-Fensters).
        TrainingsPauseFactory(
            user=user, start_datum=_wk_mo(3), end_datum=_wk_mo(3) + timedelta(days=6)
        )
        assert _pause_blockiert_volumenvergleich(user, now) is False
        assert _get_volume_trend_score(user, now) == 20


def _wk_mo_heute(heute_d: date, k: int) -> date:
    """Montag der ISO-Woche ``k`` Wochen vor ``heute_d``."""
    d = heute_d - timedelta(weeks=k)
    return d - timedelta(days=d.weekday())


def _iso_von(d: date) -> str:
    iy, iw, _ = d.isocalendar()
    return f"{iy}-W{iw:02d}"


@pytest.mark.django_db
class TestPfad6BlockdauerPhasenwechsel:
    """Pfad 6 (Phase 34): Die Blockdauer-/Phasenwechsel-Empfehlung zählt keine
    dokumentierten Pausenwochen mit (Kernbug: Karte „läuft seit 15 Wochen"
    feuerte, WEIL der User pausiert hatte)."""

    def test_netto_unterdrueckt_verfruehte_empfehlung(self):
        """Brutto ≥ Schwelle, Netto < Schwelle → keine Empfehlung (Kernbug)."""
        user = UserFactory()
        heute_d = timezone.localdate()
        start = _wk_mo_heute(heute_d, 10)
        block = TrainingsblockFactory(user=user, typ="definition", start_datum=start)
        # 4 volle ISO-Wochen dokumentierte Pause (Mo vor 6 Wo. bis So vor 3 Wo.)
        TrainingsPauseFactory(
            user=user,
            start_datum=_wk_mo_heute(heute_d, 6),
            end_datum=_wk_mo_heute(heute_d, 3) + timedelta(days=6),
        )
        pausen = TrainingsPause.objects.filter(user=user)
        ausfall = pausen_ausfall_wochen(pausen, start, heute_d, sessions_week_keys=set())
        assert ausfall == 4
        brutto = block.weeks_since_start
        assert brutto >= 8
        # Brutto hätte gefeuert (IST-Zustand vor Phase 34) ...
        assert get_block_age_warning(block) is not None
        # ... Netto (10 − 4 = 6 < 8) feuert nicht.
        assert get_block_age_warning(block, netto_weeks=brutto - ausfall) is None

    def test_anzeige_brutto_und_netto_severity_auf_netto(self):
        """Karte zeigt Brutto UND Netto (#1053); Severity wird auf Netto bewertet."""
        user = UserFactory()
        heute_d = timezone.localdate()
        block = TrainingsblockFactory(
            user=user, typ="definition", start_datum=_wk_mo_heute(heute_d, 15)
        )
        warning = get_block_age_warning(block, netto_weeks=11)
        assert warning is not None
        assert warning["weeks"] == block.weeks_since_start
        assert warning["netto_weeks"] == 11
        assert warning["pausen_wochen"] == warning["weeks"] - 11
        # Brutto 15 ≥ 12 wäre „danger" – Netto 11 < 12 bleibt „warning".
        assert warning["severity"] == "warning"

    def test_abdeckungs_semantik_rand_und_trainierte_woche(self):
        """Nur voll abgedeckte Wochen ohne Session zählen: eine ab Donnerstag
        überlappte Rand-Woche und eine trotz Pause trainierte Woche nicht."""
        user = UserFactory()
        heute_d = timezone.localdate()
        start = _wk_mo_heute(heute_d, 8)
        # Pause Donnerstag (vor 6 Wo.) bis Sonntag (vor 3 Wo.):
        # berührt 4 ISO-Wochen, deckt nur 3 voll ab (Prod-Fall-Muster).
        TrainingsPauseFactory(
            user=user,
            start_datum=_wk_mo_heute(heute_d, 6) + timedelta(days=3),
            end_datum=_wk_mo_heute(heute_d, 3) + timedelta(days=6),
        )
        pausen = TrainingsPause.objects.filter(user=user)
        assert pausen_ausfall_wochen(pausen, start, heute_d, sessions_week_keys=set()) == 3
        # Session in einer voll abgedeckten Woche → die Woche zählt als Trainingswoche.
        key_wo4 = _iso_von(_wk_mo_heute(heute_d, 4))
        assert pausen_ausfall_wochen(pausen, start, heute_d, sessions_week_keys={key_wo4}) == 2

    def test_positivkontrolle_ohne_pause_feuert_weiter(self):
        """Ohne Pause: Netto == Brutto, Empfehlung erscheint unverändert."""
        user = UserFactory()
        heute_d = timezone.localdate()
        start = _wk_mo_heute(heute_d, 10)
        block = TrainingsblockFactory(user=user, typ="definition", start_datum=start)
        pausen = TrainingsPause.objects.filter(user=user)
        assert pausen_ausfall_wochen(pausen, start, heute_d, sessions_week_keys=set()) == 0
        warning = get_block_age_warning(block, netto_weeks=block.weeks_since_start)
        assert warning is not None
        assert warning["pausen_wochen"] == 0


@pytest.mark.django_db
class TestPfad6DashboardIntegration:
    """Phase 34.2 (View-Verdrahtung): Während einer laufenden Wiedereinstiegs-
    Rampe (33.x) wird die Phasenwechsel-Karte unterdrückt – die beiden Karten
    dürfen sich nicht widersprechen."""

    def test_laufende_rampe_unterdrueckt_karte(self, client):
        user = UserFactory()
        client.force_login(user)
        cache.clear()
        heute_d = timezone.localdate()
        TrainingsblockFactory(
            user=user, typ="definition", start_datum=heute_d - timedelta(weeks=20)
        )
        # 14-Tage-Pause, vor 3 Tagen beendet → Rampe (2 Wochen) läuft.
        end = heute_d - timedelta(days=3)
        TrainingsPauseFactory(user=user, start_datum=end - timedelta(days=13), end_datum=end)
        response = client.get("/")
        assert response.status_code == 200
        assert response.context["reentry_pause"] is not None
        # Netto (≥ 18) läge über der Schwelle – unterdrückt wird wegen der Rampe.
        assert response.context["block_age_warning"] is None

    def test_ohne_rampe_erscheint_karte(self, client):
        """Positivkontrolle Verdrahtung: alter Block ohne Pause → Karte da."""
        user = UserFactory()
        client.force_login(user)
        cache.clear()
        heute_d = timezone.localdate()
        TrainingsblockFactory(
            user=user, typ="definition", start_datum=heute_d - timedelta(weeks=20)
        )
        response = client.get("/")
        assert response.status_code == 200
        assert response.context["reentry_pause"] is None
        warning = response.context["block_age_warning"]
        assert warning is not None
        assert warning["pausen_wochen"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# Phase 35: Pfade 7–12 (Report-Audit #1059/#1061)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPfad7RueckschrittWiederaufbau:
    """Pfad 7 (35.1): Der Status-Klassifikator bestraft nicht die eigene
    Wiedereinstiegs-Rampe (Kernbug #1059 b: Rampengewichte Faktor 0,85 →
    „Rückschritt" bei exakt den vom Tool empfohlenen Gewichten)."""

    def _szenario(self, mit_pause: bool):
        user = UserFactory()
        plan = PlanFactory(user=user)
        ue = UebungFactory()
        heute_d = timezone.localdate()
        # All-Time-PR vor der Pause (außerhalb des 4W-Fensters)
        _session(user, plan, ue, heute_d - timedelta(days=35), n_sets=2, gewicht=100)
        if mit_pause:
            # 14-Tage-Pause, vor 3 Tagen beendet → Rampe läuft (Muster Pfad 6)
            end = heute_d - timedelta(days=3)
            TrainingsPauseFactory(user=user, start_datum=end - timedelta(days=13), end_datum=end)
        # Comeback heute mit Rampengewicht (−15 % → Drop > 5 %-Schwelle)
        _session(user, plan, ue, heute_d, n_sets=2, gewicht=85)
        return user, ue

    def _plateau(self, user, ue, reentry_pause):
        saetze = Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False)
        top = [{"uebung__bezeichnung": ue.bezeichnung, "muskelgruppe_display": "Brust"}]
        return calculate_plateau_analysis(saetze, top, reentry_pause=reentry_pause)

    def test_rampe_zeigt_wiederaufbau_statt_rueckschritt(self):
        user, ue = self._szenario(mit_pause=True)
        reentry = get_active_reentry_pause(user)
        assert reentry is not None, "Rampe muss im Szenario aktiv sein"
        result = self._plateau(user, ue, reentry)
        assert result, "Übung muss klassifiziert werden"
        assert result[0]["status"] == "reentry"
        assert result[0]["status_label"] == "Wiederaufbau nach Pause"
        # Diagnose-Feld bleibt für die Übungsdetail-Annotation erhalten.
        assert result[0]["weight_drop_pct"] > 5

    def test_positivkontrolle_ohne_pause_bleibt_rueckschritt(self):
        """Echtes Detraining ohne dokumentierte Pause wird NICHT unterdrückt."""
        user, ue = self._szenario(mit_pause=False)
        assert get_active_reentry_pause(user) is None
        result = self._plateau(user, ue, None)
        assert result[0]["status"] == "regression"


@pytest.mark.django_db
class TestPfad8und9EinseitigkeitUndSchwachstellen:
    """Pfad 8+9 (35.2), Integrationsebene ``collect_pdf_stats``: nach einer
    Pause mit genau einer einseitigen Session (Prod-Report 21.07.: Push 0 /
    Pull 18) liefert der Report „Nicht bewertbar" statt Gesundheitslob, und
    0-Satz-Gruppen erscheinen als Schwachstellen (keine Inversion)."""

    def test_einseitige_session_im_pdf_report(self):
        user = UserFactory()
        plan = PlanFactory(user=user)
        pull_ue = UebungFactory(bezeichnung="Rudern Audit", muskelgruppe="RUECKEN_LAT")
        heute = timezone.now()
        _session(user, plan, pull_ue, heute.date(), n_sets=18)
        stats = collect_pdf_stats(user, heute - timedelta(days=30), heute)
        # Pfad 8: keine degenerierte Balance-Bewertung
        assert stats["push_pull_bewertung"] == "Nicht bewertbar"
        assert "überwiegt" not in stats["push_pull_empfehlung"]
        assert "positiv" not in stats["push_pull_empfehlung"]
        # Pfad 9: 0-Satz-Gruppen sind die Top-Schwachstellen
        schwachstellen = stats["schwachstellen"]
        assert schwachstellen, "Schwachstellen dürfen nicht leer sein"
        assert schwachstellen[0]["saetze"] == 0
        assert any(s["status"] == "nicht_trainiert" for s in schwachstellen)
        # Die trainierte Pull-Gruppe ist KEINE Top-Schwachstelle mehr.
        assert all(s["key"] != "RUECKEN_LAT" for s in schwachstellen[:3])

    def test_positivkontrolle_beidseitig_wird_bewertet(self):
        user = UserFactory()
        plan = PlanFactory(user=user)
        push_ue = UebungFactory(bezeichnung="Bank Audit", muskelgruppe="BRUST")
        pull_ue = UebungFactory(bezeichnung="Rudern Audit 2", muskelgruppe="RUECKEN_LAT")
        heute = timezone.now()
        _session(user, plan, push_ue, heute.date(), n_sets=10)
        _session(user, plan, pull_ue, heute.date() - timedelta(days=1), n_sets=10)
        stats = collect_pdf_stats(user, heute - timedelta(days=30), heute)
        assert stats["push_pull_bewertung"] != "Nicht bewertbar"


@pytest.mark.django_db
class TestPfad10RpeAllTimeFallback:
    """Pfad 10 (35.2): Fällt die RPE-Bewertung mangels 4W-Daten auf All-Time
    zurück, ist das als solches markiert (Kontextzeile + insufficient-Flag);
    die 4W-Karte behält ihren Wert, trägt aber das Flag (Prod-Widerspruch:
    2W „zu wenig" bei n=18, 4W-Wert unmarkiert bei demselben n=18)."""

    def _saetze(self, user, plan, ue):
        heute_d = timezone.localdate()
        # All-Time-Historie außerhalb des 4W-Fensters (40 Sätze, RPE-10-lastig)
        for tag in range(5):
            _session(user, plan, ue, heute_d - timedelta(days=60 + tag), n_sets=8, gewicht=100)
        Satz.objects.filter(einheit__user=user).update(rpe=Decimal("10.0"))
        # Comeback: 18 Sätze mit moderatem RPE (unter MIN_SETS_FOR_WINDOW=30)
        comeback = _session(user, plan, ue, heute_d, n_sets=18, gewicht=85)
        Satz.objects.filter(einheit=comeback).update(rpe=Decimal("8.0"))
        return Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False)

    def test_fallback_ist_markiert(self):
        user = UserFactory()
        plan = PlanFactory(user=user)
        ue = UebungFactory()
        result = calculate_rpe_quality_analysis_windowed(
            self._saetze(user, plan, ue), reference_date=timezone.now()
        )
        assert result is not None
        assert result["insufficient_4w"] is True
        assert result["primary_window"] == "all"
        # Kontextzeile benennt den Fallback explizit …
        assert "Gesamtzeitraum" in result["recommendation"]
        # … und die 4W-Karte zeigt ihren Wert MIT insufficient-Flag
        card_4w = next(c for c in result["cards"] if c["key"] == "4w")
        assert card_4w["insufficient_data"] is True
        assert card_4w["result"] is not None

    def test_positivkontrolle_genug_4w_daten_kein_fallback(self):
        user = UserFactory()
        plan = PlanFactory(user=user)
        ue = UebungFactory()
        heute_d = timezone.localdate()
        for tag in range(5):
            _session(user, plan, ue, heute_d - timedelta(days=2 + tag), n_sets=8, gewicht=90)
        Satz.objects.filter(einheit__user=user).update(rpe=Decimal("8.0"))
        saetze = Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False)
        result = calculate_rpe_quality_analysis_windowed(saetze, reference_date=timezone.now())
        assert result["insufficient_4w"] is False
        assert result["primary_window"] == "4w"


@pytest.mark.django_db
class TestPfad11ReportBanner:
    """Pfad 11 (35.3): Der Pausen-Banner-Helfer erkennt den Report-Zeitraum-
    Fall (Detail-Semantik in test_week_classification.TestPausenImZeitraum)."""

    def test_comeback_szenario_liefert_banner(self, comeback_szenario):
        ctx = comeback_szenario
        heute_d = ctx["heute"].date()
        banner = pausen_im_zeitraum(ctx["pausen"], heute_d - timedelta(days=30), heute_d)
        assert banner is not None
        assert banner["tage"] == 14  # 2 volle Pausenwochen im Fenster
        assert banner["medizinisch"] is False

    def test_positivkontrolle_ohne_pause_kein_banner(self):
        user = UserFactory()
        heute_d = timezone.localdate()
        banner = pausen_im_zeitraum(
            TrainingsPause.objects.filter(user=user),
            heute_d - timedelta(days=30),
            heute_d,
        )
        assert banner is None
