from django.contrib import admin
from django import forms
from .models import Uebung, Trainingseinheit, Satz, KoerperWerte, Plan, PlanUebung, ProgressPhoto, Equipment, MUSKELGRUPPEN

# --- ÜBUNGEN ---
class UebungAdminForm(forms.ModelForm):
    hilfsmuskeln = forms.MultipleChoiceField(
        choices=MUSKELGRUPPEN,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Hilfsmuskelgruppen'
    )
    
    class Meta:
        model = Uebung
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.hilfsmuskeln:
            self.initial['hilfsmuskeln'] = self.instance.hilfsmuskeln

@admin.register(Uebung)
class UebungAdmin(admin.ModelAdmin):
    form = UebungAdminForm
    list_display = ('bezeichnung', 'muskelgruppe', 'gewichts_typ', 'bewegungstyp', 'equipment_anzeige', 'hilfsmuskel_anzeige')
    list_filter = ('muskelgruppe', 'bewegungstyp', 'gewichts_typ', 'equipment')
    search_fields = ('bezeichnung',)
    ordering = ('bezeichnung',)
    filter_horizontal = ('equipment', 'favoriten')
    
    fieldsets = (
        ('Grundinformationen', {
            'fields': ('bezeichnung', 'muskelgruppe', 'hilfsmuskeln')
        }),
        ('Trainingsdetails', {
            'fields': ('gewichts_typ', 'bewegungstyp', 'equipment')
        }),
        ('Zusätzliche Infos', {
            'fields': ('beschreibung', 'bild', 'video_link'),
            'classes': ('collapse',)
        }),
    )
    
    def equipment_anzeige(self, obj):
        equipment_list = obj.equipment.all()
        if equipment_list:
            return ', '.join(str(eq) for eq in equipment_list[:2]) + ('...' if len(equipment_list) > 2 else '')
        return '❌ Kein Equipment'
    equipment_anzeige.short_description = 'Equipment'
    
    def hilfsmuskel_anzeige(self, obj):
        if obj.hilfsmuskeln:
            labels = [dict(MUSKELGRUPPEN).get(hm, hm) for hm in obj.hilfsmuskeln]
            return ', '.join(labels[:2]) + ('...' if len(labels) > 2 else '')
        return '-'
    hilfsmuskel_anzeige.short_description = 'Hilfsmuskeln'

# --- TRAINING ---
class SatzInline(admin.TabularInline):
    model = Satz
    extra = 0

@admin.register(Trainingseinheit)
class TrainingseinheitAdmin(admin.ModelAdmin):
    list_display = ('datum_formatiert', 'dauer_minuten', 'anzahl_saetze')
    inlines = [SatzInline]
    
    def datum_formatiert(self, obj):
        return obj.datum.strftime("%d.%m.%Y %H:%M")
    datum_formatiert.short_description = "Datum"

    def anzahl_saetze(self, obj):
        return obj.saetze.count()
    anzahl_saetze.short_description = "Sätze"

# --- PLÄNE (NEU) ---
class PlanUebungInline(admin.TabularInline):
    model = PlanUebung
    extra = 1 # Zeigt immer eine leere Zeile für neue Übungen
    ordering = ('reihenfolge',) # Sortiert nach deiner Reihenfolge

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'anzahl_uebungen')
    inlines = [PlanUebungInline] # Hier fügst du die Übungen hinzu

    def anzahl_uebungen(self, obj):
        return obj.uebungen.count()
    anzahl_uebungen.short_description = "Übungen"

# --- KÖRPERWERTE ---
@admin.register(KoerperWerte)
class KoerperWerteAdmin(admin.ModelAdmin):
    list_display = ('datum', 'gewicht', 'bmi', 'ffmi')
    ordering = ('-datum',)


# --- FORTSCHRITTSFOTOS ---
@admin.register(ProgressPhoto)
class ProgressPhotoAdmin(admin.ModelAdmin):
    list_display = ('user', 'datum', 'gewicht_kg', 'notiz', 'foto_thumbnail')
    list_filter = ('user', 'datum')
    ordering = ('-datum',)
    readonly_fields = ('erstellt_am',)
    
    def foto_thumbnail(self, obj):
        if obj.foto:
            return f'<img src="{obj.foto.url}" width="80" height="80" style="object-fit: cover; border-radius: 4px;" />'
        return '-'
    foto_thumbnail.short_description = 'Vorschau'
    foto_thumbnail.allow_tags = True


# --- EQUIPMENT ---
@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'anzahl_user', 'erstellt_am')
    search_fields = ('name',)
    filter_horizontal = ('users',)
    
    def anzahl_user(self, obj):
        return obj.users.count()
    anzahl_user.short_description = 'Anzahl User'