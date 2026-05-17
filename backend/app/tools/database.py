import os
import asyncpg
from typing import Dict, List
import sqlglot
from sqlglot import exp

GET_DB_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_database_schema",
        "description": "Reads the structure of the connected database. Call this tool FIRST to understand the available tables, columns, and data types before trying to write any SQL queries.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}

EXECUTE_SQL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "execute_sql_query",
        "description": "Executes a read-only SELECT SQL query on the connected database. Use this AFTER you have retrieved the schema. Only pure SELECT queries are allowed. Do not attempt to use INSERT, UPDATE, DELETE, DROP, or ALTER.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The valid SQL SELECT query to execute."
                }
            },
            "required": ["query"]
        }
    }
}


async def get_database_schema(**kwargs) -> str:
    """
    Підключається до БД користувача (BYOD), читає системний каталог 
    і повертає Markdown-структуру таблиць для штучного інтелекту.
    """
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        return "Error: DATABASE_URL is not set. Please provide the connection string to your database."

    try:
        conn = await asyncpg.connect(db_url)
    except Exception as e:
        return f"Database Connection Error: {str(e)}"

    try:
        query = """
                SELECT table_name, column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public'
                ORDER BY table_name, ordinal_position; \
                """

        rows = await conn.fetch(query)

        if not rows:
            return "The database connected successfully, but the 'public' schema is empty (no tables found)."

        schema_dict: Dict[str, List[str]] = {}
        for row in rows:
            table = row['table_name']
            column_def = f"- {row['column_name']} ({row['data_type']})"

            if table not in schema_dict:
                schema_dict[table] = []
            schema_dict[table].append(column_def)

        formatted_output = ["Database Schema:\n"]
        for table, columns in schema_dict.items():
            formatted_output.append(f"Table: {table}")
            formatted_output.extend(columns)
            formatted_output.append("")

        return "\n".join(formatted_output)

    except Exception as e:
        return f"Error executing schema discovery query: {str(e)}"

    finally:
        await conn.close()


def is_safe_read_query(query: str) -> tuple[bool, str]:
    """
    Аналізує SQL-запит через побудову синтаксичного дерева (AST).
    Повертає (True, "ok"), якщо запит безпечний (тільки SELECT).
    Повертає (False, "причина"), якщо знайдено спробу модифікації бази.
    """
    try:
        statements = sqlglot.parse(query, read="postgres")
    except sqlglot.errors.ParseError as e:
        return False, f"SQL Syntax Error: {str(e)}"

    if not statements:
        return False, "The query is empty."

    if len(statements) > 1:
        return False, "Multiple SQL statements are not allowed. Please provide only one SELECT query."

    statement = statements[0]

    if not isinstance(statement, exp.Select):
        root_type = type(statement).__name__
        return False, f"Only SELECT queries are permitted. You attempted to use a '{root_type}' operation."

    return True, "ok"


async def execute_sql_query(query: str, **kwargs) -> str:
    """
    Приймає SQL-запит від ШІ, перевіряє його на безпеку (тільки SELECT),
    виконує в базі даних користувача і повертає результат у вигляді Markdown-таблиці.
    """
    is_safe, error_message = is_safe_read_query(query)
    if not is_safe:
        return f"Security Exception: {error_message}"

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        return "Error: DATABASE_URL is not set. Please provide the connection string."

    try:
        conn = await asyncpg.connect(db_url)
    except Exception as e:
        return f"Database Connection Error: {str(e)}"

    try:
        rows = await conn.fetch(query)

        if not rows:
            return "Query executed successfully, but returned no data (empty result)."

        columns = list(rows[0].keys())

        header = " | ".join(columns)
        separator = " | ".join(["---"] * len(columns))

        data_rows = []
        for row in rows:
            string_values = [str(row[col]).replace("|", "\\|") for col in columns]
            data_rows.append(" | ".join(string_values))

        return f"{header}\n{separator}\n" + "\n".join(data_rows)

    except Exception as e:
        return f"Database Execution Error: {str(e)}"

    finally:
        await conn.close()