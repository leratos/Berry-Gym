"""
Data Analyzer - Trainingshistorie-Analyse für AI Coach
Analysiert letzte 30 Tage Training und bereitet Daten für LLM auf
"""

import json
from collections import defaultdict
from datetime import timedelta
from typing import Any, Dict, List

from django.utils import timezone


class TrainingAnalyzer:
    """
    Analysiert Trainingshistorie und berechnet Metriken
    """

    # Muskelgruppen-Definitionen (aus core/views.py)
    MUSKELGRUPPEN = [
        "Brust",
        "Rücken",
        "Beine",
        "Schultern",
        "Bizeps",
        "Trizeps",
        "Bauch",
        "Unterer Rücken",
        "Waden",
        "Unterarme",
        "Nacken",
        "Trapez",
        "Vordere Schulter",
        "Seitliche Schulter",
        "Hintere Schulter",
        "Oberer Rücken",
        "Mittlerer Rücken",
        "Latissimus",
        "Oberschenkel Vorne",
        "Oberschenkel Hinten",
        "Gesäß",
        "Hüfte",
    ]

    # Push/Pull Kategorisierung
    PUSH_GROUPS = ["Brust", "Schultern", "Trizeps", "Vordere Schulter", "Seitliche Schulter"]
    PULL_GROUPS = [
        "Rücken",
        "Bizeps",
        "Trapez",
        "Oberer Rücken",
        "Mittlerer Rücken",
        "Latissimus",
        "Hintere Schulter",
    ]

    def __init__(self, user_id: int, days: int = 30):
        """
        Initialisiert Analyzer für spezifischen User

        Args:
            user_id: User ID für Analyse
            days: Anzahl Tage zurück (default: 30)
        """
        self.user_id = user_id
        self.days = days
        self.start_date = timezone.now() - timedelta(days=days)

    def analyze(self) -> Dict[str, Any]:
        """
        Hauptfunktion: Analysiert Training und gibt strukturierte Daten zurück

        Returns:
            Dict mit allen relevanten Metriken für LLM
        """
        from core.models import Trainingseinheit  # Satz, Uebung via ForeignKey Relations

        # Trainingseinheiten laden
        sessions = Trainingseinheit.objects.filter(
            user_id=self.user_id, datum__gte=self.start_date
        ).order_by("datum")

        if not sessions.exists():
            return self._empty_analysis()

        # Daten sammeln
        muscle_volume = defaultdict(
            lambda: {"effective_reps": 0, "avg_rpe": [], "last_trained": None}
        )
        exercise_performance = {}
        total_sessions = sessions.count()
        total_duration = sum(s.dauer_minuten or 0 for s in sessions)

        # Alle Sätze durchgehen
        for session in sessions:
            for satz in session.saetze.select_related("uebung").filter(ist_aufwaermsatz=False):
                if not satz.wiederholungen or not satz.rpe:
                    continue

                # Effektive Wiederholungen berechnen (RPE-weighted)
                effective_reps = satz.wiederholungen * (float(satz.rpe) / 10.0)

                # Muskelgruppen-Statistiken
                mg = satz.uebung.muskelgruppe
                muscle_volume[mg]["effective_reps"] += effective_reps
                muscle_volume[mg]["avg_rpe"].append(float(satz.rpe))
                if (
                    not muscle_volume[mg]["last_trained"]
                    or session.datum > muscle_volume[mg]["last_trained"]
                ):
                    muscle_volume[mg]["last_trained"] = session.datum

                # Exercise Performance Tracking
                ex_name = satz.uebung.bezeichnung
                if ex_name not in exercise_performance:
                    exercise_performance[ex_name] = {"records": [], "muscle_group": mg}

                # 1RM berechnen (Epley-Formel)
                if satz.gewicht and satz.wiederholungen >= 1:
                    one_rm = float(satz.gewicht) * (1 + satz.wiederholungen / 30.0)
                    exercise_performance[ex_name]["records"].append(
                        {
                            "date": session.datum.isoformat(),
                            "1rm": round(one_rm, 1),
                            "weight": float(satz.gewicht),
                            "reps": satz.wiederholungen,
                            "rpe": float(satz.rpe),
                        }
                    )

        # Durchschnitte berechnen
        for mg in muscle_volume:
            if muscle_volume[mg]["avg_rpe"]:
                muscle_volume[mg]["avg_rpe"] = round(
                    sum(muscle_volume[mg]["avg_rpe"]) / len(muscle_volume[mg]["avg_rpe"]), 1
                )
                muscle_volume[mg]["last_trained"] = muscle_volume[mg]["last_trained"].isoformat()

        # Exercise Performance: Trends berechnen
        for ex_name in exercise_performance:
            records = exercise_performance[ex_name]["records"]
            if len(records) >= 2:
                # Sortieren nach Datum
                records.sort(key=lambda x: x["date"])
                first_1rm = records[0]["1rm"]
                last_1rm = records[-1]["1rm"]
                trend = round(last_1rm - first_1rm, 1)
                exercise_performance[ex_name]["trend"] = (
                    f"+{trend}kg" if trend > 0 else f"{trend}kg"
                )
                exercise_performance[ex_name]["last_1rm"] = last_1rm
                exercise_performance[ex_name]["avg_rpe"] = round(
                    sum(r["rpe"] for r in records) / len(records), 1
                )
            else:
                exercise_performance[ex_name]["trend"] = "Nicht genug Daten"
                exercise_performance[ex_name]["last_1rm"] = records[0]["1rm"] if records else 0
                exercise_performance[ex_name]["avg_rpe"] = records[0]["rpe"] if records else 0

        # Push/Pull Balance
        push_volume = sum(
            muscle_volume[mg]["effective_reps"] for mg in self.PUSH_GROUPS if mg in muscle_volume
        )
        pull_volume = sum(
            muscle_volume[mg]["effective_reps"] for mg in self.PULL_GROUPS if mg in muscle_volume
        )

        # Schwachstellen identifizieren
        weaknesses = self._identify_weaknesses(muscle_volume, exercise_performance)

        # Trainingsfrequenz
        weeks = self.days / 7
        frequency_per_week = round(total_sessions / weeks, 1)

        return {
            "user_id": self.user_id,
            "analysis_period": f"{self.days} days",
            "training_stats": {
                "total_sessions": total_sessions,
                "avg_duration_minutes": (
                    round(total_duration / total_sessions) if total_sessions > 0 else 0
                ),
                "frequency_per_week": frequency_per_week,
            },
            "muscle_groups": dict(muscle_volume),
            "exercise_performance": exercise_performance,
            "push_pull_balance": {
                "push_volume": round(push_volume, 1),
                "pull_volume": round(pull_volume, 1),
                "ratio": round(push_volume / pull_volume, 2) if pull_volume > 0 else 0,
                "balanced": (
                    0.85 <= (push_volume / pull_volume) <= 1.15 if pull_volume > 0 else False
                ),
            },
            "weaknesses": weaknesses,
        }

    def _identify_weaknesses(self, muscle_volume: dict, exercise_performance: dict) -> List[str]:
        """
        Identifiziert Schwachstellen basierend auf Volumen und Performance

        Returns:
            Liste mit Schwachstellen-Beschreibungen
        """
        weaknesses = []

        # Durchschnittsvolumen berechnen
        if muscle_volume:
            avg_volume = sum(mg["effective_reps"] for mg in muscle_volume.values()) / len(
                muscle_volume
            )

            # Muskelgruppen mit <60% des Durchschnitts
            for mg, data in muscle_volume.items():
                if data["effective_reps"] < avg_volume * 0.6:
                    weaknesses.append(
                        f"{mg}: Untertrainiert (nur {round(data['effective_reps'])} eff. Wdh vs. Ø {round(avg_volume)})"
                    )

        # Übungen die nicht mehr gemacht wurden
        for ex_name, data in exercise_performance.items():
            if data["records"]:
                from dateutil import parser

                last_date = parser.parse(data["records"][-1]["date"])
                if last_date.tzinfo is None:
                    last_date = timezone.make_aware(last_date)
                days_ago = (timezone.now() - last_date).days
                if days_ago > 14:  # Nicht in den letzten 2 Wochen
                    weaknesses.append(f"{ex_name}: Nicht mehr trainiert seit {days_ago} Tagen")

        return weaknesses

    def _empty_analysis(self) -> Dict[str, Any]:
        """
        Gibt leere Analyse zurück wenn keine Daten vorhanden
        """
        return {
            "user_id": self.user_id,
            "analysis_period": f"{self.days} days",
            "training_stats": {
                "total_sessions": 0,
                "avg_duration_minutes": 0,
                "frequency_per_week": 0,
            },
            "muscle_groups": {},
            "exercise_performance": {},
            "push_pull_balance": {
                "push_volume": 0,
                "pull_volume": 0,
                "ratio": 0,
                "balanced": False,
            },
            "weaknesses": ["Keine Trainingsdaten vorhanden"],
        }

    def to_json(self, analysis: Dict[str, Any] = None) -> str:
        """
        Konvertiert Analyse zu JSON String für LLM

        Args:
            analysis: Optional, wenn None wird analyze() aufgerufen

        Returns:
            JSON String
        """
        if analysis is None:
            analysis = self.analyze()
        return json.dumps(analysis, indent=2, ensure_ascii=False)

    def print_summary(self, analysis: Dict[str, Any] = None):
        """
        Gibt Human-Readable Summary aus

        Args:
            analysis: Optional, wenn None wird analyze() aufgerufen
        """
        if analysis is None:
            analysis = self.analyze()

        print("\n" + "=" * 60)
        print(f"📊 TRAININGSANALYSE - User {analysis['user_id']}")
        print(f"📅 Zeitraum: {analysis['analysis_period']}")
        print("=" * 60)

        stats = analysis["training_stats"]
        print("\n🏋️ Training:")
        print(f"   Sessions: {stats['total_sessions']}")
        print(f"   Durchschnitt: {stats['avg_duration_minutes']} min")
        print(f"   Frequenz: {stats['frequency_per_week']}x pro Woche")

        print("\n💪 Muskelgruppen (Top 5 nach Volumen):")
        sorted_mg = sorted(
            analysis["muscle_groups"].items(), key=lambda x: x[1]["effective_reps"], reverse=True
        )[:5]
        for mg, data in sorted_mg:
            print(f"   {mg}: {round(data['effective_reps'])} eff. Wdh (Ø RPE {data['avg_rpe']})")

        print("\n📈 Exercise Performance (Top 5 nach 1RM):")
        sorted_ex = sorted(
            analysis["exercise_performance"].items(),
            key=lambda x: x[1].get("last_1rm", 0),
            reverse=True,
        )[:5]
        for ex, data in sorted_ex:
            trend = data.get("trend", "N/A")
            print(f"   {ex}: {data.get('last_1rm', 0)}kg 1RM ({trend})")

        balance = analysis["push_pull_balance"]
        print("\n⚖️ Push/Pull Balance:")
        print(f"   Push: {balance['push_volume']} | Pull: {balance['pull_volume']}")
        print(
            f"   Ratio: {balance['ratio']} {'✓ Balanced' if balance['balanced'] else '✗ Unbalanced'}"
        )

        if analysis["weaknesses"]:
            print("\n⚠️ Schwachstellen:")
            for weakness in analysis["weaknesses"][:5]:  # Top 5
                print(f"   - {weakness}")

        print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    # Test: Analyzer mit User ID 1
    from db_client import DatabaseClient

    print("=== Training Analyzer Test ===\n")

    try:
        with DatabaseClient() as db:
            analyzer = TrainingAnalyzer(user_id=1, days=30)

            print("🔍 Analysiere Trainingshistorie...")
            analysis = analyzer.analyze()

            # Human-Readable Summary
            analyzer.print_summary(analysis)

            # JSON für LLM
            print("📄 JSON Output für LLM:")
            print(analyzer.to_json(analysis)[:500] + "...\n")  # Erste 500 Zeichen

    except Exception as e:
        print(f"\n❌ Fehler: {e}")
        import traceback

        traceback.print_exc()
