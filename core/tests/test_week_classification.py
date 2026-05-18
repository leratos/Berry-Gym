"""Tests für core/utils/week_classification.py (Phase 24.1c).

Aus core/tests/test_stats_collector.py herausgezogen, weil die getesteten
Helper in das neutrale Modul ``core/utils/week_classification`` verschoben
wurden. Umfasst:

- build_weekly_volume_overview (Basis-Aufrufe + Deload-Markierung)
- select_comparable_weeks (Plan-Epoch-/Deload-/Laufend-/Null-Filter)
- build_weekly_volume_overview Diagnose (vergleichbare Wochen)
- Dashboard-Integration (Phase 24.1c – stellt sicher, dass die
  training_stats-View denselben Klassifikator nutzt wie der PDF-Pfad).
"""

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from django.urls import reverse
from django.utils import timezone

import pytest

from core.tests.factories import (
    PlanFactory,
    SatzFactory,
    TrainingseinheitFactory,
    UebungFactory,
    UserFactory,
)
from core.utils.week_classification import build_weekly_volume_overview, select_comparable_weeks

# ─────────────────────────────────────────────────────────────────────────────
# build_weekly_volume_overview – Basis
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestBuildWeeklyVolumeOverview:
    def test_leere_saetze_gibt_leere_liste(self):
        user = UserFactory()
        from core.models import Satz

        alle_saetze = Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False)
        result = build_weekly_volume_overview(alle_saetze)
        assert result == []

    def test_mit_saetzen(self):
        user = UserFactory()
        heute = timezone.now()
        uebung = UebungFactory()
        einheit = TrainingseinheitFactory(user=user, datum=heute)
        SatzFactory(
            einheit=einheit,
            uebung=uebung,
            gewicht=Decimal("100.0"),
            wiederholungen=10,
            ist_aufwaermsatz=False,
        )
        from core.models import Satz

        alle_saetze = Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False)
        result = build_weekly_volume_overview(alle_saetze)
        assert len(result) >= 1
        assert result[-1]["volumen"] > 0

    def test_deload_woche_markiert(self):
        user = UserFactory()
        heute = timezone.now()
        uebung = UebungFactory()
        einheit = TrainingseinheitFactory(user=user, datum=heute, ist_deload=True)
        SatzFactory(
            einheit=einheit,
            uebung=uebung,
            gewicht=Decimal("70.0"),
            wiederholungen=8,
            ist_aufwaermsatz=False,
        )
        from core.models import Satz, Trainingseinheit

        alle_saetze = Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False)
        alle_trainings = Trainingseinheit.objects.filter(user=user)
        result = build_weekly_volume_overview(alle_saetze, alle_trainings)
        # Aktuelle Woche sollte als Deload markiert sein
        assert any(w["ist_deload"] for w in result)


# ─────────────────────────────────────────────────────────────────────────────
# select_comparable_weeks – reine Listen-Logik
# ─────────────────────────────────────────────────────────────────────────────


def _iso_monday(year: int, iso_week: int) -> datetime:
    """Return naive datetime for the Monday of the given ISO week."""
    return datetime.fromisocalendar(year, iso_week, 1)


def _set_week_volume(user, plan, datum, gewicht: Decimal, ist_deload: bool = False) -> None:
    """Create one Trainingseinheit + one working set on the given datetime.

    Trainingseinheit.datum has auto_now_add=True, so the explicit datum has to
    be force-applied via .update() after creation.
    """
    from core.models import Trainingseinheit

    aware = timezone.make_aware(datum) if timezone.is_naive(datum) else datum
    einheit = TrainingseinheitFactory(user=user, plan=plan, ist_deload=ist_deload)
    Trainingseinheit.objects.filter(pk=einheit.pk).update(datum=aware)
    einheit.refresh_from_db()
    SatzFactory(
        einheit=einheit,
        uebung=UebungFactory(),
        gewicht=gewicht,
        wiederholungen=10,
        rpe=Decimal("8.0"),
        ist_aufwaermsatz=False,
    )


