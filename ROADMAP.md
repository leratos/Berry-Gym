# 🏋️ HomeGym App - Roadmap & Feature-Tracking

**Stand:** 10.01.2026  
**Version:** 0.4.0

---

## ✅ PHASE 1: Basis-Features (100% KOMPLETT)

### Training Logging
- [x] Sätze erfassen (Gewicht, Wiederholungen, RPE)
- [x] Aufwärmsätze markieren
- [x] Smart Ghosting (letzte Werte vorschlagen)
- [x] Sätze bearbeiten/löschen
- [x] Freies Training ohne Plan
- [x] Training mit Plan-Vorausfüllung
- [x] Training Abschluss-Screen mit Dauer & Kommentar
- [x] Volumen-Tracking (kg × Wdh)
- [x] Übungen nach Muskelgruppen filtern

### Körperwerte
- [x] Gewicht, Größe, Körperfett, Muskelmasse erfassen
- [x] BMI & FFMI Berechnung
- [x] Gewichtsverlauf Graph (4 Charts: Gewicht, BMI/FFMI, KFA, Muskeln)
- [x] Dashboard-Anzeige mit aktuellen Werten
- [x] Body Stats Detail-Seite mit Verlaufs-Tabelle

### Statistiken
- [x] 1RM Progression pro Übung (Epley-Formel)
- [x] Chart.js Visualisierung
- [x] Trainingshistorie mit Volumen-Anzeige
- [x] Personal Records (1RM Max, schwerster Satz)
- [x] Dashboard Metriken: Trainingsfrequenz diese Woche
- [x] Dashboard Metriken: Streak Counter (Wochen in Folge)
- [x] Dashboard Metriken: Top 3 Favoriten-Übungen

### UI/UX
- [x] Dark Mode Design (Bootstrap 5)
- [x] Responsive Mobile-First
- [x] Bootstrap Modals für Bestätigungs-Dialoge
- [x] Gruppierung nach Muskelgruppen
- [x] Übersichtliche Karten-basierte UI

---

## ✅ PHASE 2: Trainingspläne & Smart Features (100% KOMPLETT)

### Trainingspläne
- [x] Plan-Modell & Admin-Interface
- [x] Plan-Auswahl Screen
- [x] Plan-Details Screen mit Übersicht aller Übungen
- [x] Sätze/Wiederholungs-Vorgaben pro Übung
- [x] Vorausfüllen beim Training-Start
- [x] Historie-Anzeige im Plan (letztes Gewicht/Wdh)
- [x] Plan-Beschreibung anzeigen
- [x] **Plan erstellen ohne Admin** (User-Interface)
- [x] **Plan bearbeiten/löschen** (mit Reihenfolge-Editor)
- [x] **Übungsauswahl mit Muskelgruppen-Filter**
- [x] **Drag & Drop Reihenfolge** (↑/↓ Buttons)
- [x] **Grafische Muskelgruppen-Darstellung** (Haupt + Hilfs)
- [x] **Übungs-Bibliothek** (alle Übungen mit Muskelgruppen)
- [x] **Intelligente Empfehlungen** (Bewegungstyp-Balance-Analyse)
  - Erkennt fehlende Isolationsübungen (z.B. Fliegende für Brust)
  - Warnt bei einseitiger Übungsauswahl (nur Drücken ohne Isolation)
  - Sport-wissenschaftliche Empfehlungen (18 neue Isolationsübungen hinzugefügt)

### Progressive Overload System
- [x] Intelligente Gewichtsvorschläge
- [x] RPE-basierte Progression (RPE <7 → +2.5kg)
- [x] Wiederholungs-Strategie (12+ Wdh → mehr Gewicht)
- [x] UI-Hinweise mit konkreten Tipps
- [x] Vergleich mit letztem Training

