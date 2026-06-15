#!/bin/bash
# One-time server setup — run once on a fresh Ubuntu 24.04 EC2 instance.
# Usage: bash deploy/setup.sh

set -e

# System packages
sudo apt-get update -y
sudo apt-get install -y git curl unzip

# Python 3.12 + uv
sudo apt-get install -y python3.12 python3.12-venv
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env

# Node.js 20
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# Caddy
sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt-get update -y
sudo apt-get install -y caddy

echo ""
echo "Setup complete. Next steps:"
echo "  1. Clone the repo: git clone <repo-url> /home/ubuntu/sway"
echo "  2. Copy env files: cp apps/api/.env.example apps/api/.env && fill in values"
echo "                     cp apps/web/.env.production.example apps/web/.env.production"
echo "  3. Copy service files: sudo cp deploy/*.service /etc/systemd/system/"
echo "  4. Copy Caddyfile: sudo cp deploy/Caddyfile /etc/caddy/Caddyfile"
echo "  5. Run: make install && make build-web"
echo "  6. Run: sudo systemctl daemon-reload && sudo systemctl enable --now sway-api sway-web"
echo "  7. Run: sudo systemctl reload caddy"
