#!/usr/bin/env bash
set -e

# Usage: install.sh <neural_helix_root>
# Example: ./install.sh /Users/dylanjensen/Desktop/Neural_Helix
# Called from the root project folder (Neural_Helix), e.g.:
#   ./mcp/lightpanda/install.sh /Users/dylanjensen/Desktop/Neural_Helix

if [ -z "$1" ]; then
  echo "Usage: $0 <neural_helix_root>"
  echo "Example: $0 /Users/dylanjensen/Desktop/Neural_Helix"
  exit 1
fi

ROOT="${1%/}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DIR="$ROOT/agents/main/skills"
MCPPER_JSON="$ROOT/config/mcporter.json"
MCP_SERVER_DIR="$ROOT/mcp/lightpanda"
MCP_CWD="$ROOT/mcp"
LIGHTPANDA_BINARY="$MCP_SERVER_DIR/lightpanda"

echo "ROOT=$ROOT"
echo "Installing Lightpanda (Web Browser) MCP Server..."

# 1. Move web_browser.md to agents/main/skills
mkdir -p "$SKILLS_DIR"
if [ -f "$SCRIPT_DIR/web_browser.md" ]; then
  mv "$SCRIPT_DIR/web_browser.md" "$SKILLS_DIR/"
  echo "Moved web_browser.md to $SKILLS_DIR"
else
  echo "Warning: $SCRIPT_DIR/web_browser.md not found (may already be installed)"
fi

# 2. Install lightpanda browser binary (if install_lightpanda.sh exists)
if [ -f "$SCRIPT_DIR/install_lightpanda.sh" ]; then
  bash "$SCRIPT_DIR/install_lightpanda.sh"
  echo "Installed lightpanda binary"
else
  echo "Warning: $SCRIPT_DIR/install_lightpanda.sh not found"
  if [ ! -f "$LIGHTPANDA_BINARY" ] && [ ! -f "$SCRIPT_DIR/lightpanda" ]; then
    echo "No lightpanda binary found; mcporter config may not work until you run install_lightpanda.sh"
  fi
fi

# 3. Append web_browser config to mcporter.json (paths under ROOT for mcporter)
if ! command -v jq &>/dev/null; then
  echo "jq is required to update mcporter.json. Install with: brew install jq"
  echo "Or manually add this to $MCPPER_JSON (inside mcpServers):"
  echo ""
  echo "    \"web_browser\": {"
  echo "      \"transport\": \"stdio\","
  echo "      \"command\": \"$LIGHTPANDA_BINARY\","
  echo "      \"args\": ["
  echo "        \"mcp\""
  echo "      ],"
  echo "      \"cwd\": \"$MCP_CWD\""
  echo "    }"
  exit 1
fi

NEW_ENTRY=$(jq -n \
  --arg binary "$LIGHTPANDA_BINARY" \
  --arg cwd "$MCP_CWD" \
  '{
    "mcpServers": {
      "web_browser": {
        "transport": "stdio",
        "command": $binary,
        "args": ["mcp"],
        "cwd": $cwd
      }
    }
  }')

if [ ! -f "$MCPPER_JSON" ]; then
  echo "Creating $MCPPER_JSON with web_browser config"
  echo "$NEW_ENTRY" > "$MCPPER_JSON"
else
  echo "$NEW_ENTRY" > "$MCPPER_JSON.new"
  jq -s '
  (.[1].mcpServers // .[1]) as $new |
  (.[0] | to_entries | map(select(.value | type == "object" and has("transport"))) | from_entries) as $stray |
  ((.[0].mcpServers // {}) * $stray * $new) as $merged |
  .[0] | .mcpServers = $merged | reduce ($merged | keys)[] as $k (.; del(.[$k]))
' "$MCPPER_JSON" "$MCPPER_JSON.new" > "$MCPPER_JSON.tmp" && mv "$MCPPER_JSON.tmp" "$MCPPER_JSON"
  rm -f "$MCPPER_JSON.new"
  echo "Appended web_browser to $MCPPER_JSON"
fi

echo "Done."
