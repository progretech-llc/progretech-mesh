#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-us-east1}"
SERVICE="${SERVICE:-progretech-mesh}"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-}"
DEPLOYMENT_TIER="${MESH_DEPLOYMENT_TIER:-staging}"
PUBLIC_ORIGIN="${MESH_PUBLIC_ORIGIN:-https://mesh.progretech.com}"

SESSION_SECRET_NAME="${SESSION_SECRET_NAME:-progretech-mesh-session-key}"
ACTIVATION_SECRET_NAME="${ACTIVATION_SECRET_NAME:-progretech-mesh-activation-secret}"
DEVICE_SECRET_NAME="${DEVICE_SECRET_NAME:-progretech-mesh-device-secret}"
SECRET_VERSION="${SECRET_VERSION:-latest}"

FIREBASE_API_KEY="${MESH_FIREBASE_API_KEY:-}"
FIREBASE_AUTH_DOMAIN="${MESH_FIREBASE_AUTH_DOMAIN:-}"
FIREBASE_PROJECT_ID="${MESH_FIREBASE_PROJECT_ID:-${PROJECT_ID}}"
FIREBASE_APP_ID="${MESH_FIREBASE_APP_ID:-}"
FIREBASE_AUTH_READY="${MESH_FIREBASE_AUTH_READY:-0}"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "PROJECT_ID is required (or set a gcloud default project)."
  exit 1
fi

if [[ "${MESH_AUTH_MODE:-progretech-shared}" != "progretech-shared" && ( -z "${FIREBASE_API_KEY}" || -z "${FIREBASE_AUTH_DOMAIN}" || -z "${FIREBASE_PROJECT_ID}" || -z "${FIREBASE_APP_ID}" ) ]]; then
  echo "Firebase web configuration is incomplete."
  echo "Required:"
  echo "  MESH_FIREBASE_API_KEY"
  echo "  MESH_FIREBASE_AUTH_DOMAIN"
  echo "  MESH_FIREBASE_PROJECT_ID"
  echo "  MESH_FIREBASE_APP_ID"
  exit 3
fi

if [[ "${DEPLOYMENT_TIER}" == "production" ]]; then
  if [[ "${MESH_CODESEAL_READY:-0}" != "1" ]]; then
    echo "Refusing production deployment."
    echo "Production requires:"
    echo "  MESH_FIREBASE_AUTH_READY=1"
    echo "  MESH_CODESEAL_READY=1"
    echo "Set these only after live acceptance."
    exit 2
  fi
fi

gcloud config set project "${PROJECT_ID}" >/dev/null

ENV_VARS="APP_ENV=production"
ENV_VARS+=",MESH_DEPLOYMENT_TIER=${DEPLOYMENT_TIER}"
ENV_VARS+=",MESH_VERSION=1.18.3-e2e-stability"
ENV_VARS+=",BUILD_ID=v1-rc2-private-lan-acceptance-20260913"
ENV_VARS+=",FLASK_DEBUG=0"
ENV_VARS+=",TRUST_PROXY_HEADERS=1"
ENV_VARS+=",DEV_AUTH_ENABLED=0"
ENV_VARS+=",DEV_SEED_AGENTS=0"
ENV_VARS+=",MESH_AUTH_MODE=progretech-shared"
ENV_VARS+=",MESH_AGENT_IDENTITY_MODE=codeseal"
ENV_VARS+=",CODESEAL_VERIFIER_MODE=${CODESEAL_VERIFIER_MODE:-unconfigured}"
ENV_VARS+=",MESH_FIREBASE_API_KEY=${FIREBASE_API_KEY}"
ENV_VARS+=",MESH_FIREBASE_AUTH_DOMAIN=${FIREBASE_AUTH_DOMAIN}"
ENV_VARS+=",MESH_FIREBASE_PROJECT_ID=${FIREBASE_PROJECT_ID}"
ENV_VARS+=",MESH_FIREBASE_APP_ID=${FIREBASE_APP_ID}"
ENV_VARS+=",MESH_FIREBASE_AUTH_READY=${FIREBASE_AUTH_READY}"
ENV_VARS+=",MESH_CODESEAL_READY=${MESH_CODESEAL_READY:-0}"
ENV_VARS+=",MESH_IDENTITY_REPLAY_MODE=${MESH_IDENTITY_REPLAY_MODE:-single-process-bounded}"
ENV_VARS+=",MESH_PUBLIC_ORIGIN=${PUBLIC_ORIGIN}"

ARGS=(
  run deploy "${SERVICE}"
  --source .
  --region "${REGION}"
  --execution-environment gen2
  --allow-unauthenticated
  --port 8080
  --timeout 3600
  --min-instances 0
  --max-instances 1
  --concurrency 80
  --cpu 1
  --memory 512Mi
  --startup-probe "httpGet.path=/startupz,httpGet.port=8080,initialDelaySeconds=0,failureThreshold=12,timeoutSeconds=2,periodSeconds=5"
  --liveness-probe "httpGet.path=/healthz,httpGet.port=8080,initialDelaySeconds=10,failureThreshold=3,timeoutSeconds=2,periodSeconds=30"
  --update-env-vars "${ENV_VARS}"
  --update-secrets "SECRET_KEY=${SESSION_SECRET_NAME}:${SECRET_VERSION},MESH_ACTIVATION_SECRET=${ACTIVATION_SECRET_NAME}:${SECRET_VERSION},MESH_DEVICE_CREDENTIAL_SECRET=${DEVICE_SECRET_NAME}:${SECRET_VERSION}"
)

if [[ -n "${SERVICE_ACCOUNT}" ]]; then
  ARGS+=(--service-account "${SERVICE_ACCOUNT}")
fi

echo "Deploying ${SERVICE} to ${REGION} as ${DEPLOYMENT_TIER}..."
gcloud "${ARGS[@]}"

URL="$(gcloud run services describe "${SERVICE}" --region "${REGION}" --format='value(status.url)')"

echo
echo "Deployment submitted."
echo "Service URL: ${URL}"
echo "Public origin target: ${PUBLIC_ORIGIN}"
echo "Run: SERVICE_URL='${PUBLIC_ORIGIN}' ./scripts/verify-cloud-run.sh"
