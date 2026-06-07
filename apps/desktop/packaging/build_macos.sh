#!/usr/bin/env bash
# Build Sway.app with PyInstaller. Run from apps/desktop: bash packaging/build_macos.sh
set -euo pipefail
cd "$(dirname "$0")/.."

uv run pyinstaller \
  --name Sway \
  --windowed \
  --noconfirm \
  --clean \
  --icon packaging/icon.icns \
  --osx-bundle-identifier com.sway.Sway \
  --add-data "app/assets:app/assets" \
  --add-data "app/db/schema.sql:app/db" \
  --collect-all supabase \
  --collect-all supabase_auth \
  --collect-all postgrest \
  --collect-all realtime \
  --collect-all storage3 \
  --collect-all supabase_functions \
  --collect-all googleapiclient \
  --collect-all google_auth_oauthlib \
  --collect-all google \
  main.py

echo "Built: dist/Sway.app"
