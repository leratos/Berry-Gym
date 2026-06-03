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

``INVENTORY`` unten ist ein Importierbarkeits-Guard: wird eine Vergleichsstelle
umbenannt/entfernt, schlägt der Test fehl und erzwingt ein Review.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db.models import Prefetch
from django.utils import timezone

import pytest

from core.export.stats_collector import calc_volume_trend_weekly
from core.models import Satz, Trainingseinheit, TrainingsPause
from core.tests.factories import (
    PlanFactory,
    SatzFactory,
    TrainingseinheitFactory,
    TrainingsPauseFactory,
    UebungFactory,
    UserFactory,
)
from core.utils.advanced_stats import calculate_fatigue_index
from core.utils.week_classification import build_weekly_volume_overview
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
    ]
    assert all(callable(f) for f in inventory)
    assert len(inventory) == 5


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
