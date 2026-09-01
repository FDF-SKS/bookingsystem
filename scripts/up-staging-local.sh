#!/usr/bin/env bash
set -euo pipefail

# Helper: bring up the local staging stack without mounting/using Let's Encrypt certs.
# This ensures nginx runs on plain HTTP (port 8001 as configured) and avoids TLS errors.

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "Tearing down any existing compose stacks that may include production services..."
docker compose -f docker-compose.yaml -f docker-compose.staging.yaml --env-file .env.staging down || true

echo "Starting staging stack (staging compose only; no TLS certs required)..."
docker compose -f docker-compose.staging.yaml --env-file .env.staging up -d --build

echo "Staging stack started. Nginx will listen on host port 8001."
