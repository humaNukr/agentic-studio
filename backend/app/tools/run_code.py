import os
from e2b_code_interpreter import AsyncSandbox

RUN_CODE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "run_code",
        "description": "Executes Python code in a secure sandboxed environment. Use this to perform math calculations, data analysis, or logic testing. Returns the console output (stdout) or errors (stderr).",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The pure Python code to execute. Do not include markdown formatting like ```python, just the raw code."
                }
            },
            "required": ["code"]
        }
    }
}


async def run_code(code: str, **kwargs) -> str:
    """
    Асинхронно створює хмарну мікро-віртуальну машину E2B,
    виконує там згенерований Python-код і повертає результати (stdout/stderr) або стек помилки.
    """
    if not os.environ.get("E2B_API_KEY"):
        raise ValueError("E2B_API_KEY is not set in the environment variables.")

    sandbox = await AsyncSandbox.create()

    try:
        execution = await sandbox.run_code(code)
    finally:
        await sandbox.kill()

    if execution.error:
        error_msg = (
            f"Code Execution Failed!\n"
            f"Type: {execution.error.name}\n"
            f"Message: {execution.error.value}\n"
            f"Traceback:\n{execution.error.traceback}"
        )
        return error_msg

    output_parts = []

    if execution.logs.stdout:
        output_parts.append("STDOUT:\n" + "".join(execution.logs.stdout))

    if execution.logs.stderr:
        output_parts.append("STDERR (Warnings):\n" + "".join(execution.logs.stderr))

    if not output_parts:
        return (
            "Code executed successfully, but there was no console output. "
            "Tip: Ensure you use print() statements to output the required results."
        )

    return "\n\n".join(output_parts)