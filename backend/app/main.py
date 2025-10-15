from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import fitz

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
                return ExtractResponse(
                    pages = len(doc),
                    kind = "scanned",
                    text_preview = "Detected PDF as Scanned. OCR planned for later iteration"
                )
            text = extract_text(doc, max_chars = 10000)
            return ExtractResponse(
                pages = len(doc),
                kind = "digital",
                text_preview =text[:1000]
            )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process PDF: {e}") 