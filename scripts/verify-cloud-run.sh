#!/usr/bin/env bash
set -euo pipefail

SERVICE_URL="${SERVICE_URL:-}"
if [[ -z "${SERVICE_URL}" ]]; then
  echo "Set SERVICE_URL to the Cloud Run service URL."
  exit 1
fi
SERVICE_URL="${SERVICE_URL%/}"

echo "Checking ${SERVICE_URL}"
curl -fsS "${SERVICE_URL}/healthz" | python3 -m json.tool
echo
curl -fsS "${SERVICE_URL}/startupz" | python3 -m json.tool
echo

READY_CODE="$(curl -sS -o /tmp/mesh-ready.json -w '%{http_code}' "${SERVICE_URL}/readyz")"
python3 -m json.tool /tmp/mesh-ready.json
rm -f /tmp/mesh-ready.json
echo
echo "readyz status: ${READY_CODE}"

LOGIN_CODE="$(curl -sS -o /tmp/mesh-login.html -w '%{http_code}' "${SERVICE_URL}/login")"
if [[ "${LOGIN_CODE}" != "200" ]]; then
  echo "LOGIN PAGE FAIL: HTTP ${LOGIN_CODE}"
  rm -f /tmp/mesh-login.html
  exit 2
fi
if grep -q "Sign in with ProgreTech" /tmp/mesh-login.html; then
  echo "Shared ProgreTech login surface: PASS"
else
  echo "Shared ProgreTech login surface: FAIL"
  rm -f /tmp/mesh-login.html
  exit 3
fi
rm -f /tmp/mesh-login.html

AUTH_CODE="$(curl -sS -o /dev/null -w '%{http_code}' "${SERVICE_URL}/auth/progretech/login")"
if [[ "${AUTH_CODE}" != "302" ]]; then
  echo "Shared ProgreTech redirect: FAIL (${AUTH_CODE})"
  exit 4
fi

curl -fsSI "${SERVICE_URL}/manifest.webmanifest" >/dev/null
curl -fsSI "${SERVICE_URL}/sw.js" >/dev/null
echo "PWA shell endpoints: reachable"

if [[ "${READY_CODE}" != "200" ]]; then
  echo "Service is running but production readiness is still incomplete."
  exit 5
fi

echo "Cloud Run verification PASS"
