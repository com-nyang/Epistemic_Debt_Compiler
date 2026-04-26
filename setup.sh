#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
LOCAL_BIN_DIR="$ROOT_DIR/.edc/bin"
DEBT_SHIM="$LOCAL_BIN_DIR/debt"

is_sourced() {
  [[ "${BASH_SOURCE[0]}" != "${0}" ]]
}

printf '[setup] project: %s\n' "$ROOT_DIR"

if [[ ! -d "$VENV_DIR" ]]; then
  printf '[setup] creating virtualenv: %s\n' "$VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

printf '[setup] upgrading pip\n'
"$VENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null

printf '[setup] installing dependencies\n'
"$VENV_DIR/bin/python" -m pip install -r "$ROOT_DIR/requirements.txt"

mkdir -p "$LOCAL_BIN_DIR"
cat > "$DEBT_SHIM" <<EOF
#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$ROOT_DIR"
exec "$VENV_DIR/bin/python" "$ROOT_DIR/debt" "\$@"
EOF
chmod +x "$DEBT_SHIM"

if is_sourced; then
  case ":$PATH:" in
    *":$LOCAL_BIN_DIR:"*) ;;
    *) export PATH="$LOCAL_BIN_DIR:$PATH" ;;
  esac
  printf '[setup] ready: debt is available in this shell\n'
  printf '[setup] try: debt --help\n'
else
  printf '[setup] ready: local launcher created at %s\n' "$DEBT_SHIM"
  printf '[setup] to use `debt` immediately in this shell, run:\n'
  printf '         source ./setup.sh\n'
  printf '[setup] or run directly:\n'
  printf '         %s --help\n' "$DEBT_SHIM"
fi
