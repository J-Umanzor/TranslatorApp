import io
from typing import List

import fitz
import pytesseract
from fastapi import HTTPException
from PIL import Image


def is_scanned(doc: fitz.Document, sample_pages: int = 3) -> bool:
    pages_to_check = min(sample_pages, len(doc))
    for i in range(pages_to_check):
        text = doc[i].get_text("text").strip()
        if text:
            return False
    return True


def extract_text(doc: fitz.Document, max_chars: int = 10000) -> str:
    parts: List[str] = []
    total = 0
    for page in doc:
        page_text = page.get_text("text")
        if not page_text:
            continue
        parts.append(page_text)
        total += len(page_text)
        if total >= max_chars:
            break
    return "".join(parts)


def extract_text_from_scanned_pdf(
    doc: fitz.Document, max_chars: int = 10000, max_pages: int = 10
) -> str:
    parts: List[str] = []
    total = 0
    pages_to_process = min(len(doc), max_pages)

    for page_num in range(pages_to_process):
        page = doc[page_num]
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat)

        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))

        try:
            page_text = pytesseract.image_to_string(img)

            if page_text.strip():
                parts.append(page_text)
                total += len(page_text)

                if total >= max_chars:
                    break
        except pytesseract.TesseractNotFoundError as exc:
            raise HTTPException(
                status_code=500,
                detail="Tesseract OCR is not installed. Please install Tesseract OCR on your system.",
            ) from exc
        except Exception as exc:
            print(f"OCR failed for page {page_num + 1}: {exc}")
            continue

    return "\n\n".join(parts)

