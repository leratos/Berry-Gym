"""Service für TrainingsPause-Schreibpfade (Konzept §32.1).

**Alle** Schreibpfade (Views, API, Skripte) MÜSSEN über `create_pause` /
`update_pause` laufen. Begründung der Härtung:

- MariaDB kennt keine Exclusion-Constraints (anders als Postgres) – der
  Overlap-Schutz ist DB-seitig nicht erzwingbar und muss auf App-Ebene sitzen.
- Django ruft `Model.clean()` NICHT automatisch in `save()` auf; Form-`clean()`
  allein schützt Nicht-Form-Schreibpfade nicht.
- `select_for_update()` auf die Overlap-Treffer reicht nicht: bei der ersten /
  keiner überlappenden Pause gibt es KEINE Zeile zu sperren – zwei gleichzeitige
  Requests bestünden beide den Check und fügten beide ein. Daher sperren wir vor
  dem Check eine stabile, immer vorhandene User-Zeile → serialisiert alle
  Pausen-Writes pro User (Codex-Review PR #200, ㉑).

`bulk_create`/`loaddata`/raw saves umgehen `save()` und damit den Lock – für
dieses Model bewusst vermeiden (durch `test_pausen_model.py` abgesichert).

Hinweis: Auf SQLite (Dev/Test) ist `select_for_update()` ein No-op; die echte
Serialisierung greift erst auf MariaDB (Prod). SQLite serialisiert Schreibzugriffe
ohnehin auf DB-Ebene.
"""

from django.contrib.auth.models import User
from django.db import transaction

from core.models import TrainingsPause

# Sentinel, um beim Update "Feld nicht ändern" von "Feld auf None setzen" zu trennen.
_UNSET = object()


def _lock_user_row(user_id: int) -> None:
    """Sperrt die User-Zeile, um alle Pausen-Writes dieses Users zu serialisieren."""
    User.objects.select_for_update().get(pk=user_id)


@transaction.atomic
def create_pause(*, user, start_datum, grund, end_datum=None, notiz=""):
    """Legt eine TrainingsPause overlap-sicher an.

    Raises:
        ValidationError: end < start oder Overlap mit bestehender Pause.
    """
    _lock_user_row(user.pk)
    pause = TrainingsPause(
        user=user,
        start_datum=start_datum,
        end_datum=end_datum,
        grund=grund,
        notiz=notiz,
    )
    pause.full_clean()  # clean() läuft jetzt unter dem User-Lock
    pause.save()
    return pause


@transaction.atomic
def update_pause(pause, *, start_datum=_UNSET, end_datum=_UNSET, grund=_UNSET, notiz=_UNSET):
    """Aktualisiert eine TrainingsPause overlap-sicher.

    Nur übergebene Felder werden geändert; `end_datum=None` setzt das Ende
    explizit auf "offen/laufend".

    Raises:
        ValidationError: end < start oder Overlap mit anderer Pause des Users.
    """
    _lock_user_row(pause.user_id)
    if start_datum is not _UNSET:
        pause.start_datum = start_datum
    if end_datum is not _UNSET:
        pause.end_datum = end_datum
    if grund is not _UNSET:
        pause.grund = grund
    if notiz is not _UNSET:
        pause.notiz = notiz
    pause.full_clean()
    pause.save()
    return pause
