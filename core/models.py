from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import User
import uuid

# --- KONSTANTEN & AUSWAHLMÖGLICHKEITEN ---

MUSKELGRUPPEN = [
    # Oberkörper Druck
    ('BRUST', 'Brust (Pectoralis major)'),
    ('SCHULTER_VORN', 'Schulter - Vordere (Deltoideus pars clavicularis)'),
    ('SCHULTER_SEIT', 'Schulter - Seitliche (Deltoideus pars acromialis)'),
    ('SCHULTER_HINT', 'Schulter - Hintere (Deltoideus pars spinalis)'),
    ('TRIZEPS', 'Trizeps (Triceps brachii)'),
    
    # Oberkörper Zug
    ('RUECKEN_LAT', 'Rücken - Breiter Muskel (Latissimus dorsi)'),
    ('RUECKEN_TRAPEZ', 'Rücken - Nacken/Trapez (Trapezius)'),
    ('RUECKEN_UNTEN', 'Unterer Rücken (Erector spinae)'),
    ('BIZEPS', 'Bizeps (Biceps brachii)'),
    ('UNTERARME', 'Unterarme (Brachioradialis/Flexoren)'),
    ('RUECKEN_OBERER', 'Oberer Rücken (Rhomboiden, mittlerer Trapez)'),
    
    # Unterkörper
    ('BEINE_QUAD', 'Oberschenkel Vorn (Quadrizeps)'),
    ('BEINE_HAM', 'Oberschenkel Hinten (Hamstrings/Ischiocrurale)'),
    ('PO', 'Gesäß (Gluteus maximus/medius)'),
    ('WADEN', 'Waden (Gastrocnemius/Soleus)'),
    ('ADDUKTOREN', 'Oberschenkel Innen (Adduktoren)'),
    ('ABDUKTOREN', 'Oberschenkel Außen (Abduktoren)'),
    ('HUEFTBEUGER', 'Hüftbeuger (Iliopsoas)'),
    
    # Sonstiges
    ('BAUCH', 'Bauch (Abdominals)'),
    ('GANZKOERPER', 'Ganzkörper / Cardio'),
]

GEWICHTS_TYP = [
    ('GESAMT', 'Gesamtgewicht (z.B. Langhantel)'),
    ('PRO_SEITE', 'Pro Seite/Hand (z.B. Kurzhanteln)'),
    ('KOERPERGEWICHT', 'Körpergewicht (+/- Zusatz)'),
    ('ZEIT', 'Zeit / Dauer (Sekunden)'), # NEU: Für Planks, Wandsitz etc.
]

# NEU: Für den "Digitalen Coach" (Phase 2b)
BEWEGUNGS_TYP = [
    ('DRUECKEN', 'Drücken (Push)'),
    ('ZIEHEN', 'Ziehen (Pull)'),
    ('BEUGEN', 'Beugen (Squat-Pattern)'),
    ('HEBEN', 'Heben (Hinge-Pattern)'),
    ('ISOLATION', 'Isolation / Sonstiges'),
]

# NEU: Tags für Übungen (Phase 5)
TAG_KATEGORIEN = [
    ('COMPOUND', 'Compound (Mehrgelenksübung)'),
    ('ISOLATION', 'Isolation (Eingelenkübung)'),
    ('BEGINNER', 'Anfängerfreundlich'),
    ('ADVANCED', 'Fortgeschritten'),
    ('FUNCTIONAL', 'Funktionell'),
    ('POWER', 'Explosiv / Power'),
    ('MOBILITY', 'Mobilität / Beweglichkeit'),
    ('CARDIO', 'Kardiovaskulär'),
    ('CORE', 'Core / Rumpfstabilität'),
    ('UNILATERAL', 'Unilateral (einseitig)'),
    ('INJURY_PRONE', 'Verletzungsanfällig'),
    ('LOW_IMPACT', 'Gelenkschonend'),
]

