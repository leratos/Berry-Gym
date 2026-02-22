# Security Policy

## Supported Versions

Only the latest version (main branch) of HomeGym is supported with security updates.

| Version | Supported          |
|---------|--------------------|
| latest  | ✅                  |
| < 1.0   | ❌                  |

---

## Reporting a Vulnerability

**Please do not report security vulnerabilities as public GitHub Issues.**

Report privately via a [GitHub Security Advisory](https://github.com/leratos/Berry-Gym/security/advisories/new)  
or by e-mail: **security@last-strawberry.com**

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Optional: suggested fix

I aim to respond within **48 hours** and will work with you on a patch before public disclosure.

---

## Scope

**In scope:**
- Authentication & authorization (login, session management)
- Cross-user data access (user isolation failures)
- Injection attacks (SQL, XSS, CSRF)
- Insecure direct object references (IDOR)
- API endpoint vulnerabilities

**Out of scope:**
- Rate-limit bypasses without real-world impact
- Self-XSS (only affects the authenticated user themselves)
- Social engineering
- Physical access to infrastructure
- Theoretical vulnerabilities without a proof of concept

---

## Security Measures

| Measure                              | Status |
|--------------------------------------|--------|
| CSRF protection (Django middleware)  | ✅     |
| Brute-force protection (django-axes) | ✅     |
| Rate limiting (AI endpoints)         | ✅     |
| HSTS (1 year, incl. subdomains)      | ✅     |
| Secure cookies (HTTPS only)          | ✅     |
| X-Frame-Options: DENY                | ✅     |
| Content-Type-Nosniff                 | ✅     |
| SSL redirect (production)            | ✅     |
| Sentry error tracking                | ✅     |
| defusedxml (XXE protection)          | ✅     |
| SQL injection (Django ORM)           | ✅     |

---

## Security Changelog

| Date       | Package  | From    | To      | Reason                                              |
|------------|----------|---------|---------|-----------------------------------------------------|
| 2026-02-22 | gunicorn | 22.0.0  | 25.1.0  | HTTP request smuggling (vuln-id: 72809)             |
| 2026-02-22 | pip      | 24.0    | 26.0.1  | Wheel installation CVE (vuln-id: 75180 / 79883)     |

---

Thank you for helping keep this project secure!
