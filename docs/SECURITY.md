# Security Policy

## Unterstützte Versionen

Sicherheitsupdates werden für die aktuell laufende Produktionsversion bereitgestellt.

| Version | Support          |
|---------|------------------|
| latest  | ✅ Aktiv          |
| < 1.0   | ❌ Kein Support   |

---

## Sicherheitslücke melden (Responsible Disclosure)

**Bitte keine Sicherheitslücken als öffentliches GitHub Issue melden.**

Sende eine E-Mail an: **security@last-strawberry.com**

Bitte gib an:
- Beschreibung der Schwachstelle
- Schritte zur Reproduktion
- Mögliche Auswirkung (Impact)
- Optional: Vorschlag für einen Fix

Ich antworte in der Regel innerhalb von **48 Stunden** und arbeite gemeinsam mit dir an einem Patch, bevor die Lücke öffentlich gemacht wird.

---

## Was in Scope ist

- Authentifizierung & Autorisierung (Login, Session-Management)
- Datenzugriff anderer User (User-Isolation-Fehler)
- Injection-Angriffe (SQL, XSS, CSRF)
- Unsichere direkte Objektreferenzen (IDOR)
- Schwachstellen in API-Endpoints

## Was außerhalb des Scope liegt

- Rate-Limiting-Bypässe ohne realen Schaden
- Self-XSS (nur der angemeldete User betrifft sich selbst)
- Social Engineering
- Physischer Zugriff auf Infrastruktur
- Theoretische Schwachstellen ohne Proof of Concept

---

## Eingesetzte Sicherheitsmaßnahmen

| Maßnahme                         | Status |
|----------------------------------|--------|
| CSRF-Schutz (Django Middleware)  | ✅     |
| Brute-Force-Schutz (django-axes) | ✅     |
| Rate Limiting (KI-Endpoints)     | ✅     |
| HSTS (1 Jahr, inkl. Subdomains)  | ✅     |
| Secure Cookies (HTTPS only)      | ✅     |
| X-Frame-Options: DENY            | ✅     |
| Content-Type-Nosniff             | ✅     |
| SSL Redirect (Production)        | ✅     |
| Sentry Error Tracking            | ✅     |
| defusedxml (XXE-Schutz)          | ✅     |
| SQL Injection (Django ORM)       | ✅     |

---

## Sicherheits-Changelogs

| Datum      | Paket       | Von     | Nach    | Grund                                      |
|------------|-------------|---------|---------|-------------------------------------------|
| 2026-02-22 | gunicorn    | 22.0.0  | 25.1.0  | HTTP Request Smuggling (vuln-id: 72809)   |
| 2026-02-22 | pip         | 24.0    | 26.0.1  | Wheel-Installation CVE (vuln-id: 75180/79883) |

---

## Danksagung

Dankeschön an alle, die verantwortungsvoll Sicherheitsprobleme melden.