# NEU: Equipment / Ausrüstung
EQUIPMENT_CHOICES = [
    ('LANGHANTEL', 'Langhantel'),
    ('KURZHANTEL', 'Kurzhanteln'),
    ('KETTLEBELL', 'Kettlebell'),
    ('BANK', 'Flachbank'),
    ('SCHRAEGBANK', 'Schrägbank'),
    ('KLIMMZUG', 'Klimmzugstange'),
    ('DIP', 'Dipstation / Barren'),
    ('KABELZUG', 'Kabelzug / Latzug'),
    ('BEINPRESSE', 'Beinpresse'),
    ('LEG_CURL', 'Leg Curl Maschine'),
    ('LEG_EXT', 'Leg Extension Maschine'),
    ('SMITHMASCHINE', 'Smith Maschine'),
    ('HACKENSCHMIDT', 'Hackenschmidt'),
    ('RUDERMASCHINE', 'Rudermaschine'),
    ('WIDERSTANDSBAND', 'Widerstandsbänder'),
    ('SUSPENSION', 'Suspension Trainer (TRX)'),
    ('MEDIZINBALL', 'Medizinball'),
    ('BOXEN', 'Plyo Box'),
    ('MATTE', 'Trainingsmatte'),
    ('KOERPER', 'Nur Körpergewicht'),
    ('ADDUKTOREN_MASCHINE', 'Adduktoren Maschine'),
    ('ABDUKTOREN_MASCHINE', 'Abduktoren Maschine'),
    
]

# --- MODELLE ---

class UebungTag(models.Model):
    """
    Tags für Übungen zur besseren Kategorisierung und Filterung
    """
    name = models.CharField(max_length=50, choices=TAG_KATEGORIEN, unique=True, verbose_name="Tag")
    beschreibung = models.TextField(blank=True, verbose_name="Beschreibung")
    farbe = models.CharField(max_length=7, default='#6c757d', verbose_name="Badge-Farbe (Hex)", 
                            help_text="z.B. #007bff für blau")
    
    erstellt_am = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.get_name_display()
    
    class Meta:
        verbose_name = "Übungs-Tag"
        verbose_name_plural = "Übungs-Tags"
        ordering = ['name']


class Equipment(models.Model):
    """
    Ausrüstung / Equipment für Übungen
    """
    name = models.CharField(max_length=50, choices=EQUIPMENT_CHOICES, unique=True, verbose_name="Equipment")
    beschreibung = models.TextField(blank=True, verbose_name="Beschreibung")
    erstellt_am = models.DateTimeField(auto_now_add=True)
    
    # Welche User haben dieses Equipment?
    users = models.ManyToManyField(User, related_name="verfuegbares_equipment", blank=True)
    
    def __str__(self):
        return self.get_name_display()
    
    class Meta:
        verbose_name = "Equipment"
        verbose_name_plural = "Equipment"
        ordering = ['name']


