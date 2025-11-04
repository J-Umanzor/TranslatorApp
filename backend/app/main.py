from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import fitz
import pytesseract
from PIL import Image
import io

# Note: PyTesseract requires Tesseract OCR to be installed separately on your system
# Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
# macOS: brew install tesseract
# Linux: sudo apt-get install tesseract-ocr
# After installation, you may need to specify the path if not in PATH:

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
            # If still not found, you can uncomment and set manually:
            # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
            pass

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

MAX_BYTES = 25 * 1024 * 1024 # 25MB

# check if the document is scanned
def is_scanned(doc: fitz.Document, sample_pages: int = 3) -> bool:
    # if the first few pages of the document does not contain text, we can assume it is scanned
    pages_to_check = min(sample_pages, len(doc))
    for i in range(pages_to_check):
        t = doc[i].get_text("text").strip()
        if t: 
            return False
    return True

def extract_text(doc: fitz.Document, max_chars: int = 10000) -> str:
    parts = []
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

def extract_text_from_scanned_pdf(doc: fitz.Document, max_chars: int = 10000, max_pages: int = 10) -> str:
    """
    Extract text from scanned PDF using OCR (PyTesseract).
    Converts each PDF page to an image and performs OCR on it.
    """
    parts = []
    total = 0
    pages_to_process = min(len(doc), max_pages)
    
    for page_num in range(pages_to_process):
        page = doc[page_num]
        
        # Convert PDF page to image (PNG format)
        # Using a high DPI for better OCR accuracy (300 DPI is recommended for OCR)
        mat = fitz.Matrix(2.0, 2.0)  # 2x zoom = ~144 DPI, can increase to 3.0 for better quality
        pix = page.get_pixmap(matrix=mat)
        
        # Convert pixmap to PIL Image
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))
        
        # Perform OCR on the image
        try:
            # Use pytesseract to extract text
            # You can specify language here if needed: pytesseract.image_to_string(img, lang='eng')
            page_text = pytesseract.image_to_string(img)
            
            if page_text.strip():
                parts.append(page_text)
                total += len(page_text)
                
                if total >= max_chars:
                    break
        except pytesseract.TesseractNotFoundError:
            # Tesseract OCR is not installed or not in PATH
            raise HTTPException(
                status_code=500,
                detail="Tesseract OCR is not installed. Please install Tesseract OCR on your system."
            )
        except Exception as e:
            # If OCR fails for a page, skip it and continue
            print(f"OCR failed for page {page_num + 1}: {e}")
            continue
    
    return "\n\n".join(parts)


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
                        text_preview="No text could be extracted from the scanned PDF. Please ensure the PDF contains clear, readable images."
                    )
                return ExtractResponse(
                    pages=len(doc),
                    kind="scanned",
                    text_preview=text[:1000]
                )
            text = extract_text(doc, max_chars=10000)
            return ExtractResponse(
                pages=len(doc),
                kind="digital",
                text_preview=text[:1000]
            )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process PDF: {e}") 