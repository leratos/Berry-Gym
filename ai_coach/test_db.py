"""Quick Test: Welche DB wird verwendet?"""

import sys

sys.path.insert(0, "..")

from datetime import timedelta

from django.utils import timezone

from db_client import DatabaseClient

with DatabaseClient() as db:
    from django.contrib.auth.models import User

    from core.models import Trainingseinheit

    print(f"\n{'='*60}")
    print(f"🔍 DATABASE: gym_ @ gym.last-strawberry.com")
    print(f"{'='*60}\n")

    # Alle User anzeigen
    all_users = User.objects.all()
    print(f"👥 ALLE USERS IN DB ({all_users.count()}):")
    print(f"{'='*60}")
    for u in all_users:
        session_count = Trainingseinheit.objects.filter(user=u).count()
        print(f"  ID {u.id}: {u.username} - {session_count} Sessions")
    print(f"{'='*60}\n")

    # Details für jeden User
    for user in all_users:
        all_sessions = Trainingseinheit.objects.filter(user=user)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_sessions = all_sessions.filter(datum__gte=thirty_days_ago)

        print(f"🔍 USER ID {user.id}: {user.username}")
        print(f"{'='*60}")
        print(f"Trainingseinheiten (gesamt): {all_sessions.count()}")
        print(f"Trainingseinheiten (letzte 30 Tage): {recent_sessions.count()}")

        if all_sessions.count() > 0:
            print(f"\nSessions:")
            for s in all_sessions.order_by("-datum"):
                try:
                    if hasattr(s, "ende") and s.ende:
                        duration = (s.ende - s.datum).total_seconds() / 60
                        print(f"  - {s.datum.strftime('%d.%m.%Y %H:%M')}: {int(duration)} min")
                    else:
                        print(f"  - {s.datum.strftime('%d.%m.%Y %H:%M')}")
                except:
                    print(f"  - {s.datum}")
        print()
