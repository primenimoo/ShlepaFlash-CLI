#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${SFLASHER_REPO_URL:-https://github.com/primenimoo/ShlepaFlash-CLI.git}"
INSTALL_DIR="${SFLASHER_INSTALL_DIR:-$HOME/.local/share/shlepaflash-cli}"
BIN_DIR="${SFLASHER_BIN_DIR:-$HOME/.local/bin}"
VENV_DIR="$INSTALL_DIR/venv"
REPO_DIR="$INSTALL_DIR/repo"
LOG_FILE="$INSTALL_DIR/install.log"

C_ORG='\033[38;5;208m'
C_GRN='\033[32m'
C_RED='\033[31m'
C_DIM='\033[2m'
C_RST='\033[0m'

bar() {
  local pct="$1" label="$2" w=28 filled i
  filled=$((pct * w / 100))
  printf "\r  ${C_ORG}[" >&2
  for ((i=0; i<w; i++)); do
    if [ "$i" -lt "$filled" ]; then printf "█" >&2; else printf "░" >&2; fi
  done
  printf "] %3d%% %s${C_RST}\033[K" "$pct" "$label" >&2
}

ok() { printf "\r  ${C_GRN}✓${C_RST} %s\033[K\n" "$*"; }
err() { printf "\n  ${C_RED}✗${C_RST} %s\n" "$*" >&2; }

mkdir -p "$INSTALL_DIR"
: > "$LOG_FILE"

printf "\n  ${C_ORG}🐾 ShlepaFlash CLI${C_RST}\n  ${C_DIM}Compact installer${C_RST}\n\n" >&2

bar 5 "Проверка окружения"
command -v python3 >/dev/null 2>&1 || { err "python3 не найден. Установи Python 3.10+."; echo "  Лог: $LOG_FILE" >&2; exit 1; }
command -v git >/dev/null 2>&1 || { err "git не найден. Установи git."; echo "  Лог: $LOG_FILE" >&2; exit 1; }

bar 15 "Подготовка каталогов"
mkdir -p "$INSTALL_DIR" "$BIN_DIR"

bar 30 "Загрузка исходников"
if [ -d "$REPO_DIR/.git" ]; then
  git -C "$REPO_DIR" fetch --depth 1 origin main >>"$LOG_FILE" 2>&1 || true
  git -C "$REPO_DIR" reset --hard origin/main >>"$LOG_FILE" 2>&1 || true
else
  rm -rf "$REPO_DIR"
  git clone --depth 1 --branch main "$REPO_URL" "$REPO_DIR" >>"$LOG_FILE" 2>&1 || { err "Не удалось скачать репозиторий."; echo "  Лог: $LOG_FILE" >&2; exit 1; }
fi

bar 55 "Создание окружения"
if [ ! -x "$VENV_DIR/bin/python" ]; then
  python3 -m venv "$VENV_DIR" >>"$LOG_FILE" 2>&1 || { err "Не удалось создать venv."; echo "  Лог: $LOG_FILE" >&2; exit 1; }
fi

bar 75 "Установка пакета"
"$VENV_DIR/bin/python" -m pip install --upgrade pip --disable-pip-version-check >>"$LOG_FILE" 2>&1
"$VENV_DIR/bin/python" -m pip install --upgrade --force-reinstall "$REPO_DIR" --disable-pip-version-check >>"$LOG_FILE" 2>&1 || { err "Не удалось установить пакет."; echo "  Лог: $LOG_FILE" >&2; exit 1; }

bar 90 "Создание команды sflasher"
cat > "$BIN_DIR/sflasher" <<LAUNCH
#!/usr/bin/env bash
exec "$VENV_DIR/bin/sflasher" "\$@"
LAUNCH
chmod +x "$BIN_DIR/sflasher"

# Add BIN_DIR to PATH in common shell rc files if missing
add_path_line="export PATH=\"\$HOME/.local/bin:\$PATH\""
for rc in "$HOME/.profile" "$HOME/.bashrc" "$HOME/.zshrc"; do
  if [ -f "$rc" ]; then
    if ! grep -F '.local/bin' "$rc" >/dev/null 2>&1; then
      printf '\n# ShlepaFlash CLI\n%s\n' "$add_path_line" >> "$rc"
    fi
  fi
done
if [ ! -f "$HOME/.profile" ] && [ ! -f "$HOME/.bashrc" ] && [ ! -f "$HOME/.zshrc" ]; then
  printf '# ShlepaFlash CLI\n%s\n' "$add_path_line" >> "$HOME/.profile"
fi
export PATH="$BIN_DIR:$PATH"

bar 100 "Готово"
printf "\n\n"
ok "ShlepaFlash CLI установлен"
printf "  ${C_DIM}Запуск:${C_RST} sflasher\n"
if ! command -v sflasher >/dev/null 2>&1; then
  printf "  ${C_DIM}Перезапусти терминал или выполни:${C_RST} export PATH=\"\$HOME/.local/bin:\$PATH\"\n"
fi
printf "\n"
