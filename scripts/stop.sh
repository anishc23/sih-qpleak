#!/usr/bin/env bash
# Stop everything start.sh started. Leaves the database and the chain state
# on disk; use reset_demo.sh to start the demo over.
set -uo pipefail
pkill -f "hardhat node"      2>/dev/null && echo "stopped chain"    || echo "chain not running"
pkill -f "uvicorn app.main"  2>/dev/null && echo "stopped API"      || echo "API not running"
pkill -f "next dev"          2>/dev/null && echo "stopped web"      || echo "web not running"
