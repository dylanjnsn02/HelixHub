#!/usr/bin/env bash
set -e

# Usage: install.sh <neural_helix_root>
# Example: ./install.sh /Users/dylanjensen/Desktop/Neural_Helix
# Called from the root project folder (Neural_Helix), e.g.:
#   ./tiny_db/install.sh /Users/dylanjensen/Desktop/Neural_Helix

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
MCP_SCRIPT="$ROOT/mcp/tiny_db/server.py"
MCP_CWD="$ROOT/mcp"

echo "ROOT=$ROOT"
echo "Installing TinyDB MCP Server..."

# 1. Move tinydb.md to agents/main/skills
mkdir -p "$SKILLS_DIR"
if [ -f "$SCRIPT_DIR/tinydb.md" ]; then
  mv "$SCRIPT_DIR/tinydb.md" "$SKILLS_DIR/"
  echo "Moved tinydb.md to $SKILLS_DIR"
else
  echo "Warning: $SCRIPT_DIR/tinydb.md not found (may already be installed)"
fi

# 2. Install Python dependencies into Neural_Helix MCP venv
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
  "$VENV_PIP" install -r "$SCRIPT_DIR/requirements.txt"
  echo "Installed requirements from $SCRIPT_DIR/requirements.txt"
else
  echo "Warning: $SCRIPT_DIR/requirements.txt not found"
  exit 1
fi

# 3. Append tinydb config to mcporter.json
JQ=""
if command -v jq &>/dev/null; then
  JQ="jq"
elif [ -x /usr/bin/jq ]; then
  JQ="/usr/bin/jq"
fi
if [ -z "$JQ" ]; then
  echo "jq is required to update mcporter.json. Install with: brew install jq (macOS) or apt install jq (Linux)"
  echo "Or manually add this to $MCPPER_JSON (inside mcpServers):"
  echo ""
  echo "    \"tinydb\": {"
  echo "      \"transport\": \"stdio\","
  echo "      \"command\": \"$VENV_PYTHON\","
  echo "      \"args\": ["
  echo "        \"$MCP_SCRIPT\""
  echo "      ],"
  echo "      \"cwd\": \"$MCP_CWD\""
  echo "    }"
  exit 1
fi

NEW_ENTRY=$("$JQ" -n \
  --arg venv_python "$VENV_PYTHON" \
  --arg script_path "$MCP_SCRIPT" \
  --arg cwd "$MCP_CWD" \
  '{
    "mcpServers": {
      "tinydb": {
        "transport": "stdio",
        "command": $venv_python,
        "args": [$script_path],
        "cwd": $cwd
      }
    }
  }')

if [ ! -f "$MCPPER_JSON" ]; then
  echo "Creating $MCPPER_JSON with tinydb config"
  echo "$NEW_ENTRY" > "$MCPPER_JSON"
else
  echo "$NEW_ENTRY" > "$MCPPER_JSON.new"
  "$JQ" -s '
  (.[1].mcpServers // .[1]) as $new |
  (.[0] | to_entries | map(select(.value | type == "object" and has("transport"))) | from_entries) as $stray |
  ((.[0].mcpServers // {}) * $stray * $new) as $merged |
  .[0] | .mcpServers = $merged | reduce ($merged | keys)[] as $k (.; del(.[$k]))
' "$MCPPER_JSON" "$MCPPER_JSON.new" > "$MCPPER_JSON.tmp" && mv "$MCPPER_JSON.tmp" "$MCPPER_JSON"
  rm -f "$MCPPER_JSON.new"
  echo "Appended tinydb to $MCPPER_JSON"
fi

echo "Done."