class Uebung(models.Model):
    bezeichnung = models.CharField(max_length=100, verbose_name="Name der Übung")
    muskelgruppe = models.CharField(max_length=50, choices=MUSKELGRUPPEN, verbose_name="Hauptmuskel")
    hilfsmuskeln = models.JSONField(default=list, blank=True, verbose_name="Hilfsmuskelgruppen")
    
    gewichts_typ = models.CharField(max_length=20, choices=GEWICHTS_TYP, default='GESAMT', verbose_name="Gewichtsart")
    
    # NEU: Bewegungstyp für Algorithmus
    bewegungstyp = models.CharField(max_length=20, choices=BEWEGUNGS_TYP, default='ISOLATION', verbose_name="Bewegungsmuster")
    
    # NEU: Equipment das für diese Übung benötigt wird
    equipment = models.ManyToManyField(Equipment, related_name="uebungen", blank=True, verbose_name="Benötigtes Equipment")

    beschreibung = models.TextField(blank=True, verbose_name="Anleitung / Notizen")
    bild = models.ImageField(upload_to='uebungen_bilder/', blank=True, null=True, verbose_name="Foto/Grafik")
    
    # Video-Optionen
    video_link = models.URLField(blank=True, null=True, verbose_name="YouTube/Vimeo Link", 
                                  help_text="z.B. https://www.youtube.com/watch?v=...")
    video_file = models.FileField(upload_to='uebungen_videos/', blank=True, null=True, 
                                   verbose_name="Video-Datei", help_text="Alternativ: MP4 hochladen")
    video_thumbnail = models.ImageField(upload_to='uebungen_thumbnails/', blank=True, null=True, 
                                        verbose_name="Video-Vorschaubild")

    # Favoriten
    favoriten = models.ManyToManyField(User, related_name="favoriten_uebungen", blank=True)
    
    # Tags
    tags = models.ManyToManyField(UebungTag, related_name="uebungen", blank=True, verbose_name="Tags")
    
    # Custom Übungen (User-spezifisch)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="custom_uebungen", null=True, blank=True, verbose_name="Erstellt von")
    is_custom = models.BooleanField(default=False, verbose_name="Benutzerdefinierte Übung")

    erstellt_am = models.DateTimeField(auto_now_add=True)

    # 1RM Kraftstandards bei 80kg Körpergewicht
    standard_beginner = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        verbose_name="1RM Anfänger (80kg KG)",
        help_text="Anfänger-Standard in kg bei 80kg Körpergewicht"
    )
    standard_intermediate = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        verbose_name="1RM Fortgeschritten (80kg KG)",
        help_text="Fortgeschritten-Standard in kg bei 80kg Körpergewicht"
    )
    standard_advanced = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        verbose_name="1RM Erfahren (80kg KG)",
        help_text="Erfahren-Standard in kg bei 80kg Körpergewicht"
    )
    standard_elite = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        verbose_name="1RM Elite (80kg KG)",
        help_text="Elite-Standard in kg bei 80kg Körpergewicht"
    )

    def __str__(self):
        return self.bezeichnung
    
    @property
    def is_global(self):
        """True wenn Übung für alle sichtbar ist (keine Custom-Übung)"""
        return not self.is_custom
    
    @property
    def has_video(self):
        """True wenn Übung ein Video hat (Link oder Upload)"""
        return bool(self.video_link or self.video_file)
    
    @property
    def video_embed_url(self):
        """Konvertiert YouTube/Vimeo URLs zu Embed-Format"""
        if not self.video_link:
            return None
        
        from urllib.parse import urlparse
        
        url = self.video_link
        
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname.lower() if parsed.hostname else ''
            
            # YouTube
            if hostname in ('www.youtube.com', 'youtube.com', 'm.youtube.com'):
                if 'watch?v=' in url:
                    video_id = url.split('watch?v=')[1].split('&')[0]
                else:
                    return url
                return f'https://www.youtube.com/embed/{video_id}'
            
            elif hostname in ('youtu.be', 'www.youtu.be'):
                video_id = parsed.path.lstrip('/').split('?')[0]
                return f'https://www.youtube.com/embed/{video_id}'
            
            # Vimeo
            elif hostname in ('vimeo.com', 'www.vimeo.com'):
                video_id = parsed.path.lstrip('/').split('?')[0]
                return f'https://player.vimeo.com/video/{video_id}'
        
        except Exception:
            # Bei Parse-Fehler Original-URL zurückgeben
            pass
        
        return url

    class Meta:
        verbose_name = "Übung"
        verbose_name_plural = "Übungen"
        ordering = ['bezeichnung']


class KoerperWerte(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="koerperwerte", null=True)
    datum = models.DateField(auto_now_add=True, verbose_name="Messdatum")
    
    groesse_cm = models.PositiveIntegerField(verbose_name="Größe (cm)", help_text="Benötigt für BMI/FFMI")
    gewicht = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Gewicht (kg)")
    
    fettmasse_kg = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, verbose_name="Fett (kg)")
    koerperfett_prozent = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True, verbose_name="KFA (%)")
    koerperwasser_kg = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, verbose_name="Wasser (kg)")
    muskelmasse_kg = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, verbose_name="Muskeln (kg)")
    knochenmasse_kg = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, verbose_name="Knochen (kg)")
    
    notiz = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        verbose_name = "Körperwert"
        verbose_name_plural = "Körperwerte"
        ordering = ['-datum']
        get_latest_by = 'datum'

    @property
    def bmi(self):
        if self.gewicht and self.groesse_cm:
            groesse_m = self.groesse_cm / 100
            return round(float(self.gewicht) / (groesse_m ** 2), 1)
        return None

    @property
    def ffmi(self):
        fett_kg = None
        if self.fettmasse_kg:
            fett_kg = float(self.fettmasse_kg)
        elif self.gewicht and self.koerperfett_prozent:
            fett_kg = float(self.gewicht) * (float(self.koerperfett_prozent) / 100)
        
        if self.gewicht and self.groesse_cm and fett_kg is not None:
            fettfreie_masse = float(self.gewicht) - fett_kg
            groesse_m = self.groesse_cm / 100
            ffmi_wert = fettfreie_masse / (groesse_m ** 2)
            ffmi_norm = ffmi_wert + 6.1 * (1.8 - groesse_m)
            return round(ffmi_norm, 1)
        return None


