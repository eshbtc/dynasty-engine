#!/usr/bin/env bash
# Package and upload React Native (Expo) mobile build to EAS or Google Play internal.
# This is a stub – real mobile deployment often uses Expo EAS CLI and Play Console.
# Usage: ./scripts/deploy_mobile.sh <PROFILE>  (e.g., production)
set -euo pipefail
PROFILE=${1:-production}

pushd apps/dynasty-mobile
  echo "[Mobile] Starting EAS build for profile $PROFILE …"
  if ! command -v eas &>/dev/null; then
    echo "EAS CLI not installed. Install with: npm i -g eas-cli" >&2
    exit 1
  fi
  eas build --profile "$PROFILE" --platform ios
popd

echo "Mobile build triggered on Expo EAS – upload to Play/TestFlight once complete."
