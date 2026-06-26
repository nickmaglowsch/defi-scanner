#!/usr/bin/env bash
set -euo pipefail

# DeFi Alpha Scanner — local dev runner.
# Pulls TimescaleDB + backend + frontend, all wired with the .env at repo root.

cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "ERROR: .env missing. Create it with at least:" >&2
  echo '  DEFI_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/<your-key>' >&2
  exit 1
fi

# Stop anything from a previous run (ignore errors if nothing is running).
docker compose down 2>/dev/null || true

# Build + start in the foreground so you see logs in this terminal.
# TimescaleDB -> backend (runs migrations) -> frontend.
exec docker compose up --build