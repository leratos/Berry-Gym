# Berry-Gym – Erweiterungs-Roadmap
**Erstellt:** 2026-03-12
**Ziel:** Professionelles, tägliches Trainings-Tool für private Nutzung mit Freunden
**Strategie:** Bugs & UX zuerst, dann Features – kein neues Feature ohne Polish des Bestehenden

---

## Phase 1 – Bugs & Navigation *(klein, sofort spürbar)*
**Branch:** `feature/phase1-ux-fixes`

| # | Aufgabe | Datei(en) |
|---|---|---|
| 1.1 | Dauer-Bug: `finish_training` zeigt für historische Trainings `jetzt - ursprung` | `training_session.py` |
| 1.2 | KI-Empfehlung auf Abschlussseite aktivieren (implementiert, deaktiviert) | `training_finish.html` |
| 1.3 | "Alle anzeigen" → "Trainingshistorie / Bearbeiten" (klarere Navigation) | `dashboard.html` |
| 1.4 | Wochenvolumen-Widget: Deload-Woche mit Kontext kennzeichnen (nicht "0 kg") | `dashboard.html`, `views/dashboard` |
| 1.5 | Session-Notiz & Dauer in Trainingshistorie anzeigen | `training_list.html` / Training-Detail |

---

## Phase 2 – PR-System *(mittlerer Aufwand, emotional wichtig)*
**Branch:** `feature/phase2-pr-system`

| # | Aufgabe | Details |
|---|---|---|
| 2.1 | PR-Detection beim Speichern | Neues Max-Gewicht ODER neue Wdh auf gleichem Gewicht → in DB markieren |
| 2.2 | PR-Moment auf Abschlussseite | Visuell hervorheben, nicht nur Text |
| 2.3 | PR-History pro Übung | In Übungsstatistik sichtbar |
| 2.4 | "Deine PRs diese Woche" auf Dashboard | Kleines Widget, optional |

---

## Phase 3 – Dashboard-Hierarchie *(täglich sichtbar)*
**Branch:** `feature/phase3-dashboard`

| # | Aufgabe | Details |
|---|---|---|
| 3.1 | Quick Actions: 3 primäre Buttons | Training, Körperwerte, Cardio – Rest unter "Mehr" |
| 3.2 | Farbwirrwarr bereinigen | Einheitliche Button-Sprache |
| 3.3 | Motivationstext datenbasisiert | "Letztes Mal 80kg – heute PR-Versuch?" statt Generic |

---

## Phase 4 – Trainingsabschluss aufwerten *(Belohnungsmoment)*
**Branch:** `feature/phase4-finish-screen`

| # | Aufgabe | Details |
|---|---|---|
| 4.1 | Volumen vs. letztes Mal gleicher Trainingstag | "+2.8% vs. letzte Woche" |
| 4.2 | PR-Integration aus Phase 2 | |
| 4.3 | Weiterleitung: "Nächstes Training vorschlagen" | |

---

## Bewusst NICHT in dieser Roadmap

- Ernährungstracking (anderes Produkt)
- Schlaf-Tracking (braucht Wearable)
- Social Feed (zu aufwändig für privates Tool)
- Weitere AI/ML-Features (erst Polish des Bestehenden)
