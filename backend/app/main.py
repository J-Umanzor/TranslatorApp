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

def translate_text_with_azure(text: str, target_language: str) -> str:
    """
    Translate text using Azure Translator API.
    Handles text splitting for large texts (Azure Translator has a 50,000 character limit per request).
    """
    if not text.strip():
        return ""
    
    try:
        client = get_translator_client()
        
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
            
            # Extract text based on document type
            if scanned:
                # Perform OCR on scanned PDF
                original_text = extract_text_from_scanned_pdf(doc, max_chars=50000)  # Increased limit for full translation
                if not original_text.strip():
                    raise HTTPException(
                        status_code=400,
                        detail="No text could be extracted from the scanned PDF. Please ensure the PDF contains clear, readable images."
                    )
            else:
                # Extract text from digital PDF
                original_text = extract_text(doc, max_chars=50000)  # Increased limit for full translation
                if not original_text.strip():
                    raise HTTPException(
                        status_code=400,
                        detail="No text could be extracted from the PDF."
                    )
            
            source_language = detect_language(original_text)
            # Translate the extracted text
            translated_text = translate_text_with_azure(original_text, target_language.strip())
            
            return TranslateResponse(
                pages=len(doc),
                kind="scanned" if scanned else "digital",
                original_text=original_text,
                translated_text=translated_text,
                target_language=target_language.strip(),
                source_language=source_language if source_language else "unknown",
            )
            
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}") 