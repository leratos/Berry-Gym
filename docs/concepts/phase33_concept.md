# Phase 33 – Wiedereinstieg nach Pause: Detraining-bewusste Einstiegsgewichts-Empfehlung

> Status: **Entwurf v2 (Scope bestätigt)** – Claude Code / VSCode, 2026-07-03.
> User-Entscheidungen eingearbeitet: (a) Medizin-Signal = **explizites Flag** am
> `TrainingsPause`-Modell (Migration), (b) UI = **Dashboard-Hinweis + eigene
> Detailseite**, (c) Umfang = **alle Sub-Phasen** inkl. Stagnations-Korrektur.
> Fortsetzung der in Phase 32 §2 explizit ausgeklammerten „Stufe 3"
> (*Plan-Generator Return-to-Training-Ramp / detraining-bewusste Lastvorschläge*).
> **Dieses Dokument enthält Hypothesen, die am Code zu verifizieren sind** – als
> solche markiert. Nicht blind umsetzen.

## 1. Ziel

Nach einer dokumentierten Trainingspause (`TrainingsPause`, Phase 32) dem Nutzer
beim Wiedereinstieg helfen, statt ihn mit den zuletzt geloggten – nach Detraining
zu schweren – Arbeitsgewichten allein zu lassen:

1. **Einstiegsgewichts-Empfehlung:** pro zuletzt trainierter Übung ein reduzierter
   Start-Arbeitsgewichts-Vorschlag = letztes Arbeitsgewicht × Detraining-Faktor
   (abhängig von Pausendauer), plus **Rückführungs-Rampe** über N Wochen zurück
   auf 100 %.
2. **Progressions-Segmentierung (Korrektur):** die per-Übung-Progressions-/
   Stagnations-Analyse darf **nicht über eine Pause hinweg** vergleichen (sonst
   wird der bewusst reduzierte Wiedereinstieg als „Rückschritt/Stagnation"
   fehlgelabelt). Phase 32 hat die *Volumen*-Vergleiche pause-aware gemacht, die
   *per-Übung-Gewichts*-Vergleiche in `ai_recommendations` **nicht**.

Konkreter Auslöser (realer Fall): 3 Wochen OP-bedingter Ausfall zusätzlich zu
bereits 3 Wochen → **6 Wochen** Gesamtausfall. Die letzten Arbeitsgewichte sind
kein valider Startpunkt mehr; ein blinder Fortsetzungsversuch ist Verletzungs-
risiko, ein Nulldaten-Neustart wäre Frust.

## 2. Leitprinzipien

- **Kein Daten-Reset.** Historie bleibt unangetastet (Phase 32 hat die Lücke
  bereits als *begründete Pause* annotiert – das ist die SoT). „Wiedereinstieg"
  ist ein **neues Progressions-Segment**, kein Löschen/Verbergen. Vergleichbarkeit
  der Langzeit-Daten bleibt erhalten.
- **Empfehlung, keine Automatik.** Der Vorschlag verändert **nie** automatisch
  Plan-Zielwerte oder geloggte Sätze. Der Nutzer entscheidet. (Analog zu den
  bestehenden `workout_recommendations` – reine Anzeige.)
- **Medizinische Vorsicht ist Default, nicht Fußnote.** Nach Verletzung/Krankheit
  (insb. post-OP) steht die Empfehlung unter **ärztlicher Freigabe** und
  respektiert mögliche Belastungsgrenzen. Verpflichtender Disclaimer über das
  bestehende Disclaimer-System (`core/models_disclaimer.py`, `docs/DISCLAIMER_SYSTEM.md`).
- **Bausteine wiederverwenden, keine Parallelstruktur.** `TrainingsPause`,
  `Satz.gewicht`/`rpe`, `UserProfile.deload_weight_factor` (bestehendes
  Reduktions-Faktor-Muster), `Trainingsblock` (Segment-Anker) existieren bereits.
