#!/usr/bin/env bash
# QistEngine bootstrap — idempotent, offline after this completes.
# Creates the venv, installs deps, generates synthetic data, trains the model,
# builds the sample files, seeds the database, installs the frontend, and copies
# the env files into place.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

GREEN=$'\033[0;32m'; BLUE=$'\033[0;34m'; YELLOW=$'\033[0;33m'; RED=$'\033[0;31m'; NC=$'\033[0m'
step() { printf "\n${BLUE}==>${NC} %s\n" "$1"; }
ok()   { printf "${GREEN}  ok${NC} %s\n" "$1"; }

# --- pick a Python 3.10/3.11/3.12 interpreter (never 3.13) ---
PYBIN=""
for cand in python3.11 python3.12 python3.10 python3 python; do
  if command -v "$cand" >/dev/null 2>&1; then
    ver="$("$cand" -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null || echo "0.0")"
    case "$ver" in
      3.10|3.11|3.12) PYBIN="$cand"; break ;;
    esac
  fi
done
if [ -z "$PYBIN" ]; then
  printf "${RED}No suitable Python found.${NC} Need 3.10, 3.11 or 3.12 (not 3.13).\n"
  printf "  macOS:  brew install python@3.11\n"
  printf "  Ubuntu: sudo apt-get install python3.11 python3.11-venv\n"
  exit 1
fi
step "Using $($PYBIN --version) at $(command -v "$PYBIN")"

VENV_PY="$ROOT/backend/.venv/bin/python"
[ -f "$VENV_PY" ] || VENV_PY="$ROOT/backend/.venv/Scripts/python.exe"  # Windows / Git Bash

# --- backend venv + deps ---
step "Backend virtual environment"
if [ ! -f "$VENV_PY" ]; then
  "$PYBIN" -m venv "$ROOT/backend/.venv"
  VENV_PY="$ROOT/backend/.venv/bin/python"
  [ -f "$VENV_PY" ] || VENV_PY="$ROOT/backend/.venv/Scripts/python.exe"
fi
"$VENV_PY" -m pip install --quiet --upgrade pip
"$VENV_PY" -m pip install --quiet -r "$ROOT/backend/requirements.txt"
ok "dependencies installed"

# --- env files ---
step "Environment files"
[ -f "$ROOT/backend/.env" ]        || { cp "$ROOT/backend/.env.example" "$ROOT/backend/.env"; ok "backend/.env"; }
[ -f "$ROOT/frontend/.env.local" ] || { cp "$ROOT/frontend/.env.local.example" "$ROOT/frontend/.env.local"; ok "frontend/.env.local"; }

# --- synthetic data + training ---
step "Synthetic data (5000 profiles, seed 42)"
( cd "$ROOT/backend" && "$VENV_PY" scripts/generate_synthetic_data.py --n 5000 --seed 42 )

step "Training the scorecard (LightGBM + isotonic calibration + SHAP)"
( cd "$ROOT/backend" && "$VENV_PY" scripts/train_model.py )

step "Fairness audit"
( cd "$ROOT/backend" && "$VENV_PY" scripts/fairness_audit.py >/dev/null && ok "docs/RESPONSIBLE_AI.md regenerated" )

step "Demo sample files"
( cd "$ROOT/backend" && "$VENV_PY" scripts/make_sample_files.py >/dev/null && ok "12 files in backend/data/samples/" )

step "Seeding the demo database"
( cd "$ROOT/backend" && "$VENV_PY" -m app.seed )

# --- frontend ---
step "Frontend dependencies"
if command -v npm >/dev/null 2>&1; then
  ( cd "$ROOT/frontend" && npm install --silent --no-audit --no-fund )
  ok "npm packages installed"
else
  printf "${YELLOW}  npm not found — install Node 20 LTS, then run: (cd frontend && npm install)${NC}\n"
fi

# --- done ---
cat <<EOF

${GREEN}============================================================${NC}
${GREEN} QistEngine is ready.${NC}
${GREEN}============================================================${NC}

  Start everything (one terminal):   ${BLUE}bash run-dev.sh${NC}

  Or run the two services yourself:
    backend :   cd backend && .venv/bin/activate && uvicorn app.main:app --reload --port 8000
    frontend:   cd frontend && npm run dev

  API docs   :  http://localhost:8000/docs
  App        :  http://localhost:3000

  Demonstration model trained on synthetic data. Not a regulated credit decision.

EOF
