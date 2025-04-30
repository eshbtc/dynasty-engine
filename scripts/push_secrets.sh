#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Push/update secrets from .env to Google Secret Manager.
# Only keys listed in the FILTERS array will be synced.
# Usage: ./scripts/push_secrets.sh [PROJECT_ID]
# Requires: gcloud CLI authenticated and IAM Secret Manager Admin role.
# ---------------------------------------------------------------------------
set -euo pipefail

ENV_FILE=.env
PROJECT=${1:-$(gcloud config get-value project 2>/dev/null)}

if [[ -z "$PROJECT" ]]; then
  echo "[Error] GCP project not set. Pass as arg or run 'gcloud config set project <id>'." >&2
  exit 1
fi

# Ensure Secret Manager API is enabled
if ! gcloud services list --enabled --project "$PROJECT" | grep -q secretmanager.googleapis.com; then
  echo "[Info] Enabling Secret Manager API for project $PROJECT …"
  gcloud services enable secretmanager.googleapis.com --project "$PROJECT"
  # Wait for propagation (max 90s)
  echo "[Info] Waiting for Secret Manager API to propagate …"
  for i in {1..18}; do  # 18*5s = 90s
    if gcloud services list --enabled --project "$PROJECT" | grep -q secretmanager.googleapis.com; then
      break
    fi
    sleep 5
  done
fi

FILTERS=(OPENAI_API_KEY POLYGON_KEY TEAMS_URL IBKR_USERNAME IBKR_PASSWORD DYNASTY_HALT PAPER_TRADE PROM_PORT)

upsert_secret() {
  local name=$1 value=$2
  if gcloud secrets describe "$name" --project "$PROJECT" &>/dev/null; then
    echo "$value" | gcloud secrets versions add "$name" --data-file=- --project "$PROJECT" >/dev/null
    echo "Updated secret $name"
  else
    echo "$value" | gcloud secrets create "$name" --replication-policy="automatic" --data-file=- --project "$PROJECT" >/dev/null
    echo "Created secret $name"
  fi
}

while IFS= read -r line || [[ -n "$line" ]]; do
  [[ "$line" =~ ^#.*$ ]] && continue  # skip comments
  [[ -z "$line" ]] && continue       # skip blanks
  if [[ "$line" =~ ^([A-Za-z0-9_]+)=(.*)$ ]]; then
    key="${BASH_REMATCH[1]}"; value="${BASH_REMATCH[2]}"
    for f in "${FILTERS[@]}"; do
      if [[ "$key" == "$f" ]]; then
        upsert_secret "$key" "$value"
      fi
    done
  fi
done < "$ENV_FILE"

# Ensure caller has Secret Manager Admin role (optional – will fail if not allowed)
ACCOUNT=$(gcloud config get-value account)
if ! gcloud projects get-iam-policy "$PROJECT" --flatten="bindings[].members" --format="value(bindings.members)" | grep -q "$ACCOUNT"; then
  echo "[Warning] $ACCOUNT may lack Secret Manager roles. Consider running:\n  gcloud projects add-iam-policy-binding $PROJECT --member=\"user:$ACCOUNT\" --role=roles/secretmanager.admin"
fi

echo "Secret sync complete for project $PROJECT."