- **Ehrliche Heuristik.** Die Detraining-Faktoren sind Erfahrungs-/Literaturwerte,
  keine Messung. Als solche kennzeichnen und zentral konfigurierbar halten.

## 3. Scope

**In Scope:**
- 33.1 Modell-Flag `aerztliche_freigabe_noetig` auf `TrainingsPause` + Migration
  + Service-/CRUD-/Admin-Anpassung + Tests (**User-Entscheidung: explizites Flag
  statt Ableitung aus `grund`**).
- 33.2 Kernlogik: reine Funktion(en) für Detraining-Faktor, Einstiegsgewicht pro
  Übung und Rampe. Unit-testbar, ohne UI.
- 33.3 UI: **Dashboard-Hinweis** bei frischer Pause + **eigene Detailseite**
  (Liste pro Übung: letztes Arbeitsgewicht → Empfehlung + Rampe), Disclaimer,
  i18n DE/EN.
- 33.4 Progressions-Segmentierung: `_get_stagnation_empfehlung`/`_is_stagnating`
  (`core/views/ai_recommendations.py`) pause-aware machen (kein Vergleich über
  `ist_pausen_grenze` hinweg) + Audit-Test analog 32.4. Prüfen, ob die PR-Logik
  (`core/models/training.py` / `test_pr_system.py`) denselben Fehler hat.