class Trainingseinheit(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="trainings", null=True)
    plan = models.ForeignKey('Plan', on_delete=models.SET_NULL, related_name="trainings", null=True, blank=True, verbose_name="Trainingsplan")
    datum = models.DateTimeField(auto_now_add=True)
    dauer_minuten = models.PositiveIntegerField(blank=True, null=True, verbose_name="Dauer (Min)")
    kommentar = models.TextField(blank=True, null=True, verbose_name="Wie lief's?")

    def __str__(self):
        return f"Training vom {self.datum.strftime('%d.%m.%Y %H:%M')}"
    
    class Meta:
        verbose_name = "Trainingseinheit"
        verbose_name_plural = "Trainingseinheiten"
        ordering = ['-datum']
        indexes = [
            models.Index(fields=['datum']),
        ]


class Satz(models.Model):
    einheit = models.ForeignKey(Trainingseinheit, on_delete=models.CASCADE, related_name="saetze")
    uebung = models.ForeignKey(Uebung, on_delete=models.PROTECT, verbose_name="Übung")
    
    satz_nr = models.PositiveIntegerField(default=1, verbose_name="Satz Nr.")
    
    gewicht = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="Gewicht (kg)")
    wiederholungen = models.PositiveIntegerField(verbose_name="Wdh.")
    ist_aufwaermsatz = models.BooleanField(default=False, verbose_name="Warmup")

    rpe = models.DecimalField(
        max_digits=3, 
        decimal_places=1, 
        blank=True, 
        null=True, 
        verbose_name="RPE (1-10)",
        validators=[MinValueValidator(1.0), MaxValueValidator(10.0)]
    )
    
    notiz = models.TextField(blank=True, null=True, verbose_name="Notiz", max_length=500)
    
    # Superset/Circuit Support
    superset_gruppe = models.PositiveIntegerField(
        default=0,
        verbose_name="Superset-Gruppe",
        help_text="0 = keine Gruppe, 1-9 = Gruppennummer für Supersätze"
    )

    class Meta:
        verbose_name = "Satz"
        verbose_name_plural = "Sätze"
        ordering = ['einheit', 'satz_nr']
        indexes = [
            models.Index(fields=['uebung', 'einheit']),
        ]


# --- NEU: CARDIO / AUSDAUER TRACKING ---

CARDIO_AKTIVITAETEN = [
    ('SCHWIMMEN', 'Schwimmen'),
    ('LAUFEN', 'Laufen'),
    ('RADFAHREN', 'Radfahren'),
    ('RUDERN', 'Rudern'),
    ('GEHEN', 'Gehen / Walking'),
    ('HIIT', 'HIIT / Intervall'),
    ('STEPPER', 'Stepper / Crosstrainer'),
    ('SEILSPRINGEN', 'Seilspringen'),
    ('SONSTIGES', 'Sonstiges'),
]

CARDIO_INTENSITAET = [
    ('LEICHT', 'Leicht (Zone 2 - kann sich unterhalten)'),
    ('MODERAT', 'Moderat (Zone 3 - anstrengend aber machbar)'),
    ('INTENSIV', 'Intensiv (Zone 4-5 - sehr anstrengend)'),
]


