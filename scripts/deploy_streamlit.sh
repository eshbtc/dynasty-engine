#!/bin/bash
# Deploy Streamlit app to Cloud Run
# Usage: ./scripts/deploy_streamlit.sh <gcp_project_id> <region> <backend_url>

set -e

PROJECT_ID=${1:-dynasty-engine}
REGION=${2:-us-central1}
BACKEND_URL=${3:-https://dynasty-engine-594497653266.us-central1.run.app}
IMAGE_NAME=streamlit-app
ARTIFACT_REGISTRY_URL="$REGION-docker.pkg.dev/$PROJECT_ID/dynasty/$IMAGE_NAME:latest"
SERVICE_NAME=streamlit-app
DOCKERFILE=streamlit.Dockerfile

# Build Docker image
echo "[Streamlit] Building Docker image..."
docker buildx build --platform linux/amd64 -f $DOCKERFILE -t $IMAGE_NAME --load .

echo "[Streamlit] Tagging image..."
docker tag $IMAGE_NAME $ARTIFACT_REGISTRY_URL

echo "[Streamlit] Pushing image to Artifact Registry..."
docker push $ARTIFACT_REGISTRY_URL

echo "[Streamlit] Deploying to Cloud Run with BACKEND_URL=$BACKEND_URL ..."
gcloud run deploy $SERVICE_NAME \
  --image=$ARTIFACT_REGISTRY_URL \
  --platform=managed \
  --region=$REGION \
  --allow-unauthenticated \
  --port=8080 \
  --set-env-vars=BACKEND_URL=$BACKEND_URL

echo "[Streamlit] Deployment complete!"
