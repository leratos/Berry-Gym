from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import User

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
    
    # Unterkörper
    ('BEINE_QUAD', 'Oberschenkel Vorn (Quadrizeps)'),
    ('BEINE_HAM', 'Oberschenkel Hinten (Hamstrings/Ischiocrurale)'),
    ('PO', 'Gesäß (Gluteus maximus/medius)'),
    ('WADEN', 'Waden (Gastrocnemius/Soleus)'),
    ('ADDUKTOREN', 'Oberschenkel Innen (Adduktoren)'),
    ('ABDUKTOREN', 'Oberschenkel Außen (Abduktoren)'),
    
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
]

# --- MODELLE ---

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
    bezeichnung = models.CharField(max_length=100, unique=True, verbose_name="Name der Übung")
    muskelgruppe = models.CharField(max_length=50, choices=MUSKELGRUPPEN, verbose_name="Hauptmuskel")
    hilfsmuskeln = models.JSONField(default=list, blank=True, verbose_name="Hilfsmuskelgruppen")
    
    gewichts_typ = models.CharField(max_length=20, choices=GEWICHTS_TYP, default='GESAMT', verbose_name="Gewichtsart")
    
    # NEU: Bewegungstyp für Algorithmus
    bewegungstyp = models.CharField(max_length=20, choices=BEWEGUNGS_TYP, default='ISOLATION', verbose_name="Bewegungsmuster")
    
    # NEU: Equipment das für diese Übung benötigt wird
    equipment = models.ManyToManyField(Equipment, related_name="uebungen", blank=True, verbose_name="Benötigtes Equipment")

    beschreibung = models.TextField(blank=True, verbose_name="Anleitung / Notizen")
    bild = models.ImageField(upload_to='uebungen_bilder/', blank=True, null=True, verbose_name="Foto/Grafik")
    video_link = models.URLField(blank=True, null=True, verbose_name="YouTube Link")

    # Favoriten
    favoriten = models.ManyToManyField(User, related_name="favoriten_uebungen", blank=True)

    erstellt_am = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.bezeichnung

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

# --- NEU: TRAININGSPLÄNE (PHASE 2) ---

class Plan(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="plaene", null=True)
    name = models.CharField(max_length=100, verbose_name="Name des Plans")
    beschreibung = models.TextField(blank=True, verbose_name="Beschreibung")
    erstellt_am = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

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