class CardioEinheit(models.Model):
    """Einfaches Cardio-Tracking für Ausdauertraining ohne Trainingsplan."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="cardio_einheiten")
    datum = models.DateField(verbose_name="Datum")
    aktivitaet = models.CharField(
        max_length=20, 
        choices=CARDIO_AKTIVITAETEN, 
        verbose_name="Aktivität"
    )
    dauer_minuten = models.PositiveIntegerField(verbose_name="Dauer (Minuten)")
    intensitaet = models.CharField(
        max_length=20, 
        choices=CARDIO_INTENSITAET, 
        default='MODERAT',
        verbose_name="Intensität"
    )
    notiz = models.CharField(max_length=200, blank=True, verbose_name="Notiz")
    erstellt_am = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.get_aktivitaet_display()} - {self.dauer_minuten} Min ({self.datum.strftime('%d.%m.%Y')})"
    
    @property
    def ermuedungs_punkte(self):
        """Berechnet Ermüdungspunkte basierend auf Intensität und Dauer."""
        basis = {
            'LEICHT': 0.1,    # 0.1 Punkte pro Minute
            'MODERAT': 0.2,   # 0.2 Punkte pro Minute
            'INTENSIV': 0.4,  # 0.4 Punkte pro Minute
        }
        return round(self.dauer_minuten * basis.get(self.intensitaet, 0.15), 1)
    
    class Meta:
        verbose_name = "Cardio-Einheit"
        verbose_name_plural = "Cardio-Einheiten"
        ordering = ['-datum', '-erstellt_am']
        indexes = [
            models.Index(fields=['user', 'datum']),
        ]


# --- NEU: TRAININGSPLÄNE (PHASE 2) ---

class Plan(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="plaene", null=True)
    name = models.CharField(max_length=100, verbose_name="Name des Plans")
    beschreibung = models.TextField(blank=True, verbose_name="Beschreibung")
    is_public = models.BooleanField(default=False, verbose_name="Öffentlich")
    erstellt_am = models.DateTimeField(auto_now_add=True)
    
    # Trainingspartner-Sharing: Mit wem wurde der Plan privat geteilt
    shared_with = models.ManyToManyField(
        User,
        related_name="shared_plans",
        blank=True,
        verbose_name="Geteilt mit",
        help_text="User, die diesen Plan sehen können (ohne öffentlich zu sein)"
    )
    
    # NEU: Gruppierung von zusammenhängenden Plänen (z.B. Push/Pull/Legs Split)
    # Pläne mit gleicher gruppe_id gehören zusammen
    gruppe_id = models.UUIDField(
        null=True, 
        blank=True, 
        verbose_name="Gruppen-ID",
        help_text="Pläne mit gleicher ID gehören zusammen (z.B. Split-Tage)"
    )
    gruppe_name = models.CharField(
        max_length=100, 
        blank=True, 
        verbose_name="Gruppenname",
        help_text="Name der Plangruppe (z.B. 'Push/Pull/Legs Split')"
    )
    gruppe_reihenfolge = models.PositiveIntegerField(
        default=0,
        verbose_name="Reihenfolge in Gruppe",
        help_text="Position des Plans innerhalb der Gruppe (0, 1, 2, ...)"
    )

    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        # Wenn gruppe_id gesetzt ist aber gruppe_name leer, extrahiere aus Plan-Namen
        if self.gruppe_id and not self.gruppe_name and ' - ' in self.name:
            self.gruppe_name = self.name.rsplit(' - ', 1)[0]
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Trainingsplan"
        verbose_name_plural = "Trainingspläne"


class PlanUebung(models.Model):
    """Verknüpft Übungen mit einem Plan in einer festen Reihenfolge."""
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="uebungen")
    uebung = models.ForeignKey(Uebung, on_delete=models.CASCADE, verbose_name="Übung")
    reihenfolge = models.PositiveIntegerField(default=1, verbose_name="Reihenfolge")
    
    # NEU: Trainingstag für Splits (z.B. "Push", "Pull", "Legs" oder "Tag 1", "Tag 2")
    trainingstag = models.CharField(max_length=100, blank=True, verbose_name="Trainingstag/Session")
    
    # Vorgaben für den Plan
    saetze_ziel = models.PositiveIntegerField(default=3, verbose_name="Geplante Sätze")
    wiederholungen_ziel = models.CharField(max_length=50, blank=True, verbose_name="Ziel-Wdh (z.B. 8-12)")
    
    # NEU: Pausenzeit zwischen Sätzen (in Sekunden)
    pausenzeit = models.PositiveIntegerField(
        default=120,
        verbose_name="Pausenzeit (Sekunden)",
        help_text="Empfohlene Pause zwischen Sätzen (60-300s)"
    )
    
    # Superset/Circuit Support
    superset_gruppe = models.PositiveIntegerField(
        default=0,
        verbose_name="Superset-Gruppe",
        help_text="0 = keine Gruppe, 1-9 = Gruppennummer für Supersätze"
    )
    
    class Meta:
        verbose_name = "Plan-Übung"
        verbose_name_plural = "Plan-Übungen"
        ordering = ['reihenfolge']


class ProgressPhoto(models.Model):
    """Fortschrittsfotos zur Dokumentation der Body Transformation."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="progress_photos")
    foto = models.ImageField(upload_to='progress_photos/%Y/%m/', verbose_name="Foto")
    datum = models.DateField(auto_now_add=True, verbose_name="Aufnahmedatum")
    
    gewicht_kg = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        blank=True, 
        null=True, 
        verbose_name="Gewicht (kg)",
        help_text="Optional: Gewicht zum Zeitpunkt des Fotos"
    )
    
    notiz = models.CharField(
        max_length=200, 
        blank=True, 
        null=True, 
        verbose_name="Notiz",
        help_text="z.B. 'Start', 'Nach 3 Monaten', 'Bulking Phase'"
    )
    
    erstellt_am = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Fortschrittsfoto"
        verbose_name_plural = "Fortschrittsfotos"
        ordering = ['-datum']
        indexes = [
            models.Index(fields=['user', '-datum']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.datum.strftime('%d.%m.%Y')}"


# --- BETA-ZUGANG & EINLADUNGSSYSTEM ---

class InviteCode(models.Model):
    """
    Einladungscode für Beta-Registrierung
    Kann von Admin oder später von aktiven Usern erstellt werden
    """
    code = models.CharField(
        max_length=20, 
        unique=True,
        verbose_name="Einladungscode"
    )
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='created_invite_codes',
        verbose_name="Erstellt von"
    )
    max_uses = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name="Max. Verwendungen",
        help_text="Wie oft kann dieser Code verwendet werden?"
    )
    used_count = models.IntegerField(
        default=0,
        verbose_name="Bereits verwendet"
    )
    expires_at = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name="Ablaufdatum",
        help_text="Leer lassen für unbegrenzte Gültigkeit"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Einladungscode"
        verbose_name_plural = "Einladungscodes"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.code} ({self.used_count}/{self.max_uses})"
    
    def is_valid(self):
        """Prüft ob Code noch gültig ist"""
        from django.utils import timezone
        
        # Max. Verwendungen erreicht?
        if self.used_count >= self.max_uses:
            return False
        
        # Abgelaufen?
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        
        return True
    
    def use(self):
        """Erhöht den Verwendungszähler"""
        if self.is_valid():
            self.used_count += 1
            self.save()
            return True
        return False


