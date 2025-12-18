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
    context_lines: list[str] = []
    for citation_idx, (_id, score, doc, meta) in enumerate(retrieved_chunks, start=1):
        source_file = meta.get("source_file", "unknown")
        chunk_index = meta.get("chunk_index", "unknown")
        source_type = meta.get("source_type", "unknown")
        context_lines.append(
            f"[CITATION {citation_idx}] file={source_file} type={source_type} chunk={chunk_index} score={score:.4f}"
        )
        context_lines.append(doc)
        context_lines.append("")
    return "\n".join(context_lines)


def _normalize_issue_citations(issues: List[Dict[str, Any]], sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ensure each issue has a human-readable citations string that includes filenames, prioritizing audio sources."""
    # Separate audio sources from other sources
    audio_files = [s.get("file") for s in sources if isinstance(s, dict) and s.get("file") and 
                   (s.get("file", "").endswith(".mp3") or s.get("file", "").endswith(".wav") or s.get("file", "").endswith(".m4a"))]
    other_files = [s.get("file") for s in sources if isinstance(s, dict) and s.get("file") and 
                   not (s.get("file", "").endswith(".mp3") or s.get("file", "").endswith(".wav") or s.get("file", "").endswith(".m4a"))]
    
    # Build fallback with audio sources first
    fallback_parts = audio_files[:2] + other_files[:3]
    fallback = ", ".join(fallback_parts[:5]) if fallback_parts else "unknown"

    normalized: List[Dict[str, Any]] = []
    for issue in issues or []:
        if not isinstance(issue, dict):
            continue

        citations_val = issue.get("citations")
        
        # Parse existing citations into a list of files
        cited_files: list[str] = []
        if isinstance(citations_val, list):
            for item in citations_val:
                if isinstance(item, str) and item.strip():
                    cited_files.append(item.strip())
                elif isinstance(item, dict):
                    file = item.get("file") or item.get("source_file")
                    if file:
                        cited_files.append(str(file))
        elif isinstance(citations_val, str) and citations_val.strip():
            # Parse comma-separated string
            cited_files = [f.strip() for f in citations_val.split(",") if f.strip()]
        
        # CRITICAL FIX: If audio sources exist but are NOT cited, inject them at the beginning
        # This ensures audio recordings (primary evidence) are always traceable
        if audio_files:
            audio_missing = all(audio not in cited_files for audio in audio_files)
            if audio_missing:
                # Prepend audio sources to ensure they appear in citations
                cited_files = audio_files[:2] + cited_files[:3]
        
        # Build final citation string
        if cited_files:
            issue["citations"] = ", ".join(cited_files[:5])
        else:
            issue["citations"] = fallback

        normalized.append(issue)

    return normalized


def answer_question(
    question: str,
    history: List[Dict[str, str]] | None = None,
    top_k: int = 10,
) -> Dict[str, Any]:
    """
    Conversational RAG helper. Retrieval is still done on the latest question; history
    is used to interpret follow-ups when constructing the chat messages.
    """
    history = history or []

    embed_client = EmbeddingClient()
    chat_client = ChatClient()
    store = VectorStore(db_path="data/index/embeddings.db")

    # Step 1: Embed query
    query_emb = embed_client.embed_texts([question])[0]

    # Step 2: Retrieve relevant chunks
    retrieved = store.query_by_embedding(query_emb, top_k=top_k)

    # Step 3: Build context
    context = build_context(retrieved)

    # Step 4: Build messages with history
    messages = [
        {
            "role": "system",
            "content": (
                "You are an experienced employment and workplace investigations lawyer. "
                "You are in a multi-turn conversation with a legal analyst. "
                "Use both the conversation history and the retrieved context to answer."
            ),
        }
    ]

    for msg in history[-8:]:
        if msg.get("role") in {"user", "assistant"} and msg.get("content"):
            messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append(
        {
            "role": "user",
            "content": (
                "Conversation continues. Here is the latest user question:\n"
                f"{question}\n\n"
                "Here are the most relevant document excerpts:\n"
                f"{context}\n\n"
                "Please answer clearly. If the question is ambiguous, use the history to resolve "
                "references like 'this', 'that one', or 'the second issue'."
            ),
        }
    )

    response = chat_client.client.chat.completions.create(
        model=chat_client.model,
        messages=messages,
        temperature=0.2,
    )

    raw = response.choices[0].message.content or ""
    cleaned = _strip_code_fences(raw)

    return {
        "answer": cleaned,
        "context": context,
    }


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
    top_k: int = 100,
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
        "- Ensure the JSON is syntactically valid.\n"
        "- Identify ALL distinct issues you can reasonably infer from the provided context.\n"
        "- Do NOT artificially limit to three issues; if the context supports more, include them all (grouping only very similar incidents).\n"
        "- If the context is sparse, it is acceptable to return only 1–2 issues."
    )

    # Override with explicit schema including timeline, keyPeople, and category taxonomy
    system_instruction = """
You are an experienced employment and workplace investigations lawyer. You will be given a high-level description of a legal matter and a set of retrieved excerpts from documents. Your task is to produce a formal but easy-to-understand analysis for legal analysts and lawyers.

LEGAL ISSUE TAXONOMY:
Use the following taxonomy to classify each issue you identify:

1. Workplace Misconduct / HR Issues
   - Harassment (sexual, verbal, physical, bullying)
   - Discrimination (gender, race, age, disability)
   - Retaliation
   - Hostile Work Environment
   - Workplace Violence / Threats
   - Inappropriate Behavior / Professional Misconduct
   - Conflict of Interest
   - Whistleblower Complaints

2. Policy Violations
   - Code of Conduct Violation
   - IT & Security Policy Violation
   - Email/Communication Policy Violation
   - Social Media Policy Violation
   - Acceptable Use Policy Violation
   - Data Privacy Policy Violation
   - Financial Policy / Expense Policy Violation
   - Bribery & Corruption

3. Compliance & Regulatory Issues
   - Non-Compliance with laws / standards / internal controls
   - GDPR / Data Privacy Violations
   - HIPAA / PHI Exposure
   - SOX Compliance Issues
   - Antitrust / Competition Law Concerns
   - Export Control Violations
   - Environmental Compliance Issues

4. Contract & Commercial Issues
   - Contract Breach / SLA Violation
   - Contractual Disputes
   - Vendor Mismanagement / Procurement Irregularities
   - Unauthorized Commitments / Signing without Authority

5. Fraud & Financial Irregularities
   - Financial Fraud / Accounting Irregularities
   - Embezzlement / Misuse of Funds
   - False Claims / Misrepresentations
   - Kickbacks / Bribes
   - Insider Trading / Money Laundering

6. Cybersecurity & Data Protection Issues
   - Data Breach / Unauthorized Access / Information Leakage
   - Malware / Phishing Incidents
   - Password Sharing
   - IP Theft / Confidentiality Breach
   - Loss of Devices with Sensitive Data

7. Intellectual Property (IP) Issues
   - Trade Secret Misuse
   - Copyright / Patent / Trademark Violations
   - Unauthorized Sharing of Proprietary Data

8. Operational & Safety Issues
   - Health & Safety Violations
   - Workplace Accidents
   - Equipment Misuse
   - Process Deviations / Operational Negligence

9. Legal Process Issues
   - Litigation Holds / Preservation Failures
   - Spoliation of Evidence
   - Improper Document Destruction
   - Privilege Breach (Attorney–Client / Work Product)

10. Communication-Based Issues
    - Threatening or Abusive Emails
    - Inappropriate Language / Unprofessional Communications
    - False or Misleading Statements
    - Pressure / Coercion

11. Governance & Ethical Issues
    - Ethics Violations
    - Board-Level Misconduct
    - Improper Influence
    - Failure to Report Issues
    - Unethical Decision-Making

CITATION FIDELITY REQUIREMENTS:
- When analyzing content that matches AUDIO transcriptions (source_type=audio), you MUST include the audio filename in citations.
- Audio recordings are PRIMARY EVIDENCE and must be traceable in the audit trail.
- If content appears in both audio transcriptions and text documents, PRIORITIZE citing the audio source.
- Example: If a discriminatory statement appears in "aiRwilliam.mp3" and also in "email123.txt", cite "aiRwilliam.mp3" first or exclusively.
- Pay special attention to [CITATION n] tags that show type=audio in the retrieved context below.

IMPORTANT:
- Base your analysis ONLY on the provided context.
- If something is not supported by the context, say so explicitly.
- Return your answer as valid JSON with this exact structure:
{
  "analysis": "string – narrative summary with headings like Executive Summary, Key Allegations, Risk Assessment, Recommended Next Steps",
  "issues": [
    {
      "id": "issue-1",
      "title": "short issue title",
      "description": "2–5 sentence description of the issue. Include 1–2 short direct quotes/snippets from the provided context inside this description to show the evidence.",
      "riskLevel": "Low" | "Medium" | "High" | "Unknown",
      "timeline": "short description of when this issue occurred; if unclear, say \"Timeline unclear from context.\"",
      "citations": "short references to sources used, e.g. file names",
      "partiesInvolved": "names or roles of key parties, if available",
      "keyPeople": "main individuals involved in this issue; if unclear, say there is insufficient detail",
      "categoryGroup": "one of the 11 high-level groups from the taxonomy above (e.g., 'Workplace Misconduct / HR Issues', 'Policy Violations', etc.)",
      "categoryLabel": "one specific label from within that group",
      "extraLabels": "optional comma-separated additional labels if multiple categories apply; leave empty string if only one label applies"
    }
  ]
}

BEHAVIORAL INSTRUCTIONS:
- Scan the entire provided context carefully and identify EVERY distinct issue or problematic pattern that reasonably fits any category in the taxonomy above.
- Do NOT artificially limit the number of issues. If the context supports 5, 10, or 20+ issues, return them all.
- CRITICAL: Split distinct issues into separate issue objects. Do NOT merge multiple distinct issues into one object (e.g., discrimination, retaliation, coercion should be separate if each is supported).
- CRITICAL: Do not stop after finding the most severe issues. Continue scanning systematically through ALL provided context until no additional issues can be supported.
- Review each document/excerpt multiple times to catch subtle issues (e.g., tone, implicit threats, policy violations).
- Use categoryGroup and categoryLabel based on the taxonomy above. If an issue fits multiple labels, choose the best primary one for categoryLabel and list the others in extraLabels (comma-separated).
- If no category clearly applies, set categoryGroup to "Uncategorized" and categoryLabel to "Other".
- Keep the existing fields (timeline, citations, keyPeople, partiesInvolved, etc.) populated as described.
- Do NOT include any other top-level keys besides "analysis" and "issues".
- Ensure the JSON is syntactically valid.
- Return valid JSON with analysis and issues only; no extra top-level keys.

PATTERN-TO-LABEL GUIDANCE (apply only if supported by context):
- Threats to deport / "return home" / immigration leverage → categoryLabel: "Pressure / Coercion" with extraLabels including "Hostile Work Environment" and "Non-Compliance with laws / standards / internal controls" if supported.
- Monitoring emails/communications of a protected group → categoryLabel: "Data Privacy Policy Violation" with extraLabels including "IT & Security Policy Violation" and "Discrimination" if supported.
- Pay docking / housing cost increases targeted at a group → categoryLabel: "Financial Policy / Expense Policy Violation" with extraLabels including "Discrimination" and "False Claims / Misrepresentations" if supported.
"""

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

    issues = _normalize_issue_citations(issues, sources)

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
