import json
import os
import logging
from typing import Dict, Any, List
from mcp_client import MCPClient

logger = logging.getLogger(__name__)


class MCPManager:
    def __init__(self, config_path: str = "mcp_servers.json"):
        self.config_path = config_path

        self.servers: Dict[str, MCPClient] = {}

        self.tool_to_server: Dict[str, str] = {}

        self.tool_schemas: List[Dict[str, Any]] = []

    async def load_and_start_all(self):
        """
        Читає конфіг, піднімає підпроцеси і збирає їхні схеми.
        Викликається один раз під час старту FastAPI сервера.
        """
        if not os.path.exists(self.config_path):
            logger.warning(f"Config file {self.config_path} not found. Skipping MCP initialization.")
            return

        with open(self.config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        mcp_servers_config = config.get("mcpServers", {})

        for server_name, server_info in mcp_servers_config.items():
            logger.info(f"Starting MCP server: {server_name}")

            client = MCPClient(
                server_name=server_name,
                command=server_info.get("command"),
                args=server_info.get("args", []),
                env=server_info.get("env", {})
            )

            await client.start()
            self.servers[server_name] = client

            try:
                response = await client.send_request("tools/list")

                tools = response.get("result", {}).get("tools", [])

                for tool in tools:
                    tool_name = tool["name"]

                    self.tool_to_server[tool_name] = server_name

                    openai_schema = self._convert_mcp_to_openai_schema(tool)
                    self.tool_schemas.append(openai_schema)

                logger.info(f"Registered tools from {server_name}: {[t['name'] for t in tools]}")

            except Exception as e:
                logger.error(f"Failed to do handshake with {server_name}: {e}")

    def _convert_mcp_to_openai_schema(self, mcp_tool: dict) -> dict:
        """
        Перекладає опис інструменту з формату MCP у формат OpenAI Function Calling.
        """
        return {
            "type": "function",
            "function": {
                "name": mcp_tool["name"],
                "description": mcp_tool.get("description", "No description provided."),
                # В MCP параметри лежать в 'inputSchema', а OpenAI чекає 'parameters'
                "parameters": mcp_tool.get("inputSchema", {
                    "type": "object",
                    "properties": {}
                })
            }
        }

    async def call_tool(self, tool_name: str, tool_input: dict) -> str:
        """
        Шукає потрібний підпроцес і відправляє йому команду на виконання інструменту.
        """
        server_name = self.tool_to_server.get(tool_name)
        if not server_name:
            return f"Error: Tool '{tool_name}' is not registered in any MCP server."

        client = self.servers.get(server_name)
        if not client:
            return f"Error: MCP server '{server_name}' is down or not found."

        try:
            mcp_params = {
                "name": tool_name,
                "arguments": tool_input
            }

            logger.info(f"Sending request to {server_name} for tool {tool_name}")
            response = await client.send_request("tools/call", mcp_params)

            content_blocks = response.get("result", {}).get("content", [])

            if not content_blocks:
                return "Tool executed successfully, but returned no content."

            result_text = "\n".join([
                block.get("text", "")
                for block in content_blocks
                if block.get("type") == "text"
            ])

            return result_text

        except Exception as e:
            logger.error(f"Error calling MCP tool {tool_name} on {server_name}: {e}")
            return f"MCP Execution Error: {str(e)}"