import json
import logging
import os
from typing import AsyncGenerator, List, Dict, Any, Callable, Awaitable
from openai import AsyncOpenAI

groq_client = AsyncOpenAI(
    api_key=os.environ.get("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

DEFAULT_MODEL = "llama-3.3-70b-versatile"

from app.models.schemas import AgentState, AgentEvent, EventType

logger = logging.getLogger(__name__)


class ReActEngine:
    def __init__(
            self,
            llm_client: AsyncOpenAI,
            model_name: str,
            tools_schema: List[Dict[str, Any]],
            tool_executor: Callable[[str, Dict[str, Any]], Awaitable[str]],
            max_iterations: int = 10
    ):
        self.llm = llm_client
        self.model = model_name
        self.tools_schema = tools_schema
        self.tool_executor = tool_executor
        self.max_iterations = max_iterations

    async def run_loop(self, state: AgentState) -> AsyncGenerator[AgentEvent, None]:
        while state.iteration_count < self.max_iterations:
            state.iteration_count += 1
            logger.info(f"Session {state.session_id} | Iteration {state.iteration_count}")

            try:
                response = await self.llm.chat.completions.create(
                    model=self.model,
                    messages=state.messages,
                    tools=self.tools_schema if self.tools_schema else None,
                    tool_choice="auto"
                )

                message = response.choices[0].message

                state.messages.append(message.model_dump(exclude_none=True))

                if message.content:
                    event_type = EventType.ANSWER if not message.tool_calls else EventType.THOUGHT
                    yield AgentEvent(type=event_type, content=message.content)

                if not message.tool_calls:
                    logger.info(f"Session {state.session_id} | Finished successfully")
                    break

                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name

                    yield AgentEvent(
                        type=EventType.TOOL_CALL,
                        content=f"Calling tool: {tool_name}",
                        metadata={"tool": tool_name}
                    )

                    try:
                        arguments = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError as e:
                        result_str = f"System Error: Invalid JSON arguments. Parse error: {str(e)}. Please try again."
                    else:
                        result_str = await self.tool_executor(tool_name, arguments)

                    yield AgentEvent(
                        type=EventType.TOOL_RESULT,
                        content=f"Result from {tool_name}",
                        metadata={"result": result_str[:200] + "..."}
                    )

                    state.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": result_str
                    })

            except Exception as e:
                logger.error(f"Critical error in ReAct loop: {e}", exc_info=True)
                yield AgentEvent(type=EventType.ERROR, content="Internal Engine Error")
                break

        else:
            error_msg = f"Agent stopped: Exceeded max iterations ({self.max_iterations})."
            logger.warning(error_msg)
            yield AgentEvent(type=EventType.ERROR, content=error_msg)