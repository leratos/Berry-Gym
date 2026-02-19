#!/usr/bin/env bash
# smoke_test.sh – Grundlegende Erreichbarkeits-Tests nach Deploy
#
# Verwendung:
#   ./scripts/smoke_test.sh https://gym.last-strawberry.com
#   ./scripts/smoke_test.sh http://localhost:8000  (lokal)
#
# Exit-Code 0 = alles ok, Exit-Code 1 = mindestens ein Check fehlgeschlagen

set -euo pipefail

BASE_URL="${1:-https://gym.last-strawberry.com}"
TIMEOUT=10
PASS=0
FAIL=0

check() {
  local description="$1"
  local url="$2"
  local expected_status="${3:-200}"

  actual_status=$(curl -s -o /dev/null -w "%{http_code}" \
    --max-time "$TIMEOUT" \
    --location \
    "$url" 2>/dev/null || echo "000")

  if [ "$actual_status" == "$expected_status" ]; then
    echo "  ✅ $description ($actual_status)"
    PASS=$((PASS + 1))
  else
    echo "  ❌ $description – erwartet $expected_status, bekommen $actual_status"
    FAIL=$((FAIL + 1))
  fi
}

echo "=========================================="
echo " Smoke Test: $BASE_URL"
echo "=========================================="

echo ""
echo "--- Öffentliche Seiten ---"
check "Login-Seite erreichbar"          "$BASE_URL/accounts/login/"        200
check "Beta-Bewerbung erreichbar"       "$BASE_URL/apply-beta/"            200
check "PWA Manifest vorhanden"          "$BASE_URL/manifest.json"          200
check "Service Worker vorhanden"        "$BASE_URL/sw.js"                  200

echo ""
echo "--- Redirects & Security ---"
check "Dashboard → Login redirect"     "$BASE_URL/dashboard/"             200
  # 200 weil curl --location dem Redirect folgt bis zur Login-Seite
check "Admin erreichbar"               "$BASE_URL/admin/"                 200

echo ""
echo "--- Static Files ---"
check "Statische Dateien verfügbar"    "$BASE_URL/static/core/css/main.css" 200

echo ""
echo "=========================================="
if [ "$FAIL" -eq 0 ]; then
  echo " ✅ Alle $PASS Checks bestanden"
  echo "=========================================="
  exit 0
else
  echo " ❌ $FAIL von $((PASS + FAIL)) Checks fehlgeschlagen"
  echo "=========================================="
  exit 1
fi
