#!/usr/bin/env bash
# Startup script run on GCE VM boot to install Docker and run IB Gateway in paper-trading mode.
# The IB Gateway container listens on host port 7497 so Dynasty Cloud-Run service can reach it.
# If you later switch to live trading, change TRADING_MODE=live and inject credentials via env.

set -euxo pipefail

apt-get update -y
apt-get install -y docker.io
systemctl enable --now docker

# Pull and start community container (stable tag)
#  - Host port 7497 maps to container 4002 (paper mode API)
#  - --restart=always ensures IB Gateway restarts on VM reboot/crash
#  - READONLY_API=yes limits trade legitimacy during vetting

docker run -d --restart=always --name ib-gateway \
  -p 7497:4002 \
  -e TRADING_MODE=paper \
  -e READONLY_API=yes \
  ghcr.io/borchero/ibgateway:stable
