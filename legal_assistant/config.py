import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load variables from .env into environment
load_dotenv()


@dataclass
class Settings:
    # Azure OpenAI (for chat / summaries)
    openai_api_key: str | None
    openai_base_url: str | None
    openai_api_version: str | None
    chat_model: str

    # Cohere (for embeddings)
    cohere_api_key: str | None
    cohere_embedding_model: str | None

    # Anthropic (Claude)
    anthropic_api_key: str | None
    anthropic_model: str

    # OpenAI code/codex style model (optional)
    openai_code_model: str | None

    # ✅ NEW: SQL Server connection string
    sqlserver_conn_str: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        # Read from the .env file (which we already loaded above)
        openai_api_key = os.getenv("OPENAI_API_KEY")
        openai_base_url = os.getenv("OPENAI_BASE_URL")
        openai_api_version = os.getenv("OPENAI_API_VERSION")
        chat_model = os.getenv("OPENAI_CHAT_MODEL")

        cohere_api_key = os.getenv("COHERE_API_KEY")
        cohere_embedding_model = os.getenv("COHERE_EMBEDDING_MODEL")

        anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4.5")

        openai_code_model = os.getenv("OPENAI_CODE_MODEL")

        # ✅ NEW: read SQL Server conn string
        sqlserver_conn_str = os.getenv("SQLSERVER_CONN_STR")

        # Require OpenAI config
        if not openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not set in .env")
        if not openai_base_url:
            raise RuntimeError("OPENAI_BASE_URL is not set in .env")
        if not openai_api_version:
            raise RuntimeError("OPENAI_API_VERSION is not set in .env")
        if not chat_model:
            raise RuntimeError("OPENAI_CHAT_MODEL is not set in .env")

        # For now, we require Cohere for embeddings
        if not cohere_api_key:
            raise RuntimeError("COHERE_API_KEY is not set in .env")
        if not cohere_embedding_model:
            raise RuntimeError("COHERE_EMBEDDING_MODEL is not set in .env")

        # Anthropic is optional; warn (don't raise) if missing when not needed
        # OpenAI code model is optional

        return cls(
            openai_api_key=openai_api_key,
            openai_base_url=openai_base_url,
            openai_api_version=openai_api_version,
            chat_model=chat_model,
            cohere_api_key=cohere_api_key,
            cohere_embedding_model=cohere_embedding_model,
            anthropic_api_key=anthropic_api_key,
            anthropic_model=anthropic_model,
            openai_code_model=openai_code_model,
            sqlserver_conn_str=sqlserver_conn_str,  # ✅ pass it through
        )


# Simple singleton-style accessor so we don't reload .env everywhere
_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
    return _settings