class WaitlistEntry(models.Model):
    """
    Wartelisten-Eintrag für Beta-Bewerbungen
    Wird nach 48h automatisch approved
    """
    EXPERIENCE_CHOICES = [
        ('beginner', 'Anfänger (< 1 Jahr Training)'),
        ('intermediate', 'Fortgeschritten (1-3 Jahre)'),
        ('advanced', 'Erfahren (> 3 Jahre)'),
        ('returning', 'Wiedereinstieg nach Pause'),
    ]
    
    INTEREST_CHOICES = [
        ('ai_plans', 'KI-Trainingspläne'),
        ('tracking', 'Trainingstracking'),
        ('analytics', 'Analyse & Statistiken'),
        ('opensource', 'Open-Source / Entwicklung'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Warteliste'),
        ('approved', 'Eingeladen'),
        ('registered', 'Registriert'),
        ('spam', 'Blockiert'),
    ]
    
    email = models.EmailField(
        unique=True,
        verbose_name="E-Mail"
    )
    reason = models.TextField(
        verbose_name="Motivation",
        help_text="Warum möchtest du HomeGym nutzen?"
    )
    experience = models.CharField(
        max_length=20,
        choices=EXPERIENCE_CHOICES,
        verbose_name="Trainingserfahrung"
    )
    interests = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Interessen",
        help_text="Mehrfachauswahl möglich"
    )
    github_username = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="GitHub Username (optional)"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Status"
    )
    invite_code = models.OneToOneField(
        InviteCode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='waitlist_entry',
        verbose_name="Zugewiesener Code"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Wartelisten-Eintrag"
        verbose_name_plural = "Warteliste"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['email']),
        ]
    
    def __str__(self):
        return f"{self.email} ({self.get_status_display()})"
    
    def should_auto_approve(self):
        """Prüft ob Eintrag alt genug für Auto-Approve ist (48h)"""
        from django.utils import timezone
        from datetime import timedelta
        
        if self.status != 'pending':
            return False
        
        age = timezone.now() - self.created_at
        return age >= timedelta(hours=48)
    
    def approve_and_send_code(self):
        """Approved den Eintrag und sendet Einladungscode per Email"""
        from django.utils import timezone
        import secrets
        
        if self.status != 'pending':
            return False
        
        # Einladungscode generieren
        code = f"BETA{secrets.token_hex(6).upper()}"
        invite = InviteCode.objects.create(
            code=code,
            created_by=None,  # System-generiert
            max_uses=1,
            expires_at=timezone.now() + timezone.timedelta(days=30)
        )
        
        # Status updaten
        self.status = 'approved'
        self.approved_at = timezone.now()
        self.invite_code = invite
        self.save()
        
        # Email senden
        self.send_invite_email()
        
        return True
    
    def send_invite_email(self):
        """Sendet Einladungscode per Email"""
        from django.core.mail import send_mail
        from django.conf import settings
        
        if not self.invite_code:
            return False
        
        subject = "🎉 Dein HomeGym Beta-Zugang ist bereit!"
        
        message = f"""Hallo!

Vielen Dank für dein Interesse an HomeGym! 🏋️

Deine Bewerbung wurde geprüft und du bist jetzt für die Beta-Phase freigeschaltet.

🔑 Dein persönlicher Einladungscode:
{self.invite_code.code}

📝 So geht's weiter:
1. Gehe zu: {settings.SITE_URL}/register/?code={self.invite_code.code}
2. Erstelle deinen Account
3. Starte dein erstes Training!

Der Code ist 30 Tage gültig und kann nur einmal verwendet werden.

Was HomeGym bietet:
✅ KI-basierte Trainingsplan-Generierung
✅ Intelligentes Trainingstracking
✅ Detaillierte Statistiken & Analysen
✅ Offline-Funktionalität (PWA)
✅ Open-Source & datenschutzfreundlich

Viel Erfolg beim Training!

Dein HomeGym Team
https://gym.last-strawberry.com

---
Diese E-Mail wurde automatisch generiert.
Bei Fragen: marcus.kohtz@signz-vision.com
"""
        
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[self.email],
                fail_silently=False,
            )
            return True
        except Exception as e:
            print(f"Email sending failed: {e}")
            return False


