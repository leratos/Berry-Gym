"""
Views package for HomeGym application.
This module re-exports all views for backward compatibility with existing URLs.
"""

# AI recommendations views
from .ai_recommendations import (
    analyze_plan_api,
    apply_optimizations_api,
    generate_plan_api,
    generate_plan_stream_api,
    live_guidance_api,
    optimize_plan_api,
    workout_recommendations,
)

# API plan sharing views
from .api_plan_sharing import (
    api_delete_group,
    api_delete_plan,
    api_get_group_shares,
    api_get_plan_shares,
    api_group_plans,
    api_rename_group,
    api_reorder_group,
    api_search_users,
    api_share_group_with_user,
    api_share_plan_with_user,
    api_ungroup_plans,
    api_unshare_group_with_user,
    api_unshare_plan_with_user,
)

# Auth views
from .auth import apply_beta, feedback_create, feedback_detail, feedback_list, profile, register

# Body tracking views
from .body_tracking import (
    add_koerperwert,
    body_stats,
    delete_koerperwert,
    delete_progress_photo,
    edit_koerperwert,
    progress_photos,
    upload_progress_photo,
)

# Cardio views
from .cardio import cardio_add, cardio_delete, cardio_list

# Config & static views
from .config import (
    datenschutz,
    favicon,
    get_last_set,
    impressum,
    manifest,
    metriken_help,
    service_worker,
)

# Exercise library views
from .exercise_library import (
    exercise_api_detail,
    exercise_detail,
    get_alternative_exercises,
    muscle_map,
    suggest_alternative_exercises,
    toggle_favorit,
    toggle_favorite,
    uebung_detail,
    uebungen_auswahl,
)

# Exercise management views
from .exercise_management import (
    create_custom_uebung,
    equipment_management,
    export_uebungen,
    import_uebungen,
    toggle_equipment,
)

# Export views
from .export import (
    export_hevy_csv,
    export_plan_group_pdf,
    export_plan_pdf,
    export_training_csv,
    export_training_pdf,
    import_hevy_csv,
)

# Machine learning views
from .machine_learning import ml_dashboard, ml_model_info, ml_predict_weight, ml_train_model

# Notifications views
from .notifications import get_vapid_public_key, subscribe_push, unsubscribe_push

# Offline sync views
from .offline import sync_offline_data

# Plan management views
from .plan_management import (
    copy_group,
    copy_plan,
    create_plan,
    delete_plan,
    duplicate_group,
    duplicate_plan,
    edit_plan,
    plan_library,
    plan_library_group,
    set_active_plan_group,
    share_group,
    share_plan,
    toggle_group_public,
    toggle_plan_public,
)

# Plan templates views
from .plan_templates import create_plan_from_template, get_plan_templates, get_template_detail

# Scientific sources
from .sources import sources_list

# Training session views
from .training_session import (
    add_set,
    delete_set,
    finish_training,
    plan_details,
    toggle_deload,
    training_select_plan,
    training_session,
    training_start,
    update_set,
)

# Training stats views
from .training_stats import (
    dashboard,
    delete_training,
    exercise_stats,
    training_list,
    training_stats,
)

__all__ = [
    # Auth
    "apply_beta",
    "register",
    "profile",
    "feedback_list",
    "feedback_create",
    "feedback_detail",
    # Training sessions
    "training_select_plan",
    "plan_details",
    "training_start",
    "training_session",
    "add_set",
    "delete_set",
    "update_set",
    "finish_training",
    "toggle_deload",
    # Training stats
    "dashboard",
    "training_list",
    "delete_training",
    "training_stats",
    "exercise_stats",
    # Body tracking
    "add_koerperwert",
    "body_stats",
    "edit_koerperwert",
    "delete_koerperwert",
    "progress_photos",
    "upload_progress_photo",
    "delete_progress_photo",
    # Plan management
    "create_plan",
    "edit_plan",
    "delete_plan",
    "copy_plan",
    "duplicate_plan",
    "share_plan",
    "toggle_plan_public",
    "duplicate_group",
    "share_group",
    "copy_group",
    "toggle_group_public",
    "plan_library",
    "plan_library_group",
    "set_active_plan_group",
    # Exercise library
    "uebungen_auswahl",
    "muscle_map",
    "uebung_detail",
    "exercise_detail",
    "toggle_favorite",
    "toggle_favorit",
    "get_alternative_exercises",
    "suggest_alternative_exercises",
    "exercise_api_detail",
    # Exercise management
    "create_custom_uebung",
    "equipment_management",
    "toggle_equipment",
    "export_uebungen",
    "import_uebungen",
    # Export
    "export_training_csv",
    "export_training_pdf",
    "export_plan_pdf",
    "export_plan_group_pdf",
    "export_hevy_csv",
    "import_hevy_csv",
    # AI recommendations
    "workout_recommendations",
    "generate_plan_api",
    "generate_plan_stream_api",
    "analyze_plan_api",
    "optimize_plan_api",
    "apply_optimizations_api",
    "live_guidance_api",
    # Plan templates
    "get_plan_templates",
    "get_template_detail",
    "create_plan_from_template",
    # Cardio
    "cardio_list",
    "cardio_add",
    "cardio_delete",
    # Notifications
    "subscribe_push",
    "unsubscribe_push",
    "get_vapid_public_key",
    # Machine learning
    "ml_train_model",
    "ml_predict_weight",
    "ml_model_info",
    "ml_dashboard",
    # Offline
    "sync_offline_data",
    # Config
    "service_worker",
    "favicon",
    "manifest",
    "impressum",
    "datenschutz",
    "metriken_help",
    "get_last_set",
    # API plan sharing
    "api_ungroup_plans",
    "api_group_plans",
    "api_delete_plan",
    "api_delete_group",
    "api_rename_group",
    "api_reorder_group",
    "api_search_users",
    "api_share_plan_with_user",
    "api_unshare_plan_with_user",
    "api_share_group_with_user",
    "api_unshare_group_with_user",
    "api_get_plan_shares",
    "api_get_group_shares",
    "sources_list",
]
