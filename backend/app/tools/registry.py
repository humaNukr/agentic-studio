import logging
from typing import Dict, Any, List
from web_search import WEB_SEARCH_SCHEMA, web_search
from run_code import RUN_CODE_SCHEMA, run_code
from database import GET_DB_SCHEMA, EXECUTE_SQL_SCHEMA, get_database_schema, execute_sql_query
from mcp_manager import MCPManager
from shell import SHELL_SCHEMA, execute_shell

logger = logging.getLogger(__name__)

mcp_manager = MCPManager()

NATIVE_TOOLS = [
    WEB_SEARCH_SCHEMA,
    RUN_CODE_SCHEMA,
    GET_DB_SCHEMA,
    EXECUTE_SQL_SCHEMA,
    SHELL_SCHEMA,
]

NATIVE_EXECUTORS = {
    "web_search": web_search,
    "run_code": run_code,
    "get_database_schema": get_database_schema,
    "execute_sql_query": execute_sql_query,
    "execute_shell": execute_shell,
}


def get_all_tools() -> List[Dict[str, Any]]:
    """
    Повертає об'єднаний список усіх інструментів для меню ШІ.
    Оркестратор викличе цю функцію, щоб передати масив у запит до OpenAI.
    """
    return NATIVE_TOOLS + mcp_manager.tool_schemas


async def execute_tool(name: str, tool_input: dict) -> str:
    """
    Єдина точка входу (Facade/Router).
    Отримує команду від ШІ і сама вирішує, куди її спрямувати.
    """
    logger.info(f"Оркестратор запросив виконання інструменту: {name}")

    if name in NATIVE_EXECUTORS:
        executor = NATIVE_EXECUTORS[name]
        try:
            return await executor(**tool_input)
        except Exception as e:
            logger.error(f"Помилка виконання нативного інструменту {name}: {e}")
            return f"Execution Error in native tool: {str(e)}"

    elif name in mcp_manager.tool_to_server:
        return await mcp_manager.call_tool(name, tool_input)

    else:
        error_msg = f"Unknown tool: {name}. Available tools: {list(NATIVE_EXECUTORS.keys()) + list(mcp_manager.tool_to_server.keys())}"
        logger.warning(error_msg)
        return error_msg