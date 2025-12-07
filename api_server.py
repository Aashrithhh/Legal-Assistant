# api_server.py
import json
from typing import List, Tuple
# from openai import OpenAI

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from rag_answer import analyze_legal_case
from legal_assistant.retrieval.ingest_uploaded import (
    ingest_uploaded_files_into_vector_store,
)
from legal_assistant.relevance_logger import (
    log_relevance_decision,
    log_llm_error,
)

# --- Azure OpenAI setup (lazy) ---
import os
from openai import AzureOpenAI
from legal_assistant.config import get_settings

# NEW: SQL imports
from legal_assistant.db import get_engine
from sqlalchemy import text as sql_text

app = FastAPI()


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


# Allow your React app (localhost:3000) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
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

    # 5) Return what the React UI expects
    return {
        "analysis": result.get("analysis", ""),
        "issues": result.get("issues", []),
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
    try:
        client = get_azure_client()
        settings = get_settings()
        model_name = getattr(settings, "OPENAI_CHAT_MODEL", "gpt-5-chat")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Azure OpenAI configuration error: {str(e)}",
        )

    highly_relevant = []
    partially_relevant = []
    less_relevant = []
    not_relevant = []
    failed_docs = []

    for upload in files:
        raw_bytes = await upload.read()

        # Try to decode as UTF-8 text (works for your .txt email files)
        try:
            text = raw_bytes.decode("utf-8", errors="ignore")
        except Exception:
            reason = "Unable to decode file as text (unsupported encoding or binary format)."
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
                print(f"[WARN] Failed to log FAILED decode for {upload.filename}: {db_err}")

            continue

        trimmed = text.strip()
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
