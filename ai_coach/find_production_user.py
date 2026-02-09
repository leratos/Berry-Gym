"""Find Production User - Welcher User hat die 4 Sessions?"""

import sys

sys.path.insert(0, "..")

from db_client import DatabaseClient

with DatabaseClient() as db:
    from datetime import timedelta

    from django.contrib.auth.models import User
    from django.utils import timezone

    from core.models import Trainingseinheit

    print(f"\n{'='*70}")
    print(f"🔍 PRODUCTION DB USER SEARCH")
    print(f"{'='*70}\n")

    # Alle User mit ihren Sessions
    all_users = User.objects.all()

    print(f"👥 Gefundene Users: {all_users.count()}\n")

    for user in all_users:
        sessions = Trainingseinheit.objects.filter(user=user)
        recent = sessions.filter(datum__gte=timezone.now() - timedelta(days=30))

        print(f"User ID {user.id}: {user.username}")
        print(f"  Email: {user.email}")
        print(f"  Sessions (gesamt): {sessions.count()}")
        print(f"  Sessions (30d): {recent.count()}")

        if recent.count() > 0:
            print(f"  Letzte Sessions:")
            for s in recent.order_by("-datum")[:5]:
                print(f"    - {s.datum.strftime('%d.%m.%Y %H:%M')}")

        print()

    # Suche nach User mit 4 Sessions im Januar
    print(f"{'='*70}")
    print(f"🎯 SUCHE: User mit 4 Sessions (03., 05., 07., 09. Januar)")
    print(f"{'='*70}\n")

    target_dates = ["03.01.2026", "05.01.2026", "07.01.2026", "09.01.2026"]

    for user in all_users:
        sessions = Trainingseinheit.objects.filter(user=user)
        session_dates = [s.datum.strftime("%d.%m.%Y") for s in sessions]

        matches = sum(1 for date in target_dates if date in session_dates)

        if matches >= 3:
            print(f"✅ GEFUNDEN: User ID {user.id} ({user.username})")
            print(f"   Matching Dates: {matches}/4")
            print(f"   All Dates: {', '.join(session_dates)}")
            print(f"\n   👉 DAS IST DER RICHTIGE USER!\n")
