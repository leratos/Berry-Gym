from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from core.models import Equipment, KoerperWerte, Trainingseinheit, Plan, PlanUebung, Satz, ProgressPhoto, Uebung


class Command(BaseCommand):
    help = 'Erstellt Gruppe "Standard User" mit passenden Rechten für normale Nutzer'

    def handle(self, *args, **options):
        # Gruppe erstellen
        group, created = Group.objects.get_or_create(name='Standard User')
        
        if not created:
            # Wenn Gruppe existiert, alle Permissions entfernen
            group.permissions.clear()
            self.stdout.write(self.style.WARNING('Gruppe existierte bereits - Permissions werden neu gesetzt'))
        
        # Permissions definieren (add, change, delete, view)
        models_with_full_access = [
            Equipment,
            KoerperWerte,
            Trainingseinheit,
            Plan,
            PlanUebung,
            Satz,
            ProgressPhoto,
        ]
        
        # Nur view für Übungen (sollen zentral von Admin verwaltet werden)
        models_view_only = [
            Uebung,
        ]
        
        # Volle Rechte für eigene Daten
        for model in models_with_full_access:
            content_type = ContentType.objects.get_for_model(model)
            permissions = Permission.objects.filter(content_type=content_type)
            for perm in permissions:
                group.permissions.add(perm)
                self.stdout.write(f'  ✓ {model.__name__}: {perm.codename}')
        
        # Nur Lese-Rechte für Übungen
        for model in models_view_only:
            content_type = ContentType.objects.get_for_model(model)
            view_perm = Permission.objects.get(content_type=content_type, codename=f'view_{model.__name__.lower()}')
            group.permissions.add(view_perm)
            self.stdout.write(f'  ✓ {model.__name__}: {view_perm.codename} (nur lesen)')
        
        self.stdout.write(self.style.SUCCESS(f'\n✅ Gruppe "{group.name}" erstellt mit {group.permissions.count()} Permissions'))
        self.stdout.write(self.style.SUCCESS('\nJetzt kannst du User "Andrea" dieser Gruppe zuweisen:'))
        self.stdout.write('  1. Im Admin zu "Andrea" gehen')
        self.stdout.write('  2. Bei "Groups" die Gruppe "Standard User" auswählen')
        self.stdout.write('  3. Speichern')
