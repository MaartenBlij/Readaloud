#!/usr/bin/env bash
# install.sh — one-shot setup for readaloud
# Supports Linux (apt/dnf/pacman) and macOS (Homebrew).
set -euo pipefail

PYTHON=${PYTHON:-python3}

echo "=== readaloud installer ==="

# ── OS detection ──────────────────────────────────────────────────────────────
OS="$(uname -s)"

install_system_deps_linux() {
    if command -v apt-get &>/dev/null; then
        echo "[apt] Installing espeak-ng..."
        sudo apt-get update -qq
        sudo apt-get install -y espeak-ng python3-pip python3-venv
    elif command -v dnf &>/dev/null; then
        echo "[dnf] Installing espeak-ng..."
        sudo dnf install -y espeak-ng python3-pip python3-venv
    elif command -v pacman &>/dev/null; then
        echo "[pacman] Installing espeak-ng..."
        sudo pacman -Sy --noconfirm espeak-ng python-pip python-virtualenv
    else
        echo "WARNING: Unknown Linux distro. Install 'espeak-ng' manually."
        echo "  Debian/Ubuntu:  sudo apt-get install espeak-ng"
        echo "  Fedora/RHEL:    sudo dnf install espeak-ng"
        echo "  Arch:           sudo pacman -S espeak-ng"
    fi
}

install_system_deps_macos() {
    # macOS ships with 'say' (no extra TTS engine needed).
    # Check for Homebrew for Python if needed.
    if ! command -v "$PYTHON" &>/dev/null; then
        if command -v brew &>/dev/null; then
            echo "[brew] Installing python..."
            brew install python
        else
            echo "ERROR: Python not found. Install Python 3.9+ from https://python.org"
            exit 1
        fi
    fi
    echo "macOS: TTS will use the built-in 'say' command via pyttsx3."
}

case "$OS" in
    Linux*)  install_system_deps_linux ;;
    Darwin*) install_system_deps_macos ;;
    *)       echo "Unsupported OS: $OS"; exit 1 ;;
esac

# ── Python venv ────────────────────────────────────────────────────────────────
VENV_DIR="$(dirname "$0")/.venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment at $VENV_DIR ..."
    "$PYTHON" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "Installing Python dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r "$(dirname "$0")/requirements.txt"

# ── Wrapper script ─────────────────────────────────────────────────────────────
WRAPPER="$(dirname "$0")/run_readaloud.sh"
cat > "$WRAPPER" <<'WRAPPER'
#!/usr/bin/env bash
# Activate the venv and run readaloud.py
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/.venv/bin/activate"
exec python "$SCRIPT_DIR/readaloud.py" "$@"
WRAPPER
chmod +x "$WRAPPER"

echo ""
echo "=== Setup complete ==="
echo ""
echo "Usage:"
echo "  ./run_readaloud.sh https://example.com"
echo "  ./run_readaloud.sh document.pdf"
echo "  ./run_readaloud.sh report.docx"
echo "  ./run_readaloud.sh --list-voices"
echo "  ./run_readaloud.sh --rate 150 --voice 1 document.pdf"
echo "  ./run_readaloud.sh --dump-text document.pdf   # just print the text"
