from legal_assistant.llm.chat_client import ChatClient

def main():
    chat = ChatClient()
    ans = chat.ask(
        "You are a helpful assistant.",
        "Reply with a short sentence confirming that Azure OpenAI is working."
    )
    print("Response from Azure:")
    print(ans)

if __name__ == "__main__":
    main()
