# 🏋️ HomeGym App - Roadmap & Feature-Tracking

**Stand:** 09.02.2026
**Version:** 0.9.0

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
- [x] **Superset-Support** (S1-S5 Gruppen mit farbiger Visualisierung)

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
- [x] **Superset-Gruppierung im Plan** (S1-S5 Buttons, farbige Border, Badges)
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
- [x] **Cardio Lite Tracking** ✅ (30.01.2026)
  - 9 Aktivitäten (Schwimmen, Laufen, Radfahren, Rudern, Gehen, HIIT, Stepper, Seilspringen, Sonstiges)
  - 3 Intensitätsstufen (Leicht, Moderat, Intensiv)
  - Ermüdungspunkte-Berechnung (0.1-0.4 Punkte pro Minute)
  - Integration in Ermüdungsindex
  - Dashboard-Statistiken (Anzahl + Minuten diese Woche)
  - Cardio-Liste mit Lösch-Funktion
  - API-Endpoints: cardio/add/, cardio/list/, cardio/delete/

### Deload & Recovery Management
- [x] **Automatische Deload-Erkennung** (Warnung bei >20% Volumen-Spikes)
- [x] **Volumen-Drop Erkennung** (Warnung bei >30% Rückgang)
- [x] **Ermüdungs-Index** (0-100 Score aus Volumen-Spikes, hohem RPE, Trainingsfrequenz, Cardio-Fatigue)
  - Berücksichtigt Kraft-Training (Sets × RPE)
  - Berücksichtigt Cardio-Training (Ermüdungspunkte basierend auf Intensität × Dauer)
  - Max. 20 Punkte für Cardio-Ermüdung (bei 120+ Cardio-Fatigue-Punkten)
- [x] **Empfehlungen für Regeneration** (automatische Warnungen bei hoher Ermüdung)

### Social & Motivation
- [x] **PR-Benachrichtigungen** (Alert bei neuem 1RM-Rekord)
- [x] **Motivations-Quotes** (dynamische Motivation basierend auf Performance & Ermüdung)
  - High Performance Quotes (bei gutem Form-Index)
  - Good Performance Quotes (bei solidem Training)
  - Need Motivation Quotes (bei niedrigem Form-Index)
  - High Fatigue Quotes (bei hohem Ermüdungs-Index)

### Trainingsprogrammierung
- [x] Periodisierung (Linear, Wellenförmig, Block) ✅
- [x] Makrozyklus-Planung (12 Wochen, Deload jede 4. Woche) ✅
- [x] Mikrozyklus-Templates (zielabhängig: Kraft/Hypertrophie/Definition) ✅
- [x] Automatische Lastanpassung nach Zyklus (Volumen-Reset nach Deload, +Satz Progression) ✅
- [x] Deload-Wochen einplanen (80% Volumen, 90% Intensität) ✅
- [x] Ziel-Profile an KI übergeben (Kraft/Hypertrophie/Definition) für RPE- und Wdh.-Zonen ✅
- [x] **Web-Interface für Periodisierung & Zielprofil-Auswahl** ✅ (24.01.2026)

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

## 🔄 PHASE 4: Erweiterte Features (65% - IN ARBEIT)

### In-App Plan-Editor
- [x] **Pläne in der App erstellen (ohne Admin)** ✅
- [x] **Übungen per Drag & Drop sortieren** ✅
- [x] **Plan bearbeiten/löschen** ✅
- [x] **Plan-Templates** (Push/Pull/Legs, Upper/Lower, Full Body) ✅
  - 3 vordefinierte Templates (6-Tage, 4-Tage, 3-Tage Splits)
  - Equipment-basierte Anpassung (automatische Substitution)
  - Template-Auswahl Modal mit Detailansicht
  - Erstellt separate Pläne pro Trainingstag
- [x] **Plan PDF-Export** (mit QR-Code) ✅
  - xhtml2pdf Integration
  - QR-Code für Plan-Link
  - Übersichtstabelle mit Muskelgruppen
  - Professionelles Layout
- [x] **Plan/Gruppe duplizieren** ✅ (01.02.2026)
  - Einzelne Pläne duplizieren
  - Komplette Gruppen (Splits) duplizieren
  - Automatische "(Kopie)"-Benennung
  - Übernimmt alle Übungen, Superset-Gruppen, Pausenzeiten
- [x] **Plan/Gruppe teilen (QR-Code/Link)** ✅ (01.02.2026)
  - Dedizierte Share-Seite pro Plan/Gruppe
  - QR-Code Generator für mobiles Scannen
  - Direkter Link zum Kopieren
  - Teilen via WhatsApp, Telegram, E-Mail
  - Öffentlich/Privat Toggle
- [x] **Öffentliche Plan-Bibliothek** ✅ (01.02.2026)
  - Durchsuchbare Bibliothek aller öffentlichen Pläne
  - Gruppierte Anzeige von Split-Plänen
  - 1-Klick Kopieren in eigene Sammlung
  - Suchfunktion
  - Link im Footer für alle Nutzer

### Übungsdatenbank
- [x] **Anatomische Muskelgruppen-Map** (SVG mit 50+ Regionen) ✅
- [x] **Übungs-Detail-Ansicht mit SVG-Visualisierung** ✅
- [x] **Muskelgruppen-Filter** ✅
- [x] **Übungs-Detail: Beschreibung + persönliche Statistik (1RM/Volumen/Sets + Chart)** ✅
- [x] **Band-Alternativen für Kabelzug-Übungen** (Crossover, Crunches, Lat Pulldown, Straight-Arm Pulldown, Trizeps Pushdown) ✅
- [x] **Cardio/Ganzkörper Ergänzungen** (Burpees, Jump Squats, Bear Crawls, High Knees, Broad Jumps) ✅
- [x] **Datenbereinigung & Coverage** (Equipment-Mappings gefixt, Coverage ~91% mit vorhandenem Equipment) ✅
- [x] **Video-Support** ✅ (01.02.2026)
  - video_link Feld im Uebung Model
  - Unterstützt YouTube & Vimeo URLs
  - Auto-Konvertierung zu Embed-Format
  - Video-Player in Exercise Info Modal
- [ ] Animationen für Übungen
- [ ] Alternative Übungen vorschlagen
- [x] **Übungen favorisieren** ✅ (04.02.2026)
  - Stern-Button in Übungsliste und Detail-Ansicht
  - Toggle-Favorit API-Endpoint
  - "Nur Favoriten anzeigen" Filter
  - Toast-Benachrichtigungen
  - ManyToMany User-Übung Relation
- [x] **Custom Übungen erstellen** ✅ (04.02.2026)
  - Model CustomUebung mit user, name, muskelgruppen, beschreibung, equipment
  - UI im Plan-Editor und Training-Session
  - CRUD API-Endpoints + Templates
  - Integration in Übungsauswahl mit Filter "Meine Übungen"
- [x] **Tags für Übungen** ✅ (04.02.2026)
  - 12 Tag-Kategorien (Compound, Isolation, Beginner, Advanced, etc.)
  - Farbige Badges in Übungskarten
  - Tag-Filter in Übungsliste (kombinierbar mit Suche + Favoriten)
  - Admin-Interface mit Farb-Preview
  - 54+ Standard-Übungen automatisch getaggt
- [ ] Schwierigkeitsgrad anzeigen
- [x] **Equipment-Manager UI** ✅ (04.02.2026)
  - 6 Kategorien mit Icons (Freie Gewichte, Racks, Bänke, Maschinen, Funktionell, Basics)
  - Live-Suche und Kategorie-Filter
  - Card-basiertes Layout mit optimistic UI
  - Alternative Übungen API-Endpoint
  - Verbesserte Presets (Home Basic/Advanced, Fitness Studio, Bodyweight)

### PWA & Offline
- [x] Progressive Web App Setup ✅
- [x] Service Worker (Offline-Support) ✅
- [x] Manifest.json (Installierbar) ✅
- [x] **Offline-Indikator (Connection Status)** ✅ (16.01.2026)
  - Zeigt Online/Offline Status rechts oben
  - Toast-Benachrichtigungen bei Verbindungswechsel
  - Automatische Erkennung via navigator.onLine
- [x] **Offline-Datenspeicherung (IndexedDB)** ✅ (16.01.2026)
  - Object Stores für trainingData, exercises, plans
  - Sync-Status Tracking (synced/unsynced)
  - CRUD Operations mit async/await
