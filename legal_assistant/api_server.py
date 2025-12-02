# api_server.py
import json
from typing import List

from fastapi import FastAPI, UploadFile, File, Form
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
    This is the endpoint your React UI will call.

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

    # 3) Ingest uploaded files into the vector store (Step 2 you already created)
    ingest_uploaded_files_into_vector_store(file_payloads)

    # 4) Run RAG case analysis using your existing function in rag.py
    filenames = [name for name, _ in file_payloads]
    result = analyze_legal_case(metadata=meta, filenames=filenames)

    # 5) Return what the React UI expects
    return {
        "analysis": result.get("analysis", ""),
        "issues": result.get("issues", []),
    }
