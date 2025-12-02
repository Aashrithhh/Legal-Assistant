from legal_assistant.llm.embeddings_client import EmbeddingClient
from legal_assistant.retrieval.vector_store import VectorStore


def main():
    # 1) Setup embedding client and vector store
    embed_client = EmbeddingClient()
    store = VectorStore(db_path="data/index/embeddings.db")

    # 2) Some dummy "documents" (just short texts for now)
    docs = [
        "This document discusses breach of contract and damages.",
        "This text is about criminal law and evidence admissibility.",
        "This passage covers negligence and duty of care in tort law.",
    ]

    ids = ["doc1", "doc2", "doc3"]
    metadatas = [
        {"label": "contract"},
        {"label": "criminal"},
        {"label": "tort"},
    ]

    # 3) Embed and store them
    embeddings = embed_client.embed_texts(docs)
    store.add_embeddings(ids=ids, embeddings=embeddings, documents=docs, metadatas=metadatas)
    print("Stored 3 documents in SQLite vector store.")

    # 4) Query: something about contract law
    query_text = "What cases involve breach of contract and remedies for damages?"
    query_embedding = embed_client.embed_texts([query_text])[0]

    results = store.query_by_embedding(query_embedding, top_k=2)

    print("\nTop matches for query:", query_text)
    for rank, (_id, score, doc, meta) in enumerate(results, start=1):
        print(f"\nResult #{rank}")
        print("  ID:", _id)
        print("  Score:", score)
        print("  Metadata:", meta)
        print("  Document:", doc)


if __name__ == "__main__":
    main()
