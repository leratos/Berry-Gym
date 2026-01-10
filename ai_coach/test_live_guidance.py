"""
Live Guidance Test Suite - Automatische Edge Case Tests
Testet verschiedene Szenarien um Fallstricke zu finden
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

# Für lokale SQLite DB (statt Production MySQL)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Django Setup (direkt, ohne db_client für lokale DB)
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import django
django.setup()

from django.contrib.auth.models import User
from django.utils import timezone
from core.models import Trainingseinheit, Satz, Uebung, KoerperWerte, Plan
from live_guidance import LiveGuidance


class LiveGuidanceTester:
    """
    Automatisches Testing für Live-Guidance mit Edge Cases
    """
    
    def __init__(self, user_id: int = 1, use_openrouter: bool = False):
        self.user_id = user_id
        self.use_openrouter = use_openrouter
        self.guidance = LiveGuidance(use_openrouter=use_openrouter)
        self.test_results = []
        
        # Hole User
        try:
            self.user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            # Erstelle Test-User
            self.user = User.objects.create_user(
                username=f'test_user_{user_id}',
                password='testpass123'
            )
            print(f"✓ Test-User erstellt: {self.user.username}")
    
    def setup_test_data(self):
        """
        Erstellt Test-Daten für verschiedene Szenarien
        """
        print("\n📦 SETUP: Erstelle Test-Daten")
        print("-" * 60)
        
        # 1. Körperwerte (optional - Test mit/ohne)
        KoerperWerte.objects.filter(user=self.user).delete()
        koerperwert = KoerperWerte.objects.create(
            user=self.user,
            gewicht=80.5,
            groesse_cm=180,
            koerperfett_prozent=15.0
        )
        print(f"✓ Körperwerte: {koerperwert.gewicht}kg, {koerperwert.groesse_cm}cm")
        
        # 2. Plan (optional)
        plan, _ = Plan.objects.get_or_create(
            user=self.user,
            name="Test 3er-Split",
            defaults={'beschreibung': 'Test Plan für Live Guidance'}
        )
        print(f"✓ Plan: {plan.name}")
        
        # 3. Alte Trainings (für Historie)
        old_sessions_count = 3
        for i in range(old_sessions_count):
            old_session = Trainingseinheit.objects.create(
                user=self.user,
                plan=plan if i % 2 == 0 else None,
                datum=timezone.now() - timedelta(days=7-i),
                dauer_minuten=60 + i*10
            )
            # Füge Sätze hinzu
            uebung = Uebung.objects.first()
            if uebung:
                for j in range(3):
                    Satz.objects.create(
                        einheit=old_session,
                        uebung=uebung,
                        satz_nr=j+1,
                        gewicht=50 + i*5,
                        wiederholungen=8,
                        rpe=7.5 + i*0.5
                    )
        
        print(f"✓ {old_sessions_count} alte Trainings mit Sätzen")
        
        # 4. Aktuelle Test-Sessions erstellen
        self.test_sessions = {}
        
        # Session A: Frisch gestartet (keine Sätze)
        self.test_sessions['empty'] = Trainingseinheit.objects.create(
            user=self.user,
            plan=plan,
            datum=timezone.now()
        )
        print(f"✓ Test-Session 'empty': ID {self.test_sessions['empty'].id} (keine Sätze)")
        
        # Session B: Mit Sätzen (normale Session)
        self.test_sessions['normal'] = Trainingseinheit.objects.create(
            user=self.user,
            plan=plan,
            datum=timezone.now() - timedelta(minutes=30),
            dauer_minuten=30
        )
        uebung1 = Uebung.objects.filter(muskelgruppe='BRUST').first() or Uebung.objects.first()
        if uebung1:
            for i in range(3):
                Satz.objects.create(
                    einheit=self.test_sessions['normal'],
                    uebung=uebung1,
                    satz_nr=i+1,
                    gewicht=60 + i*2.5,
                    wiederholungen=10-i,
                    rpe=7.0 + i*0.5
                )
        print(f"✓ Test-Session 'normal': ID {self.test_sessions['normal'].id} (3 Sätze)")
        
        # Session C: Nur Warm-up Sätze
        self.test_sessions['warmup_only'] = Trainingseinheit.objects.create(
            user=self.user,
            plan=None,  # Kein Plan
            datum=timezone.now() - timedelta(minutes=10)
        )
        if uebung1:
            Satz.objects.create(
                einheit=self.test_sessions['warmup_only'],
                uebung=uebung1,
                satz_nr=1,
                gewicht=20,
                wiederholungen=15,
                ist_aufwaermsatz=True
            )
        print(f"✓ Test-Session 'warmup_only': ID {self.test_sessions['warmup_only'].id} (nur Warm-up)")
        
        # Session D: Mehrere Übungen, keine RPE
        self.test_sessions['no_rpe'] = Trainingseinheit.objects.create(
            user=self.user,
            plan=plan,
            datum=timezone.now() - timedelta(minutes=45),
            dauer_minuten=45
        )
        uebung2 = Uebung.objects.filter(muskelgruppe='RUECKEN').first() or Uebung.objects.last()
        for uebung in [uebung1, uebung2]:
            if uebung:
                Satz.objects.create(
                    einheit=self.test_sessions['no_rpe'],
                    uebung=uebung,
                    satz_nr=1,
                    gewicht=50,
                    wiederholungen=10,
                    rpe=None  # Keine RPE!
                )
        print(f"✓ Test-Session 'no_rpe': ID {self.test_sessions['no_rpe'].id} (2 Übungen, keine RPE)")
        
        print("-" * 60)
        print(f"✅ Setup abgeschlossen: {len(self.test_sessions)} Test-Sessions bereit\n")
    
    def test_scenario(self, name: str, session_key: str, question: str, exercise_id=None):
        """
        Führt einen Test-Fall aus
        """
        print(f"\n🧪 TEST: {name}")
        print(f"   Session: {session_key} (ID: {self.test_sessions[session_key].id})")
        print(f"   Frage: {question[:50]}...")
        
        try:
            result = self.guidance.get_guidance(
                trainingseinheit_id=self.test_sessions[session_key].id,
                user_question=question,
                current_uebung_id=exercise_id
            )
            
            answer = result.get('answer', '')
            
            # Validierung
            if not answer or len(answer) < 10:
                status = "⚠️ WARNUNG"
                message = "Antwort zu kurz"
            elif len(answer) > 500:
                status = "⚠️ WARNUNG"
                message = "Antwort zu lang"
            elif "fehler" in answer.lower() or "error" in answer.lower():
                status = "⚠️ WARNUNG"
                message = "Fehlermeldung in Antwort"
            else:
                status = "✅ BESTANDEN"
                message = f"{len(answer)} Zeichen"
            
            print(f"   {status}: {message}")
            print(f"   Antwort: {answer[:100]}...")
            
            self.test_results.append({
                'name': name,
                'status': 'pass' if status == "✅ BESTANDEN" else 'warn',
                'message': message
            })
            
            return True
            
        except Exception as e:
            print(f"   ❌ FEHLER: {str(e)}")
            self.test_results.append({
                'name': name,
                'status': 'fail',
                'message': str(e)
            })
            return False
    
    def run_all_tests(self):
        """
        Führt alle Test-Szenarien aus
        """
        print("=" * 60)
        print("🚀 LIVE GUIDANCE TEST SUITE")
        print("=" * 60)
        print(f"User: {self.user.username} (ID: {self.user.id})")
        print(f"LLM: {'OpenRouter' if self.use_openrouter else 'Ollama'}")
        print("=" * 60)
        
        # Setup
        self.setup_test_data()
        
        # TEST 1: Normale Frage, normale Session
        self.test_scenario(
            "Normale Session - Satzzahl",
            "normal",
            "Wie viele Sätze soll ich noch machen?"
        )
        
        # TEST 2: Leere Session (keine Sätze)
        self.test_scenario(
            "Leere Session - Warm-up Frage",
            "empty",
            "Wie soll ich mit dem Warm-up anfangen?"
        )
        
        # TEST 3: Nur Warm-up Sätze
        self.test_scenario(
            "Nur Warm-up - Arbeitsgewicht",
            "warmup_only",
            "Mit welchem Gewicht soll ich jetzt die Arbeitssätze machen?"
        )
        
        # TEST 4: Keine RPE-Werte
        self.test_scenario(
            "Keine RPE - RPE-Empfehlung",
            "no_rpe",
            "Welche RPE sollte ich anstreben?"
        )
        
        # TEST 5: Sehr kurze Frage
        self.test_scenario(
            "Kurze Frage",
            "normal",
            "Pause?"
        )
        
        # TEST 6: Sehr lange Frage
        self.test_scenario(
            "Lange Frage",
            "normal",
            "Ich habe gerade Bankdrücken mit 60kg gemacht und es fühlte sich relativ leicht an, "
            "RPE war so bei 6-7. Jetzt frage ich mich ob ich das Gewicht erhöhen soll oder lieber "
            "noch einen Satz bei dem gleichen Gewicht machen soll, um die Technik zu verbessern. "
            "Was würdest du empfehlen basierend auf meinem aktuellen Training?"
        )
        
        # TEST 7: Frage mit Sonderzeichen
        self.test_scenario(
            "Sonderzeichen",
            "normal",
            "Soll ich @home mit 50kg/bar trainieren? 🏋️"
        )
        
        # TEST 8: Technische Frage
        self.test_scenario(
            "Technik-Frage",
            "normal",
            "Meine Ellbogen schmerzen leicht bei Trizeps-Übungen. Was könnte das sein?"
        )
        
        # TEST 9: Ernährungs-Frage (Off-Topic)
        self.test_scenario(
            "Off-Topic Ernährung",
            "normal",
            "Was soll ich heute Abend essen?"
        )
        
        # TEST 10: Motivations-Frage
        self.test_scenario(
            "Motivation",
            "normal",
            "Ich bin heute nicht motiviert. Was kann ich tun?"
        )
        
        # TEST 11: Spezifische Übung
        uebung_id = Uebung.objects.first().id if Uebung.objects.exists() else None
        if uebung_id:
            self.test_scenario(
                "Übungs-spezifisch",
                "normal",
                "Kann ich diese Übung durch was anderes ersetzen?",
                exercise_id=uebung_id
            )
        
        # TEST 12: Leere Frage (sollte Fehler geben)
        print(f"\n🧪 TEST: Leere Frage (Error-Test)")
        try:
            result = self.guidance.get_guidance(
                trainingseinheit_id=self.test_sessions['normal'].id,
                user_question=""
            )
            print(f"   ⚠️ WARNUNG: Leere Frage wurde akzeptiert")
        except Exception as e:
            print(f"   ✅ BESTANDEN: Leere Frage abgelehnt ({str(e)[:50]})")
        
        # Zusammenfassung
        self.print_summary()
    
    def print_summary(self):
        """
        Gibt Test-Zusammenfassung aus
        """
        print("\n" + "=" * 60)
        print("📊 TEST ZUSAMMENFASSUNG")
        print("=" * 60)
        
        passed = sum(1 for r in self.test_results if r['status'] == 'pass')
        warned = sum(1 for r in self.test_results if r['status'] == 'warn')
        failed = sum(1 for r in self.test_results if r['status'] == 'fail')
        total = len(self.test_results)
        
        print(f"\nGesamt Tests: {total}")
        print(f"✅ Bestanden: {passed}")
        print(f"⚠️  Warnungen: {warned}")
        print(f"❌ Fehlgeschlagen: {failed}")
        
        if failed > 0:
            print("\n❌ FEHLERHAFTE TESTS:")
            for r in self.test_results:
                if r['status'] == 'fail':
                    print(f"   - {r['name']}: {r['message']}")
        
        if warned > 0:
            print("\n⚠️  WARNUNGEN:")
            for r in self.test_results:
                if r['status'] == 'warn':
                    print(f"   - {r['name']}: {r['message']}")
        
        # Erfolgsrate
        success_rate = (passed / total * 100) if total > 0 else 0
        print(f"\n🎯 Erfolgsrate: {success_rate:.1f}%")
        
        if success_rate >= 90:
            print("✅ EXZELLENT - System ist produktionsbereit")
        elif success_rate >= 75:
            print("✅ GUT - Kleinere Verbesserungen empfohlen")
        elif success_rate >= 50:
            print("⚠️  AKZEPTABEL - Mehrere Probleme sollten behoben werden")
        else:
            print("❌ KRITISCH - System nicht produktionsbereit")
        
        print("=" * 60)
    
    def cleanup(self):
        """
        Räumt Test-Daten auf
        """
        print("\n🧹 CLEANUP: Entferne Test-Daten...")
        for session in self.test_sessions.values():
            Satz.objects.filter(einheit=session).delete()
            session.delete()
        print("✓ Test-Sessions gelöscht")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Live Guidance Test Suite")
    parser.add_argument('--user-id', type=int, default=1, help='User ID für Tests')
    parser.add_argument('--use-openrouter', action='store_true', help='OpenRouter nutzen (kostet Geld!)')
    parser.add_argument('--no-cleanup', action='store_true', help='Test-Daten nicht löschen')
    
    args = parser.parse_args()
    
    # Warnung bei OpenRouter
    if args.use_openrouter:
        print("\n⚠️  WARNUNG: OpenRouter kostet ~0.002€ pro Test!")
        print(f"Geschätzte Kosten: ~0.024€ für 12 Tests")
        response = input("Fortfahren? (y/n): ")
        if response.lower() != 'y':
            print("Abgebrochen.")
            sys.exit(0)
    
    # Tests ausführen
    tester = LiveGuidanceTester(user_id=args.user_id, use_openrouter=args.use_openrouter)
    
    try:
        tester.run_all_tests()
    finally:
        if not args.no_cleanup:
            tester.cleanup()
        else:
            print("\n⚠️  Test-Daten wurden NICHT gelöscht (--no-cleanup)")
