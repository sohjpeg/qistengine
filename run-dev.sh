#!/usr/bin/env bash
# Run FastAPI (:8000) and Next.js (:3000) together with prefixed output.
# Ctrl-C stops both.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BLUE=$'\033[0;34m'; MAGENTA=$'\033[0;35m'; RED=$'\033[0;31m'; NC=$'\033[0m'

VENV_PY="$ROOT/backend/.venv/bin/python"
[ -f "$VENV_PY" ] || VENV_PY="$ROOT/backend/.venv/Scripts/python.exe"
if [ ! -f "$VENV_PY" ]; then
  printf "${RED}Backend venv missing. Run: bash bootstrap.sh${NC}\n"
  exit 1
fi
if [ ! -f "$ROOT/backend/app/ml/artifacts/model.pkl" ]; then
  printf "${RED}Model artifacts missing. Run: bash bootstrap.sh${NC}\n"
  exit 1
fi

pids=()
cleanup() {
  printf "\nStopping…\n"
  for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
  exit 0
}
trap cleanup INT TERM

( cd "$ROOT/backend" && "$VENV_PY" -m uvicorn app.main:app --reload --port 8000 2>&1 \
    | sed "s/^/${BLUE}[api]${NC}  /" ) &
pids+=($!)

( cd "$ROOT/frontend" && npm run dev 2>&1 \
    | sed "s/^/${MAGENTA}[web]${NC}  /" ) &
pids+=($!)

printf "${BLUE}[api]${NC}  http://localhost:8000/docs\n"
printf "${MAGENTA}[web]${NC}  http://localhost:3000\n\n"

wait
