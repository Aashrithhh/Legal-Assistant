# legal_assistant/relevance_logger.py

import os
from typing import Optional

from sqlalchemy import create_engine, text

# Cache globals so we don't recreate engine every time
_engine = None
_conn_str: Optional[str] = None


def _get_conn_str() -> str:
    """
    Read SQL Server connection string from env.
    Uses SQLSERVER_CONN_STR in your .env.
    """
    global _conn_str
    if _conn_str:
        return _conn_str

    conn = os.getenv("SQLSERVER_CONN_STR")
    if not conn:
        raise RuntimeError("SQLSERVER_CONN_STR is not set in the .env")

    _conn_str = conn
    return conn


def _get_engine():
    global _engine
    if _engine is not None:
        return _engine

    conn_str = _get_conn_str()
    _engine = create_engine(conn_str, pool_pre_ping=True)
    return _engine


def _ensure_table():
    """
    Make sure dbo.RelevanceDecisions exists.
    """
    engine = _get_engine()
    ddl = """
    IF NOT EXISTS (
        SELECT * FROM sys.objects
        WHERE name = 'RelevanceDecisions' AND type = 'U'
    )
    BEGIN
        CREATE TABLE dbo.RelevanceDecisions (
            Id INT IDENTITY(1,1) PRIMARY KEY,
            FileName NVARCHAR(255) NOT NULL,
            Criteria NVARCHAR(MAX) NULL,
            EmailBody NVARCHAR(MAX) NULL,
            RelevanceLabel TINYINT NOT NULL, -- 0 = non-relevant, 1 = relevant, 3 = failed
            Citation NVARCHAR(MAX) NULL,
            CreatedAt DATETIME2 NOT NULL DEFAULT SYSDATETIME()
        );
    END;
    """
    with engine.begin() as conn:
        conn.exec_driver_sql(ddl)


def log_relevance_decision(
    file_name: str,
    criteria: str,
    email_body: str,
    label: int,
    citation: str,
) -> None:
    """
    Write a normal relevance decision row.
    label: 0 = non-relevant, 1 = relevant, 3 = failed.
    """
    try:
        _ensure_table()
        engine = _get_engine()

        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO dbo.RelevanceDecisions
                        (FileName, Criteria, EmailBody, RelevanceLabel, Citation)
                    VALUES
                        (:file_name, :criteria, :email_body, :label, :citation)
                    """
                ),
                {
                    "file_name": file_name,
                    "criteria": criteria,
                    "email_body": email_body,
                    "label": int(label),
                    "citation": citation,
                },
            )
    except Exception as e:
        print(f"[WARN] Failed to log relevance decision for {file_name}: {e}")


def log_llm_error(
    file_name: str,
    criteria: str,
    email_body: str,
    error_message: str,
) -> None:
    """
    Convenience helper: store LLM failures as label=3.
    """
    try:
        log_relevance_decision(
            file_name=file_name,
            criteria=criteria,
            email_body=email_body,
            label=3,
            citation=f"LLM error: {error_message}",
        )
    except Exception as e:
        print(f"[WARN] Failed to log LLM error for {file_name}: {e}")
