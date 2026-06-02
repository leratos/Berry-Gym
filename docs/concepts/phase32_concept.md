# Phase 32 – Trainingspausen / Ausfallzeiten (Stufe 1+2)

> Status: Konzept (claude.app, 2026-06-02; rev. nach Codex-Review PR #200). Journal-Ref: berry-gym #678.
> Implementierung: Claude Code / VSCode. **Dieses Dokument enthält Hypothesen,
> die am Code zu verifizieren sind** – als solche markiert. Nicht blind umsetzen.

## 1. Ziel

Trainingsfreie Zeiträume (Krankheit, Verletzung, Urlaub, Sonstiges) explizit
dokumentierbar machen und die Analyse-Schichten so anpassen, dass eine
dokumentierte Pause als *begründete Lücke* behandelt wird – statt als stilles
Datenloch, das jede Schicht selbst (falsch) interpretiert.

Konkreter Auslöser: reale 2-wöchige Krankheitspause. Heute erzeugt eine
sessionlose Woche **gar keinen** Wocheneintrag (sie fehlt im Chart, vgl. #481);
der Wiedereinstieg löst voraussichtlich eine falsche „starker Volumen-Anstieg"-
Warnung im Fatigue-Index aus (strukturgleich zum Deload→Re-Aufbau-Bug 24.1b /#477,
nur ohne unterdrückendes Flag).

## 2. Scope

**In Scope (Stufe 1+2):**
- 32.1 Datenmodell `TrainingsPause` + Migration + Validierung + Admin.
- 32.2 CRUD-UI (rückwirkend eintragbar, Datums-Range, i18n).
- 32.3 Klassifikations-Awareness (`ist_ausfall` / `teilweise_ausfall`, leere
  Wochen als gelabelte Lücke, `select_comparable_weeks` ausschließen).
- 32.4 Volumen-Vergleiche pause-aware (Comeback-Spike): **alle** Pfade –
  Fatigue (Dashboard+PDF), Form-Index, Stats-Warnungen.
- 32.5 Streak: dokumentierte Pause pausiert den Streak.

**Explizit NICHT in Scope (→ spätere eigene Phase, „Stufe 3"):**
- Deload-Slot-Verschiebung / 3+1-Zyklus-Zähler-Interaktion.
- Plan-Generator Return-to-Training-Ramp / detraining-bewusste Lastvorschläge.
- *Begründung:* 2 Wochen krank ≈ erzwungener Deload-plus (eher Detraining als
  Ermüdungsabbau); danach einen geplanten Deload zu erzwingen wäre falsch. Wenn
  das später in den Generator fließt, **als harte Validator-Constraint, nicht
  als Soft-Prompt-Hint** (Phase-11- / 30.1-Lektion: Validatoren erzwingen
  Regeln zuverlässig, Prompt-Hinweise nicht).

## 3. Leitprinzipien

- **Datenintegrität vor Präsentation:** echtes Volumen einer teilweise von
  Krankheit betroffenen Woche wird nie weggeworfen, nur als Trend-Anker
  ausgeschlossen. Keine falschen Daten zur Glättung der Statistik.
- **Single Source of Truth:** `ist_ausfall` wird **nicht persistiert**, sondern
  zur Analysezeit aus den `TrainingsPause`-Ranges berechnet (SoT = das Model),
  analog zur nicht-persistierten comparable-weeks-Berechnung.
- **Bestehende Pfade wiederverwenden, keine Parallelstruktur:** die
  laufende-/Teil-Splitwochen-Ausschlusslogik (#481, `select_comparable_weeks`)
  ist der Andockpunkt, nicht ein neuer paralleler Klassifikator.
- **Ehrliches Dokumentieren darf nicht bestraft werden** (Streak-Pause).

## 4. Sub-Phasen

### 32.1 – Datenmodell `TrainingsPause`

*Hypothese (Submodul am Code bestätigen):* neue Datei oder bestehendes
Submodul unter `core/models/`. **`core/models/__init__.py` ist das einzige
Interface nach außen und re-exportiert alle Models** – `TrainingsPause` dort
ergänzen, sonst schlägt `from core.models import TrainingsPause`
(Admin/Views/Tests) fehl und Django entdeckt das Model evtl. nicht zuverlässig
(Codex-Review PR #200, ⑫).

Felder:
- `user` – FK auf Auth-User, `on_delete=CASCADE`, `db_index=True`.
- `start_datum` – `DateField`.
- `end_datum` – `DateField(null=True, blank=True)` → **offen = laufende Pause**.
- `grund` – `CharField(choices=Grund.choices)` (TextChoices, s. §7 i18n).
- `notiz` – `TextField(blank=True)`.
- `erstellt_am` / `geaendert_am` – Timestamps.

Constraints / Validierung:
- `CheckConstraint`: `end_datum IS NULL OR end_datum >= start_datum`.
- **Overlap-Schutz auf App-Ebene** in `Model.clean()`: keine zwei sich
  überlappenden Pausen pro User. *MariaDB hat keine Exclusion-Constraints
  (anders als Postgres) – DB-seitig nicht erzwingbar.* (Annahme verifizieren,
  ist aber Stand der Technik für MariaDB.)
- **Validierung außerhalb von Forms erzwingen (Codex-Review PR #200, ③ + ⑩):**
  Django ruft `clean()` **nicht** automatisch in `save()` auf – Form-`clean()`
  allein schützt Nicht-Form-Schreibpfade nicht. **Wichtige Abstufung:** ein
  `save()`→`self.full_clean()` deckt nur `Manager.create()` / Instanz-`save()`
  ab, **nicht** `bulk_create` (umgeht `save()` komplett, keine Signale) und
  **nicht** Fixtures/`loaddata`/raw saves. `save()`+`full_clean()` ist also
  **keine** vollständige Absicherung. Sicher ist nur: **alle Schreibpfade über
  eine Service-/Manager-Methode** mit transaktionalem `select_for_update` +
  Overlap-Check; `bulk_create`/raw-Loads für dieses Model **explizit vermeiden**
  und das in einem Test absichern. Der Overlap-Test läuft bewusst über
  `clean`/Service, nicht über die Factory (die `clean()` umgeht).
- Multi-User-Isolation: alle Queries `filter(user=request.user)`.

Migration: reine Schema-Migration in `core/migrations/`, keine Datenmigration.

`tests` (pytest + factory_boy): Factory; `end >= start`; offene Pause
(`end_datum=None`) zulässig; Overlap wird abgelehnt; nicht-überlappende
Mehrfachpausen zulässig.

### 32.2 – CRUD-UI (rückwirkend, i18n)

- Views unter `core/views/` (z. B. neues Modul `pausen.py` *oder* in ein
  passendes bestehendes Views-Modul einsortieren – am Code entscheiden, keine
  neue App). `@login_required`, strikt user-scoped (kein Zugriff auf fremde
  Pausen – auch nicht über manipulierte IDs → `get_object_or_404(..., user=...)`).
- Template: Liste + Formular mit **Datums-Range-Picker** (Start + optionales
  Ende), `grund`-Dropdown (übersetzte Labels), `notiz`. Rückwirkende Eingabe ist
  der Normalfall.
- **Overlap mit Wochen, die bereits Sessions haben → Warnung anzeigen, NICHT
  hart blocken** (legitimer Teilwochen-Fall, §32.3 Q3).
- Einstiegspunkt verlinken (Dashboard / Stats-Seite).
- i18n: alle UI-Strings via `{% trans %}` / `gettext`, DE/EN `.po` aktualisieren.
- **Dashboard-Cache invalidieren (Codex-Review PR #200, ⑬):** der Dashboard-Block
  (Streak/Volumen/Fatigue) wird unter `dashboard_computed_<user>` gecacht
  (`core/views/training_stats.py`, TTL); `core/signals.py` invalidiert bisher
  **nur** bei `Trainingseinheit`-`post_save`. Anlegen/Ändern/**Löschen** einer
  `TrainingsPause` muss denselben Key löschen → Signal für `post_save` **und**
  `post_delete` auf `TrainingsPause` ergänzen, sonst zeigt das jetzt
  pause-bewusste Dashboard bis zum TTL den alten Streak/Fatigue-Stand.

`tests`: Auth erzwungen; User-Isolation; rückwirkendes Anlegen; Overlap-Warnung
erscheint, blockt aber nicht; offene Pause anlegbar; Pause-Save **und** -Delete
invalidieren `dashboard_computed_<user>`.

### 32.3 – Klassifikations-Awareness (Kern)

*Andockpunkt:* `core/utils/week_classification.py` (seit 24.1c SoT der
Wochen-Flags).

1. Helper, der für eine ISO-Woche + die Pausen-Ranges eines Users **zwei
   orthogonale Achsen** bestimmt – (a) Label/Abdeckung, (b) Vergleichs-Grenze –
   nicht „irgendein Overlap" (Codex-Review PR #200, ⑤/⑥/⑭/⑯):
   - **`ist_ausfall=True`** ⇔ Pause deckt die *komplette* ISO-Woche (Mo–So) ab
     **und** 0 Sessions. Echter Vollausfall, primär fürs Lücken-Label; impliziert
     `ist_pausen_grenze` (→ Streak-Bridge, §32.5).
   - **`teilweise_ausfall=True`** ⇔ Woche überlappt eine Pause, ist aber **nicht**
     `ist_ausfall`. Deckt damit *alle* übrigen pause-berührten Wochen ab:
     partieller Overlap (mit/ohne Sessions) **und** Voll-Overlap *mit* einer
     trotzdem geloggten Session (Codex-Review PR #200, ⑯ – sonst fiele dieser
     Fall durch beide Zweige und bliebe normaler Trend-Anker). Volumen bleibt
     erhalten, Woche ist aber **kein** Trend-Anker. Ein 1-Tages-Urlaub in einer
     session-losen Woche wird so nicht zum Vollausfall (⑤): er verbirgt die Woche
     nicht und schützt den Streak nicht.
   - **`ist_pausen_grenze=True`** ⇔ Woche überlappt ein dokumentiertes
     Pausen-Intervall von **≥ Mindestdauer** – **unabhängig von Abdeckung *und*
     Session-Zahl** (Codex-Review PR #200, ⑭: das Grenz-Flag darf **nicht** auf
     session-lose Wochen gegated sein – sonst erzeugt z. B. eine Do–Di-Pause mit
     Training vor *und* nach der Pause *keine* Grenze, und der Vergleich überquert
     sie weiter). Mindestdauer **inklusiv** gezählt:
     `dauer_tage = (end − start).days + 1`, Default `PAUSE_BOUNDARY_MIN_DAYS = 5`
     (bewusst ≤ 6, damit das Di–So-Beispiel = 6 inkl. Tage sie erreicht, ⑪;
     trennt echte Trainingslücke vom verlängerten Wochenende). Das ist die
     **Trend-Vergleichs-Grenze** (§32.4) und – für session-lose Wochen – die
     **Streak-Bridge** (§32.5). Beispiel: Krankheit Di–So (6 ≥ 5) + Comeback am
     Montag setzt `ist_pausen_grenze` und bricht den Spike-Vergleich.
2. **Strukturelle Änderung (riskantester Teil):** Die Wochenliste muss aus
   `union(Wochen-mit-Sessions, Wochen-mit-Pausen-Overlap)` emittiert werden,
   damit eine komplett leere Krankheitswoche **als gelabelte Lücke erscheint**
   statt im Chart zu fehlen. *Hypothese: der Join-/Emissions-Punkt liegt in
   `core/export/stats_collector.py` und/oder dem Live-Helfer in
   `core/views/training_stats.py` – vor der Implementierung lokalisieren.*
   - **Jede Pause auf ≤ heute clampen (Codex-Review PR #200, ⑦ + ⑰):**
     Analyse-Range = `[start, min(end_datum or heute, heute)]`, begrenzt auf die
     **aktuelle ISO-Woche**. Das gilt **nicht nur** für offene Pausen
     (`end_datum=None`), sondern auch für **geschlossene Zukunfts-Ranges** – sonst
     emittiert die union zukünftige Null-Volumen-Wochen ins Chart und pausiert die
     Trend-Diagnose verfrüht (⑰). Zukunftsdatierte Pausen entweder verbieten oder
     rein als „geplant" speichern, ohne Analyse-Wochen zu emittieren. Keine
     `None`-Datumsvergleiche. Eine laufende Pause erscheint als gelabelte
     **aktuelle** Lücke.
3. `select_comparable_weeks` liegt in `core/utils/week_classification.py`
   (**nicht** in `stats_collector.py` – seit 24.1c ist `week_classification`
   die SoT; `stats_collector` konsumiert nur `build_weekly_volume_overview`;
   Codex-Review PR #200, ①). Dort wird **jede `ist_pausen_grenze`-Woche als
   Epoch-Grenze** behandelt (`break`, analog `ist_plan_wechsel`) – gebunden ans
   Pausen-Intervall, **nicht** nur an `ist_ausfall` (⑥). Die Funktion läuft von
   der neuesten zur ältesten Woche und bricht bei `ist_plan_wechsel` bereits ab;
   eine Pausen-Grenze analog zu behandeln stellt sicher, dass **kein** Vergleich
   über die Pause hinweg passiert, auch wenn die Pause keine ISO-Woche voll
   abdeckt (Begründung in §32.4). Kurze `teilweise_ausfall`-Wochen *ohne*
   Grenz-Flag werden weiterhin nur per `continue` übersprungen (Volumen erhalten,
   aber kein Anker).

`tests`: `ist_ausfall` ⇔ Vollabdeckung **+ 0 Sessions**; Voll-Overlap **mit**
Session → `teilweise_ausfall` (⑯), nicht Anker; partielle Pause mit/ohne Session
→ `teilweise_ausfall`; 1-Tages-Pause → **kein** `ist_ausfall`; Pause ≥ Mindestdauer
setzt `ist_pausen_grenze` auch wenn **beide Teilwochen Sessions** haben (Do–Di, ⑭)
und bei Di–So ohne volle Wochenabdeckung (⑥); geschlossene **Zukunfts**-Pause
emittiert **keine** Zukunfts-Wochen (⑰); offene Pause = aktuelle Lücke; leere
Krankheitswoche wird emittiert; `select_comparable_weeks` bricht an
`ist_pausen_grenze` (`break`) und überspringt kurze `teilweise_ausfall`
(`continue`) – keine Vor-Pause-Woche landet hinter der Pause in der Vergleichsliste.

### 32.4 – Volumen-Vergleiche pause-aware (Fatigue-Spike, Form-Index, Warnungen)

`calculate_fatigue_index` (in `core/utils/advanced_stats.py`) routet die
Volumen-Spike-Komponente über `select_comparable_weeks` (Lazy-Import, seit
24.1b) und vergleicht dort `comparable_weeks[-1]` mit `comparable_weeks[-2]`.

**Korrektur (Codex-Review PR #200, ④):** Das bloße *Ausschließen* der
`ist_ausfall`-Wochen als Anker genügt **nicht**. Werden die Ausfallwochen nur
übersprungen (`continue`), rückt die Comeback-Woche direkt neben die letzte
Vor-Pause-Woche – der Vergleich überquert weiterhin die Pause und der Spike
entsteht (genau das Fehlverhalten aus Abnahmekriterium 3). Deshalb sitzt der Fix
in §32.3: die Pausen-Grenze (`ist_pausen_grenze`) wird in
`select_comparable_weeks` als **Epoch-Grenze** behandelt (`break`). Folge: nach
der Pause sind nur Post-Pause-Wochen vergleichbar; die erste Comeback-Woche
allein ergibt `len < 2` → „Trend pausiert", bis eine zweite Post-Pause-Woche
existiert. Kein Vergleich überquert die Pause.

**Nicht nur ein Pfad – VIER Volumen-Vergleiche pause-aware machen (Codex-Review
PR #200, ⑧ + ⑮ + ⑱):** `select_comparable_weeks` ist **nicht** der einzige
Chokepoint. Im Code vergleichen mindestens **vier** Stellen aufeinanderfolgende/
benachbarte Wochen-Volumina, von denen bisher nur **eine** pause-aware ist:

| # | Pfad | Funktion | nutzt `select_comparable_weeks`? |
|---|------|----------|-------------------------------|
| 1 | Export/PDF Fatigue-Spike | `advanced_stats.calculate_fatigue_index` | ✅ ja |
| 2 | Dashboard Fatigue-Spike | `_calculate_fatigue_index` → `_get_volume_spike_fatigue` ← `_calculate_weekly_volumes` (rohe 4 Wo.) | ❌ (⑧) |
| 3 | Dashboard Form-Index Volumen-Trend | `_calculate_form_index` → `_get_volume_trend_score` (letzte Nicht-Null-Wochen) | ❌ (⑮) |
| 4 | Stats-Seite Volumen-Warnungen | `_detect_volume_warnings` (benachbarte Nicht-Null-Wochen) | ❌ (⑱) |

Pfade 2–4 würden nach einer Pause weiterhin die Comeback-Woche direkt gegen die
Vor-Pause-Woche vergleichen (Form-Index belohnt/bestraft „Volumen-Trend",
Stats-Seite zeigt „Anstieg"-Warnung), selbst wenn der Fatigue-Spike (1) gefixt
ist. **Konsequenz gemäß Leitprinzip „keine Parallelstruktur":** *einen*
gemeinsamen pause-aware Comparable-Weeks-Helfer schaffen (bzw.
`select_comparable_weeks` + die Flags als geteilte Quelle), den **alle vier**
Pfade konsumieren – `_calculate_weekly_volumes`/`_get_volume_trend_score`/
`_detect_volume_warnings` tragen dafür die neuen Flags. Plus **Audit/Guard-Test**,
der alle benachbarten Wochen-Volumen-Vergleiche aufzählt, damit kein fünfter
Pfad still vorbeiläuft.

`tests`: Wiedereinstiegs-Woche nach Pause erzeugt **keine** falsche
Volumen-Anstiegs-Warnung/-Bewertung in **allen vier Pfaden** (Fatigue Dashboard +
PDF, Form-Index, Stats-Warnungen); auch bei einer Di–So-Pause ohne volle
Wochenabdeckung (Reproduktion des erwarteten Fehlverhaltens + Fix).

### 32.5 – Streak: Pause pausiert

Dokumentierte Pause → Streak läuft über die Lücke weiter (kein Reset, keine
Bestrafung). **Un-dokumentierter** Gap verhält sich unverändert. Eine
session-lose Woche **bridged** den Streak (kein Bruch), wenn sie
`ist_pausen_grenze` ist – also von einer dokumentierten Pause **≥ Mindestdauer**
berührt wird (dieselbe Schwelle wie die Trend-Grenze, §32.3). **Bewusst *nicht*
nur an `ist_ausfall` (volle Mo–So-Abdeckung) gekoppelt** (Codex-Review PR #200,
⑨): sonst bräche eine reale, aber nicht auf Wochengrenzen liegende Lücke
(Krankheit Di–So + Comeback Montag) den Streak und verletzte Abnahmekriterium 4.
Eine 1-Tages-Pause (< Mindestdauer) bridged **nicht** – ⑤ bleibt gewahrt.

**Zwei Streak-Implementierungen – beide müssen pausieren (Codex-Review PR #200,
②):** Die Streak-Logik existiert doppelt; wird nur eine gepatcht, entsteht
Live/PDF-Divergenz (§8):
- **Dashboard:** `_calculate_streak` in `core/views/training_stats.py`.
- **PDF/Export:** die separate Streak-Schleife in `calculate_consistency_metrics`
  (`core/utils/advanced_stats.py`), die via `stats_collector`
  (`consistency_metrics`) in `training_pdf_simple.html` als `aktueller_streak`
  gerendert wird.

Beide sind wochenbasiert (laufende Woche neutral). Idealerweise vor 32.5 die
Duplikat-Logik konsolidieren oder zumindest eine gemeinsame
„ist-diese-Woche-pausiert?"-Hilfsfunktion teilen, statt zweimal dieselbe
Pausen-Awareness einzubauen.

*Vor Umsetzung am Code klären:* exakte Streak-Definition (aus #475
wochenbasiert) und ob beide Schleifen auf dieselbe Pausen-Quelle zugreifen.

`tests`: dokumentierte Pause ≥ Mindestdauer erhält den Streak – **auch** bei
Di–So-Pause ohne volle Wochenabdeckung (⑨), in **beiden** Implementierungen;
1-Tages-Pause bridged nicht; un-dokumentierter Gap wie bisher.

## 5. Reihenfolge & Branch

32.1 → 32.2 → 32.3 → 32.4 → 32.5. Begründung: Model zuerst (alles hängt daran),
UI früh (damit Testdaten eingebbar sind), Klassifikation als Kern, Fatigue +
Streak als nachgelagerte Konsumenten.

Ein Feature-Branch für die Phase (`feature/phase-32-trainingspausen`), Commit
pro Sub-Phase, kein Merge nach main bis Phase komplett (Merge = Prod-Deploy).
Konzept-Doc selbst nach `docs/concepts/phase32_concept.md` tragen und mit-committen.

## 6. Betroffene Dateien (Hypothesen – am Code verifizieren)

- `core/models/…` – neues Model `TrainingsPause` + Migration; **`core/models/__init__.py`
  re-export ergänzen** (⑫).
- `core/views/…` – CRUD-Views (+ ggf. neues Modul) + URLs in `core/urls`.
- `core/signals.py` – Cache-Invalidierung `dashboard_computed_<user>` für
  `TrainingsPause` (`post_save` **und** `post_delete`, ⑬).
- `core/templates/core/…` – Pausen-Liste/-Formular; Lücken-Label in
  `training_stats.html` **und** `training_pdf_simple.html` (Live/PDF-Parität!).
- `core/utils/week_classification.py` – `ist_ausfall` / `teilweise_ausfall`
  **und** `select_comparable_weeks` (Pause als Epoch-Grenze, §32.3/§32.4).
- `core/export/stats_collector.py` – Wochen-Emission (union); konsumiert
  `build_weekly_volume_overview` (**nicht** `select_comparable_weeks`).
- `core/utils/advanced_stats.py` – **Export/PDF**-Fatigue-Spike-Fluss
  (`calculate_fatigue_index` via `select_comparable_weeks`) + zweite
  Streak-Schleife in `calculate_consistency_metrics` (PDF-Streak, §32.5).
- `core/views/training_stats.py` – **Dashboard/Stats**-Pfade, die `select_comparable_weeks`
  *umgehen* und ebenfalls pause-aware werden müssen (§32.4): Fatigue
  `_calculate_fatigue_index` + `_calculate_weekly_volumes` + `_get_volume_spike_fatigue`
  (⑧); Form-Index `_calculate_form_index` + `_get_volume_trend_score` (⑮);
  Stats-Warnungen `_detect_volume_warnings` (⑱); Streak `_calculate_streak` (§32.5).
- `core/chart_generator.py` – Lücken-Darstellung im matplotlib-Volumen-Chart.
- `core/admin.py` – `TrainingsPause` registrieren.
- `locale/en/LC_MESSAGES/django.po` **+ kompiliertes `django.mo`** – Deutsch ist
  Quell-Sprache (msgid), **kein** `locale/de`-Katalog im Repo; nur Englisch wird
  übersetzt. Neue Strings ins `.po` **und** `compilemessages` ausführen, sonst
  nutzt die EN-UI das alte `.mo` (⑲; `test_i18n` verlangt die `.mo`).
- Tests in `core/tests/…`.

## 7. i18n (DE/EN)

```python
class Grund(models.TextChoices):
    KRANKHEIT  = "krankheit",  _("Krankheit")
    VERLETZUNG = "verletzung", _("Verletzung")
    URLAUB     = "urlaub",     _("Urlaub")
    SONSTIGES  = "sonstiges",  _("Sonstiges")
```
Stabiler deutscher Key in der DB; Übersetzung via `gettext_lazy` **nur beim
Rendern**. Niemals den übersetzten String persistieren.

**Katalog-Realität (⑲):** Deutsch ist die **Quell-Sprache** (msgid) – es gibt
**keinen** `locale/de`-Katalog. Nur Englisch wird übersetzt
(`locale/en/LC_MESSAGES/django.po`). Neue UI-/`grund`-Strings müssen ins
englische `.po` **und** danach mit `django-admin compilemessages` ins
`django.mo` kompiliert werden – sonst rendert die EN-UI den alten Stand und
`core/tests/test_i18n.py` (verlangt die `.mo`) schlägt fehl. Das kompilierte
`.mo` mit-committen.

## 8. Risiken

- **Wochen-Emissions-Änderung (32.3) ist der riskanteste Eingriff** – berührt
  die Teil-Splitwochen-Logik aus #481. Regressionsgefahr für bestehende
  Trend-/Diagnose-Karten. → Full-Test-Run **inkl. `test_chart_generator`**
  (27.6a-Lektion: Teil-Runs verschleiern Fails).
- **Ausschluss-Stacking / Grenz-Break:** laufend + teilweise + Pausen-Grenze
  (`break`) → evtl. < 2 comparable weeks → Trend „pausiert". Genau das ist nach
  einer Pause erwünscht, muss aber als **getesteter Pfad** abgesichert sein, kein
  stiller Crash.
- **Kein Auto-Backfill:** historische Löcher lassen sich nicht automatisch als
  Krankheit/Urlaub nachklassifizieren – nur vorwärts + manuell rückwirkend.
  Ehrliche Grenze, nicht kaschieren.
- **Live/PDF-Divergenz:** Lücken-Label muss in beiden Render-Pfaden landen.

## 9. Abnahmekriterien

1. Pause anlegen/ändern/löschen, rückwirkend; offene (laufende) Pause möglich
   und als **gelabelte aktuelle Lücke** sichtbar (auf `heute` geclamped, ⑦);
   strikt user-isoliert. Overlap-Schutz greift auch außerhalb von Forms (③).
2. 2-Wochen-Krankheit mit 0 Sessions erscheint als **gelabelte Lücke** (nicht
   stumm fehlend) in Live **und** PDF.
3. Wiedereinstiegs-Woche nach Pause erzeugt **keine** falsche
   Volumen-Anstiegs-Warnung/-Bewertung – in **allen vier Vergleichspfaden**
   (Fatigue Dashboard + PDF, Form-Index, Stats-Warnungen; ⑧/⑮/⑱), auch bei nicht
   auf Mo–So ausgerichteten Pausen (⑥) inkl. Sessions in beiden Teilwochen (⑭).
4. Dokumentierte Pause ≥ Mindestdauer **resettet den Streak nicht** – auch bei
   nicht auf Mo–So ausgerichteten Pausen (⑨), in Dashboard **und** PDF.
5. Teil-Overlap-Woche behält ihr echtes Volumen, ist aber als Trend-Anker
   ausgeschlossen (auch Voll-Overlap *mit* Session, ⑯).
6. `grund`-Labels DE/EN korrekt; englisches `.mo` kompiliert, `test_i18n` grün (⑲).
7. Anlegen/Ändern/**Löschen** einer Pause wirkt **sofort** im Dashboard
   (`dashboard_computed_<user>` invalidiert, nicht erst nach TTL) (⑬).
8. Zukunftsdatierte Pause emittiert **keine** Zukunfts-Wochen ins Chart (⑰).
9. Gesamte Testsuite grün, inkl. `test_chart_generator` **und** `test_i18n`.

## 10. Vor Implementierung am Code zu klärende Hypothesen

- Exakte Streak-Definition + **beide** Orte (Dashboard `_calculate_streak`
  **und** PDF `calculate_consistency_metrics`, §32.5).
- Join-/Emissions-Punkt der Wochenliste (`stats_collector` vs.
  `training_stats`-Helfer) **inkl. Clamping JEDER Pause** (offen *und*
  geschlossene Zukunfts-Ranges) auf `heute`/aktuelle ISO-Woche (§32.3.2, ⑦ + ⑰).
- `select_comparable_weeks` ist **nicht** der einzige Chokepoint (beantwortet,
  ⑧/⑮/⑱): **vier** Pfade vergleichen Wochen-Volumina (Fatigue Dashboard+PDF,
  Form-Index `_get_volume_trend_score`, Stats-Warnungen `_detect_volume_warnings`)
  – einen **gemeinsamen** pause-aware Helfer schaffen, den alle konsumieren, +
  Audit-Test gegen vergessene fünfte Stelle.
- Mindestdauer (`PAUSE_BOUNDARY_MIN_DAYS`, inklusiv gezählt, Default 5) so
  festlegen, dass das Di–So-Beispiel sie erreicht (§32.3, ⑥ + ⑪) – **geteilte**
  Schwelle für Trend-Grenze (§32.4) **und** Streak-Bridge (§32.5, ⑨).
- Ziel-Submodul für das Model in `core/models/` **+ Re-Export in
  `core/models/__init__.py`** (⑫).
- Overlap-Erzwingung außerhalb von Forms: Service-/Manager-only-Schreibpfad,
  da `save()`+`full_clean()` `bulk_create`/Fixtures **nicht** abdeckt (§32.1,
  ③ + ⑩); MariaDB-Exclusion-Constraint-Annahme verifizieren.
- Dashboard-Cache-Invalidierung: `TrainingsPause`-Signale (`post_save` +
  `post_delete`) auf `dashboard_computed_<user>` (`core/signals.py`, §32.2, ⑬).