### Training Experience
- [x] Rest Timer (90 Sek, automatisch nach Satz)
- [x] Manueller Timer-Start Button (Navbar)
- [x] Countdown mit Farbwechsel (Gelb → Rot)
- [x] Vibration & Alert bei Ende
- [x] Timer-Stop per Klick

---

## ✅ PHASE 3: Fortgeschrittene Statistiken (100% KOMPLETT)

### Erweiterte Statistiken
- [x] **Volumen-Progression Graph** (Gesamt-Volumen pro Training)
- [x] **Wöchentliches Volumen** (letzte 12 Wochen als Bar-Chart)
- [x] **Wöchentliches Volumen im Dashboard** (aktuelle Woche + letzte 3 Wochen)
- [x] **Muskelgruppen-Balance Analyse** (Horizontal Bar Chart)
- [x] **Muskelgruppen-Balance SVG-Visualisierung** (Anatomische Darstellung mit Farbgradient grau→rot)
- [x] **Trainings-Heatmap** (90-Tage Kalender-Aktivität)
- [x] **Performance Form-Index** (0-100 Score aus Frequenz, RPE, Volumen, Konsistenz)
- [x] **Durchschnittliches RPE pro Übung** (mit Trend-Anzeige: improving/stable/declining)

### Deload & Recovery Management
- [x] **Automatische Deload-Erkennung** (Warnung bei >20% Volumen-Spikes)
- [x] **Volumen-Drop Erkennung** (Warnung bei >30% Rückgang)
- [x] **Ermüdungs-Index** (0-100 Score aus Volumen-Spikes, hohem RPE, Trainingsfrequenz)
- [x] **Empfehlungen für Regeneration** (automatische Warnungen bei hoher Ermüdung)

### Social & Motivation
- [x] **PR-Benachrichtigungen** (Alert bei neuem 1RM-Rekord)
- [x] **Motivations-Quotes** (dynamische Motivation basierend auf Performance & Ermüdung)
  - High Performance Quotes (bei gutem Form-Index)
  - Good Performance Quotes (bei solidem Training)
  - Need Motivation Quotes (bei niedrigem Form-Index)
  - High Fatigue Quotes (bei hohem Ermüdungs-Index)

### Trainingsprogrammierung
- [ ] Periodisierung (Linear, Wellenförmig, Block)
- [ ] Makrozyklus-Planung (12+ Wochen)
- [ ] Mikrozyklus-Templates
- [ ] Automatische Lastanpassung nach Zyklus
- [ ] Deload-Wochen einplanen

---

## ✅ PHASE 3.5: Anatomische Visualisierung (100% KOMPLETT)

### Interaktive Muskelgruppen-Map
- [x] **SVG Anatomie-Grafik** (Vorder- & Rückseite, 50+ Muskelregionen)
- [x] **Klickbare Muskelregionen** (Übungen nach Muskelgruppe filtern)
- [x] **Übungs-Detail-Ansicht** (Hauptmuskel rot, Hilfsmuskeln blau)
- [x] **Muskelgruppen-Navigation** (Quick-Select Buttons für alle MUSKELGRUPPEN)
- [x] **Balance-Visualisierung** (SVG in Trainingsstatistik mit Farbgradient)
- [x] **Belastungsverteilung** (Grau→Rot basierend auf Trainingsvolumen)
- [x] **Übungsstatistiken** (Max Gewicht, Gesamt Volumen, Sätze pro Übung)
- [x] **Text-zu-Code Mapping** (Automatische Konvertierung Hilfsmuskeln → SVG IDs)

### Visualisierungs-Features
- [x] Color-Coding System (Rot = Hauptmuskel, Blau = Hilfsmuskel, Grau = Inaktiv)
- [x] Hover-Effekte auf Muskelregionen
- [x] Dynamisches SVG-Laden via Fetch API
- [x] Responsive SVG-Darstellung
- [x] Intensitäts-basierte Färbung (0-1 normalisiert)

---

