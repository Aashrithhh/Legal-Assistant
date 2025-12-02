from legal_assistant.utils.chunking import chunk_text

def main():
    text = (
        "This is a small example text to test our chunking function. "
        "In a real scenario, this would be a long legal document with many paragraphs, "
        "sections, and clauses about contract law, negligence, and other topics."
    )

    chunks = chunk_text(text, max_words=10, overlap=3)

    print(f"Total chunks: {len(chunks)}")
    for i, ch in enumerate(chunks, start=1):
        print(f"\nChunk {i}:")
        print(ch)

if __name__ == "__main__":
    main()
