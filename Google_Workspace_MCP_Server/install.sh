#!/usr/bin/env bash
set -e

# Usage: install.sh <neural_helix_root>
# Example: ./install.sh /Users/dylanjensen/Desktop/Neural_Helix
# Called from the root project folder (Neural_Helix), e.g.:
#   ./mcp/Google_Workspace_MCP_Server/install.sh /Users/dylanjensen/Desktop/Neural_Helix

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
MCP_SERVER_DIR="$ROOT/mcp/Google_Workspace_MCP_Server"

echo "ROOT=$ROOT"
echo "Installing Google Workspace MCP Server..."

# 1. Move google_workspace.md to agents/main/skills
mkdir -p "$SKILLS_DIR"
if [ -f "$SCRIPT_DIR/google_workspace.md" ]; then
  mv "$SCRIPT_DIR/google_workspace.md" "$SKILLS_DIR/"
  echo "Moved google_workspace.md to $SKILLS_DIR"
else
  echo "Warning: $SCRIPT_DIR/google_workspace.md not found (may already be installed)"
fi

# 2. Install Python dependencies into Neural_Helix MCP venv
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
  "$VENV_PIP" install -r "$SCRIPT_DIR/requirements.txt"
  echo "Installed requirements from $SCRIPT_DIR/requirements.txt"
else
  echo "Warning: $SCRIPT_DIR/requirements.txt not found"
  exit 1
fi

# 3. Append google_workspace config to mcporter.json
if ! command -v jq &>/dev/null; then
  echo "jq is required to update mcporter.json. Install with: brew install jq"
  echo "Or manually add this to $MCPPER_JSON (inside mcpServers):"
  echo ""
  echo "    \"google_workspace\": {"
  echo "      \"transport\": \"stdio\","
  echo "      \"command\": \"sh\","
  echo "      \"args\": ["
  echo "        \"-c\","
  echo "        \"$VENV_PYTHON $MCP_SERVER_DIR/mcp_server.py 2>/dev/null\""
  echo "      ],"
  echo "      \"cwd\": \"$MCP_SERVER_DIR\""
  echo "    }"
  exit 1
fi

GOOGLE_WORKSPACE_CMD="$VENV_PYTHON $MCP_SERVER_DIR/mcp_server.py 2>/dev/null"
NEW_ENTRY=$(jq -n \
  --arg cmd "$GOOGLE_WORKSPACE_CMD" \
  --arg cwd "$MCP_SERVER_DIR" \
  '{
    "mcpServers": {
      "google_workspace": {
        "transport": "stdio",
        "command": "sh",
        "args": ["-c", $cmd],
        "cwd": $cwd
      }
    }
  }')

if [ ! -f "$MCPPER_JSON" ]; then
  echo "Creating $MCPPER_JSON with google_workspace config"
  echo "$NEW_ENTRY" > "$MCPPER_JSON"
else
  echo "$NEW_ENTRY" > "$MCPPER_JSON.new"
  jq -s '.[0] | .mcpServers = ((.[0].mcpServers // {}) * .[1].mcpServers)' "$MCPPER_JSON" "$MCPPER_JSON.new" > "$MCPPER_JSON.tmp" && mv "$MCPPER_JSON.tmp" "$MCPPER_JSON"
  rm -f "$MCPPER_JSON.new"
  echo "Appended google_workspace to $MCPPER_JSON"
fi

echo "Done."
