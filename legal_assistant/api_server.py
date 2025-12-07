# api_server.py
import json
from typing import List

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from rag import analyze_legal_case
from legal_assistant.retrieval.ingest_uploaded import (
    ingest_uploaded_files_into_vector_store,
)

app = FastAPI()

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


@app.post("/api/analyze-case")
async def analyze_case_endpoint(
    files: List[UploadFile] = File(...),
    metadata: str = Form(...),
):
    """
    This is the endpoint your React UI will call for the main case summary.

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
    meta = json.loads(metadata)

    # 2) Read file contents into memory
    file_payloads = []
    for f in files:
        content = await f.read()
        file_payloads.append((f.filename, content))

    # 3) Ingest uploaded files into the vector store
    ingest_uploaded_files_into_vector_store(file_payloads)

    # 4) Run RAG case analysis using your existing function in rag.py
    filenames = [name for name, _ in file_payloads]
    result = analyze_legal_case(metadata=meta, filenames=filenames)

    # 5) Return what the React UI expects
    return {
        "analysis": result.get("analysis", ""),
        "issues": result.get("issues", []),
    }


# =========================
#  Relevance Check Helpers
# =========================

def simple_relevance_classification(doc_text: str, criteria: str) -> tuple[str, str]:
    """
    Super-simple placeholder classifier.

    Returns: (category, explanation)
      category: 'relevant' | 'non_relevant'
    """
    text_lower = doc_text.lower()
    crit_lower = criteria.lower()

    if crit_lower in text_lower:
        return (
            "relevant",
            f"This document contains content that directly mentions or matches the criteria: {criteria}.",
        )
    else:
        return (
            "non_relevant",
            f"This document does not appear to contain information directly related to the criteria: {criteria}.",
        )


# =========================
#    Relevance Check API
# =========================

@app.post("/api/relevance-check")
async def relevance_check_endpoint(
    criteria: str = Form(...),
    files: List[UploadFile] = File(...),
):
    """
    Endpoint for the Relevance page.

    Input:
      - criteria: text from the Relevance Criteria box
      - files: same uploaded documents

    Output JSON shape (matches React state):
      {
        "relevant":    [{ "name": str, "summary": str }],
        "nonRelevant": [{ "name": str, "summary": str }],
        "failed":      [{ "name": str, "reason": str }]
      }
    """

    if not criteria.strip():
        raise HTTPException(status_code=400, detail="Relevance criteria is required.")

    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required.")

    relevant: List[dict] = []
    non_relevant: List[dict] = []
    failed: List[dict] = []

    for f in files:
        try:
            content_bytes = await f.read()

            if not content_bytes:
                failed.append(
                    {
                        "name": f.filename,
                        "reason": "File is empty or could not be read.",
                    }
                )
                continue

            # Basic text extraction for now.
            try:
                text = content_bytes.decode("utf-8", errors="ignore")
            except Exception:
                text = ""

            if not text.strip():
                failed.append(
                    {
                        "name": f.filename,
                        "reason": (
                            "Could not extract readable text. The file may be scanned, "
                            "image-only, or in an unsupported format."
                        ),
                    }
                )
                continue

            category, explanation = simple_relevance_classification(text, criteria)

            if category == "relevant":
                relevant.append(
                    {
                        "name": f.filename,
                        "summary": explanation,
                    }
                )
            elif category == "non_relevant":
                non_relevant.append(
                    {
                        "name": f.filename,
                        "summary": explanation,
                    }
                )

        except Exception as exc:
            failed.append(
                {
                    "name": f.filename,
                    "reason": f"Unexpected error processing file: {exc}",
                }
            )

    return {
        "relevant": relevant,
        "nonRelevant": non_relevant,
        "failed": failed,
    }
