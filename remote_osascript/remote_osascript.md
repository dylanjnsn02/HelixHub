# Remote macOS osascript

Use this pattern when the user needs to run AppleScript (or JXA) on a remote macOS host.

## When to use

Use when the user asks to automate macOS apps, dialogs, files, or system actions remotely with `osascript`.

## Common MCP tool usage

Use the `remote-osascript.run_osascript` tool with a host IP and script body.

## Parameters

- **ip**: The IP address of the target macOS host
- **script**: Script content passed to `osascript -e`
- **timeout**: Optional timeout in seconds (default: 30)
- **language**: Optional script language: `AppleScript` (default) or `JavaScript` (JXA)

## Example user requests

- Open Safari on 10.0.0.86
- Show a dialog on 192.168.1.50
- Get the current frontmost application name

## Example approach

1. Identify the target host IP.
2. Write a minimal script for the desired action.
3. Execute using `remote-osascript.run_osascript`.
4. Summarize `stdout`, `stderr`, and exit code.

## Safety notes

- Confirm before running scripts that change files, apps, or system settings.
- Start with read-only or harmless script checks when possible.
- Use reasonable timeouts and inspect `stderr` on failures.
