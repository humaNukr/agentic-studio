import traceback
from web_search import WEB_SEARCH_SCHEMA, web_search
from run_code import RUN_CODE_SCHEMA, run_code
from database import GET_DB_SCHEMA, EXECUTE_SQL_SCHEMA, get_database_schema, execute_sql_query

TOOLS = [
    WEB_SEARCH_SCHEMA,
    RUN_CODE_SCHEMA,
    GET_DB_SCHEMA,
    EXECUTE_SQL_SCHEMA,
]

TOOL_EXECUTORS = {
    "web_search": web_search,
    "run_code": run_code,
    "get_database_schema": get_database_schema,
    "execute_sql_query": execute_sql_query,
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