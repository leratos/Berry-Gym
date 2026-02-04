# Plan-Templates & PDF-Export - Implementierungsdokumentation

## Überblick
Zwei neue Features wurden implementiert, um die Nutzererfahrung beim Erstellen von Trainingsplänen zu verbessern:

1. **Plan-Templates**: Vorgefertigte Trainingspläne basierend auf bewährten Prinzipien
2. **Plan-PDF-Export**: Export von Trainingsplänen als druckbares PDF mit QR-Code

---

## Feature 1: Plan-Templates

### Beschreibung
Ermöglicht es Nutzern, aus vorgefertigten Trainingsplan-Templates auszuwählen anstatt einen Plan komplett von Grund auf zu erstellen. Die Templates basieren auf wissenschaftlich fundierten Trainingsprinzipien und werden automatisch an das verfügbare Equipment des Nutzers angepasst.

### Verfügbare Templates

#### 1. Push/Pull/Legs (6 Tage)
- **Schwierigkeit**: Fortgeschritten
- **Frequenz**: 6x pro Woche
- **Ziel**: Hypertrophie & Kraftaufbau
- **Trainingstage**: 
  - Push A (Brust-Fokus): 6 Übungen
  - Pull A (Rücken-Fokus): 6 Übungen
  - Legs A: 6 Übungen
  - Push B (Schulter-Fokus): 6 Übungen
  - Pull B (Lat-Fokus): 6 Übungen
  - Legs B: 6 Übungen
- **Gesamt**: 36 Übungen

#### 2. Upper/Lower (4 Tage)
- **Schwierigkeit**: Mittel
- **Frequenz**: 4x pro Woche
- **Ziel**: Kraft & Hypertrophie
- **Trainingstage**:
  - Upper A (Kraft): 7 Übungen
  - Lower A (Kraft): 6 Übungen
  - Upper B (Hypertrophie): 8 Übungen
  - Lower B (Hypertrophie): 6 Übungen
- **Gesamt**: 27 Übungen

#### 3. Full Body (3 Tage)
- **Schwierigkeit**: Anfänger bis Mittel
- **Frequenz**: 3x pro Woche
- **Ziel**: Allgemeine Fitness & Kraft
- **Trainingstage**:
  - Full Body A: 7 Übungen
  - Full Body B: 7 Übungen
  - Full Body C: 7 Übungen
- **Gesamt**: 21 Übungen

### Technische Implementation

#### Dateien
- **Template-Daten**: `core/fixtures/plan_templates.json`
- **Views**: `core/views.py` (3 neue Funktionen)
  - `get_plan_templates()`: API Endpoint für Template-Übersicht
  - `get_template_detail(template_key)`: API für Template-Details mit Equipment-Anpassung
  - `create_plan_from_template(template_key)`: Erstellt Plan aus Template
  - `find_substitute_exercise()`: Findet Ersatzübungen bei fehlendem Equipment
- **URLs**: `core/urls.py` (3 neue Routen)
  - `/api/plan-templates/`
  - `/api/plan-templates/<key>/`
  - `/api/plan-templates/<key>/create/`
- **Frontend**: `core/templates/core/create_plan.html`
  - Modal mit Template-Auswahl
  - Template-Detail-Ansicht mit Übungsvorschau
  - JavaScript für API-Kommunikation

#### Equipment-Anpassung
Das System prüft automatisch, welches Equipment der Nutzer zur Verfügung hat:

1. **Equipment vorhanden**: ✅ Übung wird übernommen
2. **Equipment fehlt**: ⚠️ Suche nach Ersatzübung
   - Zuerst: Gleiche Muskelgruppe + Bewegungstyp
   - Fallback: Nur gleiche Muskelgruppe
   - Letzter Ausweg: Hinweis auf fehlendes Equipment

#### Verwendung
1. Plan-Erstellung öffnen (`/plan/create/`)
2. Button "Von Template starten" klicken
3. Template auswählen
4. "Details anzeigen" für Übersichtsvorschau
5. "Plan erstellen" → Automatische Erstellung mit Equipment-Anpassung

