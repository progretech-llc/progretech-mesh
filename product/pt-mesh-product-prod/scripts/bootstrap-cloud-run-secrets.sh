#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-}"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-}"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "PROJECT_ID is required."
  exit 1
fi

gcloud config set project "${PROJECT_ID}"
gcloud services enable run.googleapis.com secretmanager.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com

create_secret_if_missing() {
  local name="$1"
  if ! gcloud secrets describe "${name}" >/dev/null 2>&1; then
    gcloud secrets create "${name}" --replication-policy=automatic
  fi
}

create_secret_version() {
  local name="$1"
  local value="$2"
  printf '%s' "${value}" | gcloud secrets versions add "${name}" --data-file=-
}

SESSION="progretech-mesh-session-key"
ACTIVATION="progretech-mesh-activation-secret"
DEVICE="progretech-mesh-device-secret"

create_secret_if_missing "${SESSION}"
create_secret_if_missing "${ACTIVATION}"
create_secret_if_missing "${DEVICE}"

python3 - <<'PY' >/tmp/mesh-secrets.txt
import secrets
for _ in range(3):
    print(secrets.token_urlsafe(48))
PY

mapfile -t VALUES </tmp/mesh-secrets.txt
rm -f /tmp/mesh-secrets.txt

create_secret_version "${SESSION}" "${VALUES[0]}"
create_secret_version "${ACTIVATION}" "${VALUES[1]}"
create_secret_version "${DEVICE}" "${VALUES[2]}"

if [[ -n "${SERVICE_ACCOUNT}" ]]; then
  for SECRET in "${SESSION}" "${ACTIVATION}" "${DEVICE}"; do
    gcloud secrets add-iam-policy-binding "${SECRET}"       --member="serviceAccount:${SERVICE_ACCOUNT}"       --role="roles/secretmanager.secretAccessor" >/dev/null
  done
fi

echo "Mesh Secret Manager baseline created."
