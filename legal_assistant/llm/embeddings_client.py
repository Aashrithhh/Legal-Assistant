from typing import List
import cohere

from legal_assistant.config import get_settings


class EmbeddingClient:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.cohere_api_key:
            raise RuntimeError("Cohere API key is missing in settings")

        self.client = cohere.Client(settings.cohere_api_key)
        self.model = settings.cohere_embedding_model

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Given a list of texts, return a list of embedding vectors using Cohere.
        """
        if not texts:
            return []

        response = self.client.embed(
            model=self.model,
            texts=texts,
            input_type="search_document",
        )

        # Cohere returns embeddings as a list of lists
        return response.embeddings