- [x] **Background Sync** ✅ (16.01.2026)
  - Automatisches Syncen wenn Verbindung zurück
  - Retry-Logic bei Fehlern
  - Markiert gesyncte Daten in IndexedDB
- [x] **Push-Notifications** ✅ (05.02.2026)
  - PushSubscription Model (user, endpoint, p256dh, auth)
  - API-Endpoints: subscribe, unsubscribe, vapid-key
  - PushNotificationsManager Class (JavaScript)
  - send_push_notification() Utility-Funktion
  - VAPID Keys Support (generate_vapid_keys.py)
  - Notification Preferences (training, rest day, achievements)
  - pywebpush Integration

**Status:** ✅ 100% Komplett (7/7 Features)

**Dateien:**
- `core/static/core/js/offline-manager.js` (280 Zeilen - IndexedDB Manager)
- `core/static/core/css/offline-manager.css` (110 Zeilen - Connection UI)
- `core/static/core/service-worker.js` (Enhanced Background Sync)
- `PWA_OFFLINE_GUIDE.md` (Integration Guide)

**Technische Details:**
- IndexedDB mit 3 Object Stores (trainingData, exercises, plans)
- Service Worker mit Cache-First und Network-First Strategien
- Background Sync registriert via `navigator.serviceWorker.sync`
- Connection Status UI (Indicator + Toast)

### Themes & Customization
- [x] **Dark/Light Mode Toggle** ✅ (Globales Theme-System mit JavaScript)
  - Theme-Toggle Button in allen Templates (15+ Seiten)
  - LocalStorage Persistenz
  - Theme-aware Cards, Heatmaps, List-Items
  - Automatisches Theme-Loading (FOUC-Prevention)
  - theme-toggle.js + theme-styles.css
- [ ] Farbschema-Auswahl (Primärfarbe)
- [ ] Dashboard personalisieren (Widgets)
- [ ] Widget-System (verschiebbar)
- [ ] Schriftgröße anpassen
- [ ] Compact/Comfortable View Mode

### Export & Backup
- [x] **CSV-Export** ✅ (09.02.2026) - Alle Trainingsdaten als CSV-Download
- [x] **PDF-Report generieren** ✅ (11.01.2026)
  - Trainings-Statistik Report (Multi-Page)
  - Body-Map Visualisierung
  - Muskelgruppen-Analyse mit Charts
  - Push/Pull Balance Assessment
  - Intelligente Empfehlungen
- [ ] Cloud-Backup (automatisch)
- [ ] Daten-Import (CSV)
- [ ] Google Drive Integration
- [ ] Backup-Erinnerungen

### Fortgeschrittene Analytics
- [x] **KI-basierte Trainingsempfehlungen** ✅ (AI Coach mit LLM)
  - Plan-Generierung mit Historie-Analyse
  - Plan-Optimierung mit Performance-Checks
  - Live Training Guidance
  - Hybrid System: Ollama (lokal, kostenlos) + OpenRouter Fallback (Cloud, ~0.003€)
- [x] **ML-Vorhersagemodelle** ✅ (05.02.2026)
  - Kraftvorhersage basierend auf Trainingshistorie (scikit-learn Random Forest Regressor)
  - Optimale Trainingsfrequenz-Empfehlung (ML-basierte Analyse)
  - Personalisierte Volumen-Empfehlungen (trainiert auf individuellen Daten)
  - **Tech-Stack:** scikit-learn 1.6.1, joblib 1.5.0 (benötigt KEINE GPU, läuft auf CPU)
  - **Training:** <5 Sekunden pro User-Modell (kleine Datensätze)
  - **Inferenz:** <10ms für Vorhersagen
  - **API Endpoints:** /api/ml/train/, /api/ml/predict/<id>/, /api/ml/model-info/<id>/
  - **Dashboard:** /ml/dashboard/ mit Modell-Übersicht
  - **Management Command:** python manage.py train_ml_models
  - **Vorteil:** Kostenlos, privat, offline-fähig, keine API-Calls, keine GPU nötig
- [x] **Verletzungsrisiko-Erkennung** ✅ (Volumen-Spikes + Cardio-Fatigue im Ermüdungsindex)
- [x] **Plateau-Erkennung** ✅ (AI Coach erkennt stagnierende Übungen 4+ Wochen)
- [x] **1RM Kraftstandards & Leistungsbewertung** ✅ (09.02.2026)
  - 4 Leistungsstufen pro Übung: Anfänger, Fortgeschritten, Erfahren, Elite
  - Körpergewicht-skalierte Standards (Referenz: 80kg)
  - 6-Monats 1RM-Entwicklung pro Übung (Epley-Formel)
  - Fortschrittsbalken zum nächsten Level
  - Standards in Uebung-Model gespeichert (Migration 0052/0053)
  - Automatische Befüllung via populate-Migration
- [x] **Advanced Training Statistics** ✅ (09.02.2026)
  - Plateau-Analyse mit 5 Status-Stufen (Progression → Langzeit-Plateau)
  - Konsistenz-Metriken (Streak, Adherence-Rate, Avg. Pause)
  - Erweiterter Ermüdungs-Index mit Deload-Empfehlungen
  - RPE-Qualitätsanalyse (Junk Volume, Optimal Intensity, Failure Rate)
  - Modulares Utility-System (`core/utils/advanced_stats.py`, 587 Zeilen)
- [x] **CSV-Export** ✅ (09.02.2026)
  - Alle Trainingsdaten als CSV-Download (Datum, Übung, Gewicht, Wdh, RPE, Volumen)
  - UTF-8 BOM für korrekte Excel-Darstellung
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

**2. PDF Export Verbesserungen** ⭐ Impact: 8/10 | Aufwand: 4h ✅ FERTIG
- [x] **Professioneller Training Report PDF** ✅
  - Executive Summary mit Trainings-Metriken
  - Datenqualitäts-Warnung (bei < 8 Trainings)
  - Körperwerte-Entwicklung (Gewicht, Umfänge)
  - Muskelgruppen-Analyse mit Status-Badges
  - Intelligente Formulierungen bei wenig Daten
- [x] **SVG Body-Map Integration im PDF** ✅
  - Anatomische Visualisierung (1100x1024px)
  - Dynamische Farbcodierung (grün/gelb/rot basierend auf Training)
  - Cairosvg-Rendering für hochwertige Darstellung
  - PIL-Fallback bei fehlender Cairo-Library
  - Legende mit Farbcodierung
- [x] **Matplotlib Charts im PDF** ✅
  - Muskelgruppen-Balance Visualisierung (Horizontal Bar Chart)
  - Trainingsvolumen-Entwicklung (Line Chart, letzte 8 Wochen)
  - Push/Pull Balance (Pie Chart)
- [x] **Plan-PDF Export** ✅
  - Trainingsplan als druckbares PDF
  - QR-Code mit Link zum Plan
  - Übersichtstabelle (Übung, Muskelgruppe, Sätze, Wiederholungen)
  - Gruppierung nach Trainingstagen
  - xhtml2pdf + qrcode Integration

**Status:** ✅ Implementiert und getestet (10.01.2026 + 11.01.2026)
- [x] **Multi-Page Layout** ✅
  - Deckblatt mit Body-Map
  - Inhaltsverzeichnis
  - Separate Seiten für Kapitel (Executive Summary, Muskelgruppen, Push/Pull, Trainingsfortschritt, Empfehlungen)
  - Page-break-Kontrolle (Überschriften mit Grafiken zusammenhalten)
- [x] **Intelligente Empfehlungen** ✅
  - Stärken & Schwachstellen Analyse
  - Push/Pull Balance-Bewertung (0.9:1 - 1.1:1 optimal)
  - Nächste Schritte (priorisiert)
  - Kraftentwicklung Top 5
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

**Status:** ✅ PDF-Statistik vollständig implementiert (11.01.2026)
**Details:**
- Professionelles Multi-Page Design
- Anatomische Body-Map mit User-Daten
- 3 Matplotlib Charts
- Intelligente Analysen mit Datenqualitäts-Checks
- xhtml2pdf-kompatibles CSS (CSS2.1)

**Warum:** Professioneller Export für Trainer & Athleten, Trainingsplan-PDF ist logische Ergänzung

