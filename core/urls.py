from django.urls import path
from . import views

urlpatterns = [
    # Auth
    # path('register/', views.register, name='register'),  # DEAKTIVIERT - keine öffentliche Registrierung
    
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    path('training/select/', views.training_select_plan, name='training_select_plan'),
    path('plan/<int:plan_id>/', views.plan_details, name='plan_details'),
    path('plan/create/', views.create_plan, name='create_plan'),
    path('plan/<int:plan_id>/edit/', views.edit_plan, name='edit_plan'),
    path('plan/<int:plan_id>/delete/', views.delete_plan, name='delete_plan'),
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
]