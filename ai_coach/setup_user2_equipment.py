"""Setup Equipment für User 2 (Production)"""
import sys
sys.path.insert(0, '..')

from db_client import DatabaseClient

with DatabaseClient() as db:
    from django.contrib.auth.models import User
    from core.models import Equipment
    
    print("\n🔧 Setup Equipment für Production User\n")
    
    # User 2
    user = User.objects.get(id=2)
    print(f"User: {user.username} (ID: {user.id})")
    print(f"Equipment vorher: {user.verfuegbares_equipment.count()}")
    
    # Equipment erstellen falls nicht vorhanden
    equipment_names = [
        'LANGHANTEL', 'KURZHANTEL', 'BANK', 'HANTELSCHEIBEN', 'KLIMMZUG'
    ]
    
    for eq_name in equipment_names:
        eq, created = Equipment.objects.get_or_create(name=eq_name)
        if created:
            print(f"  ✓ Equipment erstellt: {eq_name}")
    
    # Home Gym Setup
    home_gym = Equipment.objects.filter(name__in=equipment_names)
    user.verfuegbares_equipment.set(home_gym)
    
    print(f"\nEquipment nachher: {user.verfuegbares_equipment.count()}")
    print(f"  {', '.join(user.verfuegbares_equipment.values_list('name', flat=True))}")
    
    print("\n✅ Equipment Setup abgeschlossen!")