**3. Plan-Templates** ⭐ Impact: 7/10 | Aufwand: 5h ✅ FERTIG
- [x] **Vordefinierte Plan-Templates** ✅
  - Push/Pull/Legs (6 Tage Split)
  - Upper/Lower (4 Tage Split)
  - Full Body (3 Tage Split)
  - JSON-basiert (core/fixtures/plan_templates.json)
  - ~80 Übungen über alle Templates
- [x] **Template-Auswahl im Plan-Editor** ✅
  - "Von Template starten" Button in create_plan.html
  - Modal mit Template-Übersicht (Karten-Layout)
  - Detail-Ansicht mit allen Trainingstagen
  - Equipment-basierte Anpassung (verfügbar/nicht verfügbar Badges)
- [x] **Equipment-basierte Anpassung** ✅
  - Automatische Substitution fehlender Übungen
  - find_substitute_exercise() Funktion
  - Case-insensitive Equipment-Matching
  - Fallback auf Körpergewicht-Übungen
- [x] **API Endpoints** ✅
  - GET /api/plan-templates/ (Template-Liste)
  - GET /api/plan-templates/<key>/ (Detail mit Equipment-Check)
  - POST /api/plan-templates/<key>/create/ (Plan-Erstellung)
- [x] **Plan-Erstellung Logic** ✅
  - Erstellt separaten Plan pro Trainingstag
  - trainingstag-Feld wird gesetzt (z.B. "Push A")
  - Automatische Übungs-Substitution bei fehlendem Equipment
  - Weiterleitung zum Dashboard nach Erstellung

**Status:** ✅ Implementiert und getestet (11.01.2026)
**Technische Details:**
- 3 Templates mit wissenschaftlich fundierter Übungsauswahl
- Equipment-Smart: passt sich an User-Equipment an
- Separate Pläne: jeder Tag = 1 eigener Plan (z.B. "Push A", "Pull A", "Legs A")
- JavaScript Fetch API für dynamisches Laden
- Bootstrap Modal UI

**Warum:** Anfänger brauchen fertige Templates statt leere Plan-Erstellung

**4. Equipment-Manager** ⭐ Impact: 6/10 | Aufwand: 3h
- [ ] **Plan duplizieren**
  - Eigene Pläne als Basis für Varianten
  - Umbenennen + Anpassen
- [ ] **Plan-Export/Import (JSON)**
  - Pläne mit Community teilen
  - QR-Code generieren

**Warum:** Senkt Einstiegshürde massiv, schneller Start für neue User

**4. AI Coach UI-Verbesserungen** ⭐ Impact: 6/10 | Aufwand: 3h ✅ FERTIG
- [x] **Plan-Generierung Web** ✅
- [x] **Plan-Optimierung Web** ✅
- [x] **Auto-Suggest nach Training** ✅ (04.02.2026)
  - Button: "Plan optimieren?" nach jedem 3. Training
  - Zeigt Performance-Warnings im Dashboard
  - Proaktive Empfehlungen basierend auf Trainingshistorie
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

**4. Notizen & Kommentare erweitern** Impact: 6/10 | Aufwand: 4h (1h bereits investiert)
- [x] **Satz-Notizen mit Quick-Tags** ✅ (05.02.2026)
  - 5 Emoji-Tag-Buttons (⭐ Perfekt, 👍 Gut, ⚠️ Schwierig, 🤕 Mit Hilfe, 😓 Schmerz)
  - insertTag(), clearNotiz(), updateCharCount() Funktionen
  - Zeichenzähler (0/500)
  - Notizen pro Satz persistent mit Anzeige in Historie
- [ ] **Übungs-Notizen** (persistent, nicht nur pro Training)
  - Separate Notiz pro Übung (unabhängig von Training)
  - "Technik-Tipps", "Setup-Hinweise", "Warnung"
  - Anzeige in Übungsauswahl und Training
- [ ] **Trainingstag-Kommentare** (Tagesform, Schlaf, Stress)
  - Tagesform-Scale (1-10)
  - Schlafqualität (1-10), Stress-Level (1-10)
  - Freitext-Kommentar
- [ ] **Rich Text Editor für Notizen** (Bold, Listen, erweiterter Emoji-Picker)

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
- [x] **Plan-Sharing** ✅ (01.02.2026)
  - Öffentliche Plan-Bibliothek
  - QR-Code & Link-Sharing
  - Shared Plans Übersicht
  - Trainingspartner einladen
- [x] **Feedback-System** ✅ (28.01.2026)
  - Feedback erstellen (Feature-Request, Bug, Verbesserung)
  - Feedback-Liste mit Filter
  - Admin-Kommentare
  - Status-Tracking (Offen, In Bearbeitung, Erledigt)
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

## 🎯 Nächste Schritte (Priorisiert nach Impact & User-Feedback)

### 🔥 Sofort (Nächste 1-2 Tage)

**1. Beta-Feature-Discovery verbessern** ⭐ Impact: 8/10 | Aufwand: 2h
- [ ] **Onboarding-Tour für neue Beta-User**
  - Tooltip-System mit Intro.js oder Shepherd.js
  - Highlight wichtiger Features (Gewichtsempfehlungen, AI Coach, Plan-Templates)
  - "Tour überspringen" Option
- [ ] **Feature-Hints im Training**
  - Erste 3 Trainings: Hinweis auf Gewichtsempfehlungen
  - Erste 5 Trainings: Hinweis auf Quick-Tags für Notizen
  - "Tipp des Tages" Carousel im Dashboard
- [ ] **Beta-Feature-Liste im Dashboard**
  - Collapsible Card "🎉 Neue Features"
  - Checkboxen zum Abhaken (LocalStorage)
  - Link zu detaillierter Doku

**Warum jetzt:** User finden Features nicht (Gewichtsempfehlungen waren versteckt)

### 🚀 Kurzfristig (Nächste 1-2 Wochen)

**2. Gewichtsempfehlungen UI-Polish** ⭐ Impact: 7/10 | Aufwand: 3h
- [ ] **Auffälligere Darstellung**
  - Animierter Einblend-Effekt beim Öffnen einer Übung
  - Pulsierender Badge bei neuer Empfehlung
  - Farbcodierung (Grün = mehr Gewicht, Gelb = mehr Wdh, Blau = halten)
- [ ] **Progressive Overload Visualisierung**
  - Mini-Chart: Gewichtsverlauf letzte 5 Sessions
  - "Streak" Anzeige (z.B. "3× in Folge gesteigert 🔥")
  - Progression Badge (z.B. "+12.5kg in 4 Wochen")
- [ ] **Empfehlungen als Overlay-Cards**
  - Erscheint beim ersten Satz einer Übung
  - "Übernehmen" Button zum Auto-Fill
  - "Eigenes Gewicht wählen" Option

**Warum wichtig:** Feature ist jetzt voll funktional, aber noch zu unauffällig

**3. Notizen-System erweitern** ⭐ Impact: 6/10 | Aufwand: 3h (Quick-Tags bereits implementiert)
- [x] **Satz-Notizen mit Quick-Tags** ✅ (05.02.2026)
  - 5 Emoji-Tags, insertTag(), clearNotiz(), Zeichenzähler
  - Notizen persistent pro Satz mit Historie-Anzeige
- [ ] **Übungs-Notizen (persistent)**
  - Separate Notiz pro Übung (nicht nur pro Training)
  - "Technik-Tipps", "Setup-Hinweise", "Warnung"
  - Anzeige in Übungsauswahl und Training
- [ ] **Trainingstag-Kommentare**
  - Tagesform-Scale (1-10)
  - Schlafqualität (1-10)
  - Stress-Level (1-10)
  - Freitext-Kommentar
- [ ] **Rich Text Editor für Notizen**
  - Bold, Italic, Listen
  - Emoji-Picker (erweitert)
  - Text-Formatierung
- [ ] **Notizen-Historie**
  - Alle Notizen einer Übung durchsuchbar
  - Datum + Training-ID
  - "Häufigste Tags" Analyse

**Warum jetzt:** Quick-Tags existieren schon, Erweiterung liegt nahe

### 📊 Mittelfristig (Nächste 2-4 Wochen)

**4. Enhanced Training Analytics** ⭐ Impact: 8/10 | Aufwand: 4h (Cardio ✅ bereits integriert)
- [x] **Training-Heatmap mit Cardio** ✅ (30.01.2026)
  - Heatmap zeigt Kraft-Training
  - Cardio-Einheiten werden im Ermüdungsindex berücksichtigt