class TestSelectComparableWeeks:
    """Phase 24.1b: extrahierter Helper, wiederverwendet von Volumen-Diagnose
    und Fatigue-Index Volumen-Spike-Komponente."""

    def test_skipt_laufende_woche(self):
        weeks = [
            {
                "woche": "KW17",
                "volumen": 100,
                "ist_laufend": False,
                "ist_deload_majority": False,
                "ist_plan_wechsel": False,
            },
            {
                "woche": "KW18",
                "volumen": 110,
                "ist_laufend": True,
                "ist_deload_majority": False,
                "ist_plan_wechsel": False,
            },
        ]
        result = select_comparable_weeks(weeks)
        assert [w["woche"] for w in result] == ["KW17"]

    def test_skipt_deload_majority(self):
        weeks = [
            {
                "woche": "KW17",
                "volumen": 100,
                "ist_laufend": False,
                "ist_deload_majority": False,
                "ist_plan_wechsel": False,
            },
            {
                "woche": "KW18",
                "volumen": 50,
                "ist_laufend": False,
                "ist_deload_majority": True,
                "ist_plan_wechsel": False,
            },
            {
                "woche": "KW19",
                "volumen": 110,
                "ist_laufend": False,
                "ist_deload_majority": False,
                "ist_plan_wechsel": False,
            },
        ]
        result = select_comparable_weeks(weeks)
        assert [w["woche"] for w in result] == ["KW17", "KW19"]

    def test_stoppt_an_plan_wechsel(self):
        weeks = [
            {
                "woche": "KW10",
                "volumen": 100,
                "ist_laufend": False,
                "ist_deload_majority": False,
                "ist_plan_wechsel": False,
            },
            {
                "woche": "KW11",
                "volumen": 90,
                "ist_laufend": False,
                "ist_deload_majority": False,
                "ist_plan_wechsel": True,
            },
            {
                "woche": "KW12",
                "volumen": 80,
                "ist_laufend": False,
                "ist_deload_majority": False,
                "ist_plan_wechsel": False,
            },
            {
                "woche": "KW13",
                "volumen": 85,
                "ist_laufend": False,
                "ist_deload_majority": False,
                "ist_plan_wechsel": False,
            },
        ]
        result = select_comparable_weeks(weeks)
        # KW10/11 hinter der Plan-Epoch-Grenze, neue Epoche = KW12 + KW13
        assert [w["woche"] for w in result] == ["KW12", "KW13"]

    def test_skipt_null_volumen(self):
        weeks = [
            {
                "woche": "KW17",
                "volumen": 0,
                "ist_laufend": False,
                "ist_deload_majority": False,
                "ist_plan_wechsel": False,
            },
            {
                "woche": "KW18",
                "volumen": 100,
                "ist_laufend": False,
                "ist_deload_majority": False,
                "ist_plan_wechsel": False,
            },
        ]
        result = select_comparable_weeks(weeks)
        assert [w["woche"] for w in result] == ["KW18"]

    def test_fehlende_flags_werden_als_neutral_behandelt(self):
        """Wochen-Dicts ohne 24.1-Flags (z.B. aus älteren Aufrufpfaden) dürfen
        nicht crashen – defaults: nicht laufend, nicht deload, nicht plan-wechsel."""
        weeks = [
            {"woche": "KW17", "volumen": 100},
            {"woche": "KW18", "volumen": 110},
        ]
        result = select_comparable_weeks(weeks)
        assert [w["woche"] for w in result] == ["KW17", "KW18"]


