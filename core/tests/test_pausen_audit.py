"""Phase 32.4 – AUDIT/Guard-Test: ALLE benachbarten Wochen-Volumen-Vergleichsstellen.

Dies ist der **Konvergenzgarant** gegen vergessene Pfade (Konzept §32.4, §11.1):
Er zählt die bekannten Vergleichsstellen explizit auf und prüft pro Pfad, dass
eine Wiedereinstiegs-Woche nach einer dokumentierten Pause **keine falsche
Volumen-Anstiegs-Warnung/-Bewertung** erzeugt.

Bekannte Vergleichsstellen (Stand Umsetzung – Liste bewusst als *unvollständig*
behandeln; ein neu entdeckter Pfad gehört hier ergänzt):

| # | Pfad                         | Funktion                                            |
|---|------------------------------|-----------------------------------------------------|
| 1 | Export/PDF Fatigue-Spike     | advanced_stats.calculate_fatigue_index              |
| 2 | Dashboard Fatigue-Spike      | training_stats._calculate_fatigue_index             |
| 3 | Dashboard Form-Index Volumen | training_stats._get_volume_trend_score              |
| 4 | Stats-Seite Volumen-Warnung  | training_stats._detect_volume_warnings              |
| 5 | Export Volumen-Trend         | stats_collector.calc_volume_trend_weekly            |
| 6 | Blockdauer/Phasenwechsel     | periodization.get_block_age_warning (Netto via      |
|   | (Phase 34)                   | week_classification.pausen_ausfall_wochen)          |

``INVENTORY`` unten ist ein Importierbarkeits-Guard: wird eine Vergleichsstelle
umbenannt/entfernt, schlägt der Test fehl und erzwingt ein Review.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

from django.core.cache import cache
from django.db.models import Prefetch
from django.utils import timezone

import pytest

from core.export.stats_collector import calc_volume_trend_weekly
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
from core.utils.advanced_stats import calculate_fatigue_index
from core.utils.periodization import get_block_age_warning
from core.utils.week_classification import build_weekly_volume_overview, pausen_ausfall_wochen
from core.views.training_stats import (
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
    ]
    assert all(callable(f) for f in inventory)
    assert len(inventory) == 7


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
