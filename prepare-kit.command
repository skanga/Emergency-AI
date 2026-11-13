#!/bin/sh
# macOS: double-click to prepare the kit (requires internet).
cd "$(dirname "$0")" || exit 1
sh ./run.sh prepare "$@"
result=$?
echo
echo "Press Enter to close."
read _
exit "$result"
