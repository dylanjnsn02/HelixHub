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
MCP_SERVER_DIR="$ROOT/mcp/http_client"

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
  echo "Or manually add this to $MCPPER_JSON (inside the top-level object):"
  echo ""
  echo "    \"http_client\": {"
  echo "      \"transport\": \"stdio\","
  echo "      \"command\": \"sh\","
  echo "      \"args\": ["
  echo "        \"-c\","
  echo "        \"$VENV_PYTHON $MCP_SERVER_DIR/http_client.py 2>/dev/null\""
  echo "      ],"
  echo "      \"cwd\": \"$MCP_SERVER_DIR\""
  echo "    }"
  exit 1
fi

NEW_ENTRY=$(jq -n \
  --arg venv_python "$VENV_PYTHON" \
  --arg server_dir "$MCP_SERVER_DIR" \
  '{
    "http_client": {
      "transport": "stdio",
      "command": "sh",
      "args": [
        "-c",
        ($venv_python + " " + $server_dir + "/http_client.py 2>/dev/null")
      ],
      "cwd": $server_dir
    }
  }')

if [ ! -f "$MCPPER_JSON" ]; then
  echo "Creating $MCPPER_JSON with http_client config"
  echo "$NEW_ENTRY" > "$MCPPER_JSON"
else
  jq -s '.[0] * .[1]' "$MCPPER_JSON" <(echo "$NEW_ENTRY") > "$MCPPER_JSON.tmp" && mv "$MCPPER_JSON.tmp" "$MCPPER_JSON"
  echo "Appended http_client to $MCPPER_JSON"
fi

echo "Done."
