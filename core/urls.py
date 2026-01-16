from django.urls import path
from . import views

urlpatterns = [
    # Auth
    # path('register/', views.register, name='register'),  # DEAKTIVIERT - keine öffentliche Registrierung
    
    # PWA Files (must be at root)
    path('service-worker.js', views.service_worker, name='service_worker'),
    path('manifest.json', views.manifest, name='manifest'),
    
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    path('training/select/', views.training_select_plan, name='training_select_plan'),
    path('plan/<int:plan_id>/', views.plan_details, name='plan_details'),
    path('plan/create/', views.create_plan, name='create_plan'),
    path('plan/<int:plan_id>/edit/', views.edit_plan, name='edit_plan'),
    path('plan/<int:plan_id>/delete/', views.delete_plan, name='delete_plan'),
    path('plan/<int:plan_id>/copy/', views.copy_plan, name='copy_plan'),
    path('uebungen/', views.uebungen_auswahl, name='uebungen_auswahl'),
    path('muscle-map/', views.muscle_map, name='muscle_map'),
    path('uebung/<int:uebung_id>/', views.uebung_detail, name='uebung_detail'),
    path('training/start/', views.training_start, name='training_start_free'),
    path('training/start/<int:plan_id>/', views.training_start, name='training_start_plan'),
    path('training/<int:training_id>/', views.training_session, name='training_session'),
    path('training/<int:training_id>/add_set/', views.add_set, name='add_set'),
    path('set/<int:set_id>/update/', views.update_set, name='update_set'),
    path('set/<int:set_id>/delete/', views.delete_set, name='delete_set'),
    path('body-stats/add/', views.add_koerperwert, name='add_koerperwert'),
    path('body-stats/', views.body_stats, name='body_stats'),
    path('body-stats/<int:wert_id>/edit/', views.edit_koerperwert, name='edit_koerperwert'),
    path('body-stats/<int:wert_id>/delete/', views.delete_koerperwert, name='delete_koerperwert'),
    path('uebung/<int:uebung_id>/toggle-favorite/', views.toggle_favorite, name='toggle_favorite'),
    path('export/training-csv/', views.export_training_csv, name='export_training_csv'),
    path('history/', views.training_list, name='training_list'),
    path('stats/', views.training_stats, name='training_stats'),
    path('training/<int:training_id>/delete/', views.delete_training, name='delete_training'),
    path('training/<int:training_id>/finish/', views.finish_training, name='finish_training'),
    path('api/last-set/<int:uebung_id>/', views.get_last_set, name='get_last_set'),
    path('stats/exercise/<int:uebung_id>/', views.exercise_stats, name='exercise_stats'),
    
    # Offline Sync
    path('api/sync-offline/', views.sync_offline_data, name='sync_offline_data'),
    
    # Progress Photos
    path('progress-photos/', views.progress_photos, name='progress_photos'),
    path('progress-photos/upload/', views.upload_progress_photo, name='upload_progress_photo'),
    path('progress-photos/<int:photo_id>/delete/', views.delete_progress_photo, name='delete_progress_photo'),
    
    # PDF Export
    path('export/training-pdf/', views.export_training_pdf, name='export_training_pdf'),
    path('plan/<int:plan_id>/pdf/', views.export_plan_pdf, name='export_plan_pdf'),
    
    # AI/ML Recommendations
    path('recommendations/', views.workout_recommendations, name='workout_recommendations'),
    
    # Equipment Management
    path('equipment/', views.equipment_management, name='equipment_management'),
    path('equipment/toggle/<int:equipment_id>/', views.toggle_equipment, name='toggle_equipment'),
    
    # Exercise API
    path('api/exercise/<int:exercise_id>/', views.exercise_api_detail, name='exercise_api_detail'),
    
    # Live Guidance API
    path('api/live-guidance/', views.live_guidance_api, name='live_guidance_api'),
    
    # AI Plan Generator API
    path('api/generate-plan/', views.generate_plan_api, name='generate_plan_api'),
    
    # AI Plan Optimization API
    path('api/analyze-plan/', views.analyze_plan_api, name='analyze_plan_api'),
    path('api/optimize-plan/', views.optimize_plan_api, name='optimize_plan_api'),
    path('api/apply-optimizations/', views.apply_optimizations_api, name='apply_optimizations_api'),
    
    # Plan Templates
    path('api/plan-templates/', views.get_plan_templates, name='get_plan_templates'),
    path('api/plan-templates/<str:template_key>/', views.get_template_detail, name='get_template_detail'),
    path('api/plan-templates/<str:template_key>/create/', views.create_plan_from_template, name='create_plan_from_template'),
    
    # Exercise Management (Admin Only)
    path('uebungen/export/', views.export_uebungen, name='export_uebungen'),
    path('uebungen/import/', views.import_uebungen, name='import_uebungen'),
]