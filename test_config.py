from legal_assistant.config import get_settings

def main():
    settings = get_settings()

    print("Azure OpenAI:")
    print("  BASE_URL:", settings.openai_base_url)
    print("  API_VERSION:", settings.openai_api_version)
    print("  CHAT_MODEL:", settings.chat_model)
    print()

    print("Cohere:")
    # Only show partial key for safety
    if settings.cohere_api_key:
        print("  COHERE_API_KEY starts with:", settings.cohere_api_key[:4] + "****")
    else:
        print("  COHERE_API_KEY is missing!")
    print("  COHERE_EMBEDDING_MODEL:", settings.cohere_embedding_model)

if __name__ == "__main__":
    main()
