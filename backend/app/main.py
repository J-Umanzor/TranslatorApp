import base64
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import fitz
import pytesseract
from azure.ai.translation.text import TextTranslationClient
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from dotenv import load_dotenv
from pathlib import Path

from app.services.extraction import (
    extract_text,
    extract_text_from_scanned_pdf,
    is_scanned,
)
from app.services.language_detection import detect_language

# Load environment variables from backend folder
# Get the backend directory (parent of app directory)
backend_dir = Path(__file__).parent.parent
env_path = backend_dir / '.env'
load_dotenv(dotenv_path=env_path)

# Automatically detect Tesseract path on Windows if not in PATH
import os
import platform
if platform.system() == 'Windows':
    # Common installation paths for Tesseract on Windows
    possible_paths = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        r'C:\Users\{}\AppData\Local\Tesseract-OCR\tesseract.exe'.format(os.getenv('USERNAME')),
    ]
    
    # Try to find Tesseract if not in PATH
    try:
        pytesseract.get_tesseract_version()
    except:
        # Tesseract not found in PATH, try common locations
        for path in possible_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                break
        else:
            raise HTTPException(status_code=500, detail="Tesseract OCR is not installed. Please install Tesseract OCR on your system.")

app = FastAPI(title = "AI PDF Translator", description = "Translate PDF documents to any language using advanced AI technology.")

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


class ExtractResponse(BaseModel):
    pages: int
    kind: str
    text_preview: str
    language: str

class TranslateRequest(BaseModel):
    target_language: str

class TranslateResponse(BaseModel):
    pages: int
    kind: str
    original_text: str
    translated_text: str
    target_language: str 
    source_language: str
    translated_pdf_base64: Optional[str] = None

MAX_BYTES = 25 * 1024 * 1024 # 25MB

# Azure Translator configuration
AZURE_TRANSLATOR_KEY = os.getenv("AZURE_TRANSLATOR_KEY")
AZURE_TRANSLATOR_ENDPOINT = os.getenv("AZURE_TRANSLATOR_ENDPOINT")
AZURE_TRANSLATOR_REGION = os.getenv("AZURE_TRANSLATOR_REGION")

def get_translator_client():
    """Initialize and return Azure Translator client"""
    if not AZURE_TRANSLATOR_KEY or not AZURE_TRANSLATOR_ENDPOINT:
        raise HTTPException(
            status_code=500,
            detail="Azure Translator credentials not configured. Please set AZURE_TRANSLATOR_KEY, AZURE_TRANSLATOR_ENDPOINT, and AZURE_TRANSLATOR_REGION in your .env file."
        )
    
    credential = AzureKeyCredential(AZURE_TRANSLATOR_KEY)
    return TextTranslationClient(
        endpoint=AZURE_TRANSLATOR_ENDPOINT, 
        credential=credential, 
        region=AZURE_TRANSLATOR_REGION
    )

def translate_text_with_azure(
    text: str, target_language: str, client: Optional[TextTranslationClient] = None
) -> str:
    """
    Translate text using Azure Translator API.
    Handles text splitting for large texts (Azure Translator has a 50,000 character limit per request).
    """
    if not text.strip():
        return ""
    
    try:
        client = client or get_translator_client()
        
        # Azure Translator has a limit of 50,000 characters per request
        # Split text into chunks if necessary
        max_chunk_size = 45000  # Leave some buffer
        text_chunks = []
        
        if len(text) > max_chunk_size:
            # Split by sentences/paragraphs to avoid breaking words
            sentences = text.split('\n\n')  # Split by paragraphs first
            current_chunk = ""
            
            for sentence in sentences:
                if len(current_chunk) + len(sentence) + 2 > max_chunk_size:
                    if current_chunk:
                        text_chunks.append(current_chunk)
                    current_chunk = sentence
                else:
                    current_chunk += "\n\n" + sentence if current_chunk else sentence
            
            if current_chunk:
                text_chunks.append(current_chunk)
        else:
            text_chunks = [text]
        
        # Translate each chunk
        translated_parts = []
        for chunk in text_chunks:
            if not chunk.strip():
                continue
                
            # Azure Translator SDK expects a body parameter with content and to_language
            response = client.translate(
                body=[{"text": chunk}],
                to_language=[target_language]
            )
            
            # Extract translated text from response
            if response and len(response) > 0:
                for translation in response:
                    if translation.translations and len(translation.translations) > 0:
                        translated_parts.append(translation.translations[0].text)
        
        return "\n\n".join(translated_parts)
        
    except HttpResponseError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Azure Translator API error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Translation failed: {str(e)}"
        )

