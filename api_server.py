# api_server.py
import json
from typing import List, Tuple, Dict
# from openai import OpenAI

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from rag_answer import analyze_legal_case, answer_question
from legal_assistant.retrieval.ingest_uploaded import (
    ingest_uploaded_files_into_vector_store,
)
from legal_assistant.utils.universal_extraction import (
    extract_text_from_upload,
    ExtractedText,
)
from legal_assistant.relevance_logger import (
    log_relevance_decision,
    log_llm_error,
)
from legal_assistant.llm import ModelSelector

# --- OpenAI client setup (lazy)
import os
from openai import AzureOpenAI
from legal_assistant.config import get_settings

# NEW: SQL imports
from legal_assistant.db import get_engine
from sqlalchemy import text as sql_text

app = FastAPI()


# Simple selector instance for lightweight chat usage
_selector: ModelSelector | None = None


def get_selector() -> ModelSelector:
    global _selector
    if _selector is None:
        _selector = ModelSelector()
    return _selector


class QARequest(BaseModel):
    question: str
    history: List[Dict[str, str]] = []  # [{role: "user" | "assistant", content: "..."}]


def get_azure_client():
    """
    Lazily create and cache a single AzureOpenAI client.

    We read values from environment variables first (OPENAI_BASE_URL, OPENAI_API_KEY,
    OPENAI_API_VERSION) and fall back to the Settings object if present.
    """
    if not hasattr(get_azure_client, "_client"):
        settings = get_settings()  # still load .env the same way

        # 1) Try env vars first (matches your .env exactly)
        base_url = os.getenv("OPENAI_BASE_URL")
        api_key = os.getenv("OPENAI_API_KEY")
        api_version = os.getenv("OPENAI_API_VERSION")

        # 2) Fallback to attributes on settings (in case config uses different names)
        if not base_url:
            base_url = (
                getattr(settings, "OPENAI_BASE_URL", None)
                or getattr(settings, "openai_base_url", None)
            )
        if not api_key:
            api_key = (
                getattr(settings, "OPENAI_API_KEY", None)
                or getattr(settings, "openai_api_key", None)
            )
        if not api_version:
            api_version = (
                getattr(settings, "OPENAI_API_VERSION", None)
                or getattr(settings, "openai_api_version", None)
            )

        if not base_url or not api_key or not api_version:
            # Clear, explicit error instead of silent crash
            raise RuntimeError(
                "Azure OpenAI environment is not fully configured. "
                "Make sure OPENAI_BASE_URL, OPENAI_API_KEY, and OPENAI_API_VERSION "
                "are set in your .env (and that uvicorn is started from the project root)."
            )

        get_azure_client._client = AzureOpenAI(
            azure_endpoint=base_url,
            api_key=api_key,
            api_version=api_version,
        )

    return get_azure_client._client


def require_azure_client_and_settings():
    """Shared helper to fetch the Azure client and settings with clear errors."""
    try:
        client = get_azure_client()
        settings = get_settings()
        env_model = os.getenv("OPENAI_CHAT_MODEL")
        model_name = env_model or getattr(settings, "OPENAI_CHAT_MODEL", None) or getattr(settings, "chat_model", None)
        if not model_name:
            raise RuntimeError("OPENAI_CHAT_MODEL is not configured")
        return client, model_name
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Azure OpenAI configuration error: {str(e)}",
        )


