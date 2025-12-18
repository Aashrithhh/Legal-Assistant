from openai import AzureOpenAI

from legal_assistant.config import get_settings


class ChatClient:
    """
    Wraps Azure OpenAI chat completion for easy reuse.
    """

    def __init__(self) -> None:
        settings = get_settings()

        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not set in .env")
        if not settings.openai_base_url:
            raise RuntimeError("OPENAI_BASE_URL is not set in .env")
        if not settings.openai_api_version:
            raise RuntimeError("OPENAI_API_VERSION is not set in .env")

        self.client = AzureOpenAI(
            api_key=settings.openai_api_key,
            azure_endpoint=settings.openai_base_url,
            api_version=settings.openai_api_version,
        )
        self.model = settings.chat_model

    def ask(self, system_prompt: str, user_prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        # New OpenAI client returns .message.content
        return response.choices[0].message.content
