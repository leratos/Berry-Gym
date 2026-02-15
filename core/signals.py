from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Trainingseinheit, UserProfile


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