# Allow your React app (localhost:3000) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------------------------------------------
# Existing endpoint: main case analysis (RAG + issues)
# -------------------------------------------------------------------
@app.post("/api/analyze-case")
async def analyze_case_endpoint(
    files: List[UploadFile] = File(...),
    metadata: str = Form(...),
):
    """
    This is the endpoint your React UI will call for the main analysis.

    It expects:
      - `files`: uploaded PDF/TXT/EML documents
      - `metadata`: JSON string with:
          {
            "matterOverview": "...",
            "peopleAndAliases": "...",
            "noteworthyOrganizations": "...",
            "noteworthyTerms": "...",
            "additionalContext": "..."
          }
    """
    # 1) Parse metadata from the form
    try:
        meta = json.loads(metadata)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid metadata JSON")

    # 2) Read file contents into memory
    file_payloads: List[Tuple[str, bytes]] = []
    for f in files:
        content = await f.read()
        file_payloads.append((f.filename, content))

    # 3) Ingest uploaded files into the vector store
    #    (this is your existing RAG ingestion)
    ingest_uploaded_files_into_vector_store(file_payloads)

    # 4) Run RAG case analysis using your existing function in rag.py
    filenames = [name for name, _ in file_payloads]
    result = analyze_legal_case(metadata=meta, filenames=filenames)

    # Debug logging
    sources = result.get("sources", [])
    print(f"[DEBUG] Total sources: {len(sources)}")
    audio_sources = [s for s in sources if s.get('file', '').endswith(('.mp3', '.wav', '.m4a'))]
    print(f"[DEBUG] Audio sources: {len(audio_sources)}")
    if audio_sources:
        for a in audio_sources[:3]:
            print(f"[DEBUG] Audio: {a.get('file')} (score: {a.get('score', 0):.4f})")
    else:
        print("[DEBUG] NO AUDIO SOURCES IN RETRIEVAL RESULTS!")
    
    # 5) Return what the React UI expects (including sources for citation tracking)
    return {
        "analysis": result.get("analysis", ""),
        "issues": result.get("issues", []),
        "sources": result.get("sources", []),
    }


