"""
Führt Migration 0012 (trainingstag) auf Production Server aus
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_client import DatabaseClient


def migrate_production():
    """Führt trainingstag Migration auf Production aus"""
    
    print("=" * 60)
    print("🔄 MIGRATION: trainingstag auf Production Server")
    print("=" * 60)
    
    try:
        with DatabaseClient() as db:
            print("\n📋 Führe Migration 0012 aus...")
            print("-" * 60)
            
            # Migration ausführen
            from django.core.management import call_command
            
            call_command('migrate', 'core', '0012', verbosity=2)
            
            print("\n" + "=" * 60)
            print("✅ Migration erfolgreich auf Production angewendet!")
            print("=" * 60)
            
    except Exception as e:
        print(f"\n❌ FEHLER: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    migrate_production()
