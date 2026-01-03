from django.contrib import admin
from django import forms
from .models import Uebung, Trainingseinheit, Satz, KoerperWerte, Plan, PlanUebung, MUSKELGRUPPEN

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
    list_display = ('bezeichnung', 'muskelgruppe', 'gewichts_typ', 'bewegungstyp', 'hilfsmuskel_anzeige')
    list_filter = ('muskelgruppe', 'bewegungstyp', 'gewichts_typ')
    search_fields = ('bezeichnung',)
    ordering = ('bezeichnung',)
    
    fieldsets = (
        ('Grundinformationen', {
            'fields': ('bezeichnung', 'muskelgruppe', 'hilfsmuskeln')
        }),
        ('Trainingsdetails', {
            'fields': ('gewichts_typ', 'bewegungstyp')
        }),
        ('Zusätzliche Infos', {
            'fields': ('beschreibung', 'bild', 'video_link'),
            'classes': ('collapse',)
        }),
    )
    
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