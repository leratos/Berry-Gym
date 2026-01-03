# 🏋️ HomeGym App - Roadmap & Feature-Tracking

**Stand:** 03.01.2026  
**Version:** 0.2.0

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

## 📅 PHASE 4: Ernährung & Lifestyle (0% - OFFEN)

### Ernährungstracking
- [ ] Makros erfassen (Protein, Carbs, Fett, Kalorien)
- [ ] Kalorienrechner (TDEE, Ziele)
- [ ] Mahlzeiten-Log mit Timestamp
- [ ] Ernährungs-Dashboard
- [ ] Gewicht-Korrelation mit Kalorien-Intake
- [ ] Wöchentliche Durchschnitte

### Lifestyle-Tracking
- [ ] Schlafqualität erfassen (1-10)
- [ ] Schlafdauer tracken
- [ ] Stresslevel erfassen
- [ ] Energielevel vor/nach Training
- [ ] Korrelations-Analyse Training ↔ Lifestyle
- [ ] Warnung bei zu wenig Schlaf

### Ernährungspläne
- [ ] Meal-Prep Vorschläge
- [ ] Rezepte-Datenbank
- [ ] Favoriten-Rezepte
- [ ] Einkaufsliste automatisch generieren
- [ ] Makro-Ziele pro Mahlzeit

---

## 🚀 PHASE 5: Erweiterte Features (0% - OFFEN)

### In-App Plan-Editor
- [x] **Pläne in der App erstellen (ohne Admin)** ✅
- [x] **Übungen per Drag & Drop sortieren** ✅
- [x] **Plan bearbeiten/löschen** ✅
- [ ] Plan-Templates (Push/Pull/Legs, etc.)
- [ ] Plan duplizieren
- [ ] Plan teilen (QR-Code/Link)
- [ ] Öffentliche Plan-Bibliothek

### Übungsdatenbank
- [ ] Video-Anleitungen hochladen
- [ ] Animationen für Übungen
- [ ] Alternative Übungen vorschlagen
- [ ] Übungen favorisieren (Quick-Access)
- [ ] Custom Übungen erstellen
- [ ] Tags für Übungen (Compound, Isolation, etc.)
- [ ] Schwierigkeitsgrad anzeigen

### PWA & Offline
- [ ] Progressive Web App Setup
- [ ] Offline-Funktionalität (Service Worker)
- [ ] Push-Notifications aktivieren
- [ ] Home Screen Installation
- [ ] Sync bei Verbindung
- [ ] Offline-Indikator

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

## 🎯 Quick Wins (Empfohlen als Nächstes)

**Priorität HOCH (1-2h pro Feature):**
- [ ] Dark/Light Mode Toggle (Theme-Switcher Button)
- [ ] Übungs-Favoriten (Stern-Icon zum Markieren)
- [ ] CSV Export für Trainings-Daten
- [ ] Rest Timer Settings (60/90/120 Sek wählbar)
- [ ] Körperwerte bearbeiten/löschen

**Priorität MITTEL (3-5h pro Feature):**
- [ ] Volumen-Progression Chart (Wochen-Verlauf)
- [ ] Heatmap für Trainingstage
- [ ] In-App Plan-Editor (Basis-Version)
- [ ] Übungs-Notizen pro Satz
- [ ] Foto-Upload für Progress Pics

**Priorität NIEDRIG (Später):**
- [ ] Ernährungs-Dashboard
- [ ] Social Features
- [ ] ML-Empfehlungen

---

## 🐛 Bekannte Bugs & Verbesserungen

### Bugs
- [ ] --

### Verbesserungen
- [ ] Loading-States bei API-Calls
- [ ] Undo-Funktion für gelöschte Sätze
- [ ] Keyboard-Shortcuts (Enter = Speichern, Esc = Schließen)
- [ ] Bessere Error-Messages
- [ ] Konfigurierbarer Rest Timer (Zeit einstellen)

---

## 📝 Notizen

### Technische Schulden
- PWA Setup fehlt noch
- Keine automatisierten Tests
- Keine CI/CD Pipeline
- Keine Migrations-Strategie für Prod

### Performance
- Lazy Loading für Bilder implementieren
- Chart.js Daten cachen
- Pagination für lange Listen

### Sicherheit
- `.env` für Secrets nutzen
- HTTPS erzwingen in Produktion
- Rate Limiting für API-Endpoints
- User-Authentication erweitern

---

**Letzte Aktualisierung:** 03.01.2026  
**Nächstes Review:** Nach Abschluss Phase 3
