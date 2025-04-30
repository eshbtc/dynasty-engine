#!/usr/bin/env bash
# Deploy Next.js LP Portal (front-end) to Cloud Run (or Cloud Run for Anthos).
# Usage: ./scripts/deploy_lp_portal.sh <PROJECT_ID> <REGION> <VPC_CONNECTOR>
set -euo pipefail
PROJECT=${1:?"project"}
REGION=${2:-us-central1}
CONNECTOR=${3:-run-connector}
SERVICE=lp-portal
IMG="$REGION-docker.pkg.dev/$PROJECT/dynasty/${SERVICE}:$(git rev-parse --short HEAD)"

pushd lp-portal
  echo "[Portal] Building image $IMG …"
  docker build --platform linux/amd64 -t "$IMG" .
  docker push "$IMG"
popd

gcloud run deploy "$SERVICE" \
  --project "$PROJECT" --image "$IMG" --region "$REGION" \
  --platform managed --allow-unauthenticated \
  --vpc-connector "$CONNECTOR" --vpc-egress all \
  --cpu 1 --memory 512Mi --max-instances 2 \
  --set-env-vars "NEXT_PUBLIC_API_URL=https://$SERVICE-$REGION.a.run.app/api"

echo "Frontend deployed at: https://$(gcloud run services describe $SERVICE --region $REGION --format='value(status.url)')"
