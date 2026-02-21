from django.urls import path

from . import views

urlpatterns = [
    # Auth
    path("apply-beta/", views.apply_beta, name="apply_beta"),
    path("register/", views.register, name="register"),
    # Profile
    path("profile/", views.profile, name="profile"),
    # Legal Pages
    path("impressum/", views.impressum, name="impressum"),
    path("datenschutz/", views.datenschutz, name="datenschutz"),
    # Feedback (Beta)
    path("feedback/", views.feedback_list, name="feedback_list"),
    path("feedback/new/", views.feedback_create, name="feedback_create"),
    path("feedback/<int:feedback_id>/", views.feedback_detail, name="feedback_detail"),
    # PWA Files (must be at root)
    path("service-worker.js", views.service_worker, name="service_worker"),
    path("manifest.json", views.manifest, name="manifest"),
    path("favicon.ico", views.favicon, name="favicon"),
    # Dashboard
    path("", views.dashboard, name="dashboard"),
    path("training/select/", views.training_select_plan, name="training_select_plan"),
    path("plan/<int:plan_id>/", views.plan_details, name="plan_details"),
    path("plan/create/", views.create_plan, name="create_plan"),
    path("plan/<int:plan_id>/edit/", views.edit_plan, name="edit_plan"),
    path("plan/<int:plan_id>/delete/", views.delete_plan, name="delete_plan"),
    path("plan/<int:plan_id>/copy/", views.copy_plan, name="copy_plan"),
    path("plan/<int:plan_id>/duplicate/", views.duplicate_plan, name="duplicate_plan"),
    path("plan/<int:plan_id>/share/", views.share_plan, name="share_plan"),
    path("plan/<int:plan_id>/toggle-public/", views.toggle_plan_public, name="toggle_plan_public"),
    path("group/<str:gruppe_id>/duplicate/", views.duplicate_group, name="duplicate_group"),
    path("group/<str:gruppe_id>/share/", views.share_group, name="share_group"),
    path("group/<str:gruppe_id>/copy/", views.copy_group, name="copy_group"),
    path(
        "group/<str:gruppe_id>/toggle-public/",
        views.toggle_group_public,
        name="toggle_group_public",
    ),
    path("set-active-plan/", views.set_active_plan_group, name="set_active_plan_group"),
    path("plan-library/", views.plan_library, name="plan_library"),
    path(
        "plan-library/group/<str:gruppe_id>/", views.plan_library_group, name="plan_library_group"
    ),
    path("uebungen/", views.uebungen_auswahl, name="uebungen_auswahl"),
    path("muscle-map/", views.muscle_map, name="muscle_map"),
    path("uebung/<int:uebung_id>/", views.uebung_detail, name="uebung_detail"),
    path("exercise/<int:uebung_id>/detail/", views.exercise_detail, name="exercise_detail"),
    path("uebung/<int:uebung_id>/toggle-favorit/", views.toggle_favorit, name="toggle_favorit"),
    path("api/custom-uebung/create/", views.create_custom_uebung, name="create_custom_uebung"),
    path(
        "api/alternative-exercises/<int:uebung_id>/",
        views.get_alternative_exercises,
        name="get_alternative_exercises",
    ),
    path("training/start/", views.training_start, name="training_start_free"),
    path("training/start/<int:plan_id>/", views.training_start, name="training_start_plan"),
    path("training/<int:training_id>/", views.training_session, name="training_session"),
    path("training/<int:training_id>/add_set/", views.add_set, name="add_set"),
    path("set/<int:set_id>/update/", views.update_set, name="update_set"),
    path("set/<int:set_id>/delete/", views.delete_set, name="delete_set"),
    path("body-stats/add/", views.add_koerperwert, name="add_koerperwert"),
    path("body-stats/", views.body_stats, name="body_stats"),
    path("body-stats/<int:wert_id>/edit/", views.edit_koerperwert, name="edit_koerperwert"),
    path("body-stats/<int:wert_id>/delete/", views.delete_koerperwert, name="delete_koerperwert"),
    path("uebung/<int:uebung_id>/toggle-favorite/", views.toggle_favorite, name="toggle_favorite"),
    path("export/training-csv/", views.export_training_csv, name="export_training_csv"),
    path("export/hevy-csv/", views.export_hevy_csv, name="export_hevy_csv"),
    path("import/hevy-csv/", views.import_hevy_csv, name="import_hevy_csv"),
    path("history/", views.training_list, name="training_list"),
    path("stats/", views.training_stats, name="training_stats"),
    path("training/<int:training_id>/delete/", views.delete_training, name="delete_training"),
    path("training/<int:training_id>/finish/", views.finish_training, name="finish_training"),
    path(
        "api/training/<int:training_id>/toggle-deload/", views.toggle_deload, name="toggle_deload"
    ),
    path("api/last-set/<int:uebung_id>/", views.get_last_set, name="get_last_set"),
    path("stats/exercise/<int:uebung_id>/", views.exercise_stats, name="exercise_stats"),
    # Offline Sync
    path("api/sync-offline/", views.sync_offline_data, name="sync_offline_data"),
    # Progress Photos
    path("progress-photos/", views.progress_photos, name="progress_photos"),
    path("progress-photos/upload/", views.upload_progress_photo, name="upload_progress_photo"),
    path(
        "progress-photos/<int:photo_id>/delete/",
        views.delete_progress_photo,
        name="delete_progress_photo",
    ),
    # PDF Export
    path("export/training-pdf/", views.export_training_pdf, name="export_training_pdf"),
    path("plan/<int:plan_id>/pdf/", views.export_plan_pdf, name="export_plan_pdf"),
    path("group/<str:gruppe_id>/pdf/", views.export_plan_group_pdf, name="export_plan_group_pdf"),
    # AI/ML Recommendations
    path("recommendations/", views.workout_recommendations, name="workout_recommendations"),
    # Equipment Management
    path("equipment/", views.equipment_management, name="equipment_management"),
    # Help Pages
    path("help/metriken/", views.metriken_help, name="metriken_help"),
    # Wissenschaftliche Quellen (öffentlich)
    path("quellen/", views.sources_list, name="sources_list"),
    path("equipment/toggle/<int:equipment_id>/", views.toggle_equipment, name="toggle_equipment"),
    path(
        "api/exercise/<int:exercise_id>/alternatives/",
        views.suggest_alternative_exercises,
        name="suggest_alternatives",
    ),
    # Exercise API
    path("api/exercise/<int:exercise_id>/", views.exercise_api_detail, name="exercise_api_detail"),
    # Live Guidance API
    path("api/live-guidance/", views.live_guidance_api, name="live_guidance_api"),
    # AI Plan Generator API
    path("api/generate-plan/", views.generate_plan_api, name="generate_plan_api"),
    path(
        "api/generate-plan/stream/", views.generate_plan_stream_api, name="generate_plan_stream_api"
    ),
    # AI Plan Optimization API
    path("api/analyze-plan/", views.analyze_plan_api, name="analyze_plan_api"),
    path("api/optimize-plan/", views.optimize_plan_api, name="optimize_plan_api"),
    path("api/apply-optimizations/", views.apply_optimizations_api, name="apply_optimizations_api"),
    # Plan Templates
    path("api/plan-templates/", views.get_plan_templates, name="get_plan_templates"),
    path(
        "api/plan-templates/<str:template_key>/",
        views.get_template_detail,
        name="get_template_detail",
    ),
    path(
        "api/plan-templates/<str:template_key>/create/",
        views.create_plan_from_template,
        name="create_plan_from_template",
    ),
    # Plan Gruppierung & Management API
    path("api/ungroup-plans/", views.api_ungroup_plans, name="api_ungroup_plans"),
    path("api/group-plans/", views.api_group_plans, name="api_group_plans"),
    path("api/delete-plan/", views.api_delete_plan, name="api_delete_plan"),
    path("api/delete-group/", views.api_delete_group, name="api_delete_group"),
    path("api/rename-group/", views.api_rename_group, name="api_rename_group"),
    path("api/reorder-group/", views.api_reorder_group, name="api_reorder_group"),
    # Trainingspartner-Sharing API
    path("api/search-users/", views.api_search_users, name="api_search_users"),
    path("api/share-plan/", views.api_share_plan_with_user, name="api_share_plan_with_user"),
    path("api/unshare-plan/", views.api_unshare_plan_with_user, name="api_unshare_plan_with_user"),
    path("api/share-group/", views.api_share_group_with_user, name="api_share_group_with_user"),
    path(
        "api/unshare-group/", views.api_unshare_group_with_user, name="api_unshare_group_with_user"
    ),
    path("api/plan/<int:plan_id>/shares/", views.api_get_plan_shares, name="api_get_plan_shares"),
    path(
        "api/group/<str:gruppe_id>/shares/", views.api_get_group_shares, name="api_get_group_shares"
    ),
    # Exercise Management (Admin Only)
    path("uebungen/export/", views.export_uebungen, name="export_uebungen"),
    path("uebungen/import/", views.import_uebungen, name="import_uebungen"),
    # Plan Gruppierung API
    path("api/plans/ungroup/", views.api_ungroup_plans, name="api_ungroup_plans"),
    path("api/plans/group/", views.api_group_plans, name="api_group_plans"),
    # Cardio Tracking
    path("cardio/", views.cardio_list, name="cardio_list"),
    path("cardio/add/", views.cardio_add, name="cardio_add"),
    path("cardio/<int:cardio_id>/delete/", views.cardio_delete, name="cardio_delete"),
    # Push Notifications
    path("api/push/subscribe/", views.subscribe_push, name="subscribe_push"),
    path("api/push/unsubscribe/", views.unsubscribe_push, name="unsubscribe_push"),
    path("api/push/vapid-key/", views.get_vapid_public_key, name="get_vapid_public_key"),
    # ML Prediction (scikit-learn, 100% lokal, CPU-only)
    path("api/ml/train/", views.ml_train_model, name="ml_train_model"),
    path("api/ml/predict/<int:uebung_id>/", views.ml_predict_weight, name="ml_predict_weight"),
    path("api/ml/model-info/<int:uebung_id>/", views.ml_model_info, name="ml_model_info"),
    path("ml/dashboard/", views.ml_dashboard, name="ml_dashboard"),
]
