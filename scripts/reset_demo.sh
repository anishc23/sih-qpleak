#!/usr/bin/env bash
#
# Reset the demo to a clean, self-consistent state.
#
# WHY THIS EXISTS
#
# The database and the chain remember different things, and resetting only one
# of them silently breaks the demo. Identifiers (PAPER-2026-001, Q-000001) are
# regenerated from the start by `seed --reset`, but the chain still holds the
# previous run's records under those same identifiers. The contracts then --
# correctly -- refuse everything that follows:
#
#   QuestionAlreadyRegistered      the id is taken
#   InvalidLifecycleTransition     the chain thinks the question is elsewhere
#   PaperAlreadyRegistered         no new paper can ever be sealed
#
# Reset both together, or neither. That is all this script does.
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RPC_PORT=8545
LOG_DIR="$ROOT/.logs"
mkdir -p "$LOG_DIR"

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }

say "1/4  Stopping the current chain"
pkill -f "hardhat node" 2>/dev/null || true
for _ in $(seq 1 20); do
  nc -z 127.0.0.1 "$RPC_PORT" 2>/dev/null || break
  sleep 0.5
done

say "2/4  Starting a fresh chain"
( cd blockchain && npx hardhat node >"$LOG_DIR/hardhat.log" 2>&1 & )
for _ in $(seq 1 60); do
  nc -z 127.0.0.1 "$RPC_PORT" 2>/dev/null && break
  sleep 0.5
done
nc -z 127.0.0.1 "$RPC_PORT" 2>/dev/null || { echo "chain did not start; see $LOG_DIR/hardhat.log"; exit 1; }
echo "     listening on 127.0.0.1:$RPC_PORT"

say "3/4  Deploying contracts"
( cd blockchain && npx hardhat run scripts/deploy.js --network localhost ) | grep -E "QuestionRegistry|PaperTimeLock"

say "4/4  Re-seeding the database against the new chain"
( cd backend && .venv/bin/python -m app.seed --reset ) 2>&1 | grep -E "Created|Approved|Anchored|demo exam" || true

say "Done. Database and chain now agree."
echo "If the API was already running it will pick the new chain up on its next"
echo "call -- the contract addresses are deterministic and did not change."
