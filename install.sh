#!/usr/bin/env sh
# Download first, inspect if desired, then: sh install.sh [new-folder]
set -eu

die() {
    echo "Installation failed: $*" >&2
    if [ -n "${log:-}" ]; then printf '%s\n' "$*" >> "$log"; echo "Log: $log" >&2; fi
    exit 1
}
[ "$#" -le 1 ] || die "Usage: sh install.sh [new-folder]"
destination=${1:-Emergency-AI}
if [ "$#" -eq 0 ] && [ "$(basename "$PWD")" = Emergency-AI ]; then
    destination=$PWD
fi
check_destination() {
    [ -e "$destination" ] || [ -L "$destination" ] || return 0
    [ -d "$destination" ] && [ ! -L "$destination" ] || die "Destination must be a regular folder: $destination"
    for entry in "$destination/"* "$destination/".[!.]* "$destination/"..?*; do
        [ -e "$entry" ] || [ -L "$entry" ] || continue
        case "${entry##*/}" in
            install.bat|install.sh|.DS_Store|Thumbs.db) [ -f "$entry" ] && [ ! -L "$entry" ] && continue ;;
        esac
        die "Destination contains existing files: $destination. Choose an empty folder."
    done
}
check_destination
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
cache="$parent/.$(basename "$destination")-downloads"
[ ! -L "$cache" ] || die "Download cache must not be a link."
mkdir -p "$cache"
log="$cache/install.log"
echo "Installation log: $log"
activated=no
mkdir "$stage/moved"
cleanup() {
    if [ "$activated" = no ]; then
        for record in "$stage/moved/"* "$stage/moved/".[!.]*; do
            [ -f "$record" ] || continue
            name=${record##*/}
            mv "$destination/$name" "$stage/kit/$name" || return
        done
    fi
    rm -rf -- "$stage"
}
trap cleanup 0
trap 'exit 1' HUP INT TERM
fetch() {
    attempt=1
    while [ "$attempt" -le 3 ]; do
        echo "Downloading $(basename "$2"), attempt $attempt/3"
        printf '%s attempt %s: %s\n' "$(date)" "$attempt" "$1" >> "$log"
        code=0
        if [ "${3:-}" = resume ]; then
            curl --fail --location --connect-timeout 30 --speed-time 60 --speed-limit 1 --proto '=https' --proto-redir '=https' -C - -o "$2" "$1" 2>> "$log" || code=$?
        else
            curl --fail --location --connect-timeout 30 --speed-time 60 --speed-limit 1 --proto '=https' --proto-redir '=https' -o "$2" "$1" 2>> "$log" || code=$?
        fi
        if [ "$code" -eq 0 ]; then echo "Download complete: $(wc -c < "$2") bytes"; return; fi
        echo "curl exit code: $code" >> "$log"
        case "$code" in 33|36) rm -f -- "$2" ;; esac
        attempt=$((attempt + 1))
        [ "$attempt" -gt 3 ] || sleep 1
    done
    die "Download failed after three attempts. Download files retained; rerun the installer."
}

echo "Downloading Emergency AI source..."
fetch https://github.com/skanga/Emergency-AI/archive/refs/heads/main.tar.gz "$stage/source.tar.gz"
mkdir "$stage/kit"
tar -xzf "$stage/source.tar.gz" -C "$stage/kit" --strip-components=1
[ -f "$stage/kit/emergency.py" ] && [ -f "$stage/kit/run.sh" ] || die "Source archive is incomplete."

echo "Downloading portable Python for $platform..."
asset="cpython-3.12.16+20261110-$triple-install_only.tar.gz"
archive="$cache/$asset.part"
if [ -f "$archive" ] && [ "$(checksum "$archive")" = "$expected" ]; then
    echo 'Reusing verified portable Python download.'
else
    fetch "https://github.com/astral-sh/python-build-standalone/releases/download/20261110/$asset" "$archive" resume
fi
if [ "$(checksum "$archive")" != "$expected" ]; then
    rm -f -- "$archive"
    die "Python checksum mismatch. Invalid download removed; rerun the installer."
fi
runtime="$stage/kit/runtime/python/$platform"
mkdir -p "$runtime"
tar -xzf "$archive" -C "$runtime"
"$runtime/python/bin/python3" -I -c 'import sys; assert sys.version_info >= (3, 8)' || die "Portable Python cannot run on this computer."
printf '{"complete": true, "asset": "%s"}\n' "$asset" > "$runtime/installation.json"
chmod +x "$stage/kit/run.sh" "$stage/kit/run.command"
check_destination
if [ -d "$destination" ]; then
    for entry in "$stage/kit/"* "$stage/kit/".[!.]* "$stage/kit/"..?*; do
        [ -e "$entry" ] || [ -L "$entry" ] || continue
        name=${entry##*/}
        case "$name" in
            install.bat|install.sh) [ -f "$destination/$name" ] && continue ;;
        esac
        mv "$entry" "$destination/$name"
        : > "$stage/moved/$name"
    done
else
    mv "$stage/kit" "$destination"
fi
activated=yes
echo "Installed in: $destination"
echo "Open run.command on macOS, or run ./run.sh inside that folder."
echo "The launcher lets you download optional AI components or open the included guides."
if [ -t 0 ]; then
    printf 'Run first-time setup now (run.sh prepare)? [y/N] '
    IFS= read -r answer || answer=""
    case "$answer" in
        y|Y|yes|YES|Yes)
            "$destination/run.sh" prepare
            printf 'Open Emergency AI now? [y/N] '
            IFS= read -r answer || answer=""
            case "$answer" in y|Y|yes|YES|Yes) "$destination/run.sh" ;; esac
            ;;
    esac
fi