## ✅ PHASE 3.7: AI Coach - Plan-Generierung & Optimierung (100% KOMPLETT)

### Automatische Plan-Generierung
- [x] **KI-basierter Plan-Generator** (CLI Tool)
- [x] **Equipment-basierte Übungsauswahl** (nur vorhandene Geräte)
- [x] **Intelligente Split-Erstellung** (2-6 Tage/Woche)
- [x] **Push/Pull/Legs Balance** (wissenschaftlich fundiert)
- [x] **Volumen-Berechnung** (Sets × Reps pro Muskelgruppe)
- [x] **Training-Historie-Analyse** (letzte 30 Tage)
- [x] **Hybrid LLM System** (Ollama lokal, OpenRouter Fallback)
- [x] **Cost Tracking** (~0.003€ pro Plan)

### Automatische Plan-Optimierung (Hybrid-Ansatz)
- [x] **Stufe 1: Regelbasierte Performance-Checks** (kostenlos)
  - [x] RPE-Analyse (<7 → Gewicht erhöhen, >8.5 → Deload)
  - [x] Muskelgruppen-Balance (>14 Tage nicht trainiert)
  - [x] Plateau-Erkennung (1RM stagniert 4+ Wochen)
  - [x] Volumen-Trends (>20% Spike, >30% Drop)
- [x] **Stufe 2: KI-Optimierungsvorschläge** (~0.003€)
  - [x] LLM analysiert Performance-Historie
  - [x] Übungs-Ersatz (nur aus Equipment-Bestand)
  - [x] Volumen-Anpassungen (Sets/Reps)
  - [x] Deload-Empfehlungen
- [x] **Web-Interface für Plan-Optimierung**
  - [x] Performance-Warnings Card (Top 3 kritischste)
  - [x] Diff-Modal (Vorher/Nachher mit Begründungen)
  - [x] Checkbox-Selektion für Optimierungen
  - [x] Apply-Funktionalität (1-Klick Übernahme)
- [x] **API Endpoints**
  - [x] GET /api/analyze-plan/ (Regelbasiert, kostenlos)
  - [x] POST /api/optimize-plan/ (KI, ~0.003€)
  - [x] POST /api/apply-optimizations/ (DB Update)

### Live Training Guidance
- [x] **AI Coach Chat während Training**
- [x] **Context-aware Tipps** (kennt aktuelle Übung, Satz, RPE)
- [x] **Formcheck-Hinweise** (basierend auf RPE/Gewicht)
- [x] **Progressive Overload Beratung**
- [x] **Technique-Verbesserungsvorschläge**
- [x] **Cost: ~0.002€ pro Chat-Session**

### LLM Infrastructure
- [x] **Hybrid Client** (ai_coach/llm_client.py)
- [x] **Ollama Integration** (lokal, 0€)
- [x] **OpenRouter Fallback** (Cloud, ~0.003€)
- [x] **Smart Retry Logic** (3 Versuche mit Backoff)
- [x] **Secrets Manager** (sichere API Key Storage)
- [x] **Prompt Engineering** (ai_coach/prompt_builder.py)

---

## 🔄 PHASE 4: Erweiterte Features (20% - IN ARBEIT)

### In-App Plan-Editor
- [x] **Pläne in der App erstellen (ohne Admin)** ✅
- [x] **Übungen per Drag & Drop sortieren** ✅
- [x] **Plan bearbeiten/löschen** ✅
- [ ] Plan-Templates (Push/Pull/Legs, etc.)
- [ ] Plan duplizieren
- [ ] Plan teilen (QR-Code/Link)
- [ ] Öffentliche Plan-Bibliothek