# -------------------------------------------------------------------
# NEW endpoint: relevance check
# -------------------------------------------------------------------
@app.post("/api/relevance-check")
async def relevance_check_endpoint(
    criteria: str = Form(None),
    metadata: str = Form(None),
    files: List[UploadFile] = File(...),
):
    """
    Given relevance criteria text and uploaded files, classify each file as:
    - highly_relevant
    - partially_relevant
    - less_relevant
    - not_relevant
    - failed (if unreadable)

    For each non-failed file, we ask the LLM to:
      - summarize the document (2–3 lines, email-style)
      - explain WHY it is categorized that way
      - return a few short snippets that support the decision

    Every decision is also logged into SQL Server (dbo.RelevanceDecisions).
    """
    meta_obj = None
    if metadata:
        try:
            meta_obj = json.loads(metadata)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid metadata JSON")

    criteria_text = (criteria or "").strip()
    if not criteria_text and meta_obj:
        criteria_text = (meta_obj.get("matterOverview") or "").strip()

    if not criteria_text:
        raise HTTPException(status_code=400, detail="Criteria is required (case summary)")

    # Ensure Azure client + settings are available
    client, model_name = require_azure_client_and_settings()

    highly_relevant = []
    partially_relevant = []
    less_relevant = []
    not_relevant = []
    failed_docs = []

    for upload in files:
        raw_bytes = await upload.read()

        # Use universal extraction for all file types
        extracted: ExtractedText = extract_text_from_upload(upload.filename, raw_bytes)
        
        if extracted.error:
            reason = f"Extraction failed: {extracted.error}"
            failed_docs.append(
                {
                    "name": upload.filename,
                    "reason": reason,
                }
            )

            # Log FAILED to SQL (label = 4)
            try:
                engine = get_engine()
                with engine.begin() as conn:
                    conn.execute(
                        sql_text(
                            """
                            INSERT INTO dbo.RelevanceDecisions
                                (FileName, Criteria, EmailBody, RelevanceLabel, Citation)
                            VALUES
                                (:file_name, :criteria, :email_body, :label, :citation)
                            """
                        ),
                        {
                            "file_name": upload.filename,
                            "criteria": criteria_text,
                            "email_body": None,
                            "label": 4,
                            "citation": reason,
                        },
                    )
            except Exception as db_err:
                print(f"[WARN] Failed to log extraction error for {upload.filename}: {db_err}")

            continue

        trimmed = extracted.text.strip()
        if not trimmed:
            reason = "File appears to be empty or contains no readable text."
            failed_docs.append(
                {
                    "name": upload.filename,
                    "reason": reason,
                }
            )

            # Log FAILED to SQL (label = 4)
            try:
                engine = get_engine()
                with engine.begin() as conn:
                    conn.execute(
                        sql_text(
                            """
                            INSERT INTO dbo.RelevanceDecisions
                                (FileName, Criteria, EmailBody, RelevanceLabel, Citation)
                            VALUES
                                (:file_name, :criteria, :email_body, :label, :citation)
                            """
                        ),
                        {
                            "file_name": upload.filename,
                            "criteria": criteria_text,
                            "email_body": None,
                            "label": 4,
                            "citation": reason,
                        },
                    )
            except Exception as db_err:
                print(f"[WARN] Failed to log EMPTY file for {upload.filename}: {db_err}")

            continue

        # Truncate if huge so prompt stays manageable
        truncated_text = trimmed[:12000]

        prompt = f"""
You are assisting a legal analyst.

Your task:
1. Read the relevance criteria.
2. Read the document text.
3. Decide whether the document is HIGHLY_RELEVANT, PARTIALLY_RELEVANT, LESS_RELEVANT, or NOT_RELEVANT to the criteria. If the document is malformed/unreadable, mark it as FAILED.
4. Produce an email-style summary and a clear explanation.

Relevance criteria:
\"\"\"{criteria_text}\"\"\"

Document text:
\"\"\"{truncated_text}\"\"\"

Return ONLY a JSON object with the following fields:
- "category": one of "highly_relevant", "partially_relevant", "less_relevant", "not_relevant", "failed"
- "summary": 2-3 sentence email-style summary of the document
- "reason": short explanation of WHY it is categorized this way (or why it failed)
- "snippets": an array of 1-3 short text snippets from the document that best support your decision (can be empty if failed)
"""

        try:
            completion = client.chat.completions.create(
                model=model_name,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": "You are a careful legal assistant. Always follow the JSON schema exactly.",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
            )

            content = completion.choices[0].message.content
            parsed = json.loads(content)

            category = (parsed.get("category") or "").lower()
            doc = {
                "name": upload.filename,
                "summary": (parsed.get("summary") or "").strip(),
                "reason": (parsed.get("reason") or "").strip(),
                "snippets": parsed.get("snippets") or [],
            }

            # Map category → numeric label
            if category == "highly_relevant":
                label = 3
                highly_relevant.append(doc)
            elif category == "partially_relevant":
                label = 2
                partially_relevant.append(doc)
            elif category == "less_relevant":
                label = 1
                less_relevant.append(doc)
            elif category == "not_relevant":
                label = 0
                not_relevant.append(doc)
            else:
                label = 4
                failed_docs.append(
                    {
                        "name": upload.filename,
                        "reason": doc["reason"]
                        or "Model could not confidently classify this document.",
                    }
                )

            # --- Log decision into SQL Server ---
            try:
                engine = get_engine()
                with engine.begin() as conn:
                    conn.execute(
                        sql_text(
                            """
                            INSERT INTO dbo.RelevanceDecisions
                                (FileName, Criteria, EmailBody, RelevanceLabel, Citation)
                            VALUES
                                (:file_name, :criteria, :email_body, :label, :citation)
                            """
                        ),
                        {
                            "file_name": upload.filename,
                            "criteria": criteria_text,
                            "email_body": truncated_text,  # decoded body
                            "label": label,                # 0 / 1 / 2 / 3 / 4
                            "citation": doc["reason"],     # explanation from model
                        },
                    )
            except Exception as db_err:
                print(f"[WARN] Failed to log relevance decision for {upload.filename}: {db_err}")

        except Exception as e:
            reason = f"Error while analyzing document with LLM: {str(e)}"
            failed_docs.append(
                {
                    "name": upload.filename,
                    "reason": reason,
                }
            )

            # Log FAILED LLM error to SQL (label = 4)
            try:
                engine = get_engine()
                with engine.begin() as conn:
                    conn.execute(
                        sql_text(
                            """
                            INSERT INTO dbo.RelevanceDecisions
                                (FileName, Criteria, EmailBody, RelevanceLabel, Citation)
                            VALUES
                                (:file_name, :criteria, :email_body, :label, :citation)
                            """
                        ),
                        {
                            "file_name": upload.filename,
                            "criteria": criteria_text,
                            "email_body": truncated_text if 'truncated_text' in locals() else None,
                            "label": 4,
                            "citation": reason,
                        },
                    )
            except Exception as db_err:
                print(f"[WARN] Failed to log LLM error for {upload.filename}: {db_err}")

    return {
        "highlyRelevant": highly_relevant,
        "partiallyRelevant": partially_relevant,
        "lessRelevant": less_relevant,
        "notRelevant": not_relevant,
        "failed": failed_docs,
    }


