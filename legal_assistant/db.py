# legal_assistant/db.py
import os
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

_engine: Engine | None = None


def get_engine() -> Engine:
    """
    Lazily create and cache a single SQLAlchemy engine for SQL Server.
    We take a raw ODBC connection string from the environment and URL-encode it.
    """
    global _engine
    if _engine is not None:
        return _engine

    raw_odbc = os.getenv("SQLSERVER_ODBC_STRING")
    if not raw_odbc:
        raise RuntimeError(
            "SQLSERVER_ODBC_STRING is not set in .env "
            "(expected a plain ODBC connection string)."
        )

    # URL-encode the ODBC string for SQLAlchemy/pyodbc
    encoded = quote_plus(raw_odbc)
    conn_url = f"mssql+pyodbc:///?odbc_connect={encoded}"

    _engine = create_engine(conn_url, pool_pre_ping=True)
    return _engine