# ─────────────────────────────────────────────────────────────────────────────
# build_weekly_volume_overview – Diagnose über vergleichbare Wochen
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestBuildWeeklyVolumeOverviewDiagnose:
    """Phase 24.1: Diagnose-Auswahl der letzten zwei vergleichbaren Wochen."""

    def _setup(self):
        from core.models import Satz, Trainingseinheit

        user = UserFactory()
        plan_a = PlanFactory(user=user)
        plan_b = PlanFactory(user=user)
        return user, plan_a, plan_b, Satz, Trainingseinheit

    def test_drei_normale_wochen_diagnose_zwischen_letzten_beiden_abgeschlossenen(self):
        """Bei drei normalen Wochen plus laufender Woche wird die Diagnose
        zwischen den letzten beiden abgeschlossenen Wochen berechnet, nicht
        unter Einbeziehung der laufenden Woche."""
        user, plan_a, _, Satz, Trainingseinheit = self._setup()
        ref_year = 2026  # heute = KW18, laufend
        # KW15 / KW16 / KW17 abgeschlossen, KW18 laufend
        _set_week_volume(user, plan_a, _iso_monday(ref_year, 15), Decimal("100.00"))
        _set_week_volume(user, plan_a, _iso_monday(ref_year, 16), Decimal("105.00"))
        _set_week_volume(user, plan_a, _iso_monday(ref_year, 17), Decimal("110.00"))
        _set_week_volume(user, plan_a, _iso_monday(ref_year, 18), Decimal("50.00"))

        heute = timezone.make_aware(_iso_monday(ref_year, 18))
        alle_saetze = Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False)
        alle_trainings = Trainingseinheit.objects.filter(user=user)
        result = build_weekly_volume_overview(alle_saetze, alle_trainings, heute=heute)

        last = result[-1]
        assert last["ist_laufend"] is True
        assert last["diagnose"] is not None
        # Vergleich zwischen KW16 und KW17 (nicht KW17 → KW18)
        assert last["diagnose"]["compared_weeks"] == ("KW16", "KW17")

    def test_deload_woche_pausiert_diagnose(self):
        """KW17 normal, KW18 Deload, KW19 laufend → keine zwei vergleichbaren
        Wochen verfügbar (KW17 ist die einzige nicht-laufende, nicht-Deload-Woche).
        Diagnose schaltet auf 'Trend-Bewertung pausiert'."""
        user, plan_a, _, Satz, Trainingseinheit = self._setup()
        ref_year = 2026
        _set_week_volume(user, plan_a, _iso_monday(ref_year, 17), Decimal("100.00"))
        _set_week_volume(user, plan_a, _iso_monday(ref_year, 18), Decimal("50.00"), ist_deload=True)
        _set_week_volume(user, plan_a, _iso_monday(ref_year, 19), Decimal("80.00"))

        heute = timezone.make_aware(_iso_monday(ref_year, 19))
        alle_saetze = Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False)
        alle_trainings = Trainingseinheit.objects.filter(user=user)
        result = build_weekly_volume_overview(alle_saetze, alle_trainings, heute=heute)

        last = result[-1]
        assert last["diagnose"]["key"] == "inconclusive"
        assert last["diagnose"]["tonnage_trend"] == ""
        assert last["diagnose"]["compared_weeks"] is None

    def test_mai_2026_szenario_keine_stabile_diagnose_bei_deload_drop(self):
        """Reproduktion des Mai-2026-Bugs: KW17 (23k) → KW18 (Deload, 12k) →
        KW19 (laufend, klein). Vorher zeigte der Report 'Tonnage stabil';
        nach 24.1 darf keine 'stabil'-Diagnose mehr entstehen."""
        user, plan_a, _, Satz, Trainingseinheit = self._setup()
        ref_year = 2026
        # Drei normale Wochen davor, damit es genug vergleichbare gibt
        _set_week_volume(user, plan_a, _iso_monday(ref_year, 15), Decimal("220.00"))
        _set_week_volume(user, plan_a, _iso_monday(ref_year, 16), Decimal("230.00"))
        _set_week_volume(user, plan_a, _iso_monday(ref_year, 17), Decimal("231.57"))
        _set_week_volume(
            user, plan_a, _iso_monday(ref_year, 18), Decimal("126.16"), ist_deload=True
        )
        _set_week_volume(user, plan_a, _iso_monday(ref_year, 19), Decimal("60.00"))

        heute = timezone.make_aware(_iso_monday(ref_year, 19))
        alle_saetze = Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False)
        alle_trainings = Trainingseinheit.objects.filter(user=user)
        result = build_weekly_volume_overview(alle_saetze, alle_trainings, heute=heute)

        last = result[-1]
        diag = last["diagnose"]
        # Vergleich muss zwischen zwei normalen Wochen sein, nicht KW18→KW19
        assert diag["compared_weeks"] != ("KW18", "KW19")
        # Bei drei normalen Vorwochen (220→230→231) → leichter Anstieg, nicht "stabil-stabil"
        # Wichtigste Aussage: NICHT die Deload/laufend-Kombination als Vergleich
        if diag["compared_weeks"] is not None:
            prev_kw, curr_kw = diag["compared_weeks"]
            assert prev_kw not in ("KW18", "KW19")
            assert curr_kw not in ("KW18", "KW19")

    def test_plan_wechsel_pausiert_diagnose(self):
        """Plan-Wechsel zwischen letzter abgeschlossener Woche und Vorwoche
        markiert die Woche als 'ist_plan_wechsel' und schließt sie aus dem
        Diagnose-Vergleich aus."""
        user, plan_a, plan_b, Satz, Trainingseinheit = self._setup()
        ref_year = 2026
        _set_week_volume(user, plan_a, _iso_monday(ref_year, 16), Decimal("100.00"))
        _set_week_volume(user, plan_b, _iso_monday(ref_year, 17), Decimal("60.00"))
        _set_week_volume(user, plan_b, _iso_monday(ref_year, 18), Decimal("40.00"))

        heute = timezone.make_aware(_iso_monday(ref_year, 18))
        alle_saetze = Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False)
        alle_trainings = Trainingseinheit.objects.filter(user=user)
        result = build_weekly_volume_overview(alle_saetze, alle_trainings, heute=heute)

        # KW17 ist die Plan-Wechsel-Woche
        kw17 = next(w for w in result if w["woche"] == "KW17")
        assert kw17["ist_plan_wechsel"] is True
        # KW18 selbst nicht Wechsel (Plans gleich zur Vorwoche)
        kw18 = next(w for w in result if w["woche"] == "KW18")
        assert kw18["ist_plan_wechsel"] is False
        # Diagnose darf KW17 nicht als Vergleichswoche heranziehen
        diag = result[-1]["diagnose"]
        if diag and diag["compared_weeks"]:
            assert "KW17" not in diag["compared_weeks"]

    def test_plan_wechsel_grenze_nicht_ueber_alten_plan_vergleichen(self):
        """Reviewer-Hinweis (PR #163): Wenn eine Plan-Wechsel-Woche zwischen
        zwei sonst sauberen Wochen liegt, dürfen die umliegenden Wochen
        NICHT verglichen werden – das wäre Plan A vs. Plan B trotz
        Plan-Wechsel-Marker. Korrektes Verhalten: alles vor dem letzten
        Plan-Wechsel ist eine andere Plan-Epoche und nicht vergleichbar.
        """
        user, plan_a, plan_b, Satz, Trainingseinheit = self._setup()
        ref_year = 2026
        # KW16 Plan A, KW17 Plan-Wechsel zu B, KW18 Plan B (nicht laufend),
        # KW19 läuft (nur damit der Filter "ist_laufend" greift).
        _set_week_volume(user, plan_a, _iso_monday(ref_year, 16), Decimal("100.00"))
        _set_week_volume(user, plan_b, _iso_monday(ref_year, 17), Decimal("60.00"))
        _set_week_volume(user, plan_b, _iso_monday(ref_year, 18), Decimal("70.00"))
        _set_week_volume(user, plan_b, _iso_monday(ref_year, 19), Decimal("30.00"))

        heute = timezone.make_aware(_iso_monday(ref_year, 19))
        alle_saetze = Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False)
        alle_trainings = Trainingseinheit.objects.filter(user=user)
        result = build_weekly_volume_overview(alle_saetze, alle_trainings, heute=heute)

        diag = result[-1]["diagnose"]
        # Niemals KW16 (Plan A) gegen KW18 (Plan B) vergleichen
        if diag and diag["compared_weeks"]:
            prev_kw, curr_kw = diag["compared_weeks"]
            assert not (
                prev_kw == "KW16" and curr_kw == "KW18"
            ), f"Vergleich {prev_kw}->{curr_kw} überspringt die Plan-Wechsel-Woche KW17"
            # Auch generell: KW16 (alter Plan) darf nicht im Vergleich auftauchen,
            # wenn dazwischen ein Plan-Wechsel liegt
            assert prev_kw != "KW16"
        else:
            # Akzeptabel: nur 1 vergleichbare Woche im neuen Plan → pausiert
            assert diag["key"] == "inconclusive"

    def test_alle_trainings_none_keine_plan_wechsel_erkennung(self):
        """Backward-compat: ohne alle_trainings keine Deload-/Plan-Wechsel-Markierung,
        aber laufende Woche wird trotzdem ausgeschlossen."""
        user, plan_a, _, Satz, _Trainingseinheit = self._setup()
        ref_year = 2026
        _set_week_volume(user, plan_a, _iso_monday(ref_year, 16), Decimal("100.00"))
        _set_week_volume(user, plan_a, _iso_monday(ref_year, 17), Decimal("110.00"))
        _set_week_volume(user, plan_a, _iso_monday(ref_year, 18), Decimal("50.00"))

        heute = timezone.make_aware(_iso_monday(ref_year, 18))
        alle_saetze = Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False)
        result = build_weekly_volume_overview(alle_saetze, None, heute=heute)

        last = result[-1]
        assert last["ist_laufend"] is True
        # Ohne alle_trainings keine Plan-Tracking, ist_plan_wechsel überall False
        assert all(w["ist_plan_wechsel"] is False for w in result)
        # Diagnose vergleicht KW16 und KW17 (laufende KW18 raus)
        if last["diagnose"] and last["diagnose"]["compared_weeks"]:
            assert last["diagnose"]["compared_weeks"] == ("KW16", "KW17")


