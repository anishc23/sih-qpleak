#!/usr/bin/env bash
#
# One-command startup for macOS and Linux -- the counterpart to start.ps1.
#
# Brings up the whole stack in dependency order: chain, contracts, database,
# API, web. Safe to re-run; it reuses whatever is already installed and only
# re-seeds when the database is missing.
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

LOG_DIR="$ROOT/.logs"
mkdir -p "$LOG_DIR"

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
fail() { printf '\n\033[31m%s\033[0m\n' "$*" >&2; exit 1; }

wait_for_port() {
  local port=$1 name=$2
  for _ in $(seq 1 120); do
    nc -z 127.0.0.1 "$port" 2>/dev/null && return 0
    sleep 0.5
  done
  fail "$name did not come up on port $port -- see $LOG_DIR/"
}

# ---------------------------------------------------------------- prerequisites
say "Checking prerequisites"

command -v node >/dev/null || fail "Node 18+ is required but was not found."
NODE_MAJOR=$(node -p "process.versions.node.split('.')[0]")
[ "$NODE_MAJOR" -ge 18 ] || fail "Node 18+ is required (found $(node -v))."

# The backend pins pydantic-core 2.27, whose PyO3 build refuses anything newer
# than 3.13. Picking the interpreter here is far kinder than a Rust build error
# five hundred lines deep in pip output.
PY=""
for candidate in python3.13 python3.12 python3.11; do
  if command -v "$candidate" >/dev/null; then PY="$candidate"; break; fi
done
if [ -z "$PY" ]; then
  if command -v python3 >/dev/null; then
    PY_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')
    if [ "$PY_MINOR" -ge 11 ] && [ "$PY_MINOR" -le 13 ]; then
      PY=python3
    else
      fail "Python 3.11-3.13 is required (found $(python3 -V)).
On macOS:  brew install python@3.13
On Ubuntu: sudo apt install python3.13-venv"
    fi
  else
    fail "Python 3.11-3.13 is required but no python3 was found."
  fi
fi
echo "     node $(node -v), $($PY -V)"

# ---------------------------------------------------------------- dependencies
if [ ! -d blockchain/node_modules ]; then
  say "Installing chain dependencies"; ( cd blockchain && npm install )
fi
if [ ! -d frontend/node_modules ]; then
  say "Installing web dependencies"; ( cd frontend && npm install )
fi
if [ ! -d backend/.venv ]; then
  say "Creating the Python environment"
  "$PY" -m venv backend/.venv
  backend/.venv/bin/pip install -q --upgrade pip
  backend/.venv/bin/pip install -q -r backend/requirements.txt
fi

# ---------------------------------------------------------------- chain
if nc -z 127.0.0.1 8545 2>/dev/null; then
  say "Chain already running on 8545 -- reusing it"
else
  say "Starting the local chain"
  ( cd blockchain && npx hardhat node >"$LOG_DIR/hardhat.log" 2>&1 & )
  wait_for_port 8545 "chain"
fi

# Deploying again onto a chain that already holds the contracts is not
# harmless: the deployer's nonce has moved on, so the new copies land at new
# addresses, the deployment file starts pointing at empty contracts, and every
# already-sealed paper is orphaned the next time the API restarts. Deploy only
# when the recorded contracts are genuinely absent from this chain.
DEPLOYMENT="blockchain/deployments/localhost.json"
NEEDS_DEPLOY=1
if [ -f "$DEPLOYMENT" ]; then
  RECORDED=$(node -p "require('./$DEPLOYMENT').contracts.PaperTimeLock" 2>/dev/null || echo "")
  if [ -n "$RECORDED" ]; then
    CODE=$(curl -s -X POST http://127.0.0.1:8545 \
      -H 'Content-Type: application/json' \
      --data "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"eth_getCode\",\"params\":[\"$RECORDED\",\"latest\"]}" \
      | node -pe 'JSON.parse(require("fs").readFileSync(0,"utf8")).result' 2>/dev/null || echo "0x")
    [ "$CODE" != "0x" ] && [ -n "$CODE" ] && NEEDS_DEPLOY=0
  fi
fi

if [ "$NEEDS_DEPLOY" -eq 1 ]; then
  say "Deploying contracts"
  ( cd blockchain && npx hardhat run scripts/deploy.js --network localhost ) \
    | grep -E "QuestionRegistry|PaperTimeLock" || true
else
  say "Contracts already deployed on this chain -- leaving them alone"
  echo "     PaperTimeLock $RECORDED"
fi

# ---------------------------------------------------------------- database
if [ ! -f backend/securelock.db ]; then
  say "Seeding the database"
  ( cd backend && .venv/bin/python -m app.seed --reset ) | grep -E "Created|Approved|Anchored" || true
else
  echo "     database present -- leaving it alone (scripts/reset_demo.sh starts over)"
fi

# ---------------------------------------------------------------- services
if nc -z 127.0.0.1 8000 2>/dev/null; then
  say "API already running on 8000 -- reusing it"
else
  say "Starting the API"
  ( cd backend && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 \
      >"$LOG_DIR/api.log" 2>&1 & )
  wait_for_port 8000 "API"
fi

if nc -z 127.0.0.1 3000 2>/dev/null; then
  say "Web already running on 3000 -- reusing it"
else
  say "Starting the web app"
  ( cd frontend && npm run dev >"$LOG_DIR/web.log" 2>&1 & )
  wait_for_port 3000 "web"
fi

cat <<'BANNER'

  ------------------------------------------------------------------
  SecureLock is up.

    Web       http://localhost:3000
    API docs  http://127.0.0.1:8000/docs
    Chain     http://127.0.0.1:8545

    Sign in with  authority@securelock.demo
    Password      SecureLock#2026

  Prove the whole flow:   backend/.venv/bin/python scripts/e2e_demo.py
  Start the demo over:    scripts/reset_demo.sh
  Stop everything:        scripts/stop.sh
  ------------------------------------------------------------------

BANNER
