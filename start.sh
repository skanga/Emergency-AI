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
  echo "Python 3.8+ not found. Install Python 3 from https://www.python.org/downloads/ or your system package manager."
  echo "Alternatively, copy a kit containing portable Python for $OS-$ARCH. Then run ./start.sh again."
  exit 1
fi

# Python handles first use, recovery, subcommands and the default web interface.
exec "$PY" survival.py "$@"
