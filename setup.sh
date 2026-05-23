#!/usr/bin/env bash
set -euo pipefail

# Always run from the script's own directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# ── colours ──────────────────────────────────────────────────────────────────
BOLD='\033[1m'; DIM='\033[2m'; CYAN='\033[0;36m'; GREEN='\033[0;32m'
YELLOW='\033[0;33m'; RED='\033[0;31m'; RESET='\033[0m'

info()    { printf "${CYAN}▸ %s${RESET}\n" "$*"; }
success() { printf "${GREEN}✓ %s${RESET}\n" "$*"; }
warn()    { printf "${YELLOW}⚠ %s${RESET}\n" "$*"; }
fatal()   { printf "${RED}✗ %s${RESET}\n" "$*"; exit 1; }
ask()     { printf "${BOLD}%s${RESET} ${DIM}%s${RESET}: " "$1" "${2:-}"; }

# ── header ───────────────────────────────────────────────────────────────────
echo
printf "${BOLD}photoblog — setup${RESET}\n"
echo "────────────────────────────────────────"
echo

# ── python check ─────────────────────────────────────────────────────────────
PYTHON=$(command -v python3 || command -v python || true)
[[ -z "$PYTHON" ]] && fatal "Python 3.12+ not found"

PY_VERSION=$("$PYTHON" -c 'import sys; print(sys.version_info.minor + sys.version_info.major * 100)')
[[ "$PY_VERSION" -lt 312 ]] && fatal "Python 3.12+ required (found $("$PYTHON" --version))"
success "Python $("$PYTHON" --version)"

# ── virtual environment ───────────────────────────────────────────────────────
if [[ ! -d .venv ]]; then
  info "Creating virtual environment..."
  "$PYTHON" -m venv .venv
  success "Virtual environment created at .venv/"
else
  success "Virtual environment already exists"
fi

VENV_PYTHON=".venv/bin/python"
[[ ! -f "$VENV_PYTHON" ]] && fatal ".venv/bin/python not found"

# Bootstrap pip if missing (happens on some system Pythons)
if ! "$VENV_PYTHON" -m pip --version &>/dev/null; then
  info "Bootstrapping pip..."
  "$VENV_PYTHON" -m ensurepip --upgrade || fatal "Could not bootstrap pip — try: python3 -m venv --clear .venv"
fi

info "Installing dependencies..."
"$VENV_PYTHON" -m pip install --quiet --upgrade pip
"$VENV_PYTHON" -m pip install --quiet -r requirements.txt
success "Dependencies installed"

# ── config.yaml ──────────────────────────────────────────────────────────────
echo
if [[ -f config.yaml ]]; then
  warn "config.yaml already exists — skipping branding setup"
  warn "Delete it and re-run this script to reconfigure"
else
  printf "${BOLD}Site branding${RESET}\n"
  echo "────────────────────────────────────────"

  ask "Site name" "e.g. Jane Smith"; read -r SITE_NAME
  SITE_NAME="${SITE_NAME:-My Photoblog}"

  ask "Tagline" "e.g. Photography · @handle"; read -r TAGLINE
  TAGLINE="${TAGLINE:-Photography}"

  ask "Instagram URL" "leave blank to skip"; read -r INSTAGRAM_URL
  ask "Facebook URL " "leave blank to skip"; read -r FACEBOOK_URL

  cat > config.yaml <<EOF
site_name: "${SITE_NAME}"
tagline: "${TAGLINE}"
instagram_url: "${INSTAGRAM_URL}"
facebook_url: "${FACEBOOK_URL}"
EOF
  success "config.yaml created"
fi

# ── admin user ───────────────────────────────────────────────────────────────
echo
printf "${BOLD}Admin account${RESET}\n"
echo "────────────────────────────────────────"

ask "Admin username"; read -r ADMIN_USER
ADMIN_USER="${ADMIN_USER:-admin}"

while true; do
  ask "Admin password"; read -rs ADMIN_PASS; echo
  [[ ${#ADMIN_PASS} -ge 8 ]] && break
  warn "Password must be at least 8 characters"
done

"$VENV_PYTHON" - <<PYEOF
import sys
sys.path.insert(0, ".")
from app.db import get_connection, create_schema, get_user_by_username, create_user
from app.auth import hash_password
conn = get_connection("photoblog.db")
create_schema(conn)
username = """$ADMIN_USER"""
if get_user_by_username(conn, username):
    print("User already exists — skipping")
else:
    create_user(conn, username=username, password_hash=hash_password("""$ADMIN_PASS"""))
    print("Admin user created")
conn.close()
PYEOF

# ── photos directory ──────────────────────────────────────────────────────────
echo
if [[ ! -d photos ]]; then
  mkdir -p photos
  success "Created photos/ directory"
fi

# ── hero image hint ───────────────────────────────────────────────────────────
if [[ ! -f photos/hero.jpg ]]; then
  warn "No hero image found — add photos/hero.jpg for the splash screen background"
fi

# ── done ─────────────────────────────────────────────────────────────────────
echo
echo "────────────────────────────────────────"
success "Setup complete"
echo
printf "Start the server:\n"
printf "  ${BOLD}source .venv/bin/activate${RESET}\n"
printf "  ${BOLD}uvicorn app.main:app --reload${RESET}\n"
echo
printf "Then open ${CYAN}http://localhost:8000${RESET}\n"
echo
