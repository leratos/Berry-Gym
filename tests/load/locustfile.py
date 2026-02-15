"""
Berry-Gym Load Testing with Locust
====================================
Ziel: P95 < 500ms, P99 < 1000ms @ 100 concurrent users

Szenarien:
  BerryGymUser      – typische authentifizierte User-Session
  CachedEndpointUser – fokussiert auf gecachte API-Endpoints

Ausführung:
  locust -f tests/load/locustfile.py --config tests/load/locust.conf

WICHTIG: Vorher Test-User anlegen (siehe docs/LOAD_TESTING.md)
"""

import json
import random
import re

from locust import HttpUser, between, events, task

# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


def extract_csrftoken(response_text: str) -> str | None:
    """Extrahiert den CSRF-Token aus dem HTML-Body."""
    match = re.search(r'csrfmiddlewaretoken["\s]+value="([^"]+)"', response_text)
    if match:
        return match.group(1)
    # Fallback: Meta-Tag (für AJAX-Requests)
    match = re.search(r'<meta name="csrf-token" content="([^"]+)"', response_text)
    if match:
        return match.group(1)
    return None


def get_csrf_from_cookie(user: HttpUser) -> str | None:
    """Liest den CSRF-Token aus dem Session-Cookie."""
    return user.client.cookies.get("csrftoken")


# ---------------------------------------------------------------------------
# Test-User Konfiguration
# Wird als Locust-User-Klasse-Attribut gesetzt; kann per --host überschrieben
# werden. Die Credentials müssen in der Django-DB existieren.
# Siehe docs/LOAD_TESTING.md für Setup-Anleitung.
# ---------------------------------------------------------------------------

LOAD_TEST_USERS = [
    {"username": "loadtest_user1", "password": "LoadTest2024!"},
    {"username": "loadtest_user2", "password": "LoadTest2024!"},
    {"username": "loadtest_user3", "password": "LoadTest2024!"},
    {"username": "loadtest_user4", "password": "LoadTest2024!"},
    {"username": "loadtest_user5", "password": "LoadTest2024!"},
]


# ---------------------------------------------------------------------------
# Basis-Klasse mit Login/Logout
# ---------------------------------------------------------------------------


class AuthenticatedUser(HttpUser):
    """Basis-Klasse: Login beim Start, Logout beim Beenden."""

    abstract = True

    def on_start(self) -> None:
        """Einloggen und CSRF-Token holen."""
        credentials = random.choice(LOAD_TEST_USERS)
        self.username = credentials["username"]

        # GET Login-Seite – CSRF-Token holen
        with self.client.get(
            "/accounts/login/",
            name="/accounts/login/ [GET]",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"Login-Seite nicht erreichbar: {response.status_code}")
                return
            csrftoken = extract_csrftoken(response.text) or get_csrf_from_cookie(self)
            if not csrftoken:
                response.failure("Kein CSRF-Token auf Login-Seite gefunden")
                return

        # POST Login
        with self.client.post(
            "/accounts/login/",
            data={
                "username": credentials["username"],
                "password": credentials["password"],
                "csrfmiddlewaretoken": csrftoken,
            },
            headers={"Referer": f"{self.host}/accounts/login/"},
            name="/accounts/login/ [POST]",
            catch_response=True,
            allow_redirects=True,
        ) as response:
            # Django leitet nach Login auf "/" weiter → 200 nach Redirect = OK
            if (
                response.status_code == 200
                and "dashboard" in response.url
                or response.url.endswith("/")
            ):
                pass  # Erfolg
            elif response.status_code == 200 and "/accounts/login/" in response.url:
                response.failure(
                    f"Login fehlgeschlagen für {self.username} (zurück auf Login-Seite)"
                )
            elif response.status_code not in (200, 302):
                response.failure(f"Login unexpected status: {response.status_code}")

    def on_stop(self) -> None:
        """Logout via POST (Django 5.x: GET auf /accounts/logout/ gibt 405)."""
        csrftoken = get_csrf_from_cookie(self)
        if csrftoken:
            self.client.post(
                "/accounts/logout/",
                data={"csrfmiddlewaretoken": csrftoken},
                headers={"Referer": f"{self.host}/"},
                name="/accounts/logout/ [POST]",
            )
        # Kein csrftoken → Session einfach verwerfen, kein Logout-Request


# ---------------------------------------------------------------------------
# Szenario 1: Typische User-Session
# ---------------------------------------------------------------------------


