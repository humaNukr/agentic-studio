import traceback
from web_search import WEB_SEARCH_SCHEMA, web_search
from run_code import RUN_CODE_SCHEMA, run_code

TOOLS = [
    WEB_SEARCH_SCHEMA,
    RUN_CODE_SCHEMA,
]

TOOL_EXECUTORS = {
    "web_search": web_search,
    "run_code": run_code,
}


async def execute_tool(name: str, tool_input: dict) -> str:
    """
    Єдина точка входу для Оркестратора.
    Приймає ім'я інструменту та аргументи, безпечно виконує його і гарантовано повертає текст (результат або помилку).
    """
    executor = TOOL_EXECUTORS.get(name)

    if not executor:
        return f"Error: Tool '{name}' is not found. Please use only allowed tools."

    try:
        return await executor(**tool_input)

    except Exception as e:
        error_msg = f"Tool '{name}' failed with an internal error: {str(e)}"

        print(f"🔥 CRITICAL TOOL ERROR [{name}]:\n{traceback.format_exc()}")

        return error_msg