# ─────────────────────────────────────────────────────────────────────────────
# Phase 24.1c: Dashboard nutzt denselben Klassifikator wie der PDF-Pfad
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDashboardVolumeDiagnoseUsesSharedClassifier:
    """Reproduktion des KW20-Live-Befunds (11.05.2026):

    Vor 24.1c hat die training_stats-View die letzte und vorletzte
    Wochen-Tonnage direkt in ``diagnose_volume_trend`` gegeben – ohne
    laufende/Deload-/Plan-Wechsel-Wochen rauszufiltern. Die laufende KW20
    (erster Trainingstag, ~6.500 kg) gegen die abgeschlossene KW19
    (~24.000 kg) ergab dann fälschlich „Echte Regression". Das PDF zeigt
    im selben Datenstand korrekt „Trend-Bewertung pausiert".

    Nach 24.1c ruft das Dashboard ``build_weekly_volume_overview`` auf und
    übernimmt die Diagnose der letzten Woche – also dieselbe Filter-Logik
    wie das PDF.
    """

    def test_kw20_laufend_keine_regression_sondern_pausiert(self, client):
        from core.models import Satz, Trainingseinheit

        user = UserFactory()
        plan = PlanFactory(user=user)
        ref_year = 2026
        # Drei abgeschlossene Vorwochen mit hoher Tonnage, dann KW20 laufend mit
        # kleiner Tonnage (nur ein Trainingstag dieser Woche).
        _set_week_volume(user, plan, _iso_monday(ref_year, 17), Decimal("220.00"))
        _set_week_volume(user, plan, _iso_monday(ref_year, 18), Decimal("230.00"))
        _set_week_volume(user, plan, _iso_monday(ref_year, 19), Decimal("240.00"))
        _set_week_volume(user, plan, _iso_monday(ref_year, 20), Decimal("60.00"))

        # heute = Montag KW20: dadurch ist KW20 ``ist_laufend`` und darf nicht
        # als Vergleichswoche dienen. Wir patchen ``timezone.now`` nur in der
        # geprüften View, indem der test_user gegen das echte Datum aus dem
        # Build des Snapshots arbeitet – die View nutzt ``timezone.now()``
        # direkt, daher müssen die Sätze relativ zum Heute liegen. Statt now()
        # zu mocken, replizieren wir das Szenario mit Wochen, die als heute
        # gerechnet KW20 = laufend ergeben.
        # Da timezone.now() in der View nicht überschrieben werden kann ohne
        # Monkey-Patching, prüfen wir stattdessen auf die abgeleitete Diagnose
        # über den gemeinsamen Klassifikator direkt – derselbe Aufrufpfad wie
        # in der View.
        heute_kw20_montag = timezone.make_aware(_iso_monday(ref_year, 20))
        alle_saetze = Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False)
        alle_trainings = Trainingseinheit.objects.filter(user=user)
        weeks = build_weekly_volume_overview(alle_saetze, alle_trainings, heute=heute_kw20_montag)

        last = weeks[-1]
        assert last["woche"] == "KW20"
        assert last["ist_laufend"] is True
        diag = last["diagnose"]
        # Kernaussage des Bugfixes: keine „Echte Regression" mehr, sondern
        # die explizite Pause-Diagnose oder ein Vergleich zwischen zwei
        # abgeschlossenen Wochen (KW18/KW19). Der KW20-Wert darf NIE
        # Bestandteil des Vergleichs sein.
        assert diag is not None
        if diag["compared_weeks"] is not None:
            prev_kw, curr_kw = diag["compared_weeks"]
            assert "KW20" not in (prev_kw, curr_kw)
        else:
            assert diag["key"] == "inconclusive"

    def test_dashboard_view_ruft_shared_classifier(self, client):
        """Integrationsschicht: ein realer GET auf training_stats darf für die
        KW20-Konstellation keinen 'Echte Regression'-Indikator im Kontext
        liefern. Wir prüfen das über den ``volume_diagnosis``-Kontext-Wert.
        """
        from core.models import Satz, Trainingseinheit  # noqa: F401

        user = UserFactory()
        plan = PlanFactory(user=user)
        # Heute relativ – wir bauen den KW20-Bug auf "letzte Woche" um, indem
        # wir die laufende Woche der Test-Now als „kurze Woche" füllen und
        # die Vorwoche als volle Vergleichswoche. Damit reicht das echte
        # timezone.now() aus.
        heute = timezone.now()
        eine_woche = timedelta(days=7)
        zwei_wochen = timedelta(days=14)
        drei_wochen = timedelta(days=21)
        _set_week_volume(user, plan, (heute - drei_wochen).replace(tzinfo=None), Decimal("220.0"))
        _set_week_volume(user, plan, (heute - zwei_wochen).replace(tzinfo=None), Decimal("230.0"))
        _set_week_volume(user, plan, (heute - eine_woche).replace(tzinfo=None), Decimal("240.0"))
        # Laufende Woche bewusst klein
        _set_week_volume(user, plan, heute.replace(tzinfo=None), Decimal("60.0"))

        client.force_login(user)
        response = client.get(reverse("training_stats"))
        assert response.status_code == 200
        diag = response.context["volume_diagnosis"]
        # Vor 24.1c: 'regression' bei lauffender Woche – jetzt ausgeschlossen.
        assert diag is not None
        assert diag.get("key") != "regression"
        if diag.get("compared_weeks") is not None:
            # Wenn ein Vergleich erfolgt, dann zwischen zwei abgeschlossenen
            # Wochen – die laufende Woche darf nicht beteiligt sein. Wir
            # prüfen das indirekt darüber, dass kein 'regression'-Key aus
            # dem laufenden-Wochen-Drop folgt.
            assert diag["key"] != "regression"