**Explizit NICHT in Scope (→ spätere „Stufe 4"):**
- Integration in den KI-Plan-Generator (`ai_coach/`). *Begründung:* Phase 32 §2
  hat festgelegt – **falls** das in den Generator fließt, dann als **harte
  Validator-Constraint** (Cap auf Zielgewichte während der Rampe), **nicht** als
  Soft-Prompt-Hint (Phase-11-/30.1-Lektion). Das ist der riskanteste Teil und
  liefert den geringsten Zusatznutzen gegenüber der Standalone-Anzeige → eigene
  Phase.
- Automatisches Anlegen eines Wiedereinstiegs-`Trainingsblock`. Optionaler
  Komfort, kein Kern; separat entscheidbar.

## 4. Sub-Phasen

### 33.1 – Modell-Flag `aerztliche_freigabe_noetig` (Migration + CRUD + Service)

**User-Entscheidung:** das Medizin-Signal ist ein **explizites, vom Nutzer
setzbares Flag** – nicht aus `grund` abgeleitet (bildet z. B. „Urlaub direkt nach
OP" korrekt ab und ist nicht ratend).

- `TrainingsPause.aerztliche_freigabe_noetig = BooleanField(default=False)` mit
  `verbose_name`/`help_text` (gettext_lazy). Schema-Migration in
  `core/migrations/` (reines `AddField`, Default `False` → kein Datenverlust,
  Bestandspausen bleiben „nicht-medizinisch").
- **Service** (`core/services/pausen.py`): `create_pause`/`update_pause` um den
  Parameter erweitern; `update_pause` mit `_UNSET`-Sentinel (nur bei Übergabe
  ändern). Alle Schreibpfade laufen weiter über den Service (§32.1-Härtung nicht
  aufweichen).
- **CRUD-View** (`core/views/pausen.py`): `_values_from_post` liest die Checkbox
  (`request.POST.get(...) == "on"`), `pausen_add`/`pausen_edit` reichen sie durch,
  Edit-Prefill ergänzen.
- **Formular-Template** (`pausen_form.html`): Checkbox mit erklärendem Hinweis.
  Optional (Komfort, kein Muss): per kleinem JS bei `grund=verletzung/krankheit`
  vorschlagsweise anhaken – bleibt user-editierbar.
- **Listen-Template** (`pausen_list.html`): kleines Badge, wenn Flag gesetzt.
- **Admin** (`core/admin.py`): Feld in `list_display`/`list_filter` ergänzen;
  `save_model` läuft schon über `update_pause` (Flag automatisch mit).

`tests`: Default `False`; Service create/update setzt/erhält Flag; `update_pause`
ohne Parameter lässt Flag unverändert (Sentinel); View-POST mit/ohne Checkbox;
Migration lädt (Bestandspause = `False`).

### 33.2 – Kernlogik (Detraining-Faktor, Einstiegsgewicht, Rampe)

*Hypothese (am Code lokalisieren):* neues Modul `core/utils/reentry.py` (oder
Einordnung in ein bestehendes `core/utils/`-Modul). Reine, DB-lesende Funktionen;
keine Schreibpfade, keine Migration.

Bausteine:
- **Auslöser / relevante Pause:** neueste `TrainingsPause` des Users mit
  `end_datum IS NOT NULL AND end_datum <= heute` und
  `dauer_tage = (end − start).days + 1 ≥ REENTRY_MIN_DAYS`. Offene Pause
  (`end_datum=None`) = noch laufend → **keine** aktive Empfehlung (optional:
  Vorschau „geplanter Wiedereinstieg"). „Frisch" nur, solange
  `end_datum ≥ heute − REENTRY_WINDOW_DAYS` (danach ist der Wiedereinstieg
  vorbei). Schwelle `REENTRY_MIN_DAYS` **teilen** mit Phase 32
  `PAUSE_BOUNDARY_MIN_DAYS` prüfen – bewusst gleich oder bewusst höher setzen
  (Detraining relevanter Effekt eher ab ~10–14 Tagen; entscheiden + dokumentieren).
- **Letztes Arbeitsgewicht pro Übung:** aus `Satz` (`ist_aufwaermsatz=False`,
  `einheit__user=user`, `einheit__datum < pause.start_datum`), je Übung das
  repräsentative Arbeitsgewicht der letzten Trainings **vor** der Pause
  (Hypothese: Top-Working-Set = `max(gewicht)` der letzten n Einheiten, am Code/
  an bestehender PR-/Stagnations-Logik ausrichten, nicht neu erfinden).
- **Detraining-Faktor & Rampe** (Default-Tabelle, zentral, konfigurierbar –
  Heuristik, **keine** medizinische Vorgabe):

  | Pausendauer (inkl.) | Faktor | Rampe zurück auf 100 % |
  |---|---|---|
  | < 7 Tage | 1.00 | – (kein Abzug) |
  | 7–13 Tage (~1–2 Wo) | 0.95 | 1 Woche |
  | 14–27 Tage (2–4 Wo) | 0.90 | 2 Wochen |
  | 28–41 Tage (4–6 Wo) | 0.85 | 3 Wochen |
  | ≥ 42 Tage (6+ Wo) | 0.80 | 4 Wochen |

  - **Medizinischer Zusatz (via Flag `aerztliche_freigabe_noetig`, §33.1):** Flag
    gesetzt → zusätzlicher konservativer Abschlag (z. B. eine Stufe tiefer)
    **und** niedrigerer RPE-Deckel **und** verpflichtender ärztlicher-Freigabe-
    Disclaimer. Ohne Flag → reine Detraining-Reduktion ohne Medizin-Hinweis. (Der
    `grund` bleibt für Anzeige/Icon relevant, ist aber **nicht** das Medizin-
    Signal – das ist bewusst das Flag.)
  - **RPE-Deckel während der Rampe** (z. B. Start ≤ 7, wöchentlich steigend) – als
    Empfehlungstext, konsistent zu `periodization.get_modus_profil`.
  - Rundung auf sinnvolle Hantel-/Gerät-Schritte (Hypothese: 2.5-kg-Schritte;
    prüfen, ob es dafür schon einen Helfer gibt).

`tests` (pytest): Faktor pro Dauer-Grenze (6/7/13/14/27/28/41/42 Tage,
Inklusiv-Zählung); Grund-Abschlag; offene Pause → keine Empfehlung; Pause
außerhalb des Fensters → keine Empfehlung; Übung ohne Vor-Pause-Daten wird
ausgelassen; Rampen-Wert Woche 1..N monoton bis 100 %.

### 33.3 – UI: Dashboard-Hinweis + Wiedereinstiegs-Detailseite + Disclaimer + i18n

**User-Entscheidung:** Dashboard-Hinweis **plus eigene Detailseite** (klar
getrennt, gut testbar).

- View (`@login_required`, strikt user-scoped) im neuen Modul
  `core/views/reentry.py`; kein neuer Schreibpfad (reine Anzeige).
- **Detailseite** unter `core/templates/core/…`: Tabelle pro Übung (letztes
  Arbeitsgewicht → Empfehlung Woche 1, Rampe, RPE-Deckel), Kontext (welche Pause,
  Dauer, Grund, Flag).
- **Dashboard-Hinweis:** Karte auf dem Dashboard, wenn eine frische Pause
  vorliegt, verlinkt auf die Detailseite. Cache-Konsistenz mit
  `dashboard_computed_<user>` beachten (Phase 32 §32.2 ⑬).
- **Disclaimer verpflichtend** über das bestehende System – bei
  Verletzung/Krankheit prominent „nur nach ärztlicher Freigabe / OP-bedingte
  Belastungsgrenzen beachten".
- i18n: alle Strings `{% trans %}`/`gettext`; **DE = Quell-Sprache (msgid)**, nur
  `locale/en/LC_MESSAGES/django.po` übersetzen **+ `compilemessages`** (Phase 32
  §7-Lektion, sonst `test_i18n` rot).

`tests`: Auth erzwungen; User-Isolation; Karte erscheint nur bei frischer Pause;
Disclaimer bei `verletzung`/`krankheit` vorhanden; `.mo` kompiliert.

### 33.4 – Progressions-/Stagnations-Analyse pause-aware (Korrektur)

*Andockpunkt:* `_get_stagnation_empfehlung` / `_is_stagnating`
(`core/views/ai_recommendations.py`, 60-Tage-Fenster über per-Übung-Max-Gewichte).
Heute vergleicht es blind Vor- und Nach-Pause-Gewichte → labelt den reduzierten
Wiedereinstieg als „Stagnation/kein Fortschritt".

- Vergleich auf **das aktuelle Segment nach der letzten Pausen-Grenze** begrenzen
  (dieselbe `ist_pausen_grenze`-Quelle wie Phase 32 §32.3/§32.4 – **keine**
  Parallel-Logik). Trainings vor der Pause werden nicht mit Post-Pause-Trainings
  in einer Stagnations-Kette verglichen.
- **Audit-Test** (analog 32.4): Comeback-nach-Pause-Szenario reproduziert das
  Fehlverhalten und sichert den Fix; zusätzlich prüfen, ob die PR-Erkennung
  (`is_pr`/`pr_type` in `core/models/training.py`, `test_pr_system.py`) über die
  Pause hinweg „PR"/„Rückschritt" fehlmeldet – falls ja, gleich mitfixen, sonst
  dokumentieren, dass sie unbetroffen ist.

`tests`: Wiedereinstiegs-Trainings nach Pause erzeugen **keine** „Stagnation"-
Empfehlung; Vor-Pause-Trainings nicht Teil der Post-Pause-Kette; Audit-Test.

## 5. Betroffene Dateien (Hypothesen – am Code verifizieren)

- `core/models/pause.py` + `core/migrations/…` – neues Feld
  `aerztliche_freigabe_noetig` + `AddField`-Migration (§33.1).
- `core/services/pausen.py` – `create_pause`/`update_pause` um Flag-Parameter
  (§33.1).
- `core/views/pausen.py` + `pausen_form.html` + `pausen_list.html` +
  `core/admin.py` – Checkbox/Badge/Admin-Spalte (§33.1).
- `core/utils/reentry.py` **(neu)** – Detraining-Faktor/Rampe/Einstiegsgewicht;
  Konstanten (`REENTRY_MIN_DAYS`, `REENTRY_WINDOW_DAYS`, Faktor-Tabelle) (§33.2).
- `core/views/reentry.py` **(neu)** + URL in `core/urls.py` + Re-Export in
  `core/views/__init__.py` (§33.3).
- `core/templates/core/…` – Wiedereinstiegs-Detailseite + Dashboard-Hinweis
  (`dashboard.html`) (§33.3).
- `core/views/ai_recommendations.py` – `_get_stagnation_empfehlung`/`_is_stagnating`
  pause-aware (§33.4).
- `core/utils/week_classification.py` – **nur lesend** die vorhandene
  `ist_pausen_grenze`-Quelle konsumieren (keine neue Klassifikation).
- `core/models_disclaimer.py` / Disclaimer-Templates – Wiedereinstiegs-Disclaimer.
- `locale/en/LC_MESSAGES/django.po` **+ kompiliertes `django.mo`**.
- `core/tests/…` – `test_reentry.py` (Kernlogik + View), Flag-Tests bei
  `test_pausen_*`, Audit-Test in/nahe `test_ai_recommendations.py`.

## 6. Entscheidungen & Restrisiken

**Vom User entschieden (2026-07-03):**

- **Medizin-Signal = explizites Flag** `aerztliche_freigabe_noetig` (§33.1),
  **nicht** aus `grund` abgeleitet → Migration eingeplant.
- **UI = Dashboard-Hinweis + eigene Detailseite** (§33.3).
- **Umfang = alle Sub-Phasen** inkl. Stagnations-Korrektur (§33.4).

**Noch bei Umsetzung zu fixieren (Heuristik/Detail, kein Scope):**

- **Detraining-Faktoren sind Heuristik.** Default-Tabelle (§33.2) als
  konfigurierbare Konstante, nicht hart verstreut; prominent als „Richtwert, kein
  ärztlicher Rat" kennzeichnen. Finale Werte beim Bau bestätigen.
- **„Letztes Arbeitsgewicht" ist definitionsabhängig** (Top-Set vs. Median-Working-
  Set vs. e1RM-basiert). An bestehender PR-/Stagnations-Definition ausrichten,
  nicht neu erfinden.
- **Schwelle `REENTRY_MIN_DAYS`** vs. `PAUSE_BOUNDARY_MIN_DAYS` (Phase 32 = 5):
  Detraining-Effekt eher ab ~10–14 Tagen – bewusst eigene, höhere Schwelle.
- **Runden auf Geräteschritte** – prüfen, ob Helfer existiert.
- **Nur Anzeige, nie Auto-Änderung** – muss getestet sein (kein Schreibpfad in
  33.2/33.3).

## 7. Abnahmekriterien

1. Für eine frische, abgeschlossene Pause ≥ Schwelle erscheint pro zuletzt
   trainierter Übung eine Einstiegsempfehlung = letztes Arbeitsgewicht × Faktor,
   plus Rampe; strikt user-isoliert; **keine** geloggten Sätze/Plan-Ziele werden
   verändert.
2. Faktor korrekt an allen Dauer-Grenzen (Inklusiv-Zählung); Grund
   `verletzung`/`krankheit` → konservativer + verpflichtender ärztlicher-Freigabe-
   Disclaimer.
3. Offene (laufende) Pause und Pause außerhalb des Fensters → **keine** aktive
   Empfehlung.
4. Wiedereinstiegs-Trainings nach Pause erzeugen **keine** falsche „Stagnation"-
   Empfehlung; kein per-Übung-Vergleich überquert die Pausen-Grenze (§33.3,
   Audit-Test).
5. i18n DE/EN korrekt; englisches `.mo` kompiliert; `test_i18n` grün.
6. Gesamte Testsuite grün.

## 8. Reihenfolge & Branch

33.1 → 33.2 → 33.3 → 33.4. Modell-Flag zuerst (Migration früh, Kernlogik hängt am
Flag), dann Kernlogik, UI danach, Stagnations-Korrektur als eigenständig testbarer
Abschluss.

Ein Feature-Branch für die Phase (`feature/phase-33-wiedereinstieg`), Commit pro
Sub-Phase, kein Merge nach main bis Phase komplett (Merge = Prod-Deploy). Dieses
Konzept-Doc mit-committen.
