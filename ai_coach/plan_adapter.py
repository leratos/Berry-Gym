"""
Plan Adapter - Automatische Plan-Anpassung
Hybrid-Ansatz: Regelbasierte Checks + KI-gestützte Optimierung

Stufe 1 (kostenlos): Performance-Warnungen
- RPE zu niedrig (<7 über 3+ Sessions)
- RPE zu hoch (>8.5 über 3+ Sessions)
- Muskelgruppen-Balance (>14 Tage nicht trainiert)
- Plateau-Erkennung (1RM stagniert 4+ Wochen)

Stufe 2 (KI, ~0.003€): Optimierungs-Vorschläge
- LLM analysiert Performance-Historie
- Schlägt konkrete Änderungen vor
- Diff-View: Alt vs Neu mit Begründungen
"""

import os
import sys
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict

# Django Setup
if __name__ == "__main__":
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, project_root)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    import django
    django.setup()

from django.utils import timezone
from django.db.models import Avg, Max, Count, Sum, Q, F
from core.models import Plan, PlanUebung, Trainingseinheit, Satz, Uebung, MUSKELGRUPPEN
from ai_coach.llm_client import LLMClient


class PlanAdapter:
    """Analysiert und optimiert Trainingspläne basierend auf Performance"""
    
    def __init__(self, plan_id: int, user_id: Optional[int] = None):
        self.plan_id = plan_id
        self.plan = Plan.objects.get(id=plan_id)
        self.user_id = user_id or self.plan.user_id
        self.llm_client = LLMClient()
        
    def analyze_plan_performance(self, days: int = 30) -> Dict[str, Any]:
        """
        Regelbasierte Performance-Analyse (kostenlos)
        
        Returns:
            {
                'warnings': [...],
                'suggestions': [...],
                'metrics': {...}
            }
        """
        warnings = []
        suggestions = []
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # 1. RPE-Analyse pro Übung
        plan_exercises = PlanUebung.objects.filter(plan=self.plan).select_related('uebung')
        
        for plan_uebung in plan_exercises:
            uebung = plan_uebung.uebung
            
            # Letzte 3 Sessions für diese Übung
            recent_sessions = Trainingseinheit.objects.filter(
                user_id=self.user_id,
                datum__gte=cutoff_date,
                plan=self.plan
            ).order_by('-datum')[:3]
            
            if not recent_sessions:
                continue
            
            # RPE-Werte sammeln (nur Arbeitssätze)
            rpe_values = []
            for session in recent_sessions:
                saetze = Satz.objects.filter(
                    einheit=session,
                    uebung=uebung,
                    ist_aufwaermsatz=False,
                    rpe__isnull=False
                )
                rpe_values.extend([s.rpe for s in saetze])
            
            if len(rpe_values) >= 3:
                avg_rpe = sum(rpe_values) / len(rpe_values)
                
                # Warnung: RPE zu niedrig
                if avg_rpe < 7.0:
                    warnings.append({
                        'type': 'rpe_low',
                        'severity': 'info',
                        'exercise': uebung.bezeichnung,
                        'value': float(round(avg_rpe, 1)),
                        'message': f'{uebung.bezeichnung}: RPE zu niedrig ({avg_rpe:.1f}). Gewicht erhöhen empfohlen.',
                        'action': 'increase_weight'
                    })
                
                # Warnung: RPE zu hoch
                if avg_rpe > 8.5:
                    warnings.append({
                        'type': 'rpe_high',
                        'severity': 'warning',
                        'exercise': uebung.bezeichnung,
                        'value': float(round(avg_rpe, 1)),
                        'message': f'{uebung.bezeichnung}: RPE sehr hoch ({avg_rpe:.1f}). Volumen reduzieren oder Deload.',
                        'action': 'reduce_volume'
                    })
        
        # 2. Muskelgruppen-Balance
        muskelgruppen_last_trained = self._check_muscle_balance(days=14)
        muskelgruppen_dict = dict(MUSKELGRUPPEN)
        
        for muskelgruppe, days_ago in muskelgruppen_last_trained.items():
            muskelgruppe_label = muskelgruppen_dict.get(muskelgruppe, muskelgruppe)
            
            if days_ago is None:
                warnings.append({
                    'type': 'muscle_untrained',
                    'severity': 'warning',
                    'muscle_group': muskelgruppe,
                    'message': f'{muskelgruppe_label}: Noch nie in diesem Plan trainiert.',
                    'action': 'add_exercises'
                })
            elif days_ago > 14:
                warnings.append({
                    'type': 'muscle_neglected',
                    'severity': 'info',
                    'muscle_group': muskelgruppe,
                    'days_ago': days_ago,
                    'message': f'{muskelgruppe_label}: {days_ago} Tage nicht trainiert. Balance-Problem.',
                    'action': 'adjust_frequency'
                })
        
        # 3. Plateau-Erkennung (1RM Stagnation)
        plateau_exercises = self._detect_plateaus(weeks=4)
        
        for exercise_name, weeks_stagnant in plateau_exercises.items():
            warnings.append({
                'type': 'plateau',
                'severity': 'warning',
                'exercise': exercise_name,
                'weeks': weeks_stagnant,
                'message': f'{exercise_name}: Keine Fortschritte seit {weeks_stagnant} Wochen.',
                'action': 'change_rep_range'
            })
        
        # 4. Volumen-Check
        volume_warning = self._check_volume_trends(days=days)
        if volume_warning:
            warnings.append(volume_warning)
        
        # Metrics zusammenfassen
        metrics = {
            'total_warnings': len(warnings),
            'critical_warnings': len([w for w in warnings if w['severity'] == 'warning']),
            'analysis_period_days': days,
            'analyzed_at': timezone.now().isoformat()
        }
        
        return {
            'warnings': warnings,
            'suggestions': suggestions,
            'metrics': metrics
        }
    
    def _check_muscle_balance(self, days: int = 14) -> Dict[str, Optional[int]]:
        """Prüft wann Muskelgruppen zuletzt trainiert wurden"""
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Alle Muskelgruppen im Plan
        plan_exercises = PlanUebung.objects.filter(plan=self.plan).select_related('uebung')
        muscle_groups = set()
        for pu in plan_exercises:
            if pu.uebung.muskelgruppe:
                muscle_groups.add(pu.uebung.muskelgruppe)
        
        # Letzte Training-Session pro Muskelgruppe
        result = {}
        for muskelgruppe in muscle_groups:
            last_training = Trainingseinheit.objects.filter(
                user_id=self.user_id,
                plan=self.plan,
                saetze__uebung__muskelgruppe=muskelgruppe
            ).order_by('-datum').first()
            
            if last_training:
                days_ago = (timezone.now() - last_training.datum).days
                result[muskelgruppe] = days_ago
            else:
                result[muskelgruppe] = None
        
        return result
    
    def _detect_plateaus(self, weeks: int = 4) -> Dict[str, int]:
        """Erkennt 1RM-Stagnation"""
        cutoff_date = timezone.now() - timedelta(weeks=weeks)
        plateau_exercises = {}
        
        plan_exercises = PlanUebung.objects.filter(plan=self.plan).select_related('uebung')
        
        for plan_uebung in plan_exercises:
            uebung = plan_uebung.uebung
            
            # 1RM über Zeit (wöchentlich)
            sessions = Trainingseinheit.objects.filter(
                user_id=self.user_id,
                datum__gte=cutoff_date,
                plan=self.plan
            ).order_by('datum')
            
            weekly_1rm = []
            for session in sessions:
                # Beste 1RM dieser Session
                saetze = Satz.objects.filter(
                    einheit=session,
                    uebung=uebung,
                    ist_aufwaermsatz=False,
                    gewicht__isnull=False,
                    wiederholungen__isnull=False,
                    wiederholungen__gte=1,
                    wiederholungen__lte=12
                ).exclude(gewicht=0)
                
                for satz in saetze:
                    # Epley-Formel: 1RM = weight × (1 + reps/30)
                    estimated_1rm = float(satz.gewicht) * (1 + satz.wiederholungen / 30)
                    weekly_1rm.append(estimated_1rm)
            
            # Stagnation: Keine Verbesserung über mehrere Wochen
            if len(weekly_1rm) >= weeks:
                max_early = max(weekly_1rm[:len(weekly_1rm)//2])
                max_late = max(weekly_1rm[len(weekly_1rm)//2:])
                
                # Weniger als 2.5% Fortschritt = Plateau
                if max_late < max_early * 1.025:
                    plateau_exercises[uebung.bezeichnung] = weeks
        
        return plateau_exercises
    
    def _check_volume_trends(self, days: int = 30) -> Optional[Dict[str, Any]]:
        """Prüft auf extreme Volumen-Änderungen"""
        cutoff_date = timezone.now() - timedelta(days=days)
        
        sessions = Trainingseinheit.objects.filter(
            user_id=self.user_id,
            datum__gte=cutoff_date,
            plan=self.plan
        ).order_by('datum')
        
        if sessions.count() < 4:
            return None
        
        # Volumen pro Session berechnen
        volumes = []
        for session in sessions:
            saetze = Satz.objects.filter(
                einheit=session,
                ist_aufwaermsatz=False
            ).exclude(gewicht=0)
            
            total_volume = sum([
                float(s.gewicht) * s.wiederholungen 
                for s in saetze 
                if s.gewicht and s.wiederholungen
            ])
            volumes.append(total_volume)
        
        if not volumes:
            return None
        
        # Erste vs Letzte Hälfte vergleichen
        avg_early = sum(volumes[:len(volumes)//2]) / (len(volumes)//2)
        avg_late = sum(volumes[len(volumes)//2:]) / (len(volumes) - len(volumes)//2)
        
        if avg_early == 0:
            return None
        
        change_pct = ((avg_late - avg_early) / avg_early) * 100
        
        # Warnung bei >20% Volumen-Spike
        if change_pct > 20:
            return {
                'type': 'volume_spike',
                'severity': 'warning',
                'change_percent': float(round(change_pct, 1)),
                'message': f'Volumen um {change_pct:.1f}% gestiegen. Übertraining-Risiko.',
                'action': 'deload'
            }
        
        # Warnung bei >30% Volumen-Drop
        if change_pct < -30:
            return {
                'type': 'volume_drop',
                'severity': 'info',
                'change_percent': float(round(change_pct, 1)),
                'message': f'Volumen um {abs(change_pct):.1f}% gefallen. Mehr Konsistenz empfohlen.',
                'action': 'increase_frequency'
            }
        
        return None
    
    def suggest_optimizations(self, days: int = 30) -> Dict[str, Any]:
        """
        KI-gestützte Optimierungs-Vorschläge (~0.003€)
        
        Returns:
            {
                'optimizations': [
                    {
                        'type': 'replace_exercise',
                        'old_exercise': 'Bankdrücken',
                        'new_exercise': 'Schrägbankdrücken',
                        'reason': 'Plateau seit 4 Wochen...'
                    }
                ],
                'cost': 0.003,
                'model': 'llama-3.1-70b'
            }
        """
        # Performance-Daten sammeln
        analysis = self.analyze_plan_performance(days=days)
        
        # Aktueller Plan
        plan_structure = self._get_plan_structure()
        
        # Training Historie (kompakt)
        training_history = self._get_training_history_summary(days=days)
        
        # Verfügbare Übungen (für LLM)
        available_exercises = self._get_available_exercises()
        
        # LLM Prompt
        system_prompt = """Du bist ein erfahrener Fitness-Coach und Trainingsplan-Optimierer.
        
Deine Aufgabe: Analysiere den aktuellen Trainingsplan und die Performance-Daten, und schlage konkrete Verbesserungen vor.

Fokus:
- Übungen ersetzen bei Plateau (>4 Wochen keine Fortschritte)
- Sets/Reps anpassen basierend auf RPE
- Muskelgruppen-Balance verbessern
- Volumen optimieren (nicht zu hoch, nicht zu niedrig)

WICHTIG: Nutze NUR Übungen aus der "Verfügbare Übungen" Liste! Erfinde keine neuen Übungsnamen.

Output Format (JSON):
{
    "optimizations": [
        {
            "type": "replace_exercise",
            "exercise_id": 15,
            "old_exercise": "Bankdrücken",
            "new_exercise": "Schrägbankdrücken (Kurzhantel)",
            "reason": "Plateau seit 4 Wochen. Variante zur Stimulation neuer Muskelfasern."
        },
        {
            "type": "adjust_volume",
            "exercise_id": 23,
            "exercise": "Seitheben",
            "old_sets": 3,
            "new_sets": 4,
            "old_reps": "12-15",
            "new_reps": "12-15",
            "reason": "Schultern untertrainiert. Volumen erhöhen."
        },
        {
            "type": "add_exercise",
            "exercise": "Kniebeuge (Körpergewicht)",
            "sets": 3,
            "reps": "8-12",
            "reason": "Beine untertrainiert. Ergänzen."
        },
        {
            "type": "deload_recommended",
            "reason": "Volumen um 25% gestiegen. Deload-Woche empfohlen."
        }
    ]
}

Gib NUR das JSON zurück, keine Markdown-Formatierung."""
        
        user_prompt = f"""Aktueller Plan:
{json.dumps(plan_structure, indent=2, ensure_ascii=False)}

Performance-Analyse (letzte {days} Tage):
{json.dumps(analysis, indent=2, ensure_ascii=False)}

Training Historie (Zusammenfassung):
{json.dumps(training_history, indent=2, ensure_ascii=False)}

Verfügbare Übungen (nutze NUR diese!):
{json.dumps(available_exercises, indent=2, ensure_ascii=False)}

Bitte analysiere und schlage Optimierungen vor."""
        
        # LLM Call mit automatischem Fallback
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            # Nutze LLMClient mit Fallback-Logik (Ollama → OpenRouter)
            from ai_coach.llm_client import LLMClient
            
            # Client mit Fallback initialisieren
            client = LLMClient(temperature=0.3, fallback_to_openrouter=True)
            
            # generate_training_plan nutzt automatisch Ollama oder OpenRouter
            result = client.generate_training_plan(messages=messages, max_tokens=2000)
            
            # Parse Result
            response = result.get('response')
            cost = result.get('cost', 0.0)
            model_used = result.get('model', 'unknown')
            
            # Parse JSON wenn String
            if isinstance(response, str):
                response = json.loads(response)
            
            return {
                'optimizations': response.get('optimizations', []),
                'cost': cost,
                'model': model_used,
                'analysis_period_days': days
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                'error': str(e),
                'optimizations': [],
                'cost': 0.0,
                'model': 'error'
            }
    
    def _get_plan_structure(self) -> Dict[str, Any]:
        """Gibt Plan-Struktur zurück"""
        plan_uebungen = PlanUebung.objects.filter(plan=self.plan).select_related('uebung').order_by('reihenfolge')
        
        # Gruppiere nach Trainingstag
        sessions = defaultdict(list)
        for pu in plan_uebungen:
            tag_name = pu.trainingstag if pu.trainingstag else "Kein Tag"
            sessions[tag_name].append({
                'id': pu.id,
                'exercise_id': pu.uebung.id,
                'exercise': pu.uebung.bezeichnung,
                'muscle_group': pu.uebung.muskelgruppe,
                'sets': pu.saetze_ziel,
                'reps': pu.wiederholungen_ziel,
                'order': pu.reihenfolge
            })
        
        return {
            'plan_name': self.plan.name,
            'plan_description': self.plan.beschreibung or "",
            'sessions': dict(sessions)
        }
    
    def _get_training_history_summary(self, days: int = 30) -> Dict[str, Any]:
        """Kompakte Training-Historie für LLM"""
        cutoff_date = timezone.now() - timedelta(days=days)
        
        sessions = Trainingseinheit.objects.filter(
            user_id=self.user_id,
            datum__gte=cutoff_date,
            plan=self.plan
        ).order_by('-datum')[:10]  # Nur letzte 10 Sessions
        
        summary = {
            'total_sessions': sessions.count(),
            'recent_sessions': []
        }
        
        for session in sessions:
            saetze = Satz.objects.filter(einheit=session, ist_aufwaermsatz=False)
            
            total_volume = sum([
                float(s.gewicht) * s.wiederholungen 
                for s in saetze 
                if s.gewicht and s.wiederholungen
            ])
            
            avg_rpe = saetze.filter(rpe__isnull=False).aggregate(Avg('rpe'))['rpe__avg']
            
            summary['recent_sessions'].append({
                'date': session.datum.strftime('%Y-%m-%d'),
                'volume_kg': float(round(total_volume, 0)) if total_volume else 0,
                'avg_rpe': float(round(avg_rpe, 1)) if avg_rpe else None,
                'sets_count': saetze.count()
            })
        
        return summary
    
    def _get_available_exercises(self) -> Dict[str, List[str]]:
        """Gibt alle verfügbaren Übungen gruppiert nach Muskelgruppe zurück"""
        exercises = Uebung.objects.all().order_by('muskelgruppe', 'bezeichnung')
        
        grouped = defaultdict(list)
        for ex in exercises:
            grouped[ex.muskelgruppe].append(ex.bezeichnung)
        
        return dict(grouped)


if __name__ == "__main__":
    # Test mit Plan ID
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan-id', type=int, required=True)
    parser.add_argument('--user-id', type=int, required=False)
    parser.add_argument('--optimize', action='store_true', help='KI-Optimierung starten')
    args = parser.parse_args()
    
    adapter = PlanAdapter(plan_id=args.plan_id, user_id=args.user_id)
    
    if args.optimize:
        print("🤖 KI-Optimierung läuft...")
        result = adapter.suggest_optimizations(days=30)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("📊 Performance-Analyse (kostenlos)...")
        result = adapter.analyze_plan_performance(days=30)
        print(json.dumps(result, indent=2, ensure_ascii=False))