- [x] **Cardio-Statistiken im Dashboard** ✅
  - Anzahl Cardio-Einheiten diese Woche
  - Gesamt-Minuten diese Woche
  - Integration in Ermüdungsindex (Fatigue-Punkte)
- [ ] **Training-Heatmap erweitern**
  - Volumen pro Tag (Farbintensität)
  - Tooltip mit Details (Übungen, Sets, Volumen)
  - Filter: Nur Kraft / Nur Cardio / Beides
- [ ] **Muscle Group Timeline**
  - Wann wurde welche Muskelgruppe zuletzt trainiert?
  - Ampel-System (Grün < 3 Tage, Gelb 3-7, Rot > 7)
  - "Training empfohlen" Vorschläge
- [ ] **Recovery Score**
  - 0-100 basierend auf: letzte Trainings, Schlaf, Tagesform
  - Empfehlung: "Heute Beine trainieren?" vs "Ruhetag?"
  - Integration mit Cardio-Daten

**5. Plan-Optimierung V2** ⭐ Impact: 7/10 | Aufwand: 5h
- [ ] **Automatische Deload-Erkennung**
  - Warnt bei 4+ Wochen ohne Deload
  - Schlägt automatisch Deload-Woche vor
  - "Jetzt Deload einplanen" Button
- [ ] **Plateau-Breaking Vorschläge**
  - Erkennt stagnierende Übungen (4+ Wochen kein Progress)
  - Schlägt Variationen vor (Tempo, Griff, Winkel)
  - Equipment-basierte Alternativen
- [ ] **Volume Landmarks**
  - "Du hast 10.000kg Volumen erreicht! 🎉"
  - Monatliche/Wöchentliche Milestones
  - Vergleich mit eigenem Durchschnitt

**6. Mobile PWA Optimierungen** ⭐ Impact: 6/10 | Aufwand: 4h
- [ ] **Fullscreen-Modus im Training**
  - Verstecke Navbar beim Scrollen
  - Fokus auf aktuelle Übung
  - Swipe-Gesten (nächste Übung)
- [ ] **Haptic Feedback**
  - Vibration bei Satz gespeichert
  - Vibration bei Timer-Ende (bereits vorhanden?)
  - Vibration bei neuer PR
- [ ] **Voice Input (experimentell)**
  - "45 kg mal 10" → auto-fill
  - "RPE 8" → RPE setzen
  - Web Speech API

### 🔮 Langfristig (1-2 Monate)

**7. Social & Community** ⭐ Impact: 7/10 | Aufwand: 15h+
- [ ] Öffentliche Profile (opt-in)
- [ ] Leaderboards (1RM, Volumen, Streak)
- [ ] Plan-Sharing erweitern (Kommentare, Bewertungen)
- [ ] Training-Feed ("User X hat heute 5000kg Volumen!")

**8. KI-Coach Erweiterungen** ⭐ Impact: 8/10 | Aufwand: 10h+
- [ ] Video-Analyse (Formcheck via Kamera)
- [ ] Sprachassistent während Training
- [ ] Automatische Exercise-Logging (Kamera erkennt Übung)
- [ ] Predictive Analytics ("In 8 Wochen: 100kg Bankdrücken")

---

## 📋 Empfohlene Umsetzungs-Reihenfolge

**Phase 1 (Nächste Woche):**
1. Beta-Feature-Discovery (2h) - Kritisch für User-Adoption
2. Gewichtsempfehlungen UI-Polish (3h) - Feature ist da, braucht Sichtbarkeit
**Gesamt: 5h**

**Phase 2 (Woche 2-3):**
3. Notizen-System erweitern (3h) - Quick-Tags ✅ bereits fertig, erweitern auf Übungs- & Trainingstag-Notizen
4. Enhanced Training Analytics (4h) - Cardio ✅ bereits integriert, erweitern Heatmap + Timeline
**Gesamt: 7h**

**Phase 3 (Woche 4-6):**
5. Plan-Optimierung V2 (5h)
6. Mobile PWA Optimierungen (4h)
**Gesamt: 9h**

**Gesamtaufwand Phase 1-3:** ~21 Stunden für massive UX-Verbesserung und User-Engagement (Quick-Tags ✅ 1h + Cardio ✅ 2h bereits fertig)

---

## 🐛 Bekannte Bugs & Verbesserungen

### Bugs
- [ ] --

### Bug-Fixes (05.02.2026)
- [x] **Gewichtsempfehlungen für freie Trainings** ✅
  - Funktionierten vorher nur bei Trainings MIT Plan
  - Jetzt auch für freie Trainings verfügbar
  - Backend berechnet Empfehlungen für alle Übungen im aktuellen Training
- [x] **JavaScript Rendering-Bug behoben** ✅
  - Fehlendes `<script>`-Tag in training_session.html
  - JavaScript-Code wurde als Text auf Seite angezeigt
  - Notiz-Funktionen (insertTag, clearNotiz, updateCharCount) nun korrekt ausgeführt
- [x] **Service Worker Cache v5** ✅
  - Cache-Version erhöht für Browser-Update
  - Alte JavaScript-Versionen werden nicht mehr cached
- [x] **Push-Notifications vollständig implementiert** ✅
  - Backend: PushSubscription Model, API-Endpoints, send_push_notification()
  - Frontend: PushNotificationsManager mit subscribe/unsubscribe
  - Infrastructure: VAPID Keys, pywebpush Integration
- [x] **Security Fixes** ✅ (30.01-04.02.2026)
  - Fixed XSS vulnerability in AI Chat (textContent statt innerHTML)
  - Fixed Information Disclosure in API responses (removed technical error details)
  - Fixed ReDoS vulnerability (bounded regex quantifiers)
  - URL Sanitization in sharing features
  - GitHub CodeQL Alerts closed (31+ alerts resolved)

### Verbesserungen
- [x] **Undo-Funktion für gelöschte Sätze** ✅ (04.02.2026)
  - 5 Sekunden Rückgängig-Fenster
  - Toast mit "Rückgängig"-Button
  - Optimistic UI (Satz wird sofort ausgeblendet)
  - Countdown-Animation (Progress Bar)
- [x] **Keyboard-Shortcuts** ✅ (04.02.2026)
  - Enter = Satz speichern (in Modals)
  - Esc = Modal schließen
  - N = Neuer Satz (nur im Training)
  - S = Satz hinzufügen (nur im Training)
  - Visuelle Badges mit Shortcuts
- [x] **Autocomplete für Übungssuche** ✅ (04.02.2026)
  - Fuzzy matching
  - Tastatur-Navigation (↑↓Enter)
  - Highlight-Match
  - Score-basiertes Ranking
  - Integration in training_session.html
- [x] **Notiz-System mit Quick-Tags** ✅ (05.02.2026)
  - 5 Emoji-Tag-Buttons (⭐ Perfekt, 👍 Gut, ⚠️ Schwierig, 🤕 Mit Hilfe, 😓 Schmerz)
  - insertTag(), clearNotiz(), updateCharCount() Funktionen
  - Zeichenzähler (0/500)
  - Notizen pro Satz persistent
  - Anzeige in Trainingshistorie
- [ ] **Bessere Error-Messages** (User-freundliche Fehlerbeschreibungen)
- [x] **Toast-Notifications** (statt Alerts für Erfolgs-Meldungen) ✅ (03.02.2026)

---

## 🎉 Neue Features in Version 0.9.0 (09.02.2026)

### 1RM Kraftstandards & Leistungsbewertung
Übungen haben jetzt evidenzbasierte Kraftstandards zur Einordnung der eigenen Leistung:

1. **4 Leistungsstufen pro Übung**
   - Anfänger, Fortgeschritten, Erfahren, Elite
   - Standards basierend auf 80kg Referenz-Körpergewicht
   - Automatische Skalierung auf individuelles Körpergewicht

2. **1RM-Berechnung & Vergleich**
   - Epley-Formel: 1RM = Gewicht × (1 + Wiederholungen/30)
   - 6-Monats 1RM-Entwicklung pro Übung
   - Fortschrittsbalken zum nächsten Level
   - Vergleich mit Leistungsstandards