# --- FEEDBACK SYSTEM (Beta) ---

FEEDBACK_TYPE_CHOICES = [
    ('BUG', '🐛 Bugreport'),
    ('FEATURE', '💡 Verbesserungsvorschlag'),
    ('QUESTION', '❓ Frage'),
]

FEEDBACK_STATUS_CHOICES = [
    ('NEW', '🆕 Neu'),
    ('ACCEPTED', '✅ Angenommen'),
    ('REJECTED', '❌ Abgelehnt'),
    ('IN_PROGRESS', '🔄 In Bearbeitung'),
    ('DONE', '🎉 Umgesetzt'),
]

FEEDBACK_PRIORITY_CHOICES = [
    ('LOW', '🟢 Niedrig'),
    ('MEDIUM', '🟡 Mittel'),
    ('HIGH', '🔴 Hoch'),
]


class Feedback(models.Model):
    """Beta-Feedback: Bugreports und Verbesserungsvorschläge"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='feedbacks')
    feedback_type = models.CharField(max_length=20, choices=FEEDBACK_TYPE_CHOICES, default='FEATURE')
    title = models.CharField(max_length=200, verbose_name="Kurzbeschreibung")
    description = models.TextField(verbose_name="Detaillierte Beschreibung")
    
    # Status-Tracking
    status = models.CharField(max_length=20, choices=FEEDBACK_STATUS_CHOICES, default='NEW')
    priority = models.CharField(max_length=20, choices=FEEDBACK_PRIORITY_CHOICES, default='MEDIUM', blank=True)
    
    # Admin-Antwort
    admin_response = models.TextField(blank=True, null=True, verbose_name="Admin-Antwort")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Feedback"
        verbose_name_plural = "Feedbacks"
    
    def __str__(self):
        return f"[{self.get_feedback_type_display()}] {self.title} - {self.user.username}"
    
    def get_status_badge_class(self):
        """Bootstrap Badge-Klasse basierend auf Status"""
        badge_classes = {
            'NEW': 'bg-info',
            'ACCEPTED': 'bg-success',
            'REJECTED': 'bg-danger',
            'IN_PROGRESS': 'bg-warning text-dark',
            'DONE': 'bg-primary',
        }
        return badge_classes.get(self.status, 'bg-secondary')


class PushSubscription(models.Model):
    """Web Push Notification Subscription für User"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='push_subscriptions')
    
    # Web Push Subscription Details (JSON vom Browser)
    endpoint = models.TextField(unique=True, verbose_name="Push Endpoint")
    p256dh = models.TextField(verbose_name="P256DH Key")
    auth = models.TextField(verbose_name="Auth Secret")
    
    # Metadata
    user_agent = models.CharField(max_length=500, blank=True, verbose_name="Browser/Gerät")
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(auto_now=True)
    
    # Notification Preferences
    training_reminders = models.BooleanField(default=True, verbose_name="Trainings-Erinnerungen")
    rest_day_reminders = models.BooleanField(default=True, verbose_name="Ruhetag-Benachrichtigungen")
    achievement_notifications = models.BooleanField(default=True, verbose_name="Erfolgs-Benachrichtigungen")
    
    class Meta:
        verbose_name = "Push Subscription"
        verbose_name_plural = "Push Subscriptions"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.user_agent[:50]}"


