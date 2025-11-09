from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import fitz

from .config import MAX_BYTES, configure_tesseract
from .models import ExtractResponse
from .services.extraction import (
    extract_text,
    extract_text_from_scanned_pdf,
    is_scanned,
)
from .services.language_detection import detect_language

configure_tesseract()

app = FastAPI(
    title="AI PDF Translator",
    description="Translate PDF documents to any language using advanced AI technology.",
)

# we will allow local dev from next.js at localhost:3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/extract", response_model=ExtractResponse)

async def extract(file: UploadFile = File(...)):
    #check if file is a pdf
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Invalid file type, Please upload a PDF file")

    data = await file.read()
    #check if file is empty
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="File is empty")
    #check if file is too large 
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="File is too large max (25MB)")

    try:
        with fitz.open(stream=data, filetype="pdf") as doc:
            scanned = is_scanned(doc)

            if scanned: 
                # Perform OCR on scanned PDF
                text = extract_text_from_scanned_pdf(doc, max_chars=10000)
                if not text.strip():
                    return ExtractResponse(
                        pages=len(doc),
                        kind="scanned",
                        language="unknown",
                        text_preview="No text could be extracted from the scanned PDF. Please ensure the PDF contains clear, readable images."
                    )
                language = detect_language(text)
                return ExtractResponse(
                    pages=len(doc),
                    kind="scanned",
                    language=language,
                    text_preview=text[:1000]
                )
            text = extract_text(doc, max_chars=10000)
            language = detect_language(text)
            return ExtractResponse(
                pages=len(doc),
                kind="digital",
                language=language,
                text_preview=text[:1000]
            )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process PDF: {e}") 