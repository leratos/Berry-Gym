"""Setup Equipment für Production Server"""
import os
import django

# Django Setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from core.models import Equipment

print("\n🔧 Setup Equipment für Production Server\n")

# Equipment erstellen falls nicht vorhanden
equipment_items = [
    'LANGHANTEL', 'KURZHANTEL', 'BANK', 'HANTELSCHEIBEN', 'KLIMMZUG',
    'SCHRAEGHANK', 'KABELZUG', 'DIPSTATION'
]

for eq_name in equipment_items:
    eq, created = Equipment.objects.get_or_create(name=eq_name)
    if created:
        print(f"✓ Equipment erstellt: {eq_name}")

# User 1 Equipment zuweisen
user = User.objects.get(id=1)
print(f"\nUser: {user.username} (ID: {user.id})")
print(f"Equipment vorher: {user.verfuegbares_equipment.count()}")

# Home Gym Setup
home_gym = Equipment.objects.filter(name__in=[
    'LANGHANTEL', 'KURZHANTEL', 'BANK', 'HANTELSCHEIBEN', 'KLIMMZUG'
])
user.verfuegbares_equipment.set(home_gym)

print(f"Equipment nachher: {user.verfuegbares_equipment.count()}")
print(f"  {', '.join(user.verfuegbares_equipment.values_list('name', flat=True))}")

print("\n✅ Equipment Setup abgeschlossen!")
