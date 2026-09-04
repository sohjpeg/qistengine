#!/usr/bin/env bash
# Start QistEngine. If it has not been set up yet, this runs bootstrap.sh for you.
# Then it launches FastAPI (:8000) and Next.js (:3000) together. Ctrl-C stops both.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
BLUE=$'\033[0;34m'; MAGENTA=$'\033[0;35m'; GREEN=$'\033[0;32m'; RED=$'\033[0;31m'; NC=$'\033[0m'

VENV_PY="$ROOT/backend/.venv/bin/python"
[ -f "$VENV_PY" ] || VENV_PY="$ROOT/backend/.venv/Scripts/python.exe"

# --- auto-setup on first run ---------------------------------------------------
if [ ! -f "$VENV_PY" ] || [ ! -f "$ROOT/backend/app/ml/artifacts/model.pkl" ] \
   || [ ! -d "$ROOT/frontend/node_modules" ]; then
  printf "${BLUE}First run — setting up (this takes ~4 minutes)…${NC}\n\n"
  bash "$ROOT/bootstrap.sh" || {
    printf "\n${RED}Setup failed. Fix the error above, then run 'bash run-dev.sh' again.${NC}\n"
    exit 1
  }
  VENV_PY="$ROOT/backend/.venv/bin/python"
  [ -f "$VENV_PY" ] || VENV_PY="$ROOT/backend/.venv/Scripts/python.exe"
  printf "\n${GREEN}Setup done — starting the app…${NC}\n\n"
fi

# --- port check --------------------------------------------------------------
port_busy() { { command -v lsof >/dev/null && lsof -ti:"$1" >/dev/null 2>&1; } \
  || { command -v netstat >/dev/null && netstat -an 2>/dev/null | grep -E "[:.]$1[[:space:]].*LISTEN" >/dev/null; }; }
for p in 8000 3000; do
  if port_busy "$p"; then
    printf "${RED}Port %s is already in use.${NC} Stop whatever is on it and re-run.\n" "$p"
    printf "  macOS/Linux:  lsof -ti:%s | xargs kill\n" "$p"
    printf "  Windows:      netstat -ano | findstr :%s   then  taskkill /PID <pid> /F\n" "$p"
    exit 1
  fi
done

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

printf "\n${GREEN}QistEngine is running.${NC}\n"
printf "  ${MAGENTA}App${NC}       http://localhost:3000\n"
printf "  ${BLUE}API docs${NC}  http://localhost:8000/docs\n"
printf "  Press Ctrl-C to stop both.\n\n"

wait