3. **Datenbank-Integration**
   - Felder: `standard_beginner`, `standard_intermediate`, `standard_advanced`, `standard_elite` im Uebung-Model
   - Migration 0052: Schema-Erweiterung
   - Migration 0053: Automatische Befüllung mit Standards für alle Hauptübungen

**Technische Details:**
- Model: `Uebung` erweitert um 4 DecimalFields
- Utils: `calculate_1rm_standards()` in `core/utils/advanced_stats.py`
- Skalierung: `standard × (user_gewicht / 80.0)`

### Advanced Training Statistics (Erweiterter PDF-Report)
Der PDF-Report wurde um 5 neue Analyse-Module erweitert:

1. **Plateau-Analyse**
   - 5 Status-Stufen: Aktive Progression → Beobachten → Leichtes Plateau → Plateau → Langzeit-Plateau
   - Regression-Erkennung (>10% Leistungsabfall)
   - Progression pro Monat (kg/Monat)
   - Farbcodierte Status-Badges (success/warning/danger)

2. **Konsistenz-Metriken**
   - Aktueller Streak (Wochen in Folge mit Training)
   - Längster Streak aller Zeiten
   - Adherence-Rate (% der Wochen mit Training)
   - Durchschnittliche Pause zwischen Trainings
   - 5-stufige Bewertung (Exzellent → Inkonsistent)

3. **Erweiterter Ermüdungs-Index**
   - Volumen-Spike Detection (40% Gewichtung)
   - RPE-Trend Analyse (30% Gewichtung)
   - Trainingsfrequenz-Bewertung (30% Gewichtung)
   - Deload-Empfehlungen mit Datum
   - 4-stufige Warnstufen (Niedrig → Kritisch)

4. **RPE-Qualitätsanalyse**
   - Optimale Intensitätsrate (% Sätze bei RPE 7-9)
   - Junk Volume Rate (% Sätze bei RPE <6)
   - Failure Rate (% Sätze bei RPE 10)
   - Empfehlungen zur Trainingsintensität
   - 4-stufige Bewertung (Exzellent → Verbesserung nötig)

5. **CSV-Export**
   - Alle Trainingsdaten als CSV-Download
   - Felder: Datum, Übung, Muskelgruppe, Satz Nr., Gewicht, Wdh, RPE, Volumen, Aufwärmsatz, Notiz
   - UTF-8 BOM für korrekte Excel-Darstellung

**Technische Details:**
- `core/utils/advanced_stats.py` (587 Zeilen - 5 Analyse-Funktionen)
- `core/views/export.py` (erweiterter PDF-Export + CSV-Export)
- `core/templates/core/training_pdf_simple.html` (erweitert um ~450 Zeilen)
- Fixtures: `initial_exercises.json` aktualisiert mit 1RM Standards
- Validierung: `validate_exercises_json.py` für Datenintegrität

---

## 🎉 Neue Features in Version 0.8.0 (30.01-05.02.2026)

### Cardio Lite Tracking
Einfaches Ausdauertraining-Tracking ohne Trainingsplan:

1. **CardioEinheit Model**
   - 9 Aktivitäten: Schwimmen, Laufen, Radfahren, Rudern, Gehen/Walking, HIIT, Stepper/Crosstrainer, Seilspringen, Sonstiges
   - 3 Intensitätsstufen: Leicht (Zone 2), Moderat (Zone 3), Intensiv (Zone 4-5)
   - Dauer in Minuten, Datum, optionale Notiz

2. **Ermüdungspunkte-System**
   - LEICHT: 0.1 Punkte/Min (z.B. 30 Min = 3.0 Punkte)
   - MODERAT: 0.2 Punkte/Min (z.B. 45 Min = 9.0 Punkte)
   - INTENSIV: 0.4 Punkte/Min (z.B. 20 Min HIIT = 8.0 Punkte)
   - Integration in Ermüdungsindex (max. 20 Punkte bei 120+ Fatigue-Punkten)

3. **Dashboard-Integration**
   - Cardio diese Woche: Anzahl Einheiten
   - Cardio-Minuten diese Woche
   - Ermüdungs-Index berücksichtigt Cardio-Volumen

4. **UI & Features**
   - Schnelles Hinzufügen: cardio/add/
   - Übersicht: cardio/list/ mit Datum, Aktivität, Dauer, Intensität
   - Löschen-Funktion: cardio/delete/{id}/
   - Toast-Benachrichtigungen

**Technische Details:**
- Model: `CardioEinheit` in core/models.py
- Views: cardio_add, cardio_list, cardio_delete
- Templates: cardio_add.html, cardio_list.html
- API-Integration: Ermüdungsindex + Dashboard-Metriken

**Warum wichtig:** Viele User machen zusätzlich Ausdauertraining, das jetzt ohne komplexen Trainingsplan getrackt werden kann. Ermüdungsindex wird genauer durch Cardio-Einbeziehung.

### Video-Support für Übungen
Übungen können jetzt Video-Anleitungen haben:

1. **Video-Link Integration**
   - Feld `video_link` im Uebung Model
   - Unterstützt YouTube & Vimeo URLs
   - Auto-Konvertierung zu Embed-Format

2. **Anzeige**
   - Video-Player in Exercise Info Modal
   - Responsive Einbettung (16:9)
   - Fallback wenn kein Video vorhanden

**Technische Details:**
- Migration: alter video_link CharField
- Admin: Video-URL-Eingabe mit Vorschau
- Template: Einbettung via iframe

### Security & Maintenance
- **GitHub Security Alerts behoben (31+ Alerts):**
  - XSS in AI Chat (textContent statt innerHTML)
  - Information Disclosure in API responses
  - ReDoS vulnerability (bounded regex)
  - URL Sanitization
- **Code-Qualität:**
  - Improved error handling
  - Input validation
  - Safe string interpolation

---

## 🎉 Neue Features in Version 0.7.8 (04.02.2026)

### Custom Übungen erstellen
Nutzer können jetzt eigene Übungen erstellen und in ihren Plänen verwenden:

1. **CustomUebung Model**
   - user (ForeignKey) - Übung gehört einem User
   - name, muskelgruppen, hilfsmuskelgruppen
   - beschreibung, equipment (optional)
   - is_active für Soft-Delete

2. **UI Integration**
   - "Eigene Übung erstellen" Button in Übungsauswahl
   - Modal mit Formular (Name, Muskelgruppen, Beschreibung, Equipment)
   - Filter "Meine Übungen" in uebungen_auswahl.html
   - Integration in Plan-Editor und Training-Session

3. **CRUD API-Endpoints**
   - POST /api/custom-uebung/create/
   - GET /api/custom-uebungen/
   - PUT /api/custom-uebung/<id>/update/
   - DELETE /api/custom-uebung/<id>/delete/

4. **Training Integration**
   - Custom Übungen erscheinen in Übungsauswahl
   - Ghosting funktioniert wie bei Standard-Übungen
   - Statistiken und 1RM-Berechnung identisch

**Technische Details:**
- Model: CustomUebung in core/models.py
- Views: custom_uebung_create, custom_uebung_list, custom_uebung_update, custom_uebung_delete
- Templates: custom_uebung_modal.html
- JavaScript: custom-uebung.js

### AI Coach Auto-Suggest nach Training
Der AI Coach schlägt jetzt automatisch Optimierungen vor:

1. **Automatische Trigger**
   - Nach jedem 3. Training: "Plan optimieren?" Button
   - Performance-Warnings im Dashboard (Top 3)
   - Proaktive Benachrichtigungen bei kritischen Problemen

2. **Dashboard-Integration**
   - Performance-Warnings Card zeigt aktuelle Probleme
   - Direkt-Link zur Plan-Optimierung
   - Badge zeigt Anzahl offener Warnings

3. **Smart Timing**
   - Nur bei relevanten Daten (mind. 8 Trainings)
   - Nicht öfter als alle 3 Trainings
   - User kann Suggest deaktivieren (Einstellungen)

4. **Verbesserungen**
   - Analyse läuft im Hintergrund
   - Cached Results für schnellere Anzeige
   - Toast-Benachrichtigung mit "Jetzt optimieren"-Link

**Technische Details:**
- Training-Counter in Session
- Dashboard-Template mit Performance-Card
- Auto-Suggest-Logic in training_complete View
- LocalStorage für User-Präferenzen

### Sicherheits-Updates (Security-Patch)
Alle GitHub CodeQL Alerts behoben:

