#!/bin/sh
# macOS: double-click this file to open Emergency AI.
# (First time: right-click > Open to allow it through Gatekeeper.)
cd "$(dirname "$0")" || exit 1
# Remove macOS quarantine from kit binaries copied from a USB drive or downloaded ZIP.
xattr -dr com.apple.quarantine runtime 2>/dev/null
exec sh ./start.sh "$@"