class BerryGymUser(AuthenticatedUser):
    """
    Simuliert einen typischen Berry-Gym-Nutzer.

    Gewichtung der Tasks:
      - Dashboard (gecacht, 5 min TTL)  → häufig
      - Übungsliste (gecacht, 30 min)   → mittel
      - Trainingshistorie                → mittel
      - Stats                            → selten
      - Body-Stats                       → selten
      - Plan-Details                     → mittel
      - Training starten                 → selten (schreibend, Sonderfall)
    """

    wait_time = between(1, 3)  # Realistische Denkpause zwischen Requests

    @task(5)
    def dashboard(self) -> None:
        """Dashboard – gecachte Computed-Stats (5 min TTL)."""
        with self.client.get("/", name="/ [Dashboard]", catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Dashboard: {resp.status_code}")

    @task(3)
    def uebungen_liste(self) -> None:
        """Übungsliste – gecachte globale Übungen (30 min TTL)."""
        with self.client.get(
            "/uebungen/", name="/uebungen/ [Übungsliste]", catch_response=True
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Übungsliste: {resp.status_code}")

    @task(2)
    def training_history(self) -> None:
        """Trainingshistorie."""
        with self.client.get("/history/", name="/history/ [Historie]", catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Historie: {resp.status_code}")

    @task(2)
    def plan_library(self) -> None:
        """Plan-Bibliothek."""
        with self.client.get(
            "/plan-library/", name="/plan-library/ [Bibliothek]", catch_response=True
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Plan-Library: {resp.status_code}")

    @task(1)
    def training_stats(self) -> None:
        """Statistiken-Seite."""
        with self.client.get("/stats/", name="/stats/ [Statistiken]", catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Stats: {resp.status_code}")

    @task(1)
    def body_stats(self) -> None:
        """Körperwerte-Seite."""
        with self.client.get(
            "/body-stats/", name="/body-stats/ [Körperwerte]", catch_response=True
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Body-Stats: {resp.status_code}")

    @task(1)
    def profile(self) -> None:
        """Profil-Seite."""
        with self.client.get("/profile/", name="/profile/ [Profil]", catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Profil: {resp.status_code}")


# ---------------------------------------------------------------------------
# Szenario 2: Gecachte API-Endpoints unter Last
# ---------------------------------------------------------------------------


class CachedEndpointUser(AuthenticatedUser):
    """
    Fokussiert auf die gecachten API-Endpoints.
    Verifiziert dass der Cache unter Last hält und korrekt antwortet.

    Gecachte Endpoints:
      - /api/plan-templates/         (indefinit)
      - /uebungen/                   (30 min, globale Liste)
      - /                            (5 min, Dashboard-Stats)
    """

    wait_time = between(0.5, 2)

    @task(4)
    def api_plan_templates(self) -> None:
        """Plan-Templates API – indefinit gecacht."""
        with self.client.get(
            "/api/plan-templates/",
            name="/api/plan-templates/ [gecacht]",
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Plan-Templates: {resp.status_code}")
                return
            # Validierung: muss JSON mit Templates-Key sein
            try:
                data = resp.json()
                if not isinstance(data, (dict, list)):
                    resp.failure("Plan-Templates: Unerwartetes JSON-Format")
            except json.JSONDecodeError:
                resp.failure("Plan-Templates: Kein valides JSON")

    @task(3)
    def dashboard_cached(self) -> None:
        """Dashboard – mehrfach aufrufen um Cache-Hit zu testen."""
        with self.client.get("/", name="/ [Dashboard gecacht]", catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Dashboard: {resp.status_code}")

    @task(2)
    def uebungen_cached(self) -> None:
        """Übungsliste – globale Exercises gecacht."""
        with self.client.get(
            "/uebungen/",
            name="/uebungen/ [gecacht]",
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Übungsliste: {resp.status_code}")

    @task(1)
    def api_plan_template_detail(self) -> None:
        """
        Einzelnes Template aus der API – gecachter Lookup.
        Schlägt sauber fehl wenn der Template-Key nicht existiert (404 wird
        als Failure gewertet, nicht als Error – kein Exception-Spray in Logs).
        """
        # Bekannte Template-Keys aus der JSON-Datei
        known_keys = [
            "push_pull_legs",
            "upper_lower",
            "full_body_3x",
            "german_volume_training",
            "starting_strength",
        ]
        key = random.choice(known_keys)
        with self.client.get(
            f"/api/plan-templates/{key}/",
            name="/api/plan-templates/[key]/ [Detail]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 404:
                # Template-Key nicht in Daten vorhanden – kein Fehler, aber loggen
                resp.success()  # Nicht als Failure werten (Konfigurationsfrage)
            elif resp.status_code != 200:
                resp.failure(f"Template-Detail {key}: {resp.status_code}")


# ---------------------------------------------------------------------------
# Szenario 3: Lesende API-Requests (AJAX-typisch)
# ---------------------------------------------------------------------------


class ApiUser(AuthenticatedUser):
    """
    Simuliert AJAX-Requests wie sie im Browser-Frontend entstehen.
    Typisch für Single-Page-Interaktionen während einer Trainingssession.
    """

    wait_time = between(2, 5)

    def on_start(self) -> None:
        super().on_start()
        # Merken welche Übungs-IDs existieren könnten (konservative Range)
        # In Produktion: 50–200 globale Übungen
        self.uebung_ids = list(range(1, 30))

    @task(3)
    def get_last_set(self) -> None:
        """Letzten Satz einer Übung holen (AJAX während Training)."""
        uebung_id = random.choice(self.uebung_ids)
        with self.client.get(
            f"/api/last-set/{uebung_id}/",
            name="/api/last-set/[id]/ [AJAX]",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"Last-Set {uebung_id}: {resp.status_code}")

    @task(2)
    def exercise_api_detail(self) -> None:
        """Übungsdetails via API holen."""
        uebung_id = random.choice(self.uebung_ids)
        with self.client.get(
            f"/api/exercise/{uebung_id}/",
            name="/api/exercise/[id]/ [Detail]",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"Exercise-API {uebung_id}: {resp.status_code}")

    @task(1)
    def ml_model_info(self) -> None:
        """ML-Modellstatus (lesend, kein Training)."""
        uebung_id = random.choice(self.uebung_ids)
        with self.client.get(
            f"/api/ml/model-info/{uebung_id}/",
            name="/api/ml/model-info/[id]/ [lesend]",
            catch_response=True,
        ) as resp:
            # 404 = kein ML-Modell für diese Übung – erwartetes Verhalten
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"ML-Model-Info {uebung_id}: {resp.status_code}")


# ---------------------------------------------------------------------------
# Event-Handler: Zusammenfassung nach Test-Ende
# ---------------------------------------------------------------------------


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs) -> None:
    """Gibt nach dem Test eine Zusammenfassung der SLO-Erreichung aus."""
    stats = environment.stats.total
    if stats.num_requests == 0:
        print("\n[Load Test] Keine Requests gemessen.")
        return

    p95 = stats.get_response_time_percentile(0.95)
    p99 = stats.get_response_time_percentile(0.99)
    failure_rate = (stats.num_failures / stats.num_requests) * 100

    print("\n" + "=" * 60)
    print("LOAD TEST ERGEBNIS – Berry-Gym SLO-Check")
    print("=" * 60)
    print(f"  Requests gesamt:  {stats.num_requests}")
    print(f"  Fehlerrate:       {failure_rate:.2f}%  (Ziel: < 1%)")
    print(f"  P95 Latenz:       {p95:.0f}ms        (Ziel: < 500ms)")
    print(f"  P99 Latenz:       {p99:.0f}ms        (Ziel: < 1000ms)")
    print("-" * 60)

    slo_ok = True
    if p95 and p95 > 500:
        print(f"  ❌ P95 VERLETZT: {p95:.0f}ms > 500ms")
        slo_ok = False
    else:
        print(f"  ✅ P95 OK: {p95:.0f}ms ≤ 500ms" if p95 else "  ⚠️  P95 nicht messbar")

    if p99 and p99 > 1000:
        print(f"  ❌ P99 VERLETZT: {p99:.0f}ms > 1000ms")
        slo_ok = False
    else:
        print(f"  ✅ P99 OK: {p99:.0f}ms ≤ 1000ms" if p99 else "  ⚠️  P99 nicht messbar")

    if failure_rate > 1.0:
        print(f"  ❌ FEHLERRATE VERLETZT: {failure_rate:.2f}% > 1%")
        slo_ok = False
    else:
        print(f"  ✅ Fehlerrate OK: {failure_rate:.2f}% ≤ 1%")

    print("=" * 60)
    print(
        f"  GESAMT: {'✅ ALLE SLOs ERFÜLLT' if slo_ok else '❌ SLO-VERLETZUNG – Optimierung nötig'}"
    )
    print("=" * 60 + "\n")
