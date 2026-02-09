"""
Views package for HomeGym application.
This module re-exports all views for backward compatibility with existing URLs.
"""

# Auth views
from .auth import (
    apply_beta,
    register,
    profile,
    feedback_list,
    feedback_create,
    feedback_detail,
)

# Training session views
from .training_session import (
    training_select_plan,
    plan_details,
    training_start,
    training_session,
    add_set,
    delete_set,
    update_set,
    finish_training,
    toggle_deload,
)

# Training stats views
from .training_stats import (
    dashboard,
    training_list,
    delete_training,
    training_stats,
    exercise_stats,
)

# Body tracking views
from .body_tracking import (
    add_koerperwert,
    body_stats,
    edit_koerperwert,
    delete_koerperwert,
    progress_photos,
    upload_progress_photo,
    delete_progress_photo,
)

# Plan management views
from .plan_management import (
    create_plan,
    edit_plan,
    delete_plan,
    copy_plan,
    duplicate_plan,
    share_plan,
    toggle_plan_public,
    duplicate_group,
    share_group,
    copy_group,
    toggle_group_public,
    plan_library,
    plan_library_group,
    set_active_plan_group,
)

# Exercise library views
from .exercise_library import (
    uebungen_auswahl,
    muscle_map,
    uebung_detail,
    exercise_detail,
    toggle_favorite,
    toggle_favorit,
    get_alternative_exercises,
    suggest_alternative_exercises,
    exercise_api_detail,
)

# Exercise management views
from .exercise_management import (
    create_custom_uebung,
    equipment_management,
    toggle_equipment,
    export_uebungen,
    import_uebungen,
)

# Export views
from .export import (
    export_training_csv,
    export_training_pdf,
    export_plan_pdf,
    export_plan_group_pdf,
)

# AI recommendations views
from .ai_recommendations import (
    workout_recommendations,
    generate_plan_api,
    analyze_plan_api,
    optimize_plan_api,
    apply_optimizations_api,
    live_guidance_api,
)

# Plan templates views
from .plan_templates import (
    get_plan_templates,
    get_template_detail,
    create_plan_from_template,
)

# Cardio views
from .cardio import (
    cardio_list,
    cardio_add,
    cardio_delete,
)

# Notifications views
from .notifications import (
    subscribe_push,
    unsubscribe_push,
    get_vapid_public_key,
)

# Machine learning views
from .machine_learning import (
    ml_train_model,
    ml_predict_weight,
    ml_model_info,
    ml_dashboard,
)

# Offline sync views
from .offline import (
    sync_offline_data,
)

# Config & static views
from .config import (
    service_worker,
    favicon,
    manifest,
    impressum,
    datenschutz,
    metriken_help,
    get_last_set,
)

# API plan sharing views
from .api_plan_sharing import (
    api_ungroup_plans,
    api_group_plans,
    api_delete_plan,
    api_delete_group,
    api_rename_group,
    api_reorder_group,
    api_search_users,
    api_share_plan_with_user,
    api_unshare_plan_with_user,
    api_share_group_with_user,
    api_unshare_group_with_user,
    api_get_plan_shares,
    api_get_group_shares,
)

__all__ = [
    # Auth
    'apply_beta', 'register', 'profile', 'feedback_list', 'feedback_create', 'feedback_detail',
    # Training sessions
    'training_select_plan', 'plan_details', 'training_start', 'training_session',
    'add_set', 'delete_set', 'update_set', 'finish_training', 'toggle_deload',
    # Training stats
    'dashboard', 'training_list', 'delete_training', 'training_stats', 'exercise_stats',
    # Body tracking
    'add_koerperwert', 'body_stats', 'edit_koerperwert', 'delete_koerperwert',
    'progress_photos', 'upload_progress_photo', 'delete_progress_photo',
    # Plan management
    'create_plan', 'edit_plan', 'delete_plan', 'copy_plan', 'duplicate_plan',
    'share_plan', 'toggle_plan_public', 'duplicate_group', 'share_group',
    'copy_group', 'toggle_group_public', 'plan_library', 'plan_library_group',
    'set_active_plan_group',
    # Exercise library
    'uebungen_auswahl', 'muscle_map', 'uebung_detail', 'exercise_detail',
    'toggle_favorite', 'toggle_favorit', 'get_alternative_exercises', 'suggest_alternative_exercises',
    'exercise_api_detail',
    # Exercise management
    'create_custom_uebung', 'equipment_management', 'toggle_equipment',
    'export_uebungen', 'import_uebungen',
    # Export
    'export_training_csv', 'export_training_pdf', 'export_plan_pdf', 'export_plan_group_pdf',
    # AI recommendations
    'workout_recommendations', 'generate_plan_api', 'analyze_plan_api',
    'optimize_plan_api', 'apply_optimizations_api', 'live_guidance_api',
    # Plan templates
    'get_plan_templates', 'get_template_detail', 'create_plan_from_template',
    # Cardio
    'cardio_list', 'cardio_add', 'cardio_delete',
    # Notifications
    'subscribe_push', 'unsubscribe_push', 'get_vapid_public_key',
    # Machine learning
    'ml_train_model', 'ml_predict_weight', 'ml_model_info', 'ml_dashboard',
    # Offline
    'sync_offline_data',
    # Config
    'service_worker', 'favicon', 'manifest', 'impressum', 'datenschutz',
    'metriken_help', 'get_last_set',
    # API plan sharing
    'api_ungroup_plans', 'api_group_plans', 'api_delete_plan', 'api_delete_group',
    'api_rename_group', 'api_reorder_group', 'api_search_users',
    'api_share_plan_with_user', 'api_unshare_plan_with_user',
    'api_share_group_with_user', 'api_unshare_group_with_user',
    'api_get_plan_shares', 'api_get_group_shares',
]
