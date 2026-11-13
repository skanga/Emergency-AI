#!/usr/bin/env sh
# Emergency AI — prepare the kit (REQUIRES INTERNET, run once)
# Non-interactive examples:
#   ./prepare-kit.sh --model standard --zims recommended --os all --python
#   ./prepare-kit.sh --search medicine          # find other libraries in the Kiwix catalog
cd "$(dirname "$0")" || exit 1
exec sh ./start.sh prepare "$@"
