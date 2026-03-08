# Remote Command Execution

Use this pattern when the user needs to run a command on a remote host.

## When to use

Use when the user asks to run any shell command on a specified host.

## Common MCP tool usage

Use the remote-exec.run_command tool with the host IP and command.

## Parameters

- **ip**: The IP address of the target host
- **command**: The shell command to execute
- **timeout**: Optional timeout in seconds (default: 30)

## Example user request

check disk space on 10.0.0.86

## Example approach

1. Identify the host
2. Determine the appropriate command (e.g., df -h)
3. Execute via remote-exec.run_command
4. Parse and summarize the output

## Safety notes

- Prefer read-only commands first (ls, cat, df, ps, etc.)
- For destructive commands (rm, kill, etc.), confirm with the user before executing
- Use reasonable timeouts for long-running commands
- If a command fails, check the error and try an alternative approach
