from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from core.models import KoerperWerte, Plan, Trainingseinheit


class Command(BaseCommand):
    help = "Weist bestehende Daten (ohne User) dem ersten Superuser zu"

    def handle(self, *args, **options):
        # Ersten Superuser finden
        superuser = User.objects.filter(is_superuser=True).first()

        if not superuser:
            self.stdout.write(self.style.ERROR("❌ Kein Superuser gefunden!"))
            self.stdout.write("Bitte erstelle zuerst einen Superuser:")
            self.stdout.write("  python manage.py createsuperuser")
            return

        self.stdout.write(f"🔧 Verwende User: {superuser.username} (ID: {superuser.id})")
        self.stdout.write("")

        # Plans ohne User
        plans_ohne_user = Plan.objects.filter(user__isnull=True)
        plan_count = plans_ohne_user.count()
        if plan_count > 0:
            plans_ohne_user.update(user=superuser)
            self.stdout.write(self.style.SUCCESS(f"✅ {plan_count} Pläne zugewiesen"))
        else:
            self.stdout.write("  Keine Pläne ohne User gefunden")

        # Trainings ohne User
        trainings_ohne_user = Trainingseinheit.objects.filter(user__isnull=True)
        training_count = trainings_ohne_user.count()
        if training_count > 0:
            trainings_ohne_user.update(user=superuser)
            self.stdout.write(self.style.SUCCESS(f"✅ {training_count} Trainings zugewiesen"))
        else:
            self.stdout.write("  Keine Trainings ohne User gefunden")

        # Körperwerte ohne User
        werte_ohne_user = KoerperWerte.objects.filter(user__isnull=True)
        werte_count = werte_ohne_user.count()
        if werte_count > 0:
            werte_ohne_user.update(user=superuser)
            self.stdout.write(self.style.SUCCESS(f"✅ {werte_count} Körperwerte zugewiesen"))
        else:
            self.stdout.write("  Keine Körperwerte ohne User gefunden")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("🎉 Migration abgeschlossen!"))
