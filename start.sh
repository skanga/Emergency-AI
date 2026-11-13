#!/usr/bin/env sh
# Survival AI — start on Linux/macOS:  ./start.sh   (options: --lang pt | --lang es)
# Subcommands: ./start.sh chat | ask "question" | status | prepare
cd "$(dirname "$0")" || exit 1

case "$(uname -s)" in
  Darwin) OS=macos ;;
  *) OS=linux ;;
esac
case "$(uname -m)" in
  x86_64|amd64) ARCH=x86_64 ;;
  arm64|aarch64) ARCH=arm64 ;;
  *) ARCH="$(uname -m)" ;;
esac

PY=""
if [ -x "runtime/python/$OS-$ARCH/python/bin/python3" ]; then
  PY="runtime/python/$OS-$ARCH/python/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
  PY="python3"
elif command -v python >/dev/null 2>&1; then
  PY="python"
fi
if [ -z "$PY" ]; then
  echo "Python 3 not found. Run ./prepare-kit.sh online (or install python3)."
  exit 1
fi

# No subcommand => web interface
case "$1" in
  start|chat|ask|search|status|prepare) exec "$PY" survival.py "$@" ;;
  *) exec "$PY" survival.py "$@" start ;;
esac
