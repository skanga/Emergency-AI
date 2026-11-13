#!/usr/bin/env sh
# Download first, inspect if desired, then: sh install.sh [new-folder]
set -eu

die() { echo "Installation failed: $*" >&2; exit 1; }
[ "$#" -le 1 ] || die "Usage: sh install.sh [new-folder]"
destination=${1:-Emergency-AI}
[ ! -e "$destination" ] && [ ! -L "$destination" ] || die "Destination already exists: $destination. Choose a new folder."
parent=$(cd "$(dirname "$destination")" && pwd) || die "Parent folder must exist."
destination="$parent/$(basename "$destination")"
for tool in curl tar mktemp; do
    command -v "$tool" >/dev/null 2>&1 || die "Required tool missing: $tool"
done
if command -v sha256sum >/dev/null 2>&1; then
    checksum() { sha256sum "$1" | cut -d ' ' -f 1; }
elif command -v shasum >/dev/null 2>&1; then
    checksum() { shasum -a 256 "$1" | cut -d ' ' -f 1; }
else
    die "sha256sum or shasum is required."
fi
case "$(uname -m)" in
    x86_64|amd64) arch=x86_64 ;;
    arm64|aarch64) arch=arm64 ;;
    *) die "Unsupported architecture: $(uname -m)" ;;
esac
# Pinned from the official python-build-standalone 20261110 release metadata.
case "$(uname -s)-$arch" in
    Linux-x86_64)
        platform=linux-x86_64; triple=x86_64-unknown-linux-gnu
        expected=c2f87d4b4e8db3abddb0f116c6ccfc503d0cbdbb9ee8faacddad1b679ec12e99 ;;
    Linux-arm64)
        platform=linux-arm64; triple=aarch64-unknown-linux-gnu
        expected=4792f81750282597fb2a3389fe18b945ed2ba6aad5e45ad406d122c58cb33081 ;;
    Darwin-x86_64)
        platform=macos-x86_64; triple=x86_64-apple-darwin
        expected=83f2922437e6d546d0fcdb8c11f150a8e52787e8d9ea8651b1974e20908eb1bc ;;
    Darwin-arm64)
        platform=macos-arm64; triple=aarch64-apple-darwin
        expected=e956e60bc9465d577ef8062059aa05cd3a2665b4b8678a2ed24e432368330b8f ;;
    *) die "Supported systems: Linux (glibc) and macOS." ;;
esac
stage=$(mktemp -d "$parent/.emergency-install-XXXXXXXX")
trap 'rm -rf -- "$stage"' 0
trap 'exit 1' HUP INT TERM
fetch() { curl --fail --location --retry 3 --connect-timeout 30 --proto '=https' --proto-redir '=https' -o "$2" "$1"; }

echo "Downloading Emergency AI source..."
fetch https://github.com/skanga/Emergency-AI/archive/refs/heads/main.tar.gz "$stage/source.tar.gz"
mkdir "$stage/kit"
tar -xzf "$stage/source.tar.gz" -C "$stage/kit" --strip-components=1
[ -f "$stage/kit/emergency.py" ] && [ -f "$stage/kit/run.sh" ] || die "Source archive is incomplete."

echo "Downloading portable Python for $platform..."
asset="cpython-3.12.16+20261110-$triple-install_only.tar.gz"
fetch "https://github.com/astral-sh/python-build-standalone/releases/download/20261110/$asset" "$stage/python.tar.gz"
[ "$(checksum "$stage/python.tar.gz")" = "$expected" ] || die "Python checksum mismatch."
runtime="$stage/kit/runtime/python/$platform"
mkdir -p "$runtime"
tar -xzf "$stage/python.tar.gz" -C "$runtime"
"$runtime/python/bin/python3" -I -c 'import sys; assert sys.version_info >= (3, 8)' || die "Portable Python cannot run on this computer."
printf '{"complete": true, "asset": "%s"}\n' "$asset" > "$runtime/installation.json"
chmod +x "$stage/kit/run.sh" "$stage/kit/run.command"
[ ! -e "$destination" ] && [ ! -L "$destination" ] || die "Destination appeared during installation."
mv "$stage/kit" "$destination"
echo "Installed in: $destination"
echo "Open run.command on macOS, or run ./run.sh inside that folder."
echo "The launcher lets you download optional AI components or open the included guides."
