from pathlib import Path
from typing import Optional

from pypdf import PdfReader


def extract_text_from_pdf(path: str | Path) -> Optional[str]:
    """
    Extracts text from a PDF file using pypdf.

    Returns the full text as a single string, or None if extraction fails.
    """
    pdf_path = Path(path)

    if not pdf_path.exists():
        print(f"[ERROR] PDF file does not exist: {pdf_path}")
        return None

    try:
        reader = PdfReader(str(pdf_path))
    except Exception as e:
        print(f"[ERROR] Failed to open PDF {pdf_path}: {e}")
        return None

    texts: list[str] = []
    for i, page in enumerate(reader.pages):
        try:
            page_text = page.extract_text() or ""
            texts.append(page_text)
        except Exception as e:
            print(f"[WARN] Failed to extract text from page {i} of {pdf_path}: {e}")

    full_text = "\n".join(texts).strip()
    if not full_text:
        print(f"[WARN] No text extracted from PDF: {pdf_path}")
        return None

    return full_text