class MLPredictionModel(models.Model):
    """Trainierte ML-Modelle für Gewichtsvorhersagen pro User"""
    
    MODEL_TYPES = [
        ('STRENGTH', 'Kraftvorhersage'),
        ('VOLUME', 'Volumenempfehlung'),
        ('FREQUENCY', 'Trainingsfrequenz'),
    ]
    
    STATUS_CHOICES = [
        ('TRAINING', 'In Training'),
        ('READY', 'Einsatzbereit'),
        ('OUTDATED', 'Veraltet'),
        ('ERROR', 'Fehler'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ml_models')
    model_type = models.CharField(max_length=20, choices=MODEL_TYPES, default='STRENGTH')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='TRAINING')
    
    # Modell-Speicherort (Pickle-File)
    model_path = models.CharField(max_length=500, verbose_name="Model File Path")
    
    # Training Metadata
    trained_at = models.DateTimeField(auto_now=True, verbose_name="Letztes Training")
    training_samples = models.IntegerField(default=0, verbose_name="Anzahl Trainingsdaten")
    accuracy_score = models.FloatField(null=True, blank=True, verbose_name="R² Score")
    mean_absolute_error = models.FloatField(null=True, blank=True, verbose_name="MAE")
    
    # Übung-spezifisch (für STRENGTH models)
    uebung = models.ForeignKey(
        'Uebung', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='ml_models',
        verbose_name="Übung (für Kraftvorhersage)"
    )
    
    # Hyperparameter (JSON)
    hyperparameters = models.JSONField(default=dict, blank=True, verbose_name="ML Hyperparameter")
    
    # Feature-Statistiken (JSON)
    feature_stats = models.JSONField(default=dict, blank=True, verbose_name="Feature-Statistiken")
    
    class Meta:
        verbose_name = "ML Prediction Model"
        verbose_name_plural = "ML Prediction Models"
        ordering = ['-trained_at']
        unique_together = [['user', 'model_type', 'uebung']]
        indexes = [
            models.Index(fields=['user', 'model_type', 'status']),
            models.Index(fields=['user', 'uebung', 'status']),
        ]
    
    def __str__(self):
        if self.uebung:
            return f"{self.user.username} - {self.get_model_type_display()} - {self.uebung.bezeichnung}"
        return f"{self.user.username} - {self.get_model_type_display()}"
    
    def is_ready(self):
        """Prüft, ob Modell einsatzbereit ist"""
        return self.status == 'READY' and self.training_samples >= 10
    
    def needs_retraining(self):
        """Prüft, ob Modell neu trainiert werden sollte (>30 Tage alt)"""
        from django.utils import timezone
        from datetime import timedelta
        return timezone.now() - self.trained_at > timedelta(days=30)