### Übungsdatenbank
- [x] **Anatomische Muskelgruppen-Map** (SVG mit 50+ Regionen) ✅
- [x] **Übungs-Detail-Ansicht mit SVG-Visualisierung** ✅
- [x] **Muskelgruppen-Filter** ✅
- [ ] Video-Anleitungen hochladen
- [ ] Animationen für Übungen
- [ ] Alternative Übungen vorschlagen
- [ ] Übungen favorisieren (Quick-Access)
- [ ] Custom Übungen erstellen
- [ ] Tags für Übungen (Compound, Isolation, etc.)
- [ ] Schwierigkeitsgrad anzeigen

### PWA & Offline
- [x] Progressive Web App Setup ✅
- [x] Service Worker (Offline-Support) ✅
- [x] Manifest.json (Installierbar) ✅
- [ ] Push-Notifications aktivieren
- [ ] Sync bei Verbindung (Background Sync)
- [ ] Offline-Indikator (Connection Status)
- [ ] Offline-Datenspeicherung (IndexedDB)

### Themes & Customization
- [ ] Dark/Light Mode Toggle
- [ ] Farbschema-Auswahl (Primärfarbe)
- [ ] Dashboard personalisieren (Widgets)
- [ ] Widget-System (verschiebbar)
- [ ] Schriftgröße anpassen
- [ ] Compact/Comfortable View Mode

### Export & Backup
- [ ] CSV/Excel Export (alle Daten)
- [ ] PDF-Report generieren (Monats-/Jahresreport)
- [ ] Cloud-Backup (automatisch)
- [ ] Daten-Import (CSV)
- [ ] Google Drive Integration
- [ ] Backup-Erinnerungen

### Fortgeschrittene Analytics
- [ ] ML-basierte Trainingsempfehlungen
- [ ] Verletzungsrisiko-Erkennung (Volumen-Spikes)
- [ ] Plateau-Erkennung mit Lösungsvorschlägen
- [ ] Optimale Trainingsfrequenz berechnen
- [ ] Kraftvorhersage (z.B. "In 12 Wochen: 100kg Bankdrücken")
- [ ] Muskelgruppen-Priorisierung vorschlagen

---

## 🎯 PHASE 5: Next Features (Priorisiert nach Impact)

### 🔥 High Priority (Nächste 2-4 Wochen)

**1. Superset-Support beim Plan-Erstellen** ⭐ Impact: 9/10 | Aufwand: 4h ✅ FERTIG
- [x] **Superset-Gruppierung im Plan-Editor** ✅
  - Übungen beim Erstellen zu Supersätzen gruppieren
  - Visuelle Gruppierung (farbige Border + Badges)
  - Buttons "Keine / S1 / S2 / S3"
  - Hidden Input für superset_gruppe beim Speichern
- [x] **Superset während Training** (bereits vorhanden) ✅
  - Superset-Badge "S1", "S2" etc.
  - Manuelles Gruppieren im Training
- [x] **Backend Logic** ✅
  - PlanUebung.superset_gruppe Feld
  - Migration erstellt und ausgeführt
  - Speichern + Laden funktioniert

**Status:** ✅ Implementiert und getestet (10.01.2026)

**2. PDF Export Verbesserungen** ⭐ Impact: 8/10 | Aufwand: 4h
- [x] **Trainingsstatistik als PDF** (bereits vorhanden) ✅
- [ ] **Trainingsplan als PDF exportieren**
  - Clean Layout für Gym (A4, druckoptimiert)
  - Übungen mit Sets/Reps-Vorgaben
  - Muskelgruppen-Icons
  - QR-Code für Web-Zugriff zum Plan
- [ ] **Workout Card** (einzelner Trainingstag)
  - Kompaktes Format (Halbseite)
  - Checkboxen für Sätze
  - Platz für Gewicht/Wdh Notizen
- [ ] **Monats-Report PDF**
  - 1RM Progressions-Charts
  - Volumen-Zusammenfassung
  - PR-Highlights

**Warum:** PDF Statistik existiert, Plan-Export ist logische Ergänzung

