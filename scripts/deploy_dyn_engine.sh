#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Deploy Dynasty Engine backend (Python) to Cloud Run.
# Builds the Docker image, pushes it to Artifact Registry and deploys.
# ---------------------------------------------------------------------------
# Usage: ./scripts/deploy_dyn_engine.sh <PROJECT_ID> <REGION> <VPC_CONNECTOR> <IB_GATEWAY_INTERNAL_IP>
# Example: ./scripts/deploy_dyn_engine.sh my-gcp-project us-central1 run-connector 10.0.0.5
# ---------------------------------------------------------------------------
set -euo pipefail

if [[ $# -lt 4 ]]; then
  echo "Usage: $0 <PROJECT_ID> <REGION> <VPC_CONNECTOR> <IB_GATEWAY_INTERNAL_IP>" >&2
  exit 1
fi

PROJECT=$1
REGION=$2
CONNECTOR=$3
IB_HOST=$4
SERVICE=dynasty-engine

# --- Ensure required APIs are enabled ---
REQUIRED_APIS=(run.googleapis.com artifactregistry.googleapis.com vpcaccess.googleapis.com secretmanager.googleapis.com)
for api in "${REQUIRED_APIS[@]}"; do
  if ! gcloud services list --enabled --project "$PROJECT" | grep -q "$api"; then
    echo "[Setup] Enabling API $api …"
    gcloud services enable "$api" --project "$PROJECT"
  fi
done

# Ensure Artifact Registry repo exists
if ! gcloud artifacts repositories describe dynasty --location "$REGION" --project "$PROJECT" &>/dev/null; then
  echo "[Setup] Creating Artifact Registry repo 'dynasty' in $REGION …"
  gcloud artifacts repositories create dynasty --repository-format=docker --location "$REGION" --description="Dynasty images"
fi

IMG="$REGION-docker.pkg.dev/$PROJECT/dynasty/${SERVICE}:$(git rev-parse --short HEAD)"

echo "[Deploy] Building container ${IMG} …"
docker build -t "$IMG" .

echo "[Deploy] Pushing to Artifact Registry …"
docker push "$IMG"

echo "[Deploy] Deploying Cloud Run service ${SERVICE} …"
gcloud run deploy "$SERVICE" \
  --project "$PROJECT" \
  --image "$IMG" \
  --region "$REGION" \
  --platform managed \
  --vpc-connector "$CONNECTOR" \
  --vpc-egress all \
  --cpu 1 --memory 1Gi \
  --max-instances 2 \
  --set-env-vars "PAPER_TRADE=true,LOG_LEVEL=INFO,IBKR_HOST=${IB_HOST},IBKR_PORT=7497,IBKR_CLIENT_ID=1002" \
  --no-allow-unauthenticated

# Grant Secret Manager access to service account used by Cloud Run
SA=$(gcloud run services describe "$SERVICE" --platform managed --region "$REGION" --project "$PROJECT" --format 'value(spec.template.spec.serviceAccount)')
if [[ -n "$SA" ]]; then
  echo "[Setup] Ensuring $SA has Secret Manager access …"
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member "serviceAccount:$SA" \
    --role roles/secretmanager.secretAccessor --quiet || true
fi

echo "[Deploy] Done – check logs with:\n  gcloud run services logs tail ${SERVICE} --region ${REGION}"
