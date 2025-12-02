# legal_assistant/utils/eml_extraction.py
from __future__ import annotations

from email import policy
from email.parser import BytesParser
from html import unescape
from pathlib import Path
import re
from typing import Dict, Any, Optional


def _strip_html(html: str) -> str:
    """Very lightweight HTML → plain text conversion."""
    text = unescape(html)
    # remove script/style blocks
    text = re.sub(r"(?is)<(script|style).*?>.*?(</\1>)", "", text)
    # remove all tags
    text = re.sub(r"(?s)<.*?>", " ", text)
    # normalize whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_eml_bytes(data: bytes) -> Dict[str, Any]:
    """
    Parse raw .eml bytes and return a dict:
    {
      "from": str,
      "to": str,
      "subject": str,
      "date": str,
      "body": str,
    }
    """
    msg = BytesParser(policy=policy.default).parsebytes(data)

    from_ = msg.get("from", "") or ""
    to = msg.get("to", "") or ""
    subject = msg.get("subject", "") or ""
    date = msg.get("date", "") or ""

    body_parts: list[str] = []
    html_candidate: Optional[str] = None

    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = part.get_content_disposition()
            if disp == "attachment":
                continue

            try:
                content = part.get_content()
            except Exception:
                continue

            if ctype == "text/plain":
                body_parts.append(str(content))
            elif ctype == "text/html" and html_candidate is None:
                html_candidate = _strip_html(str(content))
    else:
        ctype = msg.get_content_type()
        try:
            content = msg.get_content()
        except Exception:
            content = ""
        if ctype == "text/plain":
            body_parts.append(str(content))
        elif ctype == "text/html":
            body_parts.append(_strip_html(str(content)))

    if not body_parts and html_candidate:
        body_parts.append(html_candidate)

    body_text = "\n".join(p for p in body_parts if p).strip()

    return {
        "from": from_,
        "to": to,
        "subject": subject,
        "date": date,
        "body": body_text,
    }


def extract_eml(path: str | Path) -> Optional[Dict[str, Any]]:
    """
    Public function used by ingest_eml_corpus.

    Returns None if the file cannot be parsed or has no meaningful body.
    """
    path = Path(path)
    try:
        data = path.read_bytes()
    except Exception as e:
        print(f"[ERROR] Failed to read EML file {path}: {e}")
        return None

    eml_data = _parse_eml_bytes(data)

    # If there is literally no body and no subject, treat as empty
    if not (eml_data["subject"].strip() or eml_data["body"].strip()):
        return None

    return eml_data


def extract_eml_from_bytes(data: bytes) -> Optional[Dict[str, Any]]:
    """
    Variant for API uploads (when you already have bytes, not a file path).
    """
    eml_data = _parse_eml_bytes(data)
    if not (eml_data["subject"].strip() or eml_data["body"].strip()):
        return None
    return eml_data