1. **Information Disclosure** (30+ Instanzen)
   - Entfernt `str(e)` aus allen JsonResponse Errors
   - Generische User-Fehlermeldungen
   - Server-seitige Logs mit exc_info=True

2. **ReDoS Prevention** (3 Instanzen)
   - Bounded regex quantifiers (`{0,50}`, `{1,4}`, `{1,10}`)
   - Schutz vor Denial-of-Service Angriffen

3. **XSS Protection** (1 Instanz)
   - AI Chat verwendet textContent statt innerHTML
   - DOM-based XSS verhindert

4. **URL Sanitization** (1 Instanz)
   - Service Worker: hostname === statt includes()
   - Verhindert Subdomain-Bypass

**Dateien:**
- core/views.py (30+ Fixes)
- core/templates/core/ai_coach_chat.html
- core/static/core/service-worker.js

---

## 🎉 Neue Features in Version 0.7.4 (03.02.2026)

### Toast-Notifications System
Moderne Toast-Benachrichtigungen ersetzen alle Browser-Alerts:

1. **Toast-Typen**
   - ✅ Success (grün) - für Erfolgsaktionen
   - ❌ Error (rot) - für Fehler
   - ⚠️ Warning (gelb) - für Warnungen
   - ℹ️ Info (blau) - für Hinweise

2. **Features**
   - Animierte Ein-/Ausblendung (slide from right)
   - Auto-dismiss nach 3-4 Sekunden
   - Manuelles Schließen möglich
   - Stapelbar (mehrere Toasts gleichzeitig)
   - Dark Mode kompatibel
   - Responsive (mobile-optimiert)

3. **Geänderte Seiten**
   - Plan teilen (share_plan.html)
   - Gruppe teilen (share_group.html)
   - Trainingsplan-Auswahl (training_select_plan.html)
   - Fortschrittsfotos (progress_photos.html)
   - Plan erstellen (create_plan.html)
   - Plan-Optimierung Modal (plan_optimization_modal.html)

**Technische Details:**
- `core/static/core/js/toast.js` - Toast-Klasse mit show/success/error/warning/info
- `core/static/core/css/toast.css` - Styles mit Gradient-Backgrounds
- Globaler `toast` Instanz verfügbar nach Script-Include

---

## 🎉 Neue Features in Version 0.7.3 (03.02.2026)

### Lite Cardio Tracking
Die App unterstützt jetzt einfaches Cardio-Tracking ohne Trainingsplan:

1. **Cardio-Einheiten erfassen**
   - Schnelles Hinzufügen vom Dashboard ("Cardio hinzufügen" Button)
   - 9 vordefinierte Aktivitäten: Schwimmen, Laufen, Radfahren, Rudern, Gehen, HIIT, Stepper, Seilspringen, Sonstiges
   - Dauer in Minuten
   - 3 Intensitätsstufen: Leicht (Zone 2), Moderat (Zone 3), Intensiv (Zone 4-5)
   - Optionale Notiz (z.B. "Brustschwimmen", "Intervalle")
   - Datum wählbar (auch rückwirkend)

2. **Cardio-Übersicht**
   - Neue Seite: `/cardio/`
   - Liste aller Cardio-Einheiten (Standard: letzte 30 Tage)
   - Statistiken: Anzahl Einheiten, Gesamtminuten
   - Aktivitäts-Icons (Schwimmen=Wasser, Laufen=Person, etc.)
   - Löschen-Funktion

3. **Ermüdungsindex-Integration**
   - Cardio fließt automatisch in den Ermüdungsindex ein
   - Ermüdungspunkte basierend auf Intensität × Dauer:
     * Leicht: 0.1 Punkte/Minute (60 Min = 6 Punkte)
     * Moderat: 0.2 Punkte/Minute (60 Min = 12 Punkte)
     * Intensiv: 0.4 Punkte/Minute (60 Min = 24 Punkte)
   - Ab 30 Punkte/Woche: +5 auf Ermüdungsindex
   - Ab 60 Punkte/Woche: +10 (Warnung "Moderates Cardio-Volumen")
   - Ab 120 Punkte/Woche: +20 (Warnung "Hohes Cardio-Volumen")

4. **Dashboard-Integration**
   - "Cardio hinzufügen" Button direkt unter "Training starten"
   - Cardio-Statistik-Karte (Einheiten + Minuten diese Woche)
   - Cardio-Link im Footer für alle Nutzer

**Technische Details:**
- Model: `CardioEinheit` mit user, datum, aktivitaet, dauer_minuten, intensitaet, notiz
- Views: `cardio_list`, `cardio_add`, `cardio_delete`
- Templates: `cardio_list.html`, `cardio_add.html`
- Migration: `0021_add_cardio_einheit.py`
- URLs: `/cardio/`, `/cardio/add/`, `/cardio/<id>/delete/`

**Warum dieses Feature?**
- KI-Coach erhält vollständiges Bild der Trainingsbelastung
- Ermüdungsindex wird genauer (Schwimmen am Sonntag beeinflusst Beine am Montag)
- "Aktive Erholung" vs. Ruhetage erkennbar
- Trainingsfrequenz/Streak berücksichtigt auch Cardio

---

## 🎉 Neue Features in Version 0.7.2 (01.02.2026)

### Plan-Sharing & Bibliothek
Die App hat jetzt ein vollständiges Sharing-System für Trainingspläne:

1. **Plan/Gruppe duplizieren**
   - Einzelne Pläne als Kopie erstellen
   - Komplette Split-Gruppen duplizieren
   - Übernimmt alle Übungen, Superset-Gruppen, Pausenzeiten
   - Automatische "(Kopie)"-Benennung

2. **Plan/Gruppe teilen**
   - Dedizierte Share-Seite (`/plan/<id>/share/`)
   - QR-Code Generator für mobiles Scannen
   - Direkter Link zum Kopieren
   - Social-Sharing (WhatsApp, Telegram, E-Mail)
   - Öffentlich/Privat Toggle direkt auf der Seite

3. **Öffentliche Plan-Bibliothek**
   - Neue Seite: `/plan-library/`
   - Durchsuchbare Sammlung aller öffentlichen Pläne
   - Gruppierte Anzeige von Split-Plänen
   - 1-Klick Kopieren in eigene Sammlung
   - Suchfunktion nach Namen/Beschreibung
   - Link im Footer für alle Nutzer

4. **Plan-Gruppen Management**
   - Gruppen umbenennen
   - Reihenfolge innerhalb der Gruppe ändern
   - Gruppierung aufheben
   - Ganze Gruppe löschen (mit Doppel-Bestätigung)

5. **Trainingspartner-Sharing** *(NEU)*
   - Pläne privat mit einzelnen Usern teilen (ohne öffentlich zu machen)
   - User-Suche mit Autocomplete direkt auf der Share-Seite
   - "Mit mir geteilt" Tab in der Planauswahl
   - Badge zeigt Anzahl geteilter Pläne
   - Freigaben können jederzeit entfernt werden
   - Funktioniert für einzelne Pläne und ganze Gruppen

**Technische Details:**
- Views: `duplicate_plan`, `duplicate_group`, `share_plan`, `share_group`, `plan_library`, `plan_library_group`, `copy_group`, `toggle_plan_public`, `toggle_group_public`, `api_search_users`, `api_share_plan_with_user`, `api_unshare_plan_with_user`, `api_share_group_with_user`, `api_unshare_group_with_user`, `api_get_plan_shares`, `api_get_group_shares`
- Templates: `share_plan.html`, `share_group.html`, `plan_library.html`, `plan_library_group.html`
- Model: `Plan.shared_with` ManyToManyField (Migration 0020)
- URLs: 17 neue Routen für Plan-Management und Sharing-API

---

## 🎉 Neue Features in Version 0.7.1 (29.01.2026)

### Beta Feedback System
Für den Beta-Test wurde ein vollständiges Feedback-System implementiert:

1. **Feedback-Typen**
   - 🐛 Bugreport (Fehler melden)
   - 💡 Verbesserungsvorschlag (Feature Request)
   - ❓ Frage (Hilfe benötigt)

2. **Status-Tracking**
   - 🆕 Neu (noch nicht geprüft)
   - ✅ Angenommen (wird umgesetzt)
   - 🔄 In Bearbeitung (wird entwickelt)
   - 🎉 Umgesetzt (live verfügbar)
   - ❌ Abgelehnt (nicht umsetzbar)

