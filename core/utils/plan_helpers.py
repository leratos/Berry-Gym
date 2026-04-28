"""Helper utilities for active training plan detection (Phase 22).

Provides functions to determine which exercises belong to the user's
currently active training plan, so statistics like plateau analysis,
strength standards, and top-exercise lists can filter out exercises
from old/inactive plans (avoiding "phantom plateaus").

Three public helpers:

- ``get_active_plan_exercise_ids(user)``: Set of Uebung IDs belonging to
  the active plan group, or ``None`` if not determinable. Callers should
  treat ``None`` as "fall back to all-time behavior".
- ``get_active_plan_start_date(user)``: Datetime of the first session in
  the current consecutive run of sessions on the active plan group.
- ``is_active_plan_too_new(user)``: ``True`` if the active plan block has
  too few sessions or is too young to be useful as a comparison window.

Design notes / known caveats:

- "Active plan" = the plan attached to the user's most recent
  Trainingseinheit. If that session is older than ``MAX_PLAN_AGE_DAYS``
  (60 days), no active plan is reported.
- Plan groups (``Plan.gruppe_id``) are the unit for "same plan", which
  matters for splits (Push/Pull/Legs share one ``gruppe_id``). Plans
  without a ``gruppe_id`` are treated as their own single-plan group.
- "Walking backwards" stops at the first session that doesn't belong to
  the active plan group OR has no plan at all.
"""

from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.utils import timezone

from core.models import PlanUebung, Trainingseinheit

# Cutoff: if the most recent plan-attached session is older than this,
# we treat the user as "not currently on any plan" and return None / False.
MAX_PLAN_AGE_DAYS = 60


def _get_active_plan(user: User):
    """Return the Plan instance from the user's most recent
    Trainingseinheit that has a plan attached.

    Returns None if no such session exists or if the most recent
    plan-attached session is older than MAX_PLAN_AGE_DAYS.
    """
    last_session_with_plan = (
        Trainingseinheit.objects.filter(user=user, plan__isnull=False)
        .select_related("plan")
        .order_by("-datum")
        .first()
    )
    if not last_session_with_plan:
        return None

    age = timezone.now() - last_session_with_plan.datum
    if age > timedelta(days=MAX_PLAN_AGE_DAYS):
        return None

    return last_session_with_plan.plan


def _active_plan_key(plan) -> tuple[str, int]:
    """Return a key identifying the plan group for equality comparison.

    Plans with a ``gruppe_id`` are grouped by it (PPL splits etc.);
    plans without are identified by their own primary key.
    """
    if plan.gruppe_id is not None:
        return ("gruppe", plan.gruppe_id)
    return ("plan", plan.id)


def get_active_plan_exercise_ids(user: User) -> set[int] | None:
    """Return the set of Uebung IDs that belong to the user's active plan.

    The active plan is the plan attached to the user's most recent
    Trainingseinheit (if recent enough). All PlanUebung entries of that
    plan's group (via ``Plan.gruppe_id``) are aggregated. Plans without a
    ``gruppe_id`` are treated as a single-plan group.

    Returns ``None`` if no active plan can be determined. Callers should
    fall back to the previous "all exercises" behavior in that case.

    Returns an empty set only if the active plan exists but contains no
    ``PlanUebung`` entries (pathological case – likely a data issue).
    """
    active_plan = _get_active_plan(user)
    if active_plan is None:
        return None

    if active_plan.gruppe_id is not None:
        plan_filter = {
            "plan__gruppe_id": active_plan.gruppe_id,
            "plan__user": user,
        }
    else:
        plan_filter = {"plan": active_plan}

    ids = set(PlanUebung.objects.filter(**plan_filter).values_list("uebung_id", flat=True))
    return ids if ids else None


def get_active_plan_start_date(user: User) -> datetime | None:
    """Return the datetime of the first Trainingseinheit in the current
    consecutive run of sessions on the active plan group.

    Walks backwards from the most recent session: as long as sessions
    belong to the same plan group (via ``Plan.gruppe_id``, or the same
    plan if no group), they're part of the active block. The first
    session of that block is returned. Sessions without a plan or with a
    different plan group end the walk.

    Returns ``None`` if no active plan is determined.
    """
    active_plan = _get_active_plan(user)
    if active_plan is None:
        return None

    active_key = _active_plan_key(active_plan)

    sessions = Trainingseinheit.objects.filter(user=user).select_related("plan").order_by("-datum")

    plan_start = None
    for session in sessions:
        if session.plan is None:
            break
        if _active_plan_key(session.plan) != active_key:
            break
        plan_start = session.datum

    return plan_start


def is_active_plan_too_new(
    user: User,
    min_sessions: int = 3,
    min_age_days: int = 10,
) -> bool:
    """Return True if the active plan block has too few sessions or is too
    young to be a meaningful comparison window for strength progression.

    A plan is considered "too new" if either:

    - the active plan block was started less than ``min_age_days`` days
      ago, OR
    - the user has completed fewer than ``min_sessions`` sessions on the
      active plan group.

    Returns ``False`` if no active plan exists – callers detect that
    case via ``get_active_plan_exercise_ids() is None`` instead.
    """
    plan_start = get_active_plan_start_date(user)
    if plan_start is None:
        return False

    age = timezone.now() - plan_start
    if age < timedelta(days=min_age_days):
        return True

    active_plan = _get_active_plan(user)
    if active_plan is None:
        return False

    if active_plan.gruppe_id is not None:
        session_count = Trainingseinheit.objects.filter(
            user=user,
            plan__gruppe_id=active_plan.gruppe_id,
            datum__gte=plan_start,
        ).count()
    else:
        session_count = Trainingseinheit.objects.filter(
            user=user,
            plan=active_plan,
            datum__gte=plan_start,
        ).count()

    return session_count < min_sessions