---

## Feature 2: Plan-PDF-Export

### Beschreibung
Exportiert einen Trainingsplan als professionell formatiertes A4-PDF mit QR-Code für schnellen mobilen Zugriff.

### Features
- **A4-Format**: Optimiert für Druck und digitale Nutzung
- **QR-Code**: Scannt zum Online-Plan für Live-Tracking
- **Übersichtstabelle**: Alle Übungen mit Sätzen, Wiederholungen, Pausen
- **Muskelgruppen-Badges**: Visuelle Kennzeichnung der Zielmuskulatur
- **Trainingstag-Gruppierung**: Übungen nach Trainingstagen sortiert
- **Header**: Plan-Info, Beschreibung, Frequenz, Erstelldatum
- **Footer**: URL und Zeitstempel

### Technische Implementation

#### Dateien
- **View**: `core/views.py` - `export_plan_pdf(plan_id)`
- **URL**: `core/urls.py` - `/plan/<int:plan_id>/pdf/`
- **Frontend**: `core/templates/core/plan_details.html` (PDF-Button hinzugefügt)
- **Dependency**: `requirements.txt` - `qrcode[pil]==8.0`

#### PDF-Generierung
- **Bibliothek**: xhtml2pdf (pisa)
- **Styling**: Inline HTML/CSS mit A4-Page-Setup
- **QR-Code**: qrcode-Library mit Base64-Einbettung

#### Verwendung
1. Plan-Details öffnen (`/plan/<id>/`)
2. Button "PDF" klicken
3. PDF wird generiert und heruntergeladen
4. QR-Code im PDF scannen für mobilen Zugriff

### PDF-Struktur
```
┌─────────────────────────────────────┐
│ Plan-Titel              [QR-Code]   │
│ Beschreibung                        │
│ Frequenz, Erstellt-am               │
├─────────────────────────────────────┤
│ Trainingstag 1                      │
│ ┌─────────────────────────────────┐ │
│ │ # │ Übung │ Muskel │ Sätze... │ │
│ │ 1 │ ...   │ ...    │ ...      │ │
│ └─────────────────────────────────┘ │
│ Trainingstag 2                      │
│ ┌─────────────────────────────────┐ │
│ │ # │ Übung │ Muskel │ Sätze... │ │
│ └─────────────────────────────────┘ │
├─────────────────────────────────────┤
│ Footer: URL, Zeitstempel            │
└─────────────────────────────────────┘
```

---

## Installation

### Pakete installieren
```bash
pip install qrcode[pil]==8.0
```

### Migrations (falls benötigt)
```bash
python manage.py migrate
```

---

## Testing

### Template-System testen
1. Gehe zu `/plan/create/`
2. Klicke "Von Template starten"
3. Wähle ein Template (z.B. "Full Body (3 Tage)")
4. Prüfe Equipment-Anpassungen (grün = verfügbar, gelb = Ersatz)
5. Klicke "Plan erstellen"
6. Verifiziere, dass Plan mit allen Übungen erstellt wurde

### PDF-Export testen
1. Öffne einen existierenden Plan
2. Klicke "PDF"-Button
3. Verifiziere:
   - PDF wird heruntergeladen
   - QR-Code ist sichtbar und funktioniert
   - Alle Übungen sind aufgelistet
   - Formatierung ist korrekt
   - Muskelgruppen-Badges sind sichtbar

---

## API-Dokumentation

### GET `/api/plan-templates/`
Liefert alle verfügbaren Templates (Übersicht).

**Response:**
```json
{
  "push_pull_legs_6day": {
    "name": "Push/Pull/Legs (6 Tage)",
    "description": "Klassischer 6-Tage Split...",
    "frequency_per_week": 6,
    "difficulty": "Fortgeschritten",
    "goal": "Hypertrophie",
    "days_count": 6
  },
  ...
}
```

### GET `/api/plan-templates/<template_key>/`
Liefert vollständige Template-Details mit Equipment-Anpassung.

