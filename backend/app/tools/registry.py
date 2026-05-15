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