3. **Features**
   - Eigene Feedback-Übersicht (`/feedback/`)
   - Formular mit Typ-Auswahl und Beschreibung
   - Admin-Antworten sichtbar für User
   - Prioritäts-Tracking (Niedrig/Mittel/Hoch)
   - Footer-Link für alle eingeloggten User

4. **Admin-Interface**
   - Bulk-Actions (Angenommen/Abgelehnt/Umgesetzt)
   - Admin-Antwort-Feld
   - Filter nach Status, Typ, Priorität

### KI-Planerstellung Verbesserungen
- **Pausenzeit pro Übung** - LLM generiert `rest_seconds` (60-180s)
- **Timer-Button pro Satz** in Training Session
- **Automatische OpenRouter-Nutzung** auf Server (keine GPU)
- **Schema-Validierung** mit Fallback zu OpenRouter bei Fehlern

---

## 🎉 Neue Features in Version 0.7.0 (16.01.2026)

### Multi-User Support & Öffentliche Pläne
Die App unterstützt jetzt mehrere User mit Privacy-Kontrollen:

1. **User-Isolation**
   - Training-History zeigt nur eigene Trainings
   - Trainingspläne sind standardmäßig privat
   - Körperwerte & Progress Photos sind user-spezifisch

2. **Öffentliche Trainingspläne**
   - `is_public` Flag im Plan Model
   - Filter: "Meine Pläne" / "Öffentliche Pläne"
   - Kopier-Funktion für öffentliche Pläne
   - Zeigt Ersteller bei öffentlichen Plänen

3. **Plan-Kopier-System**
   - 1-Klick Kopie von öffentlichen Plänen
   - Kopien sind standardmäßig privat
   - Übernimmt alle Übungen, Sets, Reps, Superset-Gruppen
   - Benennt automatisch um "(Kopie)"

4. **Standard User Group**
   - Management Command: `create_standard_user_group`
   - 29 Permissions für normale User
   - Volle Rechte auf eigene Daten
   - Nur Lese-Rechte auf Übungsdatenbank

5. **Zielwerte während Training**
   - Zeigt Plan-Ziele (Sätze × Wiederholungen) als Badge
   - Nicht editierbar, nur Info-Anzeige
   - Template Filter für Dictionary-Zugriff
   - Nur sichtbar bei Training mit Plan

### PWA & Offline Features (85% Complete)

1. **Offline-Indikator**
   - Connection Status rechts oben (Online/Offline)
   - Toast-Benachrichtigungen bei Verbindungswechsel
   - Pulse-Animation bei Offline-Status
   - Dark Mode Support

2. **IndexedDB Offline-Speicherung**
   - 3 Object Stores: trainingData, exercises, plans
   - Sync-Status Tracking (synced/unsynced)
   - Timestamp für jede Änderung
   - CRUD Operations mit async/await
   - Automatisches Cleanup von syncten Daten

3. **Background Sync**
   - Automatisches Syncen wenn Verbindung zurück
   - Service Worker Event Listener
   - Retry-Logic bei Fehlern
   - Markiert erfolgreich gesyncte Daten

4. **Offline Manager JavaScript Class**
   - `offlineManager.saveOfflineData(store, data)`
   - `offlineManager.getOfflineData(store, id)`
   - `offlineManager.getUnsyncedData(store)`
   - `offlineManager.markAsSynced(store, id)`
   - Automatische DB-Initialisierung

### Technische Details
- **Backend:** 
  - `training_list`: User-Filter für History
  - `training_select_plan`: Filter eigene/öffentliche Pläne
  - `copy_plan`: View zum Kopieren öffentlicher Pläne
  - `create_standard_user_group`: Management Command
- **Frontend:**
  - `offline-manager.js` (280 Zeilen)
  - `offline-manager.css` (110 Zeilen)
  - Enhanced Service Worker (250 Zeilen)
  - Custom Template Filter `get_item`
- **Database:**
  - Migration: `0014_add_plan_is_public`
  - IndexedDB: 3 Object Stores mit Indizes

### Bugfixes & Verbesserungen
- ✅ Training-History filtert nach User
- ✅ Delete-Training prüft User-Ownership
- ✅ Plan-Details zeigt nur eigene oder öffentliche Pläne
- ✅ Plan-Edit nur für Owner
- ✅ Zielwerte-Badge in Training-Session
- ✅ Connection Status UI mit Animations

---

## 🎉 Neue Features in Version 0.6.0 (11.01.2026)

### Professioneller PDF Training Report
Die App hat jetzt einen vollständigen professionellen PDF-Export mit anatomischen Visualisierungen:

1. **Multi-Page Professional Layout**
   - Deckblatt mit dynamischer Body-Map (SVG-basiert)
   - Inhaltsverzeichnis mit 6 Kapiteln
   - Separate Seiten für: Executive Summary, Muskelgruppen-Analyse, Push/Pull Balance, Trainingsfortschritt, Trainer-Empfehlungen
   - Page-break-Kontrolle (Überschriften bleiben mit Grafiken zusammen)

2. **Anatomische Body-Map Visualisierung**
   - SVG-Muscle-Map (muscle_map.svg, 1100x1024px, 50+ Muskelregionen)
   - Dynamische Farbcodierung basierend auf Trainingsdaten
   - Cairosvg-Rendering (hochwertig, professionell)
   - PIL-Fallback bei fehlender Cairo-Library (Windows-kompatibel)
   - Legende mit 4 Status-Farben (Optimal=Grün, Untertrainiert=Gelb, Übertrainiert=Rot, Nicht trainiert=Grau)
   - CSS class/style removal für korrekte Farbdarstellung

3. **Matplotlib Charts**
   - Muskelgruppen-Balance Visualisierung (Horizontal Bar Chart mit Referenzlinien)
   - Trainingsvolumen-Entwicklung (Line Chart mit Area Fill, letzte 8 Wochen)
   - Push/Pull Balance (Pie Chart mit Prozent-Anzeige)
   - Base64-Encoding für PDF-Einbettung
   - Dark mode compatible colors

4. **Intelligente Datenqualitäts-Checks**
   - Warnung bei < 8 Trainingseinheiten: "Bewertungen mit Vorsicht interpretieren"
   - Softere Formulierungen bei wenig Daten:
     * "Untertrainiert" → "Wenig trainiert"
     * "Mögl. Übertraining" → "Viel trainiert"
     * Zusatz: "(mehr Daten für genauere Analyse)"
   - Körperdaten-Hinweis wenn keine Umfänge erfasst

5. **Muskelgruppen-Analyse**
   - Evidenzbasierte Empfehlungen (12-20 Sätze/Monat je Muskelgruppe)
   - Status-Badges (Optimal/Untertrainiert/Übertrainiert/Nicht trainiert)
   - Detaillierte Erklärungen mit konkreten Empfehlungen
   - Sortiert nach Trainingsvolumen
   - Angepasste Bewertungen bei niedriger Datenlage

6. **Push/Pull Balance**
   - Automatische Berechnung (korrigierte Muskelgruppen-Keys)
   - Push: BRUST, SCHULTER_VORN, SCHULTER_SEIT, TRIZEPS
   - Pull: RUECKEN_LAT, RUECKEN_TRAPEZ, RUECKEN_UNTEN, RUECKEN_OBERER, SCHULTER_HINT, BIZEPS
   - Ratio-Berechnung mit 3 Status:
     * "Keine Daten" (beide 0)
     * "Nur Push" (Pull = 0)
     * "Ausgewogen" (0.9:1 - 1.1:1)
     * "Zu viel Push/Pull" (außerhalb Range)
   - Konkrete Empfehlungen basierend auf Ratio

7. **Trainer-Empfehlungen**
   - Stärken-Liste (optimal trainierte Muskelgruppen)
   - Schwachstellen-Liste (untertrainiert, sortiert nach Priorität)
   - Nächste Schritte (3-4 konkrete Actions)
   - Wissenschaftlich fundierte Ratschläge

### Technische Details
- **Backend:** core/views.py - export_training_pdf() (380 Zeilen)
- **Frontend:** core/templates/core/training_pdf_simple.html (462 Zeilen)
- **Charts:** core/chart_generator.py (514 Zeilen)
  - SVG Rendering: _render_svg_muscle_map_png_base64()
  - PIL Fallback: _generate_body_map_with_data_pil_fallback()
  - Matplotlib: generate_muscle_heatmap(), generate_volume_chart(), generate_push_pull_pie()