**Response:**
```json
{
  "name": "Full Body (3 Tage)",
  "description": "...",
  "frequency_per_week": 3,
  "days_adapted": [
    {
      "name": "Full Body A",
      "exercises": [
        {
          "name": "Kniebeugen (Langhantel)",
          "sets": 3,
          "reps": "8-10",
          "equipment": "Langhantel",
          "available": true,
          "substitute": null
        },
        ...
      ]
    }
  ]
}
```

### POST `/api/plan-templates/<template_key>/create/`
Erstellt einen neuen Plan basierend auf Template.

**Request:** (nur CSRF-Token im Header)

**Response:**
```json
{
  "success": true,
  "plan_id": 42
}
```

**Error Response:**
```json
{
  "error": "Template nicht gefunden"
}
```

---

## Bekannte Limitationen

### Plan-Templates
- Templates sind statisch in JSON-Datei definiert
- Equipment-Substitution basiert nur auf Muskelgruppe & Bewegungstyp
- Keine personalisierten Template-Anpassungen (z.B. für Verletzungen)
- Templates können nicht über UI erstellt/bearbeitet werden

### PDF-Export
- QR-Code funktioniert nur bei erreichbarem Server
- Keine Übungsbilder im PDF (nur Tabelle)
- Fixe Formatierung (keine Nutzer-Customization)
- Superset-Gruppierungen werden nicht visuell hervorgehoben im PDF

---

## Zukünftige Erweiterungen

### Mögliche Verbesserungen
1. **Template-Editor**: Admin-Interface zum Erstellen neuer Templates
2. **Personalisierung**: Nutzer-spezifische Template-Anpassungen
3. **Mehr Templates**: Spezialisierte Templates (z.B. Powerlifting, Bodybuilding, Functional)
4. **Übungsbilder im PDF**: Visuelle Anleitung direkt im PDF
5. **PDF-Customization**: Nutzer wählt Spalten/Layout
6. **Template-Sharing**: Nutzer können Templates teilen
7. **Intelligente Substitution**: KI-basierte Übungsempfehlungen
8. **Template-Varianten**: Auto-Generierung von Progressionsvarianten

---

## Changelog

### Version 0.6.0 (2024-XX-XX)
- ✅ Plan-Templates implementiert (3 Templates)
- ✅ Equipment-basierte Übungsanpassung
- ✅ Plan-PDF-Export mit QR-Code
- ✅ Template-Auswahl-UI in create_plan.html
- ✅ API-Endpoints für Templates
- ✅ qrcode Dependency hinzugefügt

---

## Entwickler-Notizen

### Code-Struktur
- **Separation of Concerns**: Template-Daten (JSON) getrennt von Logik (Python)
- **API-First**: Template-System nutzt REST-APIs für Flexibilität
- **Equipment-Integration**: Nutzt bestehende Equipment-Management-Features
- **PDF-Reuse**: Nutzt xhtml2pdf wie export_training_pdf

### Performance
- Template-Loading: O(1) File-Read (cached by OS)
- Equipment-Check: O(n) für n Übungen (akzeptabel für <50 Übungen)
- PDF-Generation: ~1-2s für 20-30 Übungen

### Sicherheit
- CSRF-Protection auf POST-Requests
- User-Isolation: Nur eigene Pläne exportierbar
- Input-Validation: Template-Keys werden validiert
- No SQL-Injection: Nutzt Django ORM

---

## Support & Troubleshooting

### Häufige Probleme

**Problem**: "PDF Export nicht verfügbar - Pakete fehlen"
- **Lösung**: `pip install qrcode[pil] xhtml2pdf`

**Problem**: Template-Modal lädt nicht
- **Lösung**: Browser-Konsole prüfen, API-Endpoint testen: `/api/plan-templates/`

**Problem**: Alle Übungen als "nicht verfügbar" markiert
- **Lösung**: Equipment-Management öffnen, benötigtes Equipment aktivieren

**Problem**: QR-Code im PDF nicht scannbar
- **Lösung**: Server muss öffentlich erreichbar sein, oder localhost-URL im Browser öffnen