**3. Plan-Templates** ⭐ Impact: 7/10 | Aufwand: 5h
- [ ] **Vordefinierte Plan-Templates**
  - Push/Pull/Legs (6 Tage)
  - Upper/Lower (4 Tage)
  - Full Body (3 Tage)
  - Bro-Split (5 Tage)
- [ ] **Template-Auswahl im Plan-Editor**
  - "Von Template starten" Button
  - Vorschau der Übungen
  - Anpassbar nach Equipment
- [ ] **Plan duplizieren**
  - Eigene Pläne als Basis für Varianten
  - Umbenennen + Anpassen
- [ ] **Plan-Export/Import (JSON)**
  - Pläne mit Community teilen
  - QR-Code generieren

**Warum:** Senkt Einstiegshürde massiv, schneller Start für neue User

**4. AI Coach UI-Verbesserungen** ⭐ Impact: 6/10 | Aufwand: 3h
- [x] **Plan-Generierung Web** (heute implementiert!) ✅
- [x] **Plan-Optimierung Web** (heute implementiert!) ✅
- [ ] **Auto-Suggest nach Training**
  - Button: "Plan optimieren?" nach jedem 3. Training
  - Zeigt Performance-Warnings im Dashboard
- [ ] **Onboarding-Tour**
  - Erste Schritte für AI Coach
  - Tooltips für Equipment-Setup
  - "Ersten Plan generieren" Wizard
- [ ] **Plan-Generierung verbessern**
  - Mehr Optionen (Fokus: Kraft/Hypertrophie/Ausdauer)
  - Trainingszeit-Vorgabe (45/60/90 Min)
  - Deload-Wochen einplanen

**Warum:** AI Coach ist Alleinstellungsmerkmal, UI-Polish wichtig

### ⚙️ Medium Priority (Nächste 1-2 Monate)

**4. Notizen & Kommentare erweitern** Impact: 6/10 | Aufwand: 3h
- [ ] **Satz-Notizen** (bereits vorhanden, aber UI verbessern)
- [ ] **Übungs-Notizen** (persistent, nicht nur pro Training)
- [ ] **Trainingstag-Kommentare** (Tagesform, Schlaf, Stress)
- [ ] **Rich Text Editor** (Bold, Listen, Emojis)

**5. Plan-Templates & Sharing** Impact: 6/10 | Aufwand: 5h
- [ ] **Plan-Templates** (Push/Pull/Legs, Upper/Lower, etc.)
- [ ] **Plan duplizieren** (als Basis für Anpassungen)
- [ ] **Plan-Export als JSON** (teilen mit anderen Usern)
- [ ] **Plan-Import** (JSON Upload)
- [ ] **QR-Code für Plan-Sharing**

**6. Erweiterte Equipment-Features** Impact: 5/10 | Aufwand: 4h
- [ ] **Equipment-Profil pro User** (bereits vorhanden, aber UI verbessern)
- [ ] **"Alternative Übungen"** (bei fehlendem Equipment)
- [ ] **Equipment-basierte Übungsfilter** (im Plan-Editor)
- [ ] **Equipment-Tracking** (Verfügbarkeit im Gym)

### 🔮 Low Priority (Later / Community-Request)

**7. Social Features** Impact: 4/10 | Aufwand: 10h+
- [ ] User-Profile (öffentlich/privat)
- [ ] Leaderboards (1RM Rankings)
- [ ] Workout-Sharing (Social Feed)
- [ ] Freunde hinzufügen
- [ ] Gemeinsame Challenges

**8. Ernährungs-Tracking** Impact: 3/10 | Aufwand: 15h+
- [ ] Kalorienzähler
- [ ] Makro-Tracking (Protein, Kohlenhydrate, Fett)
- [ ] Meal-Planner
- [ ] Barcode-Scanner für Lebensmittel

**Warum niedrige Prio:** MyFitnessPal & Co machen das bereits besser

