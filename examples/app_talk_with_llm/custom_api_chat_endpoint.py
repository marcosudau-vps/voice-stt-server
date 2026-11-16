"""
Chat endpoint helpers for assistant examples.
"""

from dataclasses import dataclass
import os
from pathlib import Path
from dotenv import load_dotenv


DEFAULT_CHAT_MODEL = "opencode-go/minimax-m3"


@dataclass(frozen=True)
class ChatEndpointConfig:
    model: str
    base_url: str | None
    api_key: str | None



def find_project_root(
    markers=(
        ".git",
        "pyproject.toml",
        "LICENSE",
        "docker-compose.yml",
        "Dockerfile",
        "setup.py",
        ".env",
        "requirements.txt",
        "CONTRIBUTING.md",
    )
):
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        if any((parent / m).exists() for m in markers):
            return parent
    raise RuntimeError("Projekt-Root konnte nicht automatisch gefunden werden")
def load_project_env(project_root: Path | None = None) -> None:
    """Load the project's single secrets file when it exists."""

    project_root = project_root or find_project_root()
    secrets_file = project_root / ".env"
    if secrets_file.is_file():
        load_dotenv(secrets_file)


class ChatEndpoint:

    @staticmethod
    def chat_endpoint_config() -> ChatEndpointConfig:
        load_project_env()

        return ChatEndpointConfig(
            model=(
                os.environ.get("CUSTOM_API_CHAT_API_MODEL")
                or os.environ.get("CUSTOM_API_CHAT_MODEL")
                or os.environ.get("CHAT_MODEL")
                or DEFAULT_CHAT_MODEL
            ),
            base_url=(
                os.environ.get("CUSTOM_API_CHAT_BASE_URL")
                or os.environ.get("CUSTOM_API_BASE_URL")
                or os.environ.get("CHAT_BASE_URL")
            ),
            api_key=(
                os.environ.get("CUSTOM_API_CHAT_API_KEY")
                or os.environ.get("CUSTOM_API_STT_API_KEY")
                or os.environ.get("CHAT_API_KEY")
            ),
        )
    @staticmethod
    def create_chat_client():
        from openai import OpenAI as ChatApiClient

        config = ChatEndpoint.chat_endpoint_config()

        if not config.api_key:
            raise RuntimeError(
                "Missing chat API key. Set CUSTOM_API_CHAT_API_KEY or CHAT_API_KEY in the project .env file."
            )

        kwargs = {"api_key": config.api_key}

        if config.base_url:
            kwargs["base_url"] = config.base_url

        return ChatApiClient(**kwargs)
    @staticmethod
    def chat_model(default: str = DEFAULT_CHAT_MODEL) -> str:
        load_project_env()
        return (
            os.environ.get("CUSTOM_API_CHAT_API_MODEL")
            or os.environ.get("CUSTOM_API_CHAT_MODEL")
            or os.environ.get("CHAT_MODEL")
            or default
        )
    @staticmethod
    def stream_chat_completion(messages, model: str | None = None, **kwargs):
        """
        Yields text deltas from a streamed chat completion response.
        """
        client = ChatEndpoint.create_chat_client()

        response_stream = client.chat.completions.create(
            model=model or ChatEndpoint.chat_model(),
            messages=messages,
            stream=True,
            **kwargs,
        )

        for chunk in response_stream:
            text_chunk = ChatEndpoint._chat_delta_text(chunk)
            if text_chunk:
                yield text_chunk
    @staticmethod
    def _chat_delta_text(chunk):
        if isinstance(chunk, dict):
            choices = chunk.get("choices") or []
            if not choices:
                return None

            delta = choices[0].get("delta") or {}
            return delta.get("content")

        choices = getattr(chunk, "choices", None) or []
        if not choices:
            return None

        delta = getattr(choices[0], "delta", None)
        return getattr(delta, "content", None)


def stream_chat_completion(messages, model: str | None = None, **kwargs):
    """Module-level convenience wrapper used by the desktop interface."""

    yield from ChatEndpoint.stream_chat_completion(messages, model=model, **kwargs)
