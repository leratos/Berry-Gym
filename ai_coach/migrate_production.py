"""Run Migrations on Production Server via SSH Tunnel"""
import sys
sys.path.insert(0, '..')

from db_client import DatabaseClient

print("\n" + "="*60)
print("🔄 MIGRATE PRODUCTION DATABASE")
print("="*60)
print("Achtung: Führt Django Migrations auf Production Server aus!")
print("="*60 + "\n")

confirm = input("Fortfahren? (yes/no): ")
if confirm.lower() != 'yes':
    print("Abgebrochen.")
    sys.exit(0)

with DatabaseClient() as db:
    # Django ist bereits initialisiert durch DatabaseClient
    from django.core.management import call_command
    
    print("\n📋 Zeige pending migrations...")
    call_command('showmigrations')
    
    print("\n⚠️ Fake existing migrations...")
    call_command('migrate', 'core', '0009', '--fake', verbosity=1)
    call_command('migrate', 'core', '0010', '--fake', verbosity=1)
    
    print("\n🚀 Führe Equipment Migration aus...")
    call_command('migrate', 'core', '0011', verbosity=2)
    
    print("\n✅ Migrations erfolgreich!")
    print("\n📊 Aktueller Status:")
    call_command('showmigrations')
