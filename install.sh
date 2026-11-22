#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${SFLASHER_REPO_URL:-https://github.com/primenimoo-alt/ShlepaFlash-CLI.git}"
INSTALL_DIR="${SFLASHER_INSTALL_DIR:-$HOME/.local/share/shlepaflash-cli}"
BIN_DIR="${SFLASHER_BIN_DIR:-$HOME/.local/bin}"
VENV_DIR="$INSTALL_DIR/venv"

have() { command -v "$1" >/dev/null 2>&1; }

info() { printf '\033[38;5;208m[ShlepaFlash]\033[0m %s\n' "$*"; }
err()  { printf '\033[31m[ShlepaFlash ERROR]\033[0m %s\n' "$*" >&2; }

info "Installing ShlepaFlash CLI..."
if ! have python3; then err "python3 not found. Install Python 3.10+ first."; exit 1; fi
if ! have git; then err "git not found. Install git first."; exit 1; fi

mkdir -p "$INSTALL_DIR" "$BIN_DIR"
if [ -d "$INSTALL_DIR/repo/.git" ]; then
  info "Updating existing repo..."
  git -C "$INSTALL_DIR/repo" pull --ff-only || true
else
  rm -rf "$INSTALL_DIR/repo"
  info "Cloning repository..."
  git clone --depth 1 "$REPO_URL" "$INSTALL_DIR/repo"
fi

info "Creating virtual environment..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null
"$VENV_DIR/bin/python" -m pip install "$INSTALL_DIR/repo" >/dev/null

cat > "$BIN_DIR/sflasher" <<EOF
#!/usr/bin/env bash
exec "$VENV_DIR/bin/sflasher" "\$@"
EOF
chmod +x "$BIN_DIR/sflasher"

info "Installed. Ensure $BIN_DIR is in PATH."
info "Run: sflasher"
