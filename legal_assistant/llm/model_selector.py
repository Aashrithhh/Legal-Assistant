from typing import Optional
import logging

from legal_assistant.config import get_settings
from legal_assistant.llm.chat_client import ChatClient

log = logging.getLogger(__name__)


class ModelSelector:
    """Simple router that lets callers choose between OpenAI (Azure) and Anthropic.

    Usage:
      selector = ModelSelector()
      selector.generate(provider="anthropic", prompt="Hello")
      selector.generate(provider="openai", system_prompt=..., user_prompt=...)
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.openai = ChatClient()

        # Try to lazily import Anthropic (optional dependency)
        self.anthropic_client = None
        try:
            from anthropic import Anthropic

            if self.settings.anthropic_api_key:
                self.anthropic_client = Anthropic(api_key=self.settings.anthropic_api_key)
        except Exception:
            # Anthropic not installed or not configured; keep None
            log.debug("Anthropic client not available; skip creating it")

        # Model defaults
        self.default_anthropic_model = getattr(self.settings, "anthropic_model", "claude-haiku-4.5")
        self.default_openai_code_model = getattr(self.settings, "openai_code_model", None)

    def generate(
        self,
        provider: str = "openai",
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None,
        prompt: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: int = 800,
        temperature: float = 0.0,
    ) -> str:
        """Generate text/code using the requested provider.

        - `provider`: 'openai' or 'anthropic'
        - For OpenAI chat use `system_prompt` and `user_prompt`.
        - For Anthropic use `prompt` (string) or `user_prompt` text.
        - `model` overrides the configured default.
        """

        provider = (provider or "openai").lower()

        if provider in ("anthropic", "claude"):
            if not self.anthropic_client:
                raise RuntimeError("Anthropic client is not initialized (missing package or API key)")

            anth_model = model or self.default_anthropic_model
            # Anthropic expects a prompt string — prefer `prompt`, fallback to user_prompt
            anth_prompt = prompt or user_prompt or system_prompt or ""
            resp = self.anthropic_client.completions.create(
                model=anth_model,
                prompt=anth_prompt,
                max_tokens_to_sample=max_tokens,
                temperature=temperature,
            )
            # Response shape: .completion
            return getattr(resp, "completion", resp.get("completion", ""))

        # Default: OpenAI / Azure chat
        # Use chat flow if system+user provided; else send single user message
        chosen_model = model or self.openai.model
        if system_prompt is not None or user_prompt is not None:
            return self.openai.client.chat.completions.create(
                model=chosen_model,
                messages=[
                    {"role": "system", "content": system_prompt or ""},
                    {"role": "user", "content": user_prompt or prompt or ""},
                ],
                temperature=temperature,
            ).choices[0].message.content

        # Fallback single-prompt style
        return self.openai.client.chat.completions.create(
            model=chosen_model,
            messages=[{"role": "user", "content": prompt or ""}],
            temperature=temperature,
        ).choices[0].message.content
