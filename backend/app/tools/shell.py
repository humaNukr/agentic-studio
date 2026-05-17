import asyncio
import shlex
import logging

logger = logging.getLogger(__name__)

SHELL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "execute_shell",
        "description": "Executes allowed shell commands (like kubectl, curl, grep, ls, cat) in the Linux container. Supports pipes '|'. Do not use for writing scripts, use run_code instead.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute."
                }
            },
            "required": ["command"]
        }
    }
}

ALLOWED_BINARIES = {"kubectl", "helm", "ls", "cat", "grep", "awk", "jq", "curl", "ping", "echo", "tail", "head"}
FORBIDDEN_TOKENS = {"rm", "sudo", "bash", "sh", "zsh", "python", "nc", ">", ">>"}

def is_safe_shell_command(command: str) -> tuple[bool, str]:
    """
    Лексично розбирає команду як shell-інтерпретатор і перевіряє кожну під-команду.
    """
    if "$(" in command or "`" in command:
        return False, "Subshells and backticks are strictly forbidden for security reasons."

    pipelines = command.split("|")

    for pipe in pipelines:
        try:
            tokens = shlex.split(pipe.strip(), posix=True)
        except ValueError as e:
            return False, f"Malformed shell syntax: {e}"

        if not tokens:
            continue

        base_cmd = tokens[0]

        if base_cmd not in ALLOWED_BINARIES:
            return False, f"Binary '{base_cmd}' is denied. Allowed tools: {', '.join(ALLOWED_BINARIES)}"

        for token in tokens:
            if token in FORBIDDEN_TOKENS:
                return False, f"Forbidden token or argument detected: '{token}'"

    return True, "ok"

async def execute_shell(command: str, **kwargs) -> str:
    """
    Перевіряє і виконує термінальну команду в ізольованому процесі.
    """
    is_safe, error_msg = is_safe_shell_command(command)
    if not is_safe:
        return f"Security Guardrail Blocked Execution: {error_msg}"

    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10.0)
        except asyncio.TimeoutError:
            process.kill()
            return "Execution Error: Command timed out after 10 seconds. Use tools like 'tail' or 'head' for large outputs."

        out_str = stdout.decode('utf-8').strip() if stdout else ""
        err_str = stderr.decode('utf-8').strip() if stderr else ""

        if process.returncode == 0:
            if not out_str:
                return "Command executed successfully, but produced no output."
            return f"Output:\n{out_str}"
        else:
            return f"Command failed (exit code {process.returncode}).\nOutput:\n{out_str}\nErrors:\n{err_str}"

    except Exception as e:
        return f"System Execution Error: {str(e)}"