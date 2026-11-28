#!/usr/bin/env bash
set -u

echo "============================================================"
echo " PROGRETECH MESH — CLOUD RUN / FIREBASE PREFLIGHT"
echo "============================================================"

RC=0

echo
echo "---- GCLOUD ----"
if command -v gcloud >/dev/null 2>&1; then
  echo "GCLOUD: $(command -v gcloud)"
  gcloud version 2>/dev/null | sed -n '1,8p'
else
  echo "GCLOUD: NOT INSTALLED"
  RC=10
fi

echo
echo "---- ACTIVE ACCOUNT ----"
if command -v gcloud >/dev/null 2>&1; then
  ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null | head -n 1)"
  if [[ -n "$ACCOUNT" ]]; then
    echo "ACTIVE ACCOUNT: $ACCOUNT"
  else
    echo "ACTIVE ACCOUNT: NONE"
    [[ "$RC" -eq 0 ]] && RC=11
  fi
fi

echo
echo "---- PROJECT ----"
if command -v gcloud >/dev/null 2>&1; then
  PROJECT="$(gcloud config get-value project 2>/dev/null || true)"
  if [[ -n "$PROJECT" && "$PROJECT" != "(unset)" ]]; then
    echo "PROJECT: $PROJECT"
  else
    echo "PROJECT: NOT SET"
    [[ "$RC" -eq 0 ]] && RC=12
  fi
fi

echo
echo "---- REQUIRED APIS ----"
if command -v gcloud >/dev/null 2>&1; then
  for api in run.googleapis.com secretmanager.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com; do
    if gcloud services list --enabled --filter="config.name=$api" --format='value(config.name)' 2>/dev/null | grep -qx "$api"; then
      echo "$api: ENABLED"
    else
      echo "$api: NOT ENABLED"
    fi
  done
fi

echo
echo "---- FIREBASE CLIENT CONFIG ----"
for key in MESH_FIREBASE_API_KEY MESH_FIREBASE_AUTH_DOMAIN MESH_FIREBASE_PROJECT_ID MESH_FIREBASE_APP_ID; do
  if [[ -n "${!key:-}" ]]; then
    echo "$key: SET"
  else
    echo "$key: MISSING"
  fi
done
echo "MESH_FIREBASE_AUTH_READY: ${MESH_FIREBASE_AUTH_READY:-0}"
echo "MESH_CODESEAL_READY: ${MESH_CODESEAL_READY:-0}"

echo
echo "---- TARGET ----"
echo "SERVICE: ${SERVICE:-progretech-mesh}"
echo "REGION: ${REGION:-us-east1}"
echo "CUSTOM ORIGIN: ${MESH_PUBLIC_ORIGIN:-https://mesh.progretech.com}"

echo
echo "PREFLIGHT RETURN CODE: $RC"
exit "$RC"
