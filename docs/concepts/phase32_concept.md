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
- 32.4 Fatigue-Index: Comeback-Spike-Suppression über die Pause hinweg.
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
Submodul unter `core/models/`.

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
- **Validierung außerhalb von Forms erzwingen (Codex-Review PR #200, ③):**
  Django ruft `clean()` **nicht** automatisch in `save()` auf – Form-`clean()`
  allein schützt `Manager.create()`, `bulk_create`, Fixtures/`loaddata`,
  factory_boy (s. Testplan unten!) und künftigen Service-Code nicht; über diese
  Pfade ließen sich überlappende Pausen weiterhin persistieren. Daher: `save()`
  ruft `self.full_clean()` auf **oder** alle Schreibpfade laufen über eine
  Service-/Manager-Methode mit transaktionalem `select_for_update` +
  Overlap-Check. Mindestens muss der Overlap-Test bewusst über `clean`/Form
  laufen, nicht über die Factory (die `clean()` umgeht).
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

`tests`: Auth erzwungen; User-Isolation; rückwirkendes Anlegen; Overlap-Warnung
erscheint, blockt aber nicht; offene Pause anlegbar.

### 32.3 – Klassifikations-Awareness (Kern)

*Andockpunkt:* `core/utils/week_classification.py` (seit 24.1c SoT der
Wochen-Flags).

1. Helper, der für eine ISO-Woche + die Pausen-Ranges eines Users bestimmt –
   Klassifikation nach **Wochen-Abdeckung**, nicht nach „irgendein Overlap"
   (Codex-Review PR #200, ⑤):
   - **0 Sessions + Pause deckt die *komplette* ISO-Woche (Mo–So) ab** →
     `ist_ausfall=True` (echter Vollausfall, zählt als Streak-Pause, §32.5).
   - **Partieller Overlap** (Pause deckt nur einen Teil der Woche ab) →
     `teilweise_ausfall=True`, unabhängig von der Session-Zahl. Volumen bleibt
     erhalten, Woche bleibt normal klassifiziert, ist aber kein Trend-Anker.
     *Wichtig:* ein 1-Tages-Urlaub in einer ohnehin session-losen Woche wird so
     **nicht** zum Vollausfall – er verbirgt die Woche nicht aus den Ankern und
     schützt den Streak nicht.
2. **Strukturelle Änderung (riskantester Teil):** Die Wochenliste muss aus
   `union(Wochen-mit-Sessions, Wochen-mit-Pausen-Overlap)` emittiert werden,
   damit eine komplett leere Krankheitswoche **als gelabelte Lücke erscheint**
   statt im Chart zu fehlen. *Hypothese: der Join-/Emissions-Punkt liegt in
   `core/export/stats_collector.py` und/oder dem Live-Helfer in
   `core/views/training_stats.py` – vor der Implementierung lokalisieren.*
3. `select_comparable_weeks` liegt in `core/utils/week_classification.py`
   (**nicht** in `stats_collector.py` – seit 24.1c ist `week_classification`
   die SoT; `stats_collector` konsumiert nur `build_weekly_volume_overview`;
   Codex-Review PR #200, ①). Dort wird eine **abgeschlossene Pause als
   Epoch-Grenze** behandelt (`break`, analog `ist_plan_wechsel`), nicht nur als
   überspringbarer Anker. Die Funktion läuft von der neuesten zur ältesten Woche
   und bricht bei `ist_plan_wechsel` bereits ab; eine `ist_ausfall`-Woche analog
   als harte Grenze zu behandeln stellt sicher, dass **kein** Vergleich über die
   Pause hinweg passiert (Begründung in §32.4). `teilweise_ausfall` wird
   zusätzlich per `continue` übersprungen (Volumen erhalten, aber kein Anker).

`tests`: voll abgedeckte Woche → `ist_ausfall`; partielle → `teilweise_ausfall`
+ Volumen erhalten, aber nicht als comparable; 1-Tages-Pause in session-loser
Woche → **kein** `ist_ausfall`; leere Krankheitswoche wird als Lücke emittiert;
`select_comparable_weeks` überspringt `teilweise_ausfall` (`continue`) und
behandelt `ist_ausfall` als Epoch-Grenze (`break`) – keine Vor-Pause-Woche
landet hinter der Pause in der Vergleichsliste.

### 32.4 – Fatigue-Index: Comeback-Spike-Suppression

`calculate_fatigue_index` (in `core/utils/advanced_stats.py`) routet die
Volumen-Spike-Komponente über `select_comparable_weeks` (Lazy-Import, seit
24.1b) und vergleicht dort `comparable_weeks[-1]` mit `comparable_weeks[-2]`.

**Korrektur (Codex-Review PR #200, ④):** Das bloße *Ausschließen* der
`ist_ausfall`-Wochen als Anker genügt **nicht**. Werden die Ausfallwochen nur
übersprungen (`continue`), rückt die Comeback-Woche direkt neben die letzte
Vor-Pause-Woche – der Vergleich überquert weiterhin die Pause und der Spike
entsteht (genau das Fehlverhalten aus Abnahmekriterium 3). Deshalb sitzt der Fix
in §32.3: die Pause wird in `select_comparable_weeks` als **Epoch-Grenze**
behandelt (`break`). Folge: nach der Pause sind nur Post-Pause-Wochen
vergleichbar; die erste Comeback-Woche allein ergibt `len < 2` → „Trend
pausiert", bis eine zweite Post-Pause-Woche existiert. Kein Vergleich überquert
die Pause.

Damit ist der Spike strukturell unterdrückt, ohne Sonderfall im Fatigue-Code –
derselbe Chokepoint wie 24.1b. Verifizieren, dass kein zweiter Volumen-Vergleich
an `select_comparable_weeks` vorbeiläuft.

`tests`: Wiedereinstiegs-Woche nach Pause erzeugt **keine** „Sehr starker
Volumen-Anstieg"-Warnung (Reproduktion des erwarteten Fehlverhaltens + Fix).

### 32.5 – Streak: Pause pausiert

Dokumentierte Pause → Streak läuft über die Lücke weiter (kein Reset, keine
Bestrafung). **Un-dokumentierter** Gap verhält sich unverändert. Eine Woche
zählt als „pausiert", wenn sie `ist_ausfall` ist (volle Wochen-Abdeckung,
§32.3) – nicht schon bei einer 1-Tages-Pause (sonst würde ⑤ den Streak
fälschlich schützen).

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

`tests`: dokumentierte Pause erhält den Streak; un-dokumentierter Gap wie bisher.

## 5. Reihenfolge & Branch

32.1 → 32.2 → 32.3 → 32.4 → 32.5. Begründung: Model zuerst (alles hängt daran),
UI früh (damit Testdaten eingebbar sind), Klassifikation als Kern, Fatigue +
Streak als nachgelagerte Konsumenten.

Ein Feature-Branch für die Phase (`feature/phase-32-trainingspausen`), Commit
pro Sub-Phase, kein Merge nach main bis Phase komplett (Merge = Prod-Deploy).
Konzept-Doc selbst nach `docs/concepts/phase32_concept.md` tragen und mit-committen.

## 6. Betroffene Dateien (Hypothesen – am Code verifizieren)

- `core/models/…` – neues Model `TrainingsPause` + Migration.
- `core/views/…` – CRUD-Views (+ ggf. neues Modul) + URLs in `core/urls`.
- `core/templates/core/…` – Pausen-Liste/-Formular; Lücken-Label in
  `training_stats.html` **und** `training_pdf_simple.html` (Live/PDF-Parität!).
- `core/utils/week_classification.py` – `ist_ausfall` / `teilweise_ausfall`
  **und** `select_comparable_weeks` (Pause als Epoch-Grenze, §32.3/§32.4).
- `core/export/stats_collector.py` – Wochen-Emission (union); konsumiert
  `build_weekly_volume_overview` (**nicht** `select_comparable_weeks`).
- `core/utils/advanced_stats.py` – Verifikation Fatigue-Spike-Fluss + zweite
  Streak-Schleife in `calculate_consistency_metrics` (PDF-Streak, §32.5).
- `core/views/training_stats.py` – Dashboard-Streak `_calculate_streak` (§32.5).
- `core/chart_generator.py` – Lücken-Darstellung im matplotlib-Volumen-Chart.
- `core/admin.py` – `TrainingsPause` registrieren.
- `locale/de`, `locale/en` – `.po` für `grund`-Labels + UI.
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

## 8. Risiken

- **Wochen-Emissions-Änderung (32.3) ist der riskanteste Eingriff** – berührt
  die Teil-Splitwochen-Logik aus #481. Regressionsgefahr für bestehende
  Trend-/Diagnose-Karten. → Full-Test-Run **inkl. `test_chart_generator`**
  (27.6a-Lektion: Teil-Runs verschleiern Fails).
- **Ausschluss-Stacking:** laufend + teilweise + ausfall → evtl. < 2 comparable
  weeks → Trend „pausiert". Akzeptabel, aber als **getesteter Pfad**, kein
  stiller Crash.
- **Kein Auto-Backfill:** historische Löcher lassen sich nicht automatisch als
  Krankheit/Urlaub nachklassifizieren – nur vorwärts + manuell rückwirkend.
  Ehrliche Grenze, nicht kaschieren.
- **Live/PDF-Divergenz:** Lücken-Label muss in beiden Render-Pfaden landen.

## 9. Abnahmekriterien

1. Pause anlegen/ändern/löschen, rückwirkend; offene (laufende) Pause möglich;
   strikt user-isoliert.
2. 2-Wochen-Krankheit mit 0 Sessions erscheint als **gelabelte Lücke** (nicht
   stumm fehlend) in Live **und** PDF.
3. Wiedereinstiegs-Woche nach Pause erzeugt **keine** falsche
   Volumen-Anstiegs-Warnung im Fatigue-Index.
4. Dokumentierte Pause **resettet den Streak nicht**.
5. Teil-Overlap-Woche behält ihr echtes Volumen, ist aber als Trend-Anker
   ausgeschlossen.
6. `grund`-Labels DE/EN korrekt.
7. Gesamte Testsuite grün, inkl. `test_chart_generator`.

## 10. Vor Implementierung am Code zu klärende Hypothesen

- Exakte Streak-Definition + **beide** Orte (Dashboard `_calculate_streak`
  **und** PDF `calculate_consistency_metrics`, §32.5).
- Join-/Emissions-Punkt der Wochenliste (`stats_collector` vs.
  `training_stats`-Helfer).
- Ist `select_comparable_weeks` der einzige Chokepoint für live + PDF + Fatigue?
- Ziel-Submodul für das Model in `core/models/`.
- MariaDB-Exclusion-Constraint-Annahme + Erzwingung außerhalb von Forms
  (`save()`/Service-`full_clean()`, §32.1).