# -------------------------------------------------------------------
# NEW endpoint: ask questions over uploaded files
# -------------------------------------------------------------------
@app.post("/api/ask-question")
async def ask_question_endpoint(
    question: str = Form(...),
    metadata: str = Form(None),
    files: List[UploadFile] = File(...),
):
    """
    Given a natural-language question and uploaded files, return an LLM answer.

    Reuses the same file handling pattern as the relevance endpoint:
      - decode uploaded files as UTF-8 text
      - skip empty/unreadable files
      - truncate each document to keep prompt size manageable
    """
    q = (question or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="Question is required")

    meta_obj = None
    if metadata:
        try:
            meta_obj = json.loads(metadata)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid metadata JSON")

    client, model_name = require_azure_client_and_settings()

    doc_chunks: List[str] = []
    failed_docs: List[dict] = []

    for upload in files:
        raw_bytes = await upload.read()
        
        # Use universal extraction for all file types
        extracted: ExtractedText = extract_text_from_upload(upload.filename, raw_bytes)
        
        if extracted.error:
            failed_docs.append({"name": upload.filename, "reason": f"Extraction failed: {extracted.error}"})
            continue

        trimmed = extracted.text.strip()
        if not trimmed:
            failed_docs.append({"name": upload.filename, "reason": "File appears to be empty."})
            continue

        snippet = trimmed[:4000]
        doc_chunks.append(f"File: {upload.filename}\n{snippet}")

    # Cap total context to avoid overly long prompts
    combined_docs = "\n\n".join(doc_chunks)[:16000] if doc_chunks else "No readable documents were provided."

    meta_context = ""
    if meta_obj:
        meta_context = f"\n\nAdditional context from metadata:\n{json.dumps(meta_obj, indent=2)}"

    prompt = f"""
You are assisting a legal analyst. Answer the user's question using ONLY the provided document excerpts. If the answer is uncertain, say so.

User question:
\"\"\"{q}\"\"\"

Document excerpts:
\"\"\"{combined_docs}\"\"\"{meta_context}
"""

    try:
        completion = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "system",
                    "content": "You are a careful legal assistant. Base answers only on provided documents and clearly note if information is missing.",
                },
                {"role": "user", "content": prompt},
            ],
        )

        answer = completion.choices[0].message.content or ""
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error while answering question: {str(e)}")

    return {
        "answer": answer.strip(),
        "failed": failed_docs,
    }


@app.post("/api/ask")
async def ask_conversational_endpoint(payload: QARequest):
    """
    Conversational RAG endpoint.
    Uses previous Q&A (history) to interpret the new question.
    """
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Question is required")

    answer = answer_question(
        question=payload.question,
        history=payload.history,
        top_k=10,
    )

    return answer



@app.post("/api/chat")
async def chat_endpoint(
    provider: str = Form("openai"),
    system_prompt: str = Form(""),
    user_prompt: str = Form(""),
    prompt: str = Form(""),
    model: str | None = Form(None),
):
    """Lightweight chat endpoint that routes to configured model providers.

    Expects form-encoded fields; returns JSON {"text": "..."}.
    """

    # Lazy selector (keeps previous behavior isolated)
    global _selector
    try:
        if _selector is None:
            _selector = ModelSelector()
    except Exception:
        # If ModelSelector creation fails, return a clear error
        raise HTTPException(status_code=500, detail="Model selector initialization failed")

    try:
        out = _selector.generate(
            provider=provider,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            prompt=prompt,
            model=model,
        )
        return {"text": out}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
