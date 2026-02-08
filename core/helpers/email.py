"""
Email utility functions for HomeGym application.
"""

from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def send_welcome_email(user):
    """Sendet Willkommens-E-Mail nach erfolgreicher Registrierung"""
    subject = "🏋️ Willkommen bei HomeGym!"

    message = f"""Hallo {user.username}!

Herzlich willkommen bei HomeGym - deiner persönlichen Fitness-App! 🎉

Dein Account wurde erfolgreich erstellt und du kannst jetzt loslegen.

🚀 Erste Schritte:
1. Richte dein Equipment ein (welche Geräte hast du?)
2. Erstelle deinen ersten Trainingsplan mit KI-Unterstützung
3. Starte dein erstes Training und tracke deine Fortschritte

💡 Tipps für Einsteiger:
• Nutze den KI-Coach während des Trainings für Tipps
• Trage regelmäßig deine Körperwerte ein
• Mache Fortschrittsfotos für visuellen Vergleich

📱 PWA-Installation:
Du kannst HomeGym als App auf deinem Smartphone installieren!
Öffne {settings.SITE_URL} im Browser und wähle "Zum Startbildschirm hinzufügen".

Bei Fragen stehen wir dir gerne zur Verfügung.

Viel Erfolg beim Training! 💪

Dein HomeGym Team
{settings.SITE_URL}

---
Diese E-Mail wurde automatisch generiert.
Kontakt: marcus.kohtz@signz-vision.com
"""

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,  # Nicht blocken wenn E-Mail fehlschlägt
        )
        logger.info(f"Welcome email sent to {user.email}")
    except Exception as e:
        logger.error(f"Failed to send welcome email to {user.email}: {e}")
