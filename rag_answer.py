import json
from typing import List, Dict, Any

from legal_assistant.llm.embeddings_client import EmbeddingClient
from legal_assistant.llm.chat_client import ChatClient
from legal_assistant.retrieval.vector_store import VectorStore

def _strip_code_fences(text: str) -> str:
    """
    Remove leading ``` / ```json and trailing ``` from an LLM response, if present.
    """
    if not text:
        return text

    text = text.strip()

    # If it starts with a code fence (``` or ```json)
    if text.startswith("```"):
        lines = text.splitlines()

        # Drop first line (``` or ```json)
        if lines:
            lines = lines[1:]

        # Drop last line if it is a closing fence
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]

        return "\n".join(lines).strip()

    return text


def build_context(retrieved_chunks):
    """
    retrieved_chunks: iterable of (_id, score, doc_text, meta_dict)
    """
    context = ""
    for _id, score, doc, meta in retrieved_chunks:
        context += f"Source: {meta.get('source_file', 'unknown')} | Score: {score:.4f}\n"
        context += doc + "\n\n"
    return context


def answer_question(question: str, top_k: int = 4) -> str:
    """
    Original simple RAG Q&A helper (CLI style).
    """
    embed_client = EmbeddingClient()
    chat_client = ChatClient()
    store = VectorStore(db_path="data/index/embeddings.db")

    # Step 1: Embed query
    query_emb = embed_client.embed_texts([question])[0]

    # Step 2: Retrieve relevant chunks
    retrieved = store.query_by_embedding(query_emb, top_k=top_k)

    # Step 3: Build context
    context = build_context(retrieved)

    # Step 4: Ask the LLM
    system_instruction = (
        "You are a legal assistant. "
        "Given the retrieved legal text chunks, answer clearly and accurately. "
        "Cite the source file names inside your explanation."
    )

    user_prompt = f"""
Question:
{question}

Relevant context:
{context}

Provide a concise legal answer based ONLY on this context.
"""

    answer = chat_client.ask(system_instruction, user_prompt)
    return answer


def _build_case_question(metadata: Dict[str, str], filenames: List[str]) -> str:
    """
    Turn UI form fields into a single 'case description' text.
    This is what we embed and use for retrieval.
    """
    matter_overview = metadata.get("matterOverview", "").strip()
    people = metadata.get("peopleAndAliases", "").strip()
    orgs = metadata.get("noteworthyOrganizations", "").strip()
    terms = metadata.get("noteworthyTerms", "").strip()
    extra = metadata.get("additionalContext", "").strip()

    docs_list = ", ".join(filenames) if filenames else "not specified"

    return f"""
Matter overview:
{matter_overview}

People and aliases:
{people}

Noteworthy organizations:
{orgs}

Noteworthy terms:
{terms}

Additional context:
{extra}

Documents provided (filenames):
{docs_list}
""".strip()


def analyze_legal_case(
    metadata: Dict[str, str],
    filenames: List[str],
    top_k: int = 6,
) -> Dict[str, Any]:
    """
    Main function used by the FastAPI endpoint.

    Returns:
      {
        "analysis": "<formal narrative summary>",
        "issues": [...],
        "sources": [
          {"file": "...", "score": 0.87},
          ...
        ]
      }
    """
    embed_client = EmbeddingClient()
    chat_client = ChatClient()
    store = VectorStore(db_path="data/index/embeddings.db")

    # Build the query from UI metadata
    question = _build_case_question(metadata, filenames)

    # 1) Embed the query
    query_emb = embed_client.embed_texts([question])[0]

    # 2) Retrieve relevant chunks
    retrieved = store.query_by_embedding(query_emb, top_k=top_k)

    # Build simple sources summary from retrieved chunks
    sources: List[Dict[str, Any]] = []
    seen_files: set[str] = set()
    for _id, score, _doc, meta in retrieved:
        fname = meta.get("source_file", "unknown")
        if fname not in seen_files:
            seen_files.add(fname)
            sources.append({"file": fname, "score": float(score)})

    # 3) Build textual context
    context = build_context(retrieved)

    # 4) Ask LLM for structured JSON
    system_instruction = (
        "You are an experienced employment and workplace investigations lawyer. "
        "You will be given a high-level description of a legal matter and a set of "
        "retrieved excerpts from documents. "
        "Your task is to produce a formal but easy-to-understand analysis for legal "
        "analysts and lawyers.\n\n"
        "IMPORTANT:\n"
        "- Base your analysis ONLY on the provided context.\n"
        "- If something is not supported by the context, say so explicitly.\n"
        "- Return your answer as valid JSON with this exact structure:\n"
        "{\n"
        '  \"analysis\": \"string – narrative summary with headings like '
        'Executive Summary, Key Allegations, Risk Assessment, Recommended Next Steps\", \n'
        '  \"issues\": [\n'
        "    {\n"
        '      \"id\": \"issue-1\",\n'
        '      \"title\": \"short issue title\",\n'
        '      \"description\": \"2–5 sentence description of the issue\",\n'
        '      \"riskLevel\": \"Low\" | \"Medium\" | \"High\" | \"Unknown\",\n'
        '      \"partiesInvolved\": \"names or roles of key parties, if available\",\n'
        '      \"citations\": \"short references to sources used, e.g. file names\"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "- Do NOT include any other top-level keys.\n"
        "- Ensure the JSON is syntactically valid."
    )

    user_prompt = f"""
CASE DESCRIPTION (from UI form):
{question}

RETRIEVED CONTEXT (from VectorStore):
{context}

Now produce the JSON response as specified.
"""

    raw_answer = chat_client.ask(system_instruction, user_prompt)

    # --- clean + parse LLM JSON ---

    cleaned = _strip_code_fences(raw_answer)

    analysis = cleaned
    issues: List[Dict[str, Any]] = []

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            analysis = parsed.get("analysis", cleaned)
            issues = parsed.get("issues", [])
            if not isinstance(issues, list):
                issues = []
    except Exception:
        # Not valid JSON; keep cleaned text as analysis
        pass

    return {
        "analysis": analysis,
        "issues": issues,
        "sources": sources,
    }


if __name__ == "__main__":
    print("=== Legal RAG Answering System ===")
    query = input("Enter your legal question: ")
    ans = answer_question(query)
    print("\nANSWER:\n")
    print(ans)
