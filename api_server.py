import json
from typing import List

from fastapi import FastAPI, UploadFile, File, Form, HTTPException

from fastapi.middleware.cors import CORSMiddleware
from case_history import (
    init_case_history_db,
    save_case,
    list_cases,
    get_case,
)

from rag_answer import analyze_legal_case
from legal_assistant.retrieval.ingest_uploaded import (
    ingest_uploaded_files_into_vector_store,
)

app = FastAPI()
# Initialise SQLite for case history
init_case_history_db()

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
    Endpoint that your React UI will call.
    """
    # 1) Parse metadata from form (JSON string -> dict)
    meta = json.loads(metadata)

    # 2) Read uploaded file contents
    file_payloads = []
    for f in files:
        content = await f.read()
        file_payloads.append((f.filename, content))

    # 3) Ingest uploads into the vector store
    ingest_uploaded_files_into_vector_store(file_payloads)

    # 4) Run RAG analysis
    filenames = [name for name, _ in file_payloads]
    result = analyze_legal_case(metadata=meta, filenames=filenames)

    analysis_text = result.get("analysis", "")
    issues_list = result.get("issues", [])
    if not isinstance(issues_list, list):
        issues_list = []

    # 5) Save this case into SQLite history
    case_id = save_case(
        metadata=meta,
        filenames=filenames,
        analysis=analysis_text,
        issues=issues_list,
    )

    # 6) Return what the frontend expects (plus caseId)
    return {
        "caseId": case_id,
        "analysis": analysis_text,
        "issues": issues_list,
    }

@app.get("/api/cases")
async def list_cases_endpoint(limit: int = 50):
    cases = list_cases(limit=limit)
    return {"cases": cases}


@app.get("/api/cases/{case_id}")
async def get_case_endpoint(case_id: int):
    case = get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case
