# Copilot Instructions for Berry-Gym

## Big picture architecture
- This is a Django monolith with three main Python packages: `core/` (web app + domain logic), `ai_coach/` (LLM-driven coaching), `ml_coach/` (local scikit-learn predictions).
- URL entrypoint is `config/urls.py` (i18n-aware routing with `i18n_patterns` and EN prefix `/en/...`). Feature routes live in `core/urls.py`.
- Views are split by domain in `core/views/*.py` and re-exported through `core/views/__init__.py` for backward-compatible imports in `core/urls.py`.
- Models are split by domain in `core/models/*.py` and re-exported through `core/models/__init__.py`. Keep imports as `from core.models import ...` unless refactoring internals.

## AI + data flow conventions
- AI endpoints are in `core/views/ai_recommendations.py`; they call service modules in `ai_coach/` (`plan_generator.py`, `plan_adapter.py`, `live_guidance.py`).
- Rate limiting is app-specific: `_check_ai_rate_limit(...)` uses `UserProfile.check_and_increment_ai_limit(...)` instead of only IP-based middleware.
- Plan generation has two flows:
  - standard JSON API: `generate_plan_api`
  - SSE preview stream: `generate_plan_stream_api` (always preview) followed by `saveCachedPlan` back to `generate_plan_api`.
- Cost/audit tracking model exists in `core/models/ki_log.py` (`KIApiLog`); preserve this path when extending AI endpoints.

## Security and ownership patterns
- For user-owned resources, follow existing access pattern: `get_object_or_404(Model, id=..., user=request.user)`.
- Most sensitive views are `@login_required`; keep this default for new user-data endpoints.
- Production security and auth hardening live in `config/settings.py` (`axes`, secure cookies/headers, `RATELIMIT_BYPASS` behavior).

## Caching, signals, and side effects
- Dashboard and computed stats rely on cache invalidation via signals in `core/signals.py` (`invalidate_dashboard_cache` on `Trainingseinheit` save).
- `core/apps.py` imports signals in `ready()`. If you add signals, wire them there (or keep in existing module structure).

## Developer workflows (use these first)
- Setup: `pip install -r requirements.txt && python manage.py migrate`
- Seed core data: `python manage.py loaddata core/fixtures/initial_exercises.json`
- Run app: `python manage.py runserver`
- Tests (project standard): `pytest` (configured in `pyproject.toml` with `core/tests` and `ai_coach/tests`)
- Fast targeted test example: `pytest core/tests/test_training_views.py -v`
- Lint/format parity with CI: `black --check core/ config/ ai_coach/`, `isort --check-only core/ config/ ai_coach/`, `flake8 core/ config/ ai_coach/`

## Execution protocol (Do / Don't)
- **Do:** Read `docs/journal.txt` first and treat it as the single source of truth for current phase/status.
- **Do:** Create a draft entry before starting implementation: `## In Arbeit: [Phase]`.
- **Do:** After reading `journal.txt`, share a short execution plan and wait for explicit user confirmation.
- **Do:** Before any file edits, list the files you plan to change.
- **Do:** After finishing, append `## Abgeschlossen: [Phase]` to `journal.txt`.
- **Don't:** Start coding or edit files before explicit confirmation.
- **Don't:** Make assumptions when scope/context is unclear; ask targeted questions.

## Quality gates
- Proactively flag missing tests, potential security issues, and technical debt relevant to the task.
- If test coverage is missing near changed logic, call it out and propose a focused test location.
- If security-sensitive paths are touched (auth, ownership, upload, AI endpoints), explicitly validate risks.

## Context rules
- `docs/journal.txt` is mandatory context before execution.
- If `docs/journal.txt` is missing or empty: stop and ask the user; do not infer current phase/state.

## Documentation workflow
- Before implementation: add `## In Arbeit: [Phase]` with intent and planned scope.
- After implementation: add `## Abgeschlossen: [Phase]` with what changed and open follow-ups.
- Keep entries concise so interrupted sessions can resume without context loss.

## Planning before execution
- Sequence is strict: read `journal.txt` → propose short plan → wait for explicit confirmation → implement.
- For unclear requirements, ask first instead of guessing.
- For file changes, announce target files before touching them.

## Optional emergency exception (critical hotfixes)
- Only for critical production incidents (e.g., active security vulnerability, data loss risk, outage).
- Still read `docs/journal.txt` first; if missing/empty, ask immediately and keep scope minimal.
- If explicit confirmation cannot be obtained in time, limit changes strictly to the smallest hotfix scope.
- Document immediately in `journal.txt`: `## In Arbeit: Emergency Hotfix` with reason, scope, and touched files.
- After completion, add `## Abgeschlossen: Emergency Hotfix` with validation performed, risks, and follow-up tasks.
- Return to normal flow (plan + explicit confirmation) for all non-critical follow-up work.

## Test-suite project specifics
- `core/tests/conftest.py` enables DB access for all tests and clears cache automatically between tests.
- Prefer Factory Boy from `core/tests/factories.py` over manual object creation.
- Many tests depend on German domain naming (`Uebung`, `Trainingseinheit`, `KoerperWerte`); keep naming consistent in new code/tests.

## Repo-specific conventions
- Domain language is mixed DE/EN by design; do not rename core model fields just for English consistency.
- For UI text, use Django i18n tags (`{% trans %}`, `{% blocktrans %}`), see templates like `core/templates/core/dashboard.html`.
- Keep changes modular: add/modify domain logic in the relevant `core/views/<domain>.py` and `core/models/<domain>.py`, then re-export in `__init__.py` if needed.
- Some docs are historical; when README/docs and code disagree, follow current behavior in `config/settings.py`, `core/urls.py`, and active views/models.