def translate_texts_with_azure(
    texts: List[str],
    target_language: str,
    client: Optional[TextTranslationClient] = None,
) -> List[str]:
    """Translate multiple texts while preserving their order."""
    cleaned_texts = [t if isinstance(t, str) else "" for t in texts]
    if not cleaned_texts:
        return []

    client = client or get_translator_client()
    translated: List[str] = []

    chunk_size = 50
    for start in range(0, len(cleaned_texts), chunk_size):
        chunk = cleaned_texts[start : start + chunk_size]
        body = [{"text": text} for text in chunk]
        try:
            response = client.translate(body=body, to_language=[target_language])
        except HttpResponseError as exc:
            raise HTTPException(
                status_code=500, detail=f"Azure Translator API error: {str(exc)}"
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=500, detail=f"Translation failed: {str(exc)}"
            ) from exc

        for translation_result in response:
            if (
                translation_result.translations
                and len(translation_result.translations) > 0
            ):
                translated.append(translation_result.translations[0].text)
            else:
                translated.append("")

    return translated


def translate_digital_pdf_with_layout(
    doc: fitz.Document,
    target_language: str,
    client: TextTranslationClient,
) -> tuple[str, str, Optional[str]]:
    """
    Translate digital PDF content block-by-block to preserve layout and
    produce a translated PDF encoded in base64.
    """
    pages_data: List[dict] = []
    block_texts: List[str] = []

    for page_index in range(len(doc)):
        page = doc[page_index]
        page_blocks = []
        page_dict = page.get_text("dict")

        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:
                continue

            bbox = block.get("bbox")
            if not bbox or len(bbox) != 4:
                continue

            rect = fitz.Rect(bbox)
            line_texts: List[str] = []
            font_sizes: List[float] = []

            for line in block.get("lines", []):
                span_text_parts: List[str] = []
                for span in line.get("spans", []):
                    span_text = span.get("text", "")
                    if span_text:
                        span_text_parts.append(span_text)
                        size = span.get("size")
                        if isinstance(size, (int, float)) and size > 0:
                            font_sizes.append(float(size))
                if span_text_parts:
                    line_texts.append("".join(span_text_parts))

            block_text = "\n".join(line_texts).strip()
            if not block_text:
                continue

            preferred_font_size = max(font_sizes) if font_sizes else 12.0
            page_blocks.append(
                {
                    "rect": rect,
                    "text": block_text,
                    "font_size": preferred_font_size,
                }
            )
            block_texts.append(block_text)

        pages_data.append({"rect": page.rect, "blocks": page_blocks})

    if not block_texts:
        raise HTTPException(
            status_code=400, detail="No textual content detected in the digital PDF."
        )

    translated_blocks = translate_texts_with_azure(
        block_texts, target_language, client=client
    )

    translated_doc = fitz.open()
    translated_doc.insert_pdf(doc)
    translated_text_parts: List[str] = []
    original_text_parts: List[str] = []
    block_index = 0

    for page_number, page_data in enumerate(pages_data):
        page_rect = page_data["rect"]
        new_page = translated_doc[page_number]

        for block in page_data["blocks"]:
            original_text_parts.append(block["text"])
            translated_text = translated_blocks[block_index]
            block_index += 1
            translated_text_parts.append(translated_text)

            if not translated_text.strip():
                continue

            rect = fitz.Rect(block["rect"])
            rect_with_margin = fitz.Rect(rect)
            rect_with_margin.x0 -= 1
            rect_with_margin.y0 -= 1
            rect_with_margin.x1 += 1
            rect_with_margin.y1 += 1
            rect_with_margin &= page_rect

            new_page.draw_rect(
                rect_with_margin,
                color=None,
                fill=(1, 1, 1),
                overlay=True,
            )

            base_fontsize = max(6.0, float(block.get("font_size", 12.0)))
            max_fontsize = base_fontsize

            def wrap_text(
                text: str,
                font_size: float,
                max_width: float,
            ) -> List[str]:
                if not text:
                    return [""]

                lines: List[str] = []
                for raw_line in text.splitlines() or [""]:
                    line = raw_line.strip()
                    if not line:
                        lines.append("")
                        continue

                    words = line.split(" ")
                    current = ""
                    for word in words:
                        candidate = f"{current} {word}".strip() if current else word
                        length = fitz.get_text_length(
                            candidate, fontname="helv", fontsize=font_size
                        )
                        if length <= max_width or not current:
                            current = candidate
                        else:
                            if current:
                                lines.append(current)
                            current = word
                    if current:
                        lines.append(current)

                if not lines:
                    lines.append("")

                # Handle languages without spaces by splitting characters when needed
                wrapped: List[str] = []
                for line in lines:
                    if (
                        fitz.get_text_length(
                            line, fontname="helv", fontsize=font_size
                        )
                        <= max_width
                    ):
                        wrapped.append(line)
                        continue

                    buffer = ""
                    for ch in line:
                        candidate = buffer + ch
                        length = fitz.get_text_length(
                            candidate, fontname="helv", fontsize=font_size
                        )
                        if length <= max_width or not buffer:
                            buffer = candidate
                        else:
                            wrapped.append(buffer)
                            buffer = ch
                    if buffer:
                        wrapped.append(buffer)

                return wrapped

            max_width = rect_with_margin.width
            max_height = rect_with_margin.height

            for attempt in range(6):
                font_size = max(6.0, base_fontsize * (0.9**attempt))
                lines = wrap_text(translated_text, font_size, max_width)
                line_height = font_size * 1.25
                required_height = line_height * max(1, len(lines))

                if required_height <= max_height or attempt == 5:
                    current_y = rect_with_margin.y0 + font_size
                    for line in lines:
                        if current_y > rect_with_margin.y1:
                            break
                        new_page.insert_text(
                            fitz.Point(rect_with_margin.x0, current_y),
                            line,
                            fontname="helv",
                            fontsize=font_size,
                            color=(0, 0, 0),
                        )
                        current_y += line_height
                    break

            else:
                fallback_rect = fitz.Rect(
                    page_rect.x0 + 36,
                    max(page_rect.y0 + 36, rect_with_margin.y0),
                    page_rect.x1 - 36,
                    page_rect.y1 - 36,
                )
                fallback_lines = wrap_text(translated_text, 9.0, fallback_rect.width)
                current_y = fallback_rect.y0 + 9.0
                line_height = 9.0 * 1.25
                for line in fallback_lines:
                    if current_y > fallback_rect.y1:
                        break
                    new_page.insert_text(
                        fitz.Point(fallback_rect.x0, current_y),
                        line,
                        fontname="helv",
                        fontsize=9.0,
                        color=(0, 0, 0),
                    )
                    current_y += line_height

    pdf_bytes = translated_doc.tobytes()
    translated_doc.close()

    translated_pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
    original_full_text = "\n\n".join(original_text_parts)
    translated_full_text = "\n\n".join(translated_text_parts)

    return original_full_text, translated_full_text, translated_pdf_base64

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
                        text_preview="No text could be extracted from the scanned PDF. Please ensure the PDF contains clear, readable images.",
                        language="unknown",
                    )
            else:
                text = extract_text(doc, max_chars=10000)

            language = detect_language(text)
            return ExtractResponse(
                pages=len(doc),
                kind="scanned" if scanned else "digital",
                text_preview=text[:1000],
                language=language if language else "unknown",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process PDF: {e}")


@app.post("/translate", response_model=TranslateResponse)
async def translate(
    file: UploadFile = File(...),
    target_language: str = Form(...)
):
    """
    Extract text from PDF (digital or scanned) and translate it to the target language.
    """
    # Check if file is a PDF
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Invalid file type, Please upload a PDF file")

    data = await file.read()
    # Check if file is empty
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="File is empty")
    # Check if file is too large
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="File is too large max (25MB)")

    # Validate target language
    if not target_language or not target_language.strip():
        raise HTTPException(status_code=400, detail="Target language is required")

    try:
        with fitz.open(stream=data, filetype="pdf") as doc:
            scanned = is_scanned(doc)
            target_language_clean = target_language.strip()
            client = get_translator_client()
            
            # Extract text based on document type
            if scanned:
                # Perform OCR on scanned PDF
                original_text = extract_text_from_scanned_pdf(doc, max_chars=50000)  # Increased limit for full translation
                if not original_text.strip():
                    raise HTTPException(
                        status_code=400,
                        detail="No text could be extracted from the scanned PDF. Please ensure the PDF contains clear, readable images."
                    )
                translated_text = translate_text_with_azure(
                    original_text, target_language_clean, client=client
                )
                translated_pdf_base64 = None
            else:
                # Extract text from digital PDF
                (
                    original_text,
                    translated_text,
                    translated_pdf_base64,
                ) = translate_digital_pdf_with_layout(
                    doc, target_language_clean, client=client
                )
                if not original_text.strip():
                    raise HTTPException(
                        status_code=400,
                        detail="No text could be extracted from the PDF."
                    )
            
            source_language = detect_language(original_text)
            
            return TranslateResponse(
                pages=len(doc),
                kind="scanned" if scanned else "digital",
                original_text=original_text,
                translated_text=translated_text,
                target_language=target_language_clean,
                source_language=source_language if source_language else "unknown",
                translated_pdf_base64=translated_pdf_base64,
            )
            
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}") 