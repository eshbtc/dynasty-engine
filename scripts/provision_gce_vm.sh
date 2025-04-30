#!/usr/bin/env bash
# Automate creation of a minimal GCE VM running IB Gateway (paper). Requires gcloud CLI.
# Usage: ./scripts/provision_gce_vm.sh <PROJECT> <ZONE> <SUBNET>
# Example: ./scripts/provision_gce_vm.sh my-gcp-project us-central1-a default

set -euo pipefail
PROJECT=${1:?"GCP project required"}
ZONE=${2:-us-central1-a}
SUBNET=${3:-default}
VM_NAME=ib-gateway

# --- Ensure required APIs are enabled ---
REQUIRED_APIS=(compute.googleapis.com vpcaccess.googleapis.com)
for api in "${REQUIRED_APIS[@]}"; do
  if ! gcloud services list --enabled --project "$PROJECT" | grep -q "$api"; then
    echo "[Setup] Enabling API $api …"
    gcloud services enable "$api" --project "$PROJECT"
  fi
done

CONNECTOR=run-connector
CONNECTOR_SUBNET=vpc-connector-subnet
CONNECTOR_SUBNET_RANGE=10.8.0.0/28

# Create VM if not exists
if gcloud compute instances describe "$VM_NAME" --zone "$ZONE" --project "$PROJECT" &>/dev/null; then
  echo "[Info] VM $VM_NAME already exists – skipping creation"
else
  echo "[Setup] Creating VM $VM_NAME …"
  gcloud compute instances create "$VM_NAME" \
    --project "$PROJECT" \
    --zone "$ZONE" \
    --machine-type e2-small \
    --subnet "$SUBNET" \
    --image-family debian-11 --image-project debian-cloud \
    --boot-disk-size 20GB \
    --metadata-from-file startup-script=scripts/startup_ibgateway.sh \
    --tags ibgateway
fi

# Get internal IP
IP=$(gcloud compute instances describe "$VM_NAME" --zone "$ZONE" --project "$PROJECT" --format='value(networkInterfaces[0].networkIP)')
echo "VM $VM_NAME internal IP → $IP"

# Create dedicated /28 subnet for VPC connector (if not exists)
echo "Ensuring VPC connector subnet $CONNECTOR_SUBNET exists"
gcloud compute networks subnets describe "$CONNECTOR_SUBNET" --region ${ZONE%-*} --project "$PROJECT" &>/dev/null || \
  gcloud compute networks subnets create "$CONNECTOR_SUBNET" \
    --network=default \
    --region=${ZONE%-*} \
    --range="$CONNECTOR_SUBNET_RANGE" \
    --project "$PROJECT"

echo "Creating Cloud Run VPC connector $CONNECTOR (if not exists)"
gcloud compute networks vpc-access connectors describe "$CONNECTOR" --region ${ZONE%-*} --project "$PROJECT" >/dev/null 2>&1 || \
  gcloud compute networks vpc-access connectors create "$CONNECTOR" --region ${ZONE%-*} --subnet "$CONNECTOR_SUBNET" --min-instances 2 --max-instances 3 --project "$PROJECT"

echo "Creating firewall rule to allow internal 7497"
RULE=allow-ib-internal
gcloud compute firewall-rules describe "$RULE" --project "$PROJECT" >/dev/null 2>&1 || \
  gcloud compute firewall-rules create "$RULE" \
    --network "$SUBNET" --direction INGRESS --action ALLOW --rules tcp:7497 --source-ranges 10.0.0.0/8

cat <<EOF
Setup complete.
Add the following env vars when deploying Cloud Run:
  IBKR_HOST=$IP
  IBKR_PORT=7497
  IBKR_CLIENT_ID=1002
  PAPER_TRADE=true
and specify --vpc-connector $CONNECTOR --vpc-egress all
EOF
