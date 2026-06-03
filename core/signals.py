from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Trainingseinheit, TrainingsPause, UserProfile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Erstellt automatisch ein UserProfile wenn ein neuer User erstellt wird."""
    if created:
        UserProfile.objects.get_or_create(user=instance)


@receiver(post_save, sender=Trainingseinheit)
def invalidate_dashboard_cache(sender, instance, **kwargs):
    """Invalidiert den Dashboard-Cache wenn ein Training gespeichert wird.

    Stellt sicher dass Streak, Volumen-Trends und Performance-Warnings
    nach dem Training sofort aktuell sind.
    """
    if instance.user_id:
        cache.delete(f"dashboard_computed_{instance.user_id}")


@receiver(post_save, sender=TrainingsPause)
@receiver(post_delete, sender=TrainingsPause)
def invalidate_dashboard_cache_on_pause(sender, instance, **kwargs):
    """Invalidiert den Dashboard-Cache bei Anlegen/Ändern/Löschen einer Pause.

    Der Dashboard-Block (Streak/Volumen/Fatigue) ist jetzt pause-bewusst und wird
    unter `dashboard_computed_<user>` gecacht – ohne Invalidierung bei post_save
    UND post_delete zeigte das Dashboard bis zum TTL den alten Stand (§32.2, ⑬).
    """
    if instance.user_id:
        cache.delete(f"dashboard_computed_{instance.user_id}")