- **PDF Engine:** xhtml2pdf (CSS2.1 kompatibel)
- **Dependencies:** cairosvg, matplotlib, Pillow, xhtml2pdf

### Bugfixes & Verbesserungen
- ✅ Push/Pull Keys7 (04.02.2026) - Quick Wins

### UX Improvements: 3 neue Produktivitäts-Features

**1. Undo-Funktion für gelöschte Sätze**
Verhindert versehentliche Datenverluste mit 5-Sekunden-Fenster:
- **Optimistic Delete:** Satz wird sofort ausgeblendet (nicht blockierend)
- **Undo-Toast:** Erscheint rechts unten mit "Rückgängig"-Button
- **Countdown-Animation:** Progress Bar zeigt verbleibende Zeit (5 Sek.)
- **Auto-Delete:** Nach Timeout wird Satz endgültig per POST gelöscht
- **Fehler-Handling:** Bei Netzwerkfehler wird Satz automatisch wiederhergestellt

**Technische Details:**
- JavaScript Array `deletedSets[]` für temporäre Speicherung
- setTimeout für Timeout-Management
- Theme-aware Toast-Styling (Dark/Light Mode)
- Slide-in Animation von rechts

**2. Keyboard-Shortcuts**
Power-User Feature für 30-40% schnellere Eingabe:
- **Enter:** Satz speichern (in Add/Edit Modals)
- **Esc:** Aktives Modal schließen
- **N:** Neuer Satz öffnen (nur im Training)
- **S:** Satz hinzufügen (nur im Training)
- **Visuelle Badges:** `<kbd>Enter</kbd>` Hinweise auf Buttons

**Technische Details:**
- `keyboard-shortcuts.js` mit Context-Awareness
- Funktioniert auch in Input-Feldern (Enter/Esc)
- Ignoriert Shortcuts in Textareas (Shift+Enter)
- Auto-Badge-Injection bei Modal-Öffnung

**3. Autocomplete für Übungssuche**
Intelligente Typeahead-Suche für 200+ Übungen:
- **Fuzzy Matching:** "bndrcke" findet "Bankdrücken"
- **Score-basiertes Ranking:**
  - Exakt-Match: 1000 Punkte
  - Starts-with: 500 Punkte
  - Contains: 250 Punkte
  - Fuzzy: 100 Punkte
  - Muskelgruppe: 50 Punkte
- **Tastatur-Navigation:** ↑↓ Enter Esc
- **Highlight-Match:** Suchbegriff wird farbig hervorgehoben
- **Auto-Select:** Wählt automatisch Muskelgruppe + Übung

**Technische Details:**
- `exercise-autocomplete.js` Klasse (wiederverwendbar)
- Dropdown mit max. 8 Ergebnissen
- Theme-aware Styling
- Integration in training_session.html
- onSelect Callback für Custom Actions

**Dateien:**
- core/templates/core/training_session.html (+140 Zeilen Undo-Logic)
- core/static/core/js/exercise-autocomplete.js (NEU - 300+ Zeilen)
- core/static/core/js/keyboard-shortcuts.js (bereits vorhanden)

---

## 🎉 Version 0.7. korrigiert (BRUST statt brust, etc.)
- ✅ h2 border-bottom entfernt bei Chart-Überschriften (keine Linien durch Grafiken)
- ✅ Page-break-after: avoid bei Überschriften (bleiben mit Inhalt zusammen)
- ✅ Legenden-Schrift vergrößert (16px, einheitlich)
- ✅ Deckblatt-Layout optimiert (kompakt, alles auf eine Seite)
- ✅ Body-Map Skalierung (62% width für optimale Darstellung)

---

## 🎉 Version 0.7.6 (04.02.2026)

### Loading-States bei API-Calls
Professionelle Loading-Indicators für alle wichtigen API-Anfragen:

**LoadingManager JavaScript-Klasse:**
- **Button Loading:** Deaktiviert Button, zeigt Spinner, speichert Original-Text
- **Overlay Loading:** Transparentes Overlay mit Spinner über Container
- **Fetch Wrapper:** Automatische Loading-State Integration
- **Auto-Reset:** Finally-Block stellt UI wieder her bei Erfolg oder Fehler

**Integrierte Templates:**
- edit_plan.html: KI-Optimierung, Performance-Analyse
- create_plan.html: Template-Loading
- equipment_management.html: Equipment Toggle
- training_session.html: Set-Loading, Ghosting

**UX-Verbesserungen:**
- Keine mehrfachen Clicks möglich während Request
- Visuelles Feedback für alle Netzwerk-Operationen
- Konsistentes Loading-Design über alle Features
- Toast-Benachrichtigungen nach Abschluss

**Technische Details:**
- CSS Animations: Spinning Border, Fade-in Overlay
- Bootstrap Integration: Nutzt spinner-border
- Error Handling: UI-Reset bei Fehlern
- Globale Instanz: `window.loadingManager`

**Dateien:**
- `core/static/core/js/loading-manager.js` (250+ Zeilen)
- Updates in 4 Templates mit API-Calls

---

## 🎉 Version 0.7.5 (04.02.2026)

### Übungen Favorisieren
Nutzer können jetzt Übungen als Favoriten markieren für schnellen Zugriff:

**Features:**
- **Favoriten-Button:** Stern-Icon in Übungsliste und Detail-Ansicht
- **Toggle-API:** POST /uebung/<id>/toggle-favorit/ mit JSON Response
- **Filter:** "Nur Favoriten anzeigen" Checkbox in Übungsliste
- **Toast-Benachrichtigungen:** Bestätigung beim Hinzufügen/Entfernen
- **Persistenz:** ManyToMany User-Übung Relation in Datenbank

**Technische Details:**
- View: `toggle_favorit()` in core/views.py
- Model: `Uebung.favoriten` ManyToManyField (bereits vorhanden)
- JavaScript: favoriten.js mit optimistic UI updates
- Templates: uebungen_auswahl.html, exercise_detail.html

**UX:**
- Optimistic UI: Icon wechselt sofort, Server-Sync im Hintergrund
- Filter aktualisiert sich automatisch bei Favorit-Änderung
- Stern-Button immer sichtbar, auch in Kartenansicht

---

## 🎉 Features aus Version 0.4.0 (10.01.2026)

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

**Letzte Aktualisierung:** 09.02.2026
**Nächstes Review:** Nach Abschluss Phase 5 (Next Features)

---

## 📊 Statistiken & Metriken

### Codebase
- **Gesamtzeilen Code:** ~19.500+ Zeilen
- **Python Backend:** ~9.500 Zeilen (inkl. advanced_stats.py, export.py)
- **Templates (HTML/Django):** ~5.500 Zeilen (erweitertes PDF-Template)
- **JavaScript:** ~2.500 Zeilen (inkl. Offline Manager)
- **Service Worker:** ~250 Zeilen

### Features Completed
- **Phase 1:** 100% (10/10 Features)
- **Phase 2:** 100% (12/12 Features)
- **Phase 3:** 100% (15/15 Features)
- **Phase 3.5:** 100% (10/10 Features)
- **Phase 3.7:** 100% (8/8 Features - AI Coach)
- **Phase 4:** 65% (7/10 Features - PDF, PWA/Offline, Templates, Übungsdb, CSV-Export)
- **Phase 5:** 85% (4/5 High Priority + Advanced Stats)

### Key Numbers (Februar 2026)
- **Übungsdatenbank:** 200+ Übungen mit anatomischen Daten + 1RM Standards
- **SVG Muskelregionen:** 50+ identifizierbare Bereiche
- **AI Coach Cost:** ~0.003€ pro Plan-Generierung/Optimierung
- **PDF Seiten:** 7+ Seiten professioneller Report (mit erweiterten Analysen)
- **Charts:** 4 (Body-Map, Heatmap, Volumen-Line, Push/Pull-Pie)
- **IndexedDB Stores:** 3 (trainingData, exercises, plans)
- **Offline-Fähig:** Ja (Service Worker + IndexedDB + Background Sync)
- **Deployment:** Produktiv auf last-strawberry.com
- **1RM Standards:** 4 Levels (Anfänger → Elite) pro Übung, körpergewicht-skaliert
