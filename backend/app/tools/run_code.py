import asyncio
import os
import tempfile

RUN_CODE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "run_code",
        "description": "Executes Python code for data processing and calculations. os, subprocess, sys, shutil are forbidden.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The raw Python script to execute. Must include print() statements to output the result."
                }
            },
            "required": ["code"]
        }
    }
}

FORBIDDEN_IMPORTS = {"os", "subprocess", "sys", "shutil"}

def is_safe_code(code: str) -> tuple[bool, str]:
    for imp in FORBIDDEN_IMPORTS:
        if f"import {imp}" in code or f"from {imp}" in code:
            return False, f"Module '{imp}' is forbidden"
    return True, "ok"

async def run_code(code: str, **kwargs) -> str:
    """
    Приймає Python код від агента, зберігає у тимчасовий файл,
    виконує в ізольованому підпроцесі з таймаутом і повертає stdout/stderr.
    """
    is_safe, error_msg = is_safe_code(code)
    if not is_safe:
        return f"Security Guardrail Blocked Execution: {error_msg}"

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', encoding='utf-8', delete=False) as f:
        f.write(code)
        temp_file_path = f.name

    try:
        process = await asyncio.create_subprocess_exec(
            "python", temp_file_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=15.0)
        except asyncio.TimeoutError:
            process.kill()
            return "Execution Error: Script timed out after 15 seconds. Did you write an infinite loop?"

        out_str = stdout.decode('utf-8').strip() if stdout else ""
        err_str = stderr.decode('utf-8').strip() if stderr else ""

        if process.returncode == 0:
            if not out_str:
                return "Execution successful, but no output was printed. Use print() to see results."
            return f"Execution successful.\nOutput:\n{out_str}"
        else:
            return f"Execution failed.\nOutput:\n{out_str}\nErrors:\n{err_str}"

    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)