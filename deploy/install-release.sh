#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /absolute/path/to/sway-web.tar.gz" >&2
  exit 2
fi

artifact="$1"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
web_root="$repo_root/apps/web"
next_root="$web_root/.next"
current_release="$next_root/standalone"
pending_release="$next_root/standalone.pending.$$"
previous_release="$next_root/standalone.previous"
uv_bin="${UV_BIN:-$HOME/.local/bin/uv}"

if [[ ! -f "$artifact" ]]; then
  echo "Web artifact not found: $artifact" >&2
  exit 2
fi

if [[ ! -x "$uv_bin" ]]; then
  uv_bin="$(command -v uv || true)"
fi
if [[ -z "$uv_bin" || ! -x "$uv_bin" ]]; then
  echo "uv is not installed or executable" >&2
  exit 2
fi

cleanup() {
  rm -rf "$pending_release"
}
trap cleanup EXIT

mkdir -p "$pending_release"
tar -xzf "$artifact" -C "$pending_release"

if [[ ! -f "$pending_release/server.js" ]]; then
  echo "Invalid web artifact: server.js is missing" >&2
  exit 2
fi

# This is normally a no-op and is far lighter than building Next.js on the VM.
"$uv_bin" sync --project "$repo_root/apps/api" --frozen

rm -rf "$previous_release"
if [[ -d "$current_release" ]]; then
  mv "$current_release" "$previous_release"
fi
mv "$pending_release" "$current_release"

release_is_healthy() {
  local attempt
  for attempt in {1..30}; do
    if curl --fail --silent --show-error --max-time 3 \
      http://127.0.0.1:8010/health >/dev/null 2>&1 && \
      curl --fail --silent --show-error --max-time 3 \
      http://127.0.0.1:3010/ >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

if sudo systemctl restart sway-api sway-web && release_is_healthy; then
  rm -rf "$previous_release"
  rm -f "$artifact"
  trap - EXIT
  echo "Sway deployed successfully."
  exit 0
fi

echo "Release health check failed; restoring the previous web release." >&2
rm -rf "$current_release"
if [[ -d "$previous_release" ]]; then
  mv "$previous_release" "$current_release"
  sudo systemctl restart sway-api sway-web || true
fi
exit 1
