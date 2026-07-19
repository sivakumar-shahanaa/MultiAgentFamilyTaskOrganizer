import os

from dotenv import load_dotenv
from pydantic_ai import Agent
try:
    from pydantic_ai.models.openai import OpenAIModel
except ImportError:  # pydantic-ai newer releases renamed this class
    from pydantic_ai.models.openai import OpenAIChatModel as OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.schemas import ChatMessage


load_dotenv()

DEFAULT_MODEL = os.getenv("LOCAL_LLM_MODEL", "llama3.2")
DEFAULT_BASE_URL = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1")
DEFAULT_API_KEY = os.getenv("LOCAL_LLM_API_KEY", "ollama")


class LocalChatAgent:
    """Small wrapper around Pydantic AI for an OpenAI-compatible local LLM.

    Ollama, LM Studio, llama.cpp server, and vLLM can all expose an
    OpenAI-compatible `/v1` API. Configure with LOCAL_LLM_* environment vars.
    """

    def __init__(self, model_name: str, system_prompt: str | None = None) -> None:
        provider = OpenAIProvider(base_url=DEFAULT_BASE_URL, api_key=DEFAULT_API_KEY)
        model = OpenAIModel(model_name, provider=provider)
        self.agent = Agent(model, system_prompt=system_prompt)

    async def run(self, message: str, history: list[ChatMessage]) -> str:
        prompt = self._build_prompt(message, history)
        result = await self.agent.run(prompt)
        return str(result.output if hasattr(result, "output") else result.data)

    @staticmethod
    def _build_prompt(message: str, history: list[ChatMessage]) -> str:
        if not history:
            return message

        transcript = "\n".join(f"{item.role}: {item.content}" for item in history)
        return f"Conversation so far:\n{transcript}\n\nuser: {message}"
