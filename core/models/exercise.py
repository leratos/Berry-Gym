"""Übungs-bezogene Models: UebungTag, Equipment, Uebung."""

from django.contrib.auth.models import User
from django.db import models

from .constants import BEWEGUNGS_TYP, EQUIPMENT_CHOICES, GEWICHTS_TYP, MUSKELGRUPPEN, TAG_KATEGORIEN


class UebungTag(models.Model):
    """Tags für Übungen zur besseren Kategorisierung und Filterung."""

    name = models.CharField(max_length=50, choices=TAG_KATEGORIEN, unique=True, verbose_name="Tag")
    beschreibung = models.TextField(blank=True, verbose_name="Beschreibung")
    farbe = models.CharField(
        max_length=7,
        default="#6c757d",
        verbose_name="Badge-Farbe (Hex)",
        help_text="z.B. #007bff für blau",
    )
    erstellt_am = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.get_name_display()

    class Meta:
        verbose_name = "Übungs-Tag"
        verbose_name_plural = "Übungs-Tags"
        ordering = ["name"]


class Equipment(models.Model):
    """Ausrüstung / Equipment für Übungen."""

    name = models.CharField(
        max_length=50, choices=EQUIPMENT_CHOICES, unique=True, verbose_name="Equipment"
    )
    beschreibung = models.TextField(blank=True, verbose_name="Beschreibung")
    erstellt_am = models.DateTimeField(auto_now_add=True)
    users = models.ManyToManyField(User, related_name="verfuegbares_equipment", blank=True)

    def __str__(self):
        return self.get_name_display()

    class Meta:
        verbose_name = "Equipment"
        verbose_name_plural = "Equipment"
        ordering = ["name"]


class Uebung(models.Model):
    bezeichnung = models.CharField(max_length=100, verbose_name="Name der Übung")
    muskelgruppe = models.CharField(
        max_length=50, choices=MUSKELGRUPPEN, verbose_name="Hauptmuskel"
    )
    hilfsmuskeln = models.JSONField(default=list, blank=True, verbose_name="Hilfsmuskelgruppen")
    gewichts_typ = models.CharField(
        max_length=20, choices=GEWICHTS_TYP, default="GESAMT", verbose_name="Gewichtsart"
    )
    bewegungstyp = models.CharField(
        max_length=20, choices=BEWEGUNGS_TYP, default="ISOLATION", verbose_name="Bewegungsmuster"
    )
    equipment = models.ManyToManyField(
        Equipment, related_name="uebungen", blank=True, verbose_name="Benötigtes Equipment"
    )
    beschreibung = models.TextField(blank=True, verbose_name="Anleitung / Notizen")
    bild = models.ImageField(
        upload_to="uebungen_bilder/", blank=True, null=True, verbose_name="Foto/Grafik"
    )
    video_link = models.URLField(
        blank=True,
        null=True,
        verbose_name="YouTube/Vimeo Link",
        help_text="z.B. https://www.youtube.com/watch?v=...",
    )
    video_file = models.FileField(
        upload_to="uebungen_videos/",
        blank=True,
        null=True,
        verbose_name="Video-Datei",
        help_text="Alternativ: MP4 hochladen",
    )
    video_thumbnail = models.ImageField(
        upload_to="uebungen_thumbnails/", blank=True, null=True, verbose_name="Video-Vorschaubild"
    )
    favoriten = models.ManyToManyField(User, related_name="favoriten_uebungen", blank=True)
    tags = models.ManyToManyField(
        UebungTag, related_name="uebungen", blank=True, verbose_name="Tags"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="custom_uebungen",
        null=True,
        blank=True,
        verbose_name="Erstellt von",
    )
    is_custom = models.BooleanField(default=False, verbose_name="Benutzerdefinierte Übung")
    erstellt_am = models.DateTimeField(auto_now_add=True)
    standard_beginner = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        verbose_name="1RM Anfänger (80kg KG)",
        help_text="Anfänger-Standard in kg bei 80kg Körpergewicht",
    )
    standard_intermediate = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        verbose_name="1RM Fortgeschritten (80kg KG)",
        help_text="Fortgeschritten-Standard in kg bei 80kg Körpergewicht",
    )
    standard_advanced = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        verbose_name="1RM Erfahren (80kg KG)",
        help_text="Erfahren-Standard in kg bei 80kg Körpergewicht",
    )
    standard_elite = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        verbose_name="1RM Elite (80kg KG)",
        help_text="Elite-Standard in kg bei 80kg Körpergewicht",
    )

    def __str__(self):
        return self.bezeichnung

    @property
    def is_global(self):
        """True wenn Übung für alle sichtbar ist (keine Custom-Übung)."""
        return not self.is_custom

    @property
    def has_video(self):
        """True wenn Übung ein Video hat (Link oder Upload)."""
        return bool(self.video_link or self.video_file)

    @property
    def video_embed_url(self):
        """Konvertiert YouTube/Vimeo URLs zu Embed-Format."""
        if not self.video_link:
            return None
        from urllib.parse import urlparse

        url = self.video_link
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname.lower() if parsed.hostname else ""
            if hostname in ("www.youtube.com", "youtube.com", "m.youtube.com"):
                if "watch?v=" in url:
                    video_id = url.split("watch?v=")[1].split("&")[0]
                else:
                    return url
                return f"https://www.youtube.com/embed/{video_id}"
            elif hostname in ("youtu.be", "www.youtu.be"):
                video_id = parsed.path.lstrip("/").split("?")[0]
                return f"https://www.youtube.com/embed/{video_id}"
            elif hostname in ("vimeo.com", "www.vimeo.com"):
                video_id = parsed.path.lstrip("/").split("?")[0]
                return f"https://player.vimeo.com/video/{video_id}"
        except Exception:
            pass
        return url

    class Meta:
        verbose_name = "Übung"
        verbose_name_plural = "Übungen"
        ordering = ["bezeichnung"]
