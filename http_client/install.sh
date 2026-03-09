#!/usr/bin/env bash
set -e

# Usage: install.sh <neural_helix_root>
# Example: ./install.sh /Users/dylanjensen/Desktop/Neural_Helix
# Called from the root project folder (Neural_Helix), e.g.:
#   ./mcp/http_client/install.sh /Users/dylanjensen/Desktop/Neural_Helix

if [ -z "$1" ]; then
  echo "Usage: $0 <neural_helix_root>"
  echo "Example: $0 /Users/dylanjensen/Desktop/Neural_Helix"
  exit 1
fi

ROOT="${1%/}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DIR="$ROOT/agents/main/skills"
MCPPER_JSON="$ROOT/config/mcporter.json"
VENV_PIP="$ROOT/mcp/.venv/bin/pip3"
VENV_PYTHON="$ROOT/mcp/.venv/bin/python3"
MCP_DIR="$ROOT/mcp"
HTTP_CLIENT_SCRIPT="$MCP_DIR/http_client.py"

echo "ROOT=$ROOT"
echo "Installing HTTP Client MCP Server..."

# 1. Move http_client.md to agents/main/skills
mkdir -p "$SKILLS_DIR"
if [ -f "$SCRIPT_DIR/http_client.md" ]; then
  mv "$SCRIPT_DIR/http_client.md" "$SKILLS_DIR/"
  echo "Moved http_client.md to $SKILLS_DIR"
else
  echo "Warning: $SCRIPT_DIR/http_client.md not found (may already be installed)"
fi

# 2. Install Python dependencies into Neural_Helix MCP venv
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
  "$VENV_PIP" install -r "$SCRIPT_DIR/requirements.txt"
  echo "Installed requirements from $SCRIPT_DIR/requirements.txt"
else
  echo "Warning: $SCRIPT_DIR/requirements.txt not found"
  exit 1
fi

# 3. Append http_client config to mcporter.json
if ! command -v jq &>/dev/null; then
  echo "jq is required to update mcporter.json. Install with: brew install jq"
  echo "Or manually add this to $MCPPER_JSON (inside mcpServers):"
  echo ""
  echo "    \"http_client\": {"
  echo "      \"transport\": \"stdio\","
  echo "      \"command\": \"$VENV_PYTHON\","
  echo "      \"args\": ["
  echo "        \"$HTTP_CLIENT_SCRIPT\""
  echo "      ],"
  echo "      \"cwd\": \"$MCP_DIR\""
  echo "    }"
  exit 1
fi

NEW_ENTRY=$(jq -n \
  --arg venv_python "$VENV_PYTHON" \
  --arg script_path "$HTTP_CLIENT_SCRIPT" \
  --arg cwd "$MCP_DIR" \
  '{
    "mcpServers": {
      "http_client": {
        "transport": "stdio",
        "command": $venv_python,
        "args": [$script_path],
        "cwd": $cwd
      }
    }
  }')

if [ ! -f "$MCPPER_JSON" ]; then
  echo "Creating $MCPPER_JSON with http_client config"
  echo "$NEW_ENTRY" > "$MCPPER_JSON"
else
  NEW_ENTRY_TMP="${MCPPER_JSON}.new"
  echo "$NEW_ENTRY" > "$NEW_ENTRY_TMP"
  jq -s '(.[0].mcpServers // {}) * .[1].mcpServers as $merged | .[0] | .mcpServers = $merged' "$MCPPER_JSON" "$NEW_ENTRY_TMP" > "$MCPPER_JSON.tmp" && mv "$MCPPER_JSON.tmp" "$MCPPER_JSON"
  rm -f "$NEW_ENTRY_TMP"
  echo "Appended http_client to $MCPPER_JSON"
fi

echo "Done."