**9. Wearables-Integration** Impact: 3/10 | Aufwand: 8h+
- [ ] Google Fit OAuth2 Integration
- [ ] Herzfrequenz-Daten importieren
- [ ] Schritte/Aktivität syncen
- [ ] Samsung Health Export/Import

**Warum niedrige Prio:** RPE ist für Krafttraining ausreichend, Aufwand/Nutzen schlecht

---

## 🎯 Empfohlene Reihenfolge (Nächste 4 Features)

1. **Superset beim Plan-Erstellen** (4h)
   - Model existiert bereits
   - Nur UI im Plan-Editor fehlt
   - Hoher User-Value

2. **Plan als PDF exportieren** (4h)
   - PDF-Export existiert bereits für Statistiken
   - Code wiederverwenden
   - Gym-freundliches Feature

3. **Plan-Templates** (5h)
   - Schnellstart für neue User
   - Reduziert Setup-Zeit massiv
   - Gute Community-Feature Basis

4. **AI Coach Auto-Suggest** (3h)
   - Macht AI Coach proaktiver
   - "Plan optimieren?" nach Training
   - Dashboard-Integration

**Gesamtaufwand:** ~16 Stunden für massive UX-Verbesserung

---

## 🐛 Bekannte Bugs & Verbesserungen

### Bugs
- [ ] --

### Verbesserungen
- [ ] **Loading-States bei API-Calls** (Spinner während LLM-Anfragen)
- [ ] **Undo-Funktion für gelöschte Sätze** (5 Sekunden Rückgängig-Fenster)
- [ ] **Keyboard-Shortcuts** (Enter = Speichern, Esc = Schließen)
- [ ] **Bessere Error-Messages** (User-freundliche Fehlerbeschreibungen)
- [ ] **Toast-Notifications** (statt Alerts für Erfolgs-Meldungen)
- [ ] **Autocomplete für Übungssuche** (Typeahead)

---

## 🎉 Neue Features in Version 0.4.0 (10.01.2026)

### AI Coach - Automatische Plan-Optimierung
Die App hat jetzt einen vollständigen AI Coach für automatische Plan-Anpassung:

1. **Regelbasierte Performance-Checks** (kostenlos)
   - RPE-Analyse: Warnt bei zu niedrig/hoch
   - Muskelgruppen-Balance: Erkennt vernachlässigte Muskelgruppen
   - Plateau-Erkennung: Identifiziert stagnierende Übungen (4+ Wochen)
   - Volumen-Trends: Warnt bei Spikes (>20%) oder Drops (>30%)

2. **KI-Optimierungsvorschläge** (~0.003€)
   - LLM analysiert Training-Historie (letzte 30 Tage)
   - Schlägt konkrete Änderungen vor (Übungs-Ersatz, Volumen-Anpassungen)
   - Nur Übungen aus deinem Equipment-Bestand
   - Diff-View: Vorher/Nachher mit Begründungen

3. **Web-Interface**
   - Performance-Warnings Card (zeigt Top 3 Probleme)
   - "KI-Optimierung starten" Button
   - Checkbox-Selektion für Änderungen
   - Apply-Funktionalität: Übernahme mit 1 Klick

4. **Hybrid-Ansatz**
   - Stufe 1 (Analyse): Immer kostenlos, regelbasiert
   - Stufe 2 (Optimierung): Optional, KI-gestützt, ~0.003€
   - Beste Balance zwischen Kosten und Mehrwert

### Technische Details
- **Backend:** ai_coach/plan_adapter.py (529 Zeilen)
- **API Endpoints:** 3 neue REST APIs (analyze, optimize, apply)
- **Frontend:** JavaScript Diff-Modal mit Live-Preview
- **LLM:** Ollama lokal (0€) oder OpenRouter Cloud (0.003€)

---

**Letzte Aktualisierung:** 10.01.2026  
**Nächstes Review:** Nach Abschluss Phase 5 (Next Features)