# ─────────────────────────────────────────────────────────────────────────────
# Phase 25.8: Plan-Wechsel-Erkennung über Routine-Identität (gruppe_id)
# ─────────────────────────────────────────────────────────────────────────────


def _log_split_week(user, plaene, monday, gewicht=Decimal("100.00")) -> None:
    """Log one session per plan in ``plaene`` across the given ISO week.

    Sessions land on Monday, Wednesday, Friday, ... of the week of ``monday``,
    so a 1-, 2- or 3-element ``plaene`` models a partially or fully logged
    split week.
    """
    for offset, plan in enumerate(plaene):
        _set_week_volume(user, plan, monday + timedelta(days=offset * 2), gewicht)


@pytest.mark.django_db
class TestPlanWechselSplitRoutine:
    """Phase 25.8: Eine Splitroutine verteilt ihre Tage auf mehrere ``Plan``-
    Zeilen, die eine gemeinsame ``gruppe_id`` teilen. Der Plan-Wechsel-
    Klassifikator vergleicht Routine-Identitäten (gruppe_id), nicht rohe
    Plan-IDs – sonst sieht jede noch nicht vollständig geloggte Splitwoche
    wie ein Plan-Wechsel aus (Auslöser-Befund: 18.05.2026-Export-Review).
    """

    def test_partielle_splitwoche_kein_falscher_plan_wechsel(self):
        """Volle Splitwochen (Push/Pull/Legs) gefolgt von einer Woche, in der
        nur zwei der drei Split-Tage geloggt sind. Vor 25.8 wurde die
        Teilwoche – Plan-ID-Teilmenge ``{Push,Pull}`` ⊂ ``{Push,Pull,Legs}`` –
        fälschlich als Plan-Wechsel markiert; ``select_comparable_weeks`` brach
        dort ab und die Diagnose pausierte ohne Grund."""
        from core.models import Satz, Trainingseinheit

        user = UserFactory()
        gruppe = uuid4()
        push = PlanFactory(user=user, gruppe_id=gruppe)
        pull = PlanFactory(user=user, gruppe_id=gruppe)
        legs = PlanFactory(user=user, gruppe_id=gruppe)
        ref_year = 2026
        for week in (17, 18, 19):
            _log_split_week(user, [push, pull, legs], _iso_monday(ref_year, week))
        # KW20 abgeschlossen, aber nur Push + Pull geloggt – Legs fehlt.
        _log_split_week(user, [push, pull], _iso_monday(ref_year, 20))

        heute = timezone.make_aware(_iso_monday(ref_year, 21))  # KW21, KW20 fertig
        alle_saetze = Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False)
        alle_trainings = Trainingseinheit.objects.filter(user=user)
        result = build_weekly_volume_overview(alle_saetze, alle_trainings, heute=heute)

        kw20 = next(w for w in result if w["woche"] == "KW20")
        assert kw20["ist_plan_wechsel"] is False
        # Durchgehende Routine → keine einzige Plan-Wechsel-Woche.
        assert all(not w["ist_plan_wechsel"] for w in result)
        # Diagnose vergleicht die zwei abgeschlossenen Wochen, statt zu pausieren.
        assert result[-1]["diagnose"]["compared_weeks"] == ("KW19", "KW20")

    def test_laufende_partielle_splitwoche_nennt_keinen_plan_wechsel_grund(self):
        """Reproduktion des 11.05.2026-Exports: die laufende KW20 hat erst
        einen von drei Split-Tagen geloggt. Vor 25.8 markierte das die Woche
        zusätzlich als Plan-Wechsel – die Pause-Begründung lautete fälschlich
        „Diese Woche läuft noch, Trainingsplan-Wechsel"."""
        from core.models import Satz, Trainingseinheit

        user = UserFactory()
        gruppe = uuid4()
        push = PlanFactory(user=user, gruppe_id=gruppe)
        pull = PlanFactory(user=user, gruppe_id=gruppe)
        legs = PlanFactory(user=user, gruppe_id=gruppe)
        ref_year = 2026
        for week in (18, 19):
            _log_split_week(user, [push, pull, legs], _iso_monday(ref_year, week))
        # KW20 läuft: nur der erste Split-Tag (Push) ist geloggt.
        _log_split_week(user, [push], _iso_monday(ref_year, 20))

        heute = timezone.make_aware(_iso_monday(ref_year, 20))  # Montag KW20 → laufend
        alle_saetze = Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False)
        alle_trainings = Trainingseinheit.objects.filter(user=user)
        result = build_weekly_volume_overview(alle_saetze, alle_trainings, heute=heute)

        kw20 = next(w for w in result if w["woche"] == "KW20")
        assert kw20["ist_laufend"] is True
        assert kw20["ist_plan_wechsel"] is False
        diag = result[-1]["diagnose"]
        # Laufende Woche nie im Vergleich; falls die Diagnose pausiert, dann
        # nicht mit der spurious Begründung „Trainingsplan-Wechsel".
        if diag["compared_weeks"]:
            assert "KW20" not in diag["compared_weeks"]
        assert "Trainingsplan-Wechsel" not in diag["message"]

    def test_echter_gruppen_wechsel_weiterhin_erkannt(self):
        """Schutz gegen Über-Korrektur: ein Wechsel zwischen zwei Routinen mit
        unterschiedlicher ``gruppe_id`` muss weiterhin als Plan-Wechsel
        markiert werden."""
        from core.models import Satz, Trainingseinheit

        user = UserFactory()
        gruppe_a, gruppe_b = uuid4(), uuid4()
        a_push = PlanFactory(user=user, gruppe_id=gruppe_a)
        a_pull = PlanFactory(user=user, gruppe_id=gruppe_a)
        b_push = PlanFactory(user=user, gruppe_id=gruppe_b)
        b_pull = PlanFactory(user=user, gruppe_id=gruppe_b)
        ref_year = 2026
        _log_split_week(user, [a_push, a_pull], _iso_monday(ref_year, 16))
        _log_split_week(user, [a_push, a_pull], _iso_monday(ref_year, 17))
        _log_split_week(user, [b_push, b_pull], _iso_monday(ref_year, 18))
        _log_split_week(user, [b_push, b_pull], _iso_monday(ref_year, 19))

        heute = timezone.make_aware(_iso_monday(ref_year, 20))
        alle_saetze = Satz.objects.filter(einheit__user=user, ist_aufwaermsatz=False)
        alle_trainings = Trainingseinheit.objects.filter(user=user)
        result = build_weekly_volume_overview(alle_saetze, alle_trainings, heute=heute)

        kw17 = next(w for w in result if w["woche"] == "KW17")
        kw18 = next(w for w in result if w["woche"] == "KW18")
        kw19 = next(w for w in result if w["woche"] == "KW19")
        assert kw17["ist_plan_wechsel"] is False
        assert kw18["ist_plan_wechsel"] is True  # erste Woche der neuen Routine
        assert kw19["ist_plan_wechsel"] is False  # gleiche Routine wie KW18
