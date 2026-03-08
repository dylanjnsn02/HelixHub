#!/usr/bin/env bash
# Install Lightpanda browser binary for the current OS/architecture.
# Run from project root or from mcp/; binary is placed in mcp/lightpanda.

set -e

RELEASE_BASE="https://github.com/lightpanda-io/browser/releases/download/nightly"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
OUTPUT="${SCRIPT_DIR}/lightpanda"

OS="$(uname -s)"
ARCH="$(uname -m)"

# Normalize arch: x86_64, amd64 -> x86_64; aarch64, arm64 -> aarch64
case "$ARCH" in
  x86_64|amd64) ARCH="x86_64" ;;
  aarch64|arm64) ARCH="aarch64" ;;
  *) echo "Unsupported architecture: $ARCH"; exit 1 ;;
esac

case "$OS" in
  Linux)
    PLATFORM="linux"
    ;;
  Darwin)
    PLATFORM="macos"
    ;;
  *)
    echo "Unsupported OS: $OS"; exit 1
    ;;
esac

BINARY_NAME="lightpanda-${ARCH}-${PLATFORM}"
URL="${RELEASE_BASE}/${BINARY_NAME}"

echo "Detected: $OS / $ARCH -> $BINARY_NAME"
echo "Downloading: $URL"

curl -L -o "$OUTPUT" "$URL"
chmod a+x "$OUTPUT"

echo "Installed: $OUTPUT"
