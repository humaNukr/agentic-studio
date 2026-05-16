import asyncio
import os
import signal
import logging
import json

logger = logging.getLogger(__name__)


class MCPClient:
    def __init__(self, server_name: str, command: str, args: list, env: dict = None):
        self.server_name = server_name
        self.command = command
        self.args = args
        self.env = env or {}

        self.process: asyncio.subprocess.Process | None = None

    async def start(self):
        """
        Запускає MCP сервер як ізольований асинхронний підпроцес.
        """
        process_env = os.environ.copy()
        process_env.update(self.env)

        try:
            self.process = await asyncio.create_subprocess_exec(
                self.command,
                *self.args,
                env=process_env,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                preexec_fn=os.setsid if os.name != 'nt' else None
            )
            logger.info(f"🚀 MCP Server '{self.server_name}' started with PID {self.process.pid}")

        except Exception as e:
            logger.error(f"❌ Failed to start MCP server '{self.server_name}': {e}")
            raise

    async def stop(self):
        """
        Безпечно вбиває процес та всі його дочірні потоки, звільняючи пам'ять.
        """
        if self.process and self.process.returncode is None:
            try:
                if os.name != 'nt':
                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                else:
                    self.process.kill()

                await self.process.wait()
                logger.info(f"🛑 MCP Server '{self.server_name}' stopped.")
            except Exception as e:
                logger.error(f"Error stopping MCP server '{self.server_name}': {e}")

    async def send_request(self, method: str, params: dict = None) -> dict:
        """
        Відправляє команду (method) з параметрами (params) у підпроцес
        і чекає на відповідь.
        """
        if not self.process:
            raise RuntimeError("Сервер ще не запущено! Викличте .start() спочатку.")

        request_id = 1
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {}
        }

        json_str = json.dumps(payload) + "\n"
        self.process.stdin.write(json_str.encode('utf-8'))
        await self.process.stdin.drain()

        response_bytes = await self.process.stdout.readline()
        response_str = response_bytes.decode('utf-8').strip()

        if not response_str:
            raise ValueError("Сервер нічого не відповів або процес \"вмер\".")

        return json.loads(response_str)