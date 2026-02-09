from django.contrib import admin
from django.utils.html import format_html
from django import forms
from .models import (
    Uebung, Trainingseinheit, Satz, KoerperWerte, Plan, PlanUebung,
    ProgressPhoto, Equipment, InviteCode, WaitlistEntry, Feedback, MUSKELGRUPPEN,
    UebungTag, MLPredictionModel, UserProfile
)

# --- ÜBUNGEN ---
class UebungAdminForm(forms.ModelForm):
    hilfsmuskeln = forms.MultipleChoiceField(
        choices=MUSKELGRUPPEN,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Hilfsmuskelgruppen'
    )
    
    beschreibung = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4, 'cols': 80}),
        required=False,
        label='Anleitung / Notizen'
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
    list_display = (
        'bezeichnung',
        'muskelgruppe',
        'gewichts_typ',
        'bewegungstyp',
        'standard_beginner',
        'standard_intermediate',
        'standard_advanced',
        'standard_elite',
        'tags_anzeige',
        'equipment_anzeige',
        'video_status',
        'hilfsmuskel_anzeige'
    )
    list_filter = ('muskelgruppe', 'bewegungstyp', 'gewichts_typ', 'tags', 'equipment')
    search_fields = ('bezeichnung',)
    ordering = ('bezeichnung',)
    filter_horizontal = ('equipment', 'favoriten', 'tags')

    fieldsets = (
        ('Grundinformationen', {
            'fields': ('bezeichnung', 'muskelgruppe', 'hilfsmuskeln', 'tags')
        }),
        ('Trainingsdetails', {
            'fields': ('gewichts_typ', 'bewegungstyp', 'equipment')
        }),
        ('1RM Kraftstandards (bei 80kg Körpergewicht)', {
            'fields': (
                'standard_beginner',
                'standard_intermediate',
                'standard_advanced',
                'standard_elite'
            ),
            'description': 'Standards in kg für einen 80kg schweren Athleten. '
                          'Werden automatisch nach Körpergewicht skaliert.',
            'classes': ('collapse',)
        }),
        ('Medien', {
            'fields': ('bild', 'video_link', 'video_file', 'video_thumbnail'),
            'description': 'YouTube/Vimeo Link ODER Video-Datei hochladen. Thumbnail ist optional.'
        }),
        ('Zusätzliche Infos', {
            'fields': ('beschreibung',),
            'classes': ('collapse',)
        }),
    )
    
    def video_status(self, obj):
        if obj.video_file:
            return format_html('<span style="color:green;">â Upload</span>')
        elif obj.video_link:
            return format_html('<span style="color:blue;">â Link</span>')
        return format_html('<span style="color:gray;">-</span>')
    video_status.short_description = 'Video'
    
    def tags_anzeige(self, obj):
        tags = obj.tags.all()
        if tags:
            return format_html(
                ' '.join([
                    f'<span style="background-color:{tag.farbe};color:white;padding:2px 6px;border-radius:3px;font-size:11px;margin-right:3px;">{tag.get_name_display()}</span>'
                    for tag in tags
                ])
            )
        return '-'
    tags_anzeige.short_description = 'Tags'
    
    def equipment_anzeige(self, obj):
        equipment_list = obj.equipment.all()
        if equipment_list:
            return ', '.join(str(eq) for eq in equipment_list[:2]) + ('...' if len(equipment_list) > 2 else '')
        return 'â Kein Equipment'
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
    list_display = ('datum_formatiert', 'user', 'ist_deload', 'dauer_minuten', 'anzahl_saetze')
    list_filter = ('ist_deload', 'user')
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


# --- BETA-ZUGANG ---
@admin.register(InviteCode)
class InviteCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'is_valid_status', 'used_count', 'max_uses', 'expires_at', 'created_by', 'created_at')
    list_filter = ('created_at', 'expires_at')
    search_fields = ('code',)
    readonly_fields = ('used_count', 'created_at')
    
    def is_valid_status(self, obj):
        if obj.is_valid():
            return format_html('<span style="color: green;">✓ Gültig</span>')
        return format_html('<span style="color: red;">✗ Ungültig</span>')
    is_valid_status.short_description = 'Status'
    
    actions = ['generate_codes']
    
    def generate_codes(self, request, queryset):
        """Bulk-Aktion: Codes generieren"""
        import secrets
        count = 10  # Anzahl zu erstellender Codes
        for _ in range(count):
            code = f"BETA{secrets.token_hex(6).upper()}"
            InviteCode.objects.create(
                code=code,
                created_by=request.user,
                max_uses=1
            )
        self.message_user(request, f'{count} Einladungscodes wurden erstellt')
    generate_codes.short_description = 'Generiere 10 neue Codes'


@admin.register(WaitlistEntry)
class WaitlistEntryAdmin(admin.ModelAdmin):
    list_display = ('email', 'status_badge', 'experience', 'created_at', 'approved_at', 'actions_column')
    list_filter = ('status', 'experience', 'created_at')
    search_fields = ('email', 'reason', 'github_username')
    readonly_fields = ('created_at', 'approved_at', 'invite_code')
    
    fieldsets = (
        ('Kontakt', {
            'fields': ('email', 'github_username')
        }),
        ('Bewerbung', {
            'fields': ('reason', 'experience', 'interests')
        }),
        ('Status', {
            'fields': ('status', 'invite_code', 'created_at', 'approved_at')
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'pending': 'orange',
            'approved': 'green',
            'registered': 'blue',
            'spam': 'red'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def actions_column(self, obj):
        if obj.status == 'pending':
            return format_html(
                '<span style="color: orange; font-weight: bold;">â³ Warte auf Approval</span>'
            )
        elif obj.status == 'approved' and obj.invite_code:
            return format_html(
                '<span style="color: green;">â Code: {}</span>',
                obj.invite_code.code
            )
        return '-'
    actions_column.short_description = 'Aktionen'
    
    actions = ['approve_selected', 'mark_as_spam']
    
    def approve_selected(self, request, queryset):
        """Bulk-Approve"""
        count = 0
        for entry in queryset.filter(status='pending'):
            if entry.approve_and_send_code():
                count += 1
        self.message_user(request, f'{count} Einträge wurden approved')
    approve_selected.short_description = 'Ausgewählte approven & Code senden'
    
    def mark_as_spam(self, request, queryset):
        """Als Spam markieren"""
        count = queryset.update(status='spam')
        self.message_user(request, f'{count} Einträge als Spam markiert')
    mark_as_spam.short_description = 'Als Spam markieren'


# --- FEEDBACK (Beta) ---
@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('title', 'feedback_type', 'user', 'status', 'priority', 'created_at')
    list_filter = ('feedback_type', 'status', 'priority', 'created_at')
    search_fields = ('title', 'description', 'user__username')
    ordering = ('-created_at',)
    readonly_fields = ('user', 'feedback_type', 'title', 'description', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Feedback-Details (vom User)', {
            'fields': ('user', 'feedback_type', 'title', 'description', 'created_at')
        }),
        ('Status & Bearbeitung', {
            'fields': ('status', 'priority', 'admin_response', 'updated_at')
        }),
    )
    
    actions = ['mark_accepted', 'mark_rejected', 'mark_done']
    
    def mark_accepted(self, request, queryset):
        count = queryset.update(status='ACCEPTED')
        self.message_user(request, f'{count} Feedback(s) als angenommen markiert')
    mark_accepted.short_description = '✅ Als angenommen markieren'
    
    def mark_rejected(self, request, queryset):
        count = queryset.update(status='REJECTED')
        self.message_user(request, f'{count} Feedback(s) als abgelehnt markiert')
    mark_rejected.short_description = '❌ Als abgelehnt markieren'
    
    def mark_done(self, request, queryset):
        count = queryset.update(status='DONE')
        self.message_user(request, f'{count} Feedback(s) als umgesetzt markiert')
    mark_done.short_description = '✅ Als umgesetzt markieren'


# --- ÜBUNGS-TAGS ---
@admin.register(UebungTag)
class UebungTagAdmin(admin.ModelAdmin):
    list_display = ('name_display', 'farbe_preview', 'beschreibung', 'anzahl_uebungen')
    list_filter = ('name',)
    search_fields = ('name', 'beschreibung')
    ordering = ('name',)
    
    def name_display(self, obj):
        return obj.get_name_display()
    name_display.short_description = 'Tag'
    
    def farbe_preview(self, obj):
        return format_html(
            '<span style="background-color:{};color:white;padding:4px 10px;border-radius:4px;font-weight:bold;">{}</span>',
            obj.farbe,
            obj.get_name_display()
        )
    farbe_preview.short_description = 'Vorschau'
    
    def anzahl_uebungen(self, obj):
        count = obj.uebungen.count()

        return f'{count} Übungen'

    anzahl_uebungen.short_description = 'Verwendung'

# --- ML PREDICTION MODELS ---
@admin.register(MLPredictionModel)
class MLPredictionModelAdmin(admin.ModelAdmin):
    list_display = ('user', 'model_type_display', 'uebung', 'status_display', 'training_samples', 'accuracy_display', 'trained_at', 'needs_retrain_display')
    list_filter = ('model_type', 'status', 'trained_at')
    search_fields = ('user__username', 'uebung__bezeichnung')
    ordering = ('-trained_at',)
    readonly_fields = ('model_path', 'trained_at', 'training_samples', 'accuracy_score', 'mean_absolute_error', 'feature_stats', 'hyperparameters')
    
    fieldsets = (
        ('Model Info', {
            'fields': ('user', 'model_type', 'uebung', 'status')
        }),
        ('Training Metrics', {
            'fields': ('trained_at', 'training_samples', 'accuracy_score', 'mean_absolute_error')
        }),
        ('Technical Details', {
            'fields': ('model_path', 'hyperparameters', 'feature_stats'),
            'classes': ('collapse',)
        }),
    )
    
    def model_type_display(self, obj):
        return obj.get_model_type_display()
    model_type_display.short_description = 'Typ'
    
    def status_display(self, obj):
        colors = {
            'TRAINING': 'orange',
            'READY': 'green',
            'OUTDATED': 'gray',
            'ERROR': 'red',
        }
        return format_html('<span style="color:{};"> {}</span>', colors.get(obj.status, 'black'), obj.get_status_display())
    status_display.short_description = 'Status'
    
    def accuracy_display(self, obj):
        if obj.accuracy_score is not None:
            return f'R²={obj.accuracy_score:.3f}, MAE={obj.mean_absolute_error:.1f}kg'
        return '-'
    accuracy_display.short_description = 'Genauigkeit'
    
    def needs_retrain_display(self, obj):
        if obj.needs_retraining():
            return format_html('<span style="color:orange;"> Ja</span>')
        return format_html('<span style="color:green;"> Nein</span>')
    needs_retrain_display.short_description = 'Neu trainieren?'
    
    actions = ['retrain_models']
    
    def retrain_models(self, request, queryset):
        """Admin Action: Trainiert ausgewählte Modelle neu"""
        from ml_coach.ml_trainer import MLTrainer
        
        count = 0
        for ml_model in queryset:
            trainer = MLTrainer(ml_model.user, ml_model.uebung)
            new_model, metrics = trainer.train_model()
            if new_model:
                count += 1
        
        self.message_user(request, f'{count} Modelle neu trainiert')
    retrain_models.short_description = ' Modelle neu trainieren'


# --- USER PROFILE ---
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'active_plan_group')
    search_fields = ('user__username',)
    list_filter = ('active_plan_group',)

