from legal_assistant.llm.embeddings_client import EmbeddingClient

def main():
    client = EmbeddingClient()

    texts = [
        "This is a test for our legal document search system.",
        "Another sentence about contracts, liability and negligence."
    ]

    vectors = client.embed_texts(texts)

    print(f"Got {len(vectors)} embeddings.")
    if vectors:
        print(f"Dimension of first embedding: {len(vectors[0])}")

if __name__ == "__main__":
    main()
