import base64
import tempfile
import os
import platform
import html
from typing import List, Optional, Any

from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
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
    extract_text_with_boxes_from_scanned_pdf,
    is_scanned,
)
from app.services.language_detection import detect_language
from app.services.translation_service import translate_texts, translate_text, get_translation_provider
from app.pdf_processor import process_pdf
from app.services.chat_service import ChatService
from app.services.pdf_context_service import PDFContextService
from app.models import (
    ChatStartRequest,
    ChatMessageRequest,
    ChatResponse,
    ChatStartResponse,
    ChatSession,
    ChatMessage,
)

# Load environment variables from backend folder
# Get the backend directory (parent of app directory)
backend_dir = Path(__file__).parent.parent
env_path = backend_dir / '.env'
load_dotenv(dotenv_path=env_path)

# Automatically detect Tesseract path on Windows if not in PATH
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


@app.get("/health/libretranslate")
def health_libretranslate():
    """
    Check if LibreTranslate server is available and healthy.
    """
    try:
        provider = get_translation_provider("libretranslate")
        if hasattr(provider, '_check_connection'):
            is_available = provider._check_connection()
            return {
                "status": "available" if is_available else "unavailable",
                "url": provider.base_url if hasattr(provider, 'base_url') else "unknown"
            }
        return {"status": "unknown", "message": "Could not check LibreTranslate status"}
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@app.post("/upload")
async def upload_and_translate(
    file: UploadFile = File(...),
    target_language: str = Form(...)
):
    """
    Upload a PDF and translate it in-place, preserving layout.
    Returns the translated PDF file.
    """
    # Validate file type
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Please upload a PDF file."
        )
    
    # Read file data
    data = await file.read()
    
    # Validate file size
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="File is empty")
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="File is too large (max 50MB)")
    
    # Validate target language
    if not target_language or not target_language.strip():
        raise HTTPException(status_code=400, detail="Target language is required")
    
    # Create temporary file for input PDF
    temp_dir = tempfile.mkdtemp()
    input_path = os.path.join(temp_dir, "input.pdf")
    
    try:
        # Save uploaded file to temp location
        with open(input_path, "wb") as f:
            f.write(data)
        
        # Process PDF and get translated PDF path
        translated_pdf_path = process_pdf(input_path, target_language.strip())
        
        # Return the translated PDF as a file response
        return FileResponse(
            path=translated_pdf_path,
            media_type="application/pdf",
            filename=f"{Path(file.filename).stem}_translated.pdf"
        )
        
    except Exception as e:
        # Clean up temp files on error
        try:
            if os.path.exists(input_path):
                os.remove(input_path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)
        except:
            pass
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process PDF: {str(e)}"
        )


class ExtractResponse(BaseModel):
    pages: int
    kind: str
    text_preview: str
    language: str

class TranslateResponse(BaseModel):
    pages: int
    kind: str
    original_text: str
    translated_text: str
    target_language: str 
    source_language: str
    translated_pdf_base64: Optional[str] = None

MAX_BYTES = 50 * 1024 * 1024 # 50MB

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


def _decimal_to_hex_color(decimal_color: int) -> str:
    """Convert decimal color to hex format."""
    if decimal_color == 0:
        return '#000000'
    hex_color = hex(decimal_color)[2:]
    hex_color = hex_color.zfill(6)
    return f'#{hex_color}'


def _hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    """
    Convert hex color string to RGB tuple (0-1 range for PyMuPDF).
    
    Args:
        hex_color: Hex color string (e.g., '#000000' or '000000')
        
    Returns:
        RGB tuple with values in 0-1 range
    """
    # Remove '#' if present
    hex_color = hex_color.lstrip('#')
    
    # Convert to RGB (0-255 range)
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    
    # Convert to 0-1 range for PyMuPDF
    return (r / 255.0, g / 255.0, b / 255.0)


def _contains_cjk_characters(text: str) -> bool:
    """
    Check if text contains CJK (Chinese, Japanese, Korean) characters.
    
    Args:
        text: Text to check
        
    Returns:
        True if text contains CJK characters, False otherwise
    """
    if not text:
        return False
    
    # CJK Unicode ranges:
    # CJK Unified Ideographs: U+4E00-U+9FFF
    # CJK Extension A: U+3400-U+4DBF
    # CJK Extension B: U+20000-U+2A6DF
    # Hiragana: U+3040-U+309F
    # Katakana: U+30A0-U+30FF
    # Hangul: U+AC00-U+D7AF
    for char in text:
        code_point = ord(char)
        if (
            (0x4E00 <= code_point <= 0x9FFF) or  # CJK Unified Ideographs
            (0x3400 <= code_point <= 0x4DBF) or  # CJK Extension A
            (0x3040 <= code_point <= 0x309F) or  # Hiragana
            (0x30A0 <= code_point <= 0x30FF) or  # Katakana
            (0xAC00 <= code_point <= 0xD7AF)     # Hangul
        ):
            return True
    return False


def _get_cjk_font(target_language: Optional[str] = None):
    """
    Get a font that supports CJK (Chinese, Japanese, Korean) characters.
    Tries to load from font files first, then falls back to built-in fonts.
    
    Args:
        target_language: Language code (e.g., 'ja', 'zh', 'ko') to select appropriate font
    
    Returns:
        fitz.Font object if a CJK font is found, None otherwise
    """
    # Get the backend directory and fonts path
    backend_dir = Path(__file__).parent.parent
    fonts_dir = backend_dir / "fonts"
    
    # Map language codes to font files
    language_font_map = {
        # Japanese
        "ja": "NotoSerifCJKjp-Regular.otf",
        "jp": "NotoSerifCJKjp-Regular.otf",
        "jpn": "NotoSerifCJKjp-Regular.otf",
        # Simplified Chinese
        "zh": "NotoSerifCJKsc-Regular.otf",
        "zh-cn": "NotoSerifCJKsc-Regular.otf",
        "zh-hans": "NotoSerifCJKsc-Regular.otf",
        "zh-simplified": "NotoSerifCJKsc-Regular.otf",
        # Traditional Chinese (Taiwan)
        "zh-tw": "NotoSerifCJKtc-Regular.otf",
        "zh-hant": "NotoSerifCJKtc-Regular.otf",
        "zh-traditional": "NotoSerifCJKtc-Regular.otf",
        # Traditional Chinese (Hong Kong)
        "zh-hk": "NotoSerifCJKhk-Regular.otf",
        # Korean
        "ko": "NotoSerifCJKkr-Regular.otf",
        "kr": "NotoSerifCJKkr-Regular.otf",
        "kor": "NotoSerifCJKkr-Regular.otf",
    }
    
    # Try to load font file based on target language
    if target_language:
        target_language_lower = target_language.lower().strip()
        font_filename = language_font_map.get(target_language_lower)
        
        if font_filename:
            font_path = fonts_dir / font_filename
            if font_path.exists():
                try:
                    # Use absolute path to avoid any path issues
                    font_path_abs = str(font_path.resolve())
                    font = fitz.Font(fontfile=font_path_abs)
                    print(f"Successfully loaded CJK font: {font_path_abs} for language {target_language}")
                    return font
                except Exception as e:
                    print(f"Failed to load font from file {font_path}: {e}")
                    import traceback
                    traceback.print_exc()
    
    # If language-specific font not found, try all available font files
    font_files = [
        "NotoSerifCJKjp-Regular.otf",  # Japanese (most common for CJK issues)
        "NotoSerifCJKsc-Regular.otf",  # Simplified Chinese
        "NotoSerifCJKtc-Regular.otf",  # Traditional Chinese
        "NotoSerifCJKkr-Regular.otf",  # Korean
        "NotoSerifCJKhk-Regular.otf",  # Hong Kong
    ]
    
    for font_filename in font_files:
        font_path = fonts_dir / font_filename
        if font_path.exists():
            try:
                # Use absolute path to avoid any path issues
                font_path_abs = str(font_path.resolve())
                font = fitz.Font(fontfile=font_path_abs)
                print(f"Successfully loaded CJK font: {font_path_abs}")
                return font
            except Exception as e:
                print(f"Failed to load font from file {font_path}: {e}")
                continue
    
    # Fallback to built-in PyMuPDF fonts
    cjk_font_names = [
        "japan",         # Japanese font
        "japan-s",       # Japanese font (alternate)
        "china-s",       # Chinese Simplified
        "china-ss",      # Chinese Simplified (alternate)
        "china-t",       # Chinese Traditional
        "korea",         # Korean
        "cjk",           # Generic CJK font
        "noto",          # Noto font (if available)
    ]
    
    for font_name in cjk_font_names:
        try:
            font = fitz.Font(font_name)
            print(f"Using built-in PyMuPDF font: {font_name}")
            return font
        except:
            continue
    
    # If no font works, return None
    print("WARNING: No CJK font could be loaded!")
    return None


def translate_digital_pdf_with_layout(
    doc: fitz.Document,
    target_language: str,
    provider: str = "azure",
) -> tuple[str, str, Optional[str]]:
    """
    Translate digital PDF content using redaction approach to preserve layout and
    produce a translated PDF encoded in base64.
    
    Uses proper redaction (not white box overlays):
    1. Extracts text at span level with formatting
    2. Marks text areas for redaction
    3. Applies redactions to remove text objects
    4. Inserts translated text with HTML formatting
    """
    pages_data: List[List[List[Any]]] = []
    block_texts: List[str] = []

    # Extract text at span level to preserve formatting
    for page_index in range(len(doc)):
        page = doc[page_index]
        page_blocks = []
        page_dict = page.get_text("dict")

        # Extract links for preservation
        links = page.get_links()
        link_map: dict = {}
        for link in links:
            rect = fitz.Rect(link["from"])
            link_map[rect] = {
                "uri": link.get("uri", ""),
                "page": link.get("page", -1),
                "to": link.get("to", None),
                "kind": link.get("kind", 0)
            }

        # Extract at span level to preserve individual formatting
        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:
                continue

            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if not text:
                        continue

                    bbox = span.get("bbox", (0, 0, 0, 0))
                    font_size = span.get("size", 12)
                    font_flags = span.get("flags", 0)
                    color = span.get("color", 0)
                    is_bold = bool(font_flags & 2**4)

                    span_rect = fitz.Rect(bbox)
                    link_info = None

                    # Check if this span intersects with any link
                    for link_rect, link_data in link_map.items():
                        if span_rect.intersects(link_rect):
                            link_info = link_data
                            break

                    # Store span data: [text, bbox, translation, angle, color, indent, is_bold, font_size, link_info]
                    page_blocks.append([
                        text,
                        tuple(bbox),
                        None,  # Translation placeholder
                        0,     # Angle (rotation)
                        _decimal_to_hex_color(color),
                        0,     # Text indent
                        is_bold,
                        font_size,
                        link_info  # Link information
                    ])
                    block_texts.append(text)

        pages_data.append(page_blocks)

    if not block_texts:
        raise HTTPException(
            status_code=400, detail="No textual content detected in the digital PDF."
        )

    # Translate all texts in batch using translation service
    translated_blocks = translate_texts(
        block_texts, target_language, provider=provider
    )

    # Create translated document
    translated_doc = fitz.open()
    translated_doc.insert_pdf(doc)
    
    # Pre-load CJK font path once for the entire document (more efficient for large documents)
    cjk_font_path = None
    cjk_font_name = None
    # Check if any translated text contains CJK characters
    sample_text = "".join(translated_blocks[:min(100, len(translated_blocks))])
    if _contains_cjk_characters(sample_text):
        # Get font file path instead of font object
        backend_dir = Path(__file__).parent.parent
        fonts_dir = backend_dir / "fonts"
        
        language_font_map = {
            "ja": "NotoSerifCJKjp-Regular.otf",
            "jp": "NotoSerifCJKjp-Regular.otf",
            "jpn": "NotoSerifCJKjp-Regular.otf",
            "zh": "NotoSerifCJKsc-Regular.otf",
            "zh-cn": "NotoSerifCJKsc-Regular.otf",
            "zh-hans": "NotoSerifCJKsc-Regular.otf",
            "zh-tw": "NotoSerifCJKtc-Regular.otf",
            "zh-hant": "NotoSerifCJKtc-Regular.otf",
            "zh-hk": "NotoSerifCJKhk-Regular.otf",
            "ko": "NotoSerifCJKkr-Regular.otf",
            "kr": "NotoSerifCJKkr-Regular.otf",
        }
        
        target_language_lower = target_language.lower().strip()
        font_filename = language_font_map.get(target_language_lower)
        
        if font_filename:
            font_path = fonts_dir / font_filename
            if font_path.exists():
                cjk_font_path = str(font_path.resolve())
                cjk_font_name = "CJKFont"  # Name to use when embedding
                print(f"Pre-loaded CJK font path for language {target_language}: {cjk_font_path}")
        
        if not cjk_font_path:
            # Try any available CJK font
            for font_file in ["NotoSerifCJKjp-Regular.otf", "NotoSerifCJKsc-Regular.otf", 
                             "NotoSerifCJKtc-Regular.otf", "NotoSerifCJKkr-Regular.otf"]:
                font_path = fonts_dir / font_file
                if font_path.exists():
                    cjk_font_path = str(font_path.resolve())
                    cjk_font_name = "CJKFont"
                    print(f"Using available CJK font: {cjk_font_path}")
                    break
        
        if not cjk_font_path:
            print(f"WARNING: Could not find CJK font file for language {target_language}")
    
    translated_text_parts: List[str] = []
    original_text_parts: List[str] = []
    block_index = 0

    # Apply translations using redaction approach
    for page_number, page_blocks in enumerate(pages_data):
        if not page_blocks:
            continue

        new_page = translated_doc[page_number]
        page_rect = new_page.rect

        # Separate bold and normal blocks for proper styling
        normal_blocks = []
        bold_blocks = []

        # First pass: prepare all blocks and mark areas for redaction
        for block in page_blocks:
            original_text = block[0]
            translated_text = translated_blocks[block_index] if block_index < len(translated_blocks) else original_text
            block_index += 1

            original_text_parts.append(original_text)
            translated_text_parts.append(translated_text)

            if not translated_text.strip():
                continue

            coords = block[1]
            x0, y0, x1, y1 = coords
            width = x1 - x0
            height = y1 - y0

            # Calculate expansion factor based on text length ratio
            len_ratio = min(1.05, max(1.01, len(translated_text) / max(1, len(original_text))))

            # Expand horizontally to accommodate longer text
            h_expand = (len_ratio - 1) * width
            x1 = x1 + h_expand

            # Reduce vertical coverage to be more precise
            vertical_margin = min(height * 0.1, 3)
            y0 = y0 + vertical_margin
            y1 = y1 - vertical_margin

            # Ensure minimum height
            if y1 - y0 < 10:
                y_center = (coords[1] + coords[3]) / 2
                y0 = y_center - 5
                y1 = y_center + 5

            enlarged_coords = (x0, y0, x1, y1)
            rect = fitz.Rect(*enlarged_coords)

            # Mark area for redaction (but don't apply yet)
            new_page.add_redact_annot(rect)

            is_bold = len(block) > 6 and block[6]
            if is_bold:
                bold_blocks.append((block, enlarged_coords, translated_text))
            else:
                normal_blocks.append((block, enlarged_coords, translated_text))

        # Apply all redactions for this page at once (removes text objects, preserves images)
        try:
            try:
                new_page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
            except (AttributeError, TypeError):
                # Fallback if PDF_REDACT_IMAGE_NONE constant doesn't exist
                new_page.apply_redactions()
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to apply redactions on page {page_number}: {str(e)}"
            )

        # Insert text blocks with proper styling after redaction
        for block_data in normal_blocks + bold_blocks:
            block, enlarged_coords, translated_text = block_data
            color = block[4] if len(block) > 4 else '#000000'
            font_size = block[7] if len(block) > 7 else 12
            is_bold = block[6] if len(block) > 6 else False
            link_info = block[8] if len(block) > 8 else None

            rect = fitz.Rect(*enlarged_coords)
            font_weight = "bold" if is_bold else "normal"
            
            # Check if text contains CJK characters
            has_cjk = _contains_cjk_characters(translated_text)

            # For CJK characters, embed font and use textbox insertion
            if has_cjk:
                try:
                    # Convert hex color to RGB tuple for PyMuPDF
                    rgb_color = _hex_to_rgb(color)
                    
                    # Embed font in page if we have a font file
                    font_name_to_use = None
                    if cjk_font_path and cjk_font_name:
                        try:
                            # Embed the font in the page (only needs to be done once per page)
                            if not hasattr(new_page, '_cjk_font_embedded'):
                                print(f"Embedding CJK font '{cjk_font_name}' from '{cjk_font_path}' on page {page_number}")
                                new_page.insert_font(fontname=cjk_font_name, fontfile=cjk_font_path)
                                new_page._cjk_font_embedded = True
                                print(f"Successfully embedded CJK font on page {page_number}")
                                # Test that the font works by inserting a test character
                                try:
                                    test_rect = fitz.Rect(10, 10, 50, 30)
                                    test_result = new_page.insert_textbox(test_rect, "测试", fontsize=12, fontname=cjk_font_name, align=0)
                                    if test_result > 0:
                                        print(f"Font test successful: {test_result} chars fitted")
                                    else:
                                        print(f"WARNING: Font test failed - {test_result} chars fitted")
                                except Exception as test_error:
                                    print(f"Font test insertion failed: {test_error}")
                            # Always set font_name_to_use after embedding (for all blocks on this page)
                            font_name_to_use = cjk_font_name
                            print(f"DEBUG: Set font_name_to_use='{font_name_to_use}' for block on page {page_number}")
                        except Exception as embed_error:
                            print(f"Failed to embed CJK font on page {page_number}: {embed_error}")
                            import traceback
                            traceback.print_exc()
                            # Try built-in CJK fonts as fallback
                            for builtin_font in ["japan", "japan-s", "china-s", "china-t", "korea", "cjk"]:
                                try:
                                    font_name_to_use = builtin_font
                                    print(f"Using built-in font '{builtin_font}' as fallback")
                                    break
                                except:
                                    continue
                    else:
                        print(f"DEBUG: cjk_font_path={cjk_font_path}, cjk_font_name={cjk_font_name} on page {page_number}")
                    
                    if font_name_to_use:
                        # Use textbox insertion with the embedded font name
                        try:
                            # Validate rect before insertion
                            page_rect = new_page.rect
                            if rect.width <= 0 or rect.height <= 0:
                                print(f"Invalid rect for CJK text: {rect}, using insert_text instead")
                                new_page.insert_text(rect.tl, translated_text, fontsize=font_size, fontname=font_name_to_use, color=rgb_color)
                            elif rect.x0 < 0 or rect.y0 < 0 or rect.x1 > page_rect.width or rect.y1 > page_rect.height:
                                print(f"Rect outside page bounds: {rect}, page_rect={page_rect}, clamping and using insert_text")
                                # Clamp to page bounds
                                clamped_point = fitz.Point(
                                    max(0, min(rect.x0, page_rect.width - 10)),
                                    max(0, min(rect.y0, page_rect.height - 10))
                                )
                                new_page.insert_text(clamped_point, translated_text, fontsize=font_size, fontname=font_name_to_use, color=rgb_color)
                            else:
                                # insert_textbox returns the number of characters that fit
                                chars_fitted = new_page.insert_textbox(rect, translated_text, fontsize=font_size, fontname=font_name_to_use, align=0, color=rgb_color)
                                if chars_fitted <= 0:
                                    print(f"Textbox insertion returned {chars_fitted} chars fitted, trying insert_text instead. rect={rect}, text_len={len(translated_text)}")
                                    new_page.insert_text(rect.tl, translated_text, fontsize=font_size, fontname=font_name_to_use, color=rgb_color)
                                else:
                                    print(f"Successfully inserted CJK text with font '{font_name_to_use}' ({chars_fitted}/{len(translated_text)} chars fitted, rect={rect})")
                        except Exception as textbox_error:
                            print(f"Textbox insertion failed for CJK text (len={len(translated_text)}): {textbox_error}")
                            # If textbox fails (e.g., text too long), try insert_text
                            try:
                                new_page.insert_text(rect.tl, translated_text, fontsize=font_size, fontname=font_name_to_use, color=rgb_color)
                                print(f"Successfully inserted CJK text with insert_text using font '{font_name_to_use}'")
                            except Exception as text_error:
                                print(f"Font insertion failed for CJK text: {text_error}")
                                import traceback
                                traceback.print_exc()
                                # Last resort: insert without font (will show dots)
                                try:
                                    new_page.insert_text(rect.tl, translated_text, fontsize=font_size)
                                    print(f"Inserted CJK text without font (will show dots)")
                                except Exception as final_error:
                                    print(f"All insertion methods failed: {final_error}")
                                    import traceback
                                    traceback.print_exc()
                    else:
                        # No CJK font available - this will likely show dots but won't crash
                        print(f"Warning: No CJK font available for page {page_number}, characters may not render correctly. cjk_font_path={cjk_font_path}, cjk_font_name={cjk_font_name}")
                        try:
                            new_page.insert_textbox(rect, translated_text, fontsize=font_size, align=0, color=rgb_color)
                        except Exception as e:
                            print(f"Textbox insertion failed without font: {e}")
                            try:
                                new_page.insert_text(rect.tl, translated_text, fontsize=font_size)
                            except Exception as e2:
                                print(f"All insertion methods failed: {e2}")
                    
                    # Add link annotation if needed
                    if link_info:
                            try:
                                link_dict = {
                                    "kind": link_info.get("kind", 1),
                                    "from": rect
                                }
                                if link_info.get("uri"):
                                    link_dict["uri"] = link_info["uri"]
                                    link_dict["kind"] = 1
                                elif link_info.get("page", -1) >= 0:
                                    link_dict["page"] = link_info["page"]
                                    link_dict["kind"] = 2
                                    if link_info.get("to"):
                                        link_dict["to"] = link_info["to"]
                                new_page.insert_link(link_dict)
                            except Exception:
                                pass  # Silently fail if link insertion fails
                    else:
                        # No CJK font available - this will likely show dots but won't crash
                        print(f"Warning: No CJK font available for page {page_number}, characters may not render correctly")
                        new_page.insert_textbox(rect, translated_text, fontsize=font_size, align=0, color=rgb_color)
                except Exception as e:
                    # Last resort: use basic insert_text
                    try:
                        new_page.insert_text(rect.tl, translated_text, fontsize=font_size)
                    except Exception as final_error:
                        # Log error but continue processing
                        print(f"Failed to insert CJK text on page {page_number}: {final_error}")
                        pass
            else:
                # For non-CJK text, use HTML insertion for better formatting
                # Escape HTML content to prevent issues with special characters
                escaped_text = html.escape(translated_text)

                # Handle links
                if link_info:
                    if link_info.get("uri"):
                        escaped_text = f'<a href="{html.escape(link_info["uri"])}" style="color: {color}; text-decoration: underline;">{escaped_text}</a>'
                    elif link_info.get("page", -1) >= 0:
                        page_num = link_info["page"]
                        escaped_text = f'<a href="#page{page_num}" style="color: {color}; text-decoration: underline;">{escaped_text}</a>'

                # CSS for styling
                css = f"""
                * {{
                    color: {color};
                    font-weight: {font_weight};
                    font-size: {font_size}px;
                    line-height: 1.2;
                    word-wrap: break-word;
                    overflow-wrap: break-word;
                    width: 100%;
                    box-sizing: border-box;
                    margin: 0;
                    padding: 0;
                }}
                a {{
                    text-decoration: underline;
                }}
                """

                # HTML content with inline styles
                html_content = f'<div style="font-size: {font_size}px; color: {color}; font-weight: {font_weight}; line-height: 1.2; word-wrap: break-word;">{escaped_text}</div>'

                try:
                    # Use HTML insertion for better formatting and automatic wrapping
                    new_page.insert_htmlbox(rect, html_content, css=css, rotate=0)

                    # Add link annotation if needed
                    if link_info:
                        try:
                            link_dict = {
                                "kind": link_info.get("kind", 1),
                                "from": rect
                            }
                            if link_info.get("uri"):
                                link_dict["uri"] = link_info["uri"]
                                link_dict["kind"] = 1
                            elif link_info.get("page", -1) >= 0:
                                link_dict["page"] = link_info["page"]
                                link_dict["kind"] = 2
                                if link_info.get("to"):
                                    link_dict["to"] = link_info["to"]
                            new_page.insert_link(link_dict)
                        except Exception:
                            pass  # Silently fail if link insertion fails
                except Exception as e:
                    # Fallback to text insertion
                    try:
                        rgb_color = _hex_to_rgb(color)
                        new_page.insert_textbox(rect, translated_text, fontsize=font_size, align=0, color=rgb_color)
                    except Exception as fallback_error:
                        # Last resort: use basic insert_text
                        try:
                            new_page.insert_text(rect.tl, translated_text, fontsize=font_size)
                        except Exception as final_error:
                            # Log error but continue processing
                            print(f"Failed to insert text on page {page_number}: {final_error}")
                            pass

    pdf_bytes = translated_doc.tobytes()
    translated_doc.close()

    translated_pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
    original_full_text = "\n\n".join(original_text_parts)
    translated_full_text = "\n\n".join(translated_text_parts)

    return original_full_text, translated_full_text, translated_pdf_base64


def translate_scanned_pdf_with_layout(
    doc: fitz.Document,
    target_language: str,
    provider: str = "azure",
) -> tuple[str, str, Optional[str]]:
    """
    Translate scanned PDF content using OCR with bounding boxes to preserve layout.
    
    For scanned PDFs, we:
    1. Extract text with bounding boxes using OCR
    2. Overlay white boxes on detected text areas (since text is part of the image)
    3. Insert translated text with HTML formatting at the same positions
    
    Note: Unlike digital PDFs, we can't remove text objects from scanned PDFs since
    the text is embedded in the image. We overlay white boxes instead.
    """
    # Extract text with bounding boxes using OCR
    pages_data = extract_text_with_boxes_from_scanned_pdf(doc, max_pages=len(doc))
    
    # Collect all texts for translation
    block_texts: List[str] = []
    for page_blocks in pages_data:
        for block in page_blocks:
            block_texts.append(block['text'])
    
    if not block_texts:
        raise HTTPException(
            status_code=400,
            detail="No textual content detected in the scanned PDF."
        )
    
    # Translate all texts in batch using translation service
    translated_blocks = translate_texts(
        block_texts, target_language, provider=provider
    )
    
    # Create translated document
    translated_doc = fitz.open()
    translated_doc.insert_pdf(doc)
    
    # Pre-load CJK font path once for the entire document (more efficient for large documents)
    cjk_font_path = None
    cjk_font_name = None
    # Check if any translated text contains CJK characters
    sample_text = "".join(translated_blocks[:min(100, len(translated_blocks))])
    if _contains_cjk_characters(sample_text):
        # Get font file path instead of font object
        backend_dir = Path(__file__).parent.parent
        fonts_dir = backend_dir / "fonts"
        
        language_font_map = {
            "ja": "NotoSerifCJKjp-Regular.otf",
            "jp": "NotoSerifCJKjp-Regular.otf",
            "jpn": "NotoSerifCJKjp-Regular.otf",
            "zh": "NotoSerifCJKsc-Regular.otf",
            "zh-cn": "NotoSerifCJKsc-Regular.otf",
            "zh-hans": "NotoSerifCJKsc-Regular.otf",
            "zh-tw": "NotoSerifCJKtc-Regular.otf",
            "zh-hant": "NotoSerifCJKtc-Regular.otf",
            "zh-hk": "NotoSerifCJKhk-Regular.otf",
            "ko": "NotoSerifCJKkr-Regular.otf",
            "kr": "NotoSerifCJKkr-Regular.otf",
        }
        
        target_language_lower = target_language.lower().strip()
        font_filename = language_font_map.get(target_language_lower)
        
        if font_filename:
            font_path = fonts_dir / font_filename
            if font_path.exists():
                cjk_font_path = str(font_path.resolve())
                cjk_font_name = "CJKFont"  # Name to use when embedding
                print(f"Pre-loaded CJK font path for language {target_language}: {cjk_font_path}")
        
        if not cjk_font_path:
            # Try any available CJK font
            for font_file in ["NotoSerifCJKjp-Regular.otf", "NotoSerifCJKsc-Regular.otf", 
                             "NotoSerifCJKtc-Regular.otf", "NotoSerifCJKkr-Regular.otf"]:
                font_path = fonts_dir / font_file
                if font_path.exists():
                    cjk_font_path = str(font_path.resolve())
                    cjk_font_name = "CJKFont"
                    print(f"Using available CJK font: {cjk_font_path}")
                    break
        
        if not cjk_font_path:
            print(f"WARNING: Could not find CJK font file for language {target_language}")
    
    translated_text_parts: List[str] = []
    original_text_parts: List[str] = []
    block_index = 0
    
    # Apply translations using overlay approach for scanned PDFs
    for page_number, page_blocks in enumerate(pages_data):
        if not page_blocks:
            continue
        
        new_page = translated_doc[page_number]
        
        # Separate bold and normal blocks for proper styling
        normal_blocks = []
        bold_blocks = []
        
        # First pass: prepare all blocks and mark areas for overlay
        for block in page_blocks:
            original_text = block['text']
            translated_text = translated_blocks[block_index] if block_index < len(translated_blocks) else original_text
            block_index += 1
            
            original_text_parts.append(original_text)
            translated_text_parts.append(translated_text)
            
            if not translated_text.strip():
                continue
            
            coords = block['bbox']
            x0, y0, x1, y1 = coords
            width = x1 - x0
            height = y1 - y0
            
            # Calculate expansion factor based on text length ratio
            len_ratio = min(1.1, max(1.01, len(translated_text) / max(1, len(original_text))))
            
            # Expand horizontally to accommodate longer text
            h_expand = (len_ratio - 1) * width
            x1 = x1 + h_expand
            
            # Add some padding around the text area
            padding = max(2, height * 0.1)
            x0 = max(0, x0 - padding)
            y0 = max(0, y0 - padding)
            x1 = min(new_page.rect.width, x1 + padding)
            y1 = min(new_page.rect.height, y1 + padding)
            
            # Ensure minimum dimensions
            if y1 - y0 < 10:
                y_center = (coords[1] + coords[3]) / 2
                y0 = max(0, y_center - 5)
                y1 = min(new_page.rect.height, y_center + 5)
            
            enlarged_coords = (x0, y0, x1, y1)
            rect = fitz.Rect(*enlarged_coords)
            
            # For scanned PDFs, overlay white rectangle to cover the text area
            # (since we can't remove text from images)
            white_rect = fitz.Rect(*enlarged_coords)
            new_page.draw_rect(white_rect, color=(1, 1, 1), fill=(1, 1, 1))
            
            is_bold = block.get('is_bold', False)
            if is_bold:
                bold_blocks.append((block, enlarged_coords, translated_text))
            else:
                normal_blocks.append((block, enlarged_coords, translated_text))
        
        # Insert text blocks with proper styling after overlay
        for block_data in normal_blocks + bold_blocks:
            block, enlarged_coords, translated_text = block_data
            color = block.get('color', '#000000')
            font_size = block.get('font_size', 12)
            is_bold = block.get('is_bold', False)
            
            rect = fitz.Rect(*enlarged_coords)
            font_weight = "bold" if is_bold else "normal"
            
            # Check if text contains CJK characters
            has_cjk = _contains_cjk_characters(translated_text)

            # For CJK characters, embed font and use textbox insertion
            if has_cjk:
                try:
                    # Convert hex color to RGB tuple for PyMuPDF
                    rgb_color = _hex_to_rgb(color)
                    
                    # Embed font in page if we have a font file
                    font_name_to_use = None
                    if cjk_font_path and cjk_font_name:
                        try:
                            # Embed the font in the page (only needs to be done once per page)
                            if not hasattr(new_page, '_cjk_font_embedded'):
                                print(f"Embedding CJK font '{cjk_font_name}' from '{cjk_font_path}' on page {page_number}")
                                new_page.insert_font(fontname=cjk_font_name, fontfile=cjk_font_path)
                                new_page._cjk_font_embedded = True
                                print(f"Successfully embedded CJK font on page {page_number}")
                                # Test that the font works by inserting a test character
                                try:
                                    test_rect = fitz.Rect(10, 10, 50, 30)
                                    test_result = new_page.insert_textbox(test_rect, "测试", fontsize=12, fontname=cjk_font_name, align=0)
                                    if test_result > 0:
                                        print(f"Font test successful: {test_result} chars fitted")
                                    else:
                                        print(f"WARNING: Font test failed - {test_result} chars fitted")
                                except Exception as test_error:
                                    print(f"Font test insertion failed: {test_error}")
                            # Always set font_name_to_use after embedding (for all blocks on this page)
                            font_name_to_use = cjk_font_name
                            print(f"DEBUG: Set font_name_to_use='{font_name_to_use}' for block on page {page_number}")
                        except Exception as embed_error:
                            print(f"Failed to embed CJK font on page {page_number}: {embed_error}")
                            import traceback
                            traceback.print_exc()
                            # Try built-in CJK fonts as fallback
                            for builtin_font in ["japan", "japan-s", "china-s", "china-t", "korea", "cjk"]:
                                try:
                                    font_name_to_use = builtin_font
                                    print(f"Using built-in font '{builtin_font}' as fallback")
                                    break
                                except:
                                    continue
                    else:
                        print(f"DEBUG: cjk_font_path={cjk_font_path}, cjk_font_name={cjk_font_name} on page {page_number}")
                    
                    if font_name_to_use:
                        # Use textbox insertion with the embedded font name
                        try:
                            # Validate rect before insertion
                            page_rect = new_page.rect
                            if rect.width <= 0 or rect.height <= 0:
                                print(f"Invalid rect for CJK text: {rect}, using insert_text instead")
                                new_page.insert_text(rect.tl, translated_text, fontsize=font_size, fontname=font_name_to_use, color=rgb_color)
                            elif rect.x0 < 0 or rect.y0 < 0 or rect.x1 > page_rect.width or rect.y1 > page_rect.height:
                                print(f"Rect outside page bounds: {rect}, page_rect={page_rect}, clamping and using insert_text")
                                # Clamp to page bounds
                                clamped_point = fitz.Point(
                                    max(0, min(rect.x0, page_rect.width - 10)),
                                    max(0, min(rect.y0, page_rect.height - 10))
                                )
                                new_page.insert_text(clamped_point, translated_text, fontsize=font_size, fontname=font_name_to_use, color=rgb_color)
                            else:
                                # insert_textbox returns the number of characters that fit
                                chars_fitted = new_page.insert_textbox(rect, translated_text, fontsize=font_size, fontname=font_name_to_use, align=0, color=rgb_color)
                                if chars_fitted <= 0:
                                    print(f"Textbox insertion returned {chars_fitted} chars fitted, trying insert_text instead. rect={rect}, text_len={len(translated_text)}")
                                    new_page.insert_text(rect.tl, translated_text, fontsize=font_size, fontname=font_name_to_use, color=rgb_color)
                                else:
                                    print(f"Successfully inserted CJK text with font '{font_name_to_use}' ({chars_fitted}/{len(translated_text)} chars fitted, rect={rect})")
                        except Exception as textbox_error:
                            print(f"Textbox insertion failed for CJK text (len={len(translated_text)}): {textbox_error}")
                            # If textbox fails (e.g., text too long), try insert_text
                            try:
                                new_page.insert_text(rect.tl, translated_text, fontsize=font_size, fontname=font_name_to_use, color=rgb_color)
                                print(f"Successfully inserted CJK text with insert_text using font '{font_name_to_use}'")
                            except Exception as text_error:
                                print(f"Font insertion failed for CJK text: {text_error}")
                                import traceback
                                traceback.print_exc()
                                # Last resort: insert without font (will show dots)
                                try:
                                    new_page.insert_text(rect.tl, translated_text, fontsize=font_size)
                                    print(f"Inserted CJK text without font (will show dots)")
                                except Exception as final_error:
                                    print(f"All insertion methods failed: {final_error}")
                                    import traceback
                                    traceback.print_exc()
                    else:
                        # No CJK font available - this will likely show dots but won't crash
                        print(f"Warning: No CJK font available for page {page_number}, characters may not render correctly. cjk_font_path={cjk_font_path}, cjk_font_name={cjk_font_name}")
                        try:
                            new_page.insert_textbox(rect, translated_text, fontsize=font_size, align=0, color=rgb_color)
                        except Exception as e:
                            print(f"Textbox insertion failed without font: {e}")
                            try:
                                new_page.insert_text(rect.tl, translated_text, fontsize=font_size)
                            except Exception as e2:
                                print(f"All insertion methods failed: {e2}")
                except Exception as e:
                    # Last resort: use basic insert_text
                    try:
                        new_page.insert_text(rect.tl, translated_text, fontsize=font_size)
                    except Exception as final_error:
                        # Log error but continue processing
                        print(f"Failed to insert CJK text on page {page_number}: {final_error}")
                        pass
            else:
                # For non-CJK text, use HTML insertion for better formatting
                # Escape HTML content to prevent issues with special characters
                escaped_text = html.escape(translated_text)
                
                # CSS for styling
                css = f"""
                * {{
                    color: {color};
                    font-weight: {font_weight};
                    font-size: {font_size}px;
                    line-height: 1.2;
                    word-wrap: break-word;
                    overflow-wrap: break-word;
                    width: 100%;
                    box-sizing: border-box;
                    margin: 0;
                    padding: 0;
                }}
                """
                
                # HTML content with inline styles
                html_content = f'<div style="font-size: {font_size}px; color: {color}; font-weight: {font_weight}; line-height: 1.2; word-wrap: break-word;">{escaped_text}</div>'
                
                try:
                    # Use HTML insertion for better formatting and automatic wrapping
                    new_page.insert_htmlbox(rect, html_content, css=css, rotate=0)
                except Exception as e:
                    # Fallback to text insertion
                    try:
                        rgb_color = _hex_to_rgb(color)
                        new_page.insert_textbox(rect, translated_text, fontsize=font_size, align=0, color=rgb_color)
                    except Exception as fallback_error:
                        # Last resort: use basic insert_text
                        try:
                            new_page.insert_text(rect.tl, translated_text, fontsize=font_size)
                        except Exception as final_error:
                            # Log error but continue processing
                            print(f"Failed to insert text on page {page_number}: {final_error}")
                            pass
    
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
        raise HTTPException(status_code=400, detail="File is too large max (50MB)")

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
    target_language: str = Form(...),
    translator_provider: str = Form("azure")
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
        raise HTTPException(status_code=400, detail="File is too large max (50MB)")

    # Validate target language
    if not target_language or not target_language.strip():
        raise HTTPException(status_code=400, detail="Target language is required")

    try:
        with fitz.open(stream=data, filetype="pdf") as doc:
            scanned = is_scanned(doc)
            target_language_clean = target_language.strip()
            provider = translator_provider.strip().lower() if translator_provider else "azure"
            
            # Extract text based on document type
            if scanned:
                # Translate scanned PDF with format preservation
                try:
                    (
                        original_text,
                        translated_text,
                        translated_pdf_base64,
                    ) = translate_scanned_pdf_with_layout(
                        doc, target_language_clean, provider=provider
                    )
                    if not original_text.strip():
                        raise HTTPException(
                            status_code=400,
                            detail="No text could be extracted from the scanned PDF. Please ensure the PDF contains clear, readable images."
                        )
                except HTTPException:
                    raise
                except Exception as e:
                    # Fallback to text-only translation if format preservation fails
                    original_text = extract_text_from_scanned_pdf(doc, max_chars=50000)
                    if not original_text.strip():
                        raise HTTPException(
                            status_code=400,
                            detail="No text could be extracted from the scanned PDF. Please ensure the PDF contains clear, readable images."
                        )
                    translated_text = translate_text(
                        original_text, target_language_clean, provider=provider
                    )
                    translated_pdf_base64 = None
            else:
                # Extract text from digital PDF
                (
                    original_text,
                    translated_text,
                    translated_pdf_base64,
                ) = translate_digital_pdf_with_layout(
                    doc, target_language_clean, provider=provider
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


# Chat endpoints
# In-memory session storage (in production, use Redis or database)
chat_sessions: dict[str, ChatSession] = {}
# Store PDF data separately (not in Pydantic model)
pdf_data_storage: dict[str, bytes] = {}
chat_service = ChatService()
pdf_context_service = PDFContextService()


@app.get("/chat/models")
async def get_chat_models():
    """Get list of available Ollama models."""
    try:
        models = chat_service.get_available_models()
        return {"models": models}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get models: {str(e)}"
        )


@app.post("/chat/start", response_model=ChatStartResponse)
async def start_chat(
    file: Optional[UploadFile] = File(None),
    pdf_base64: Optional[str] = Form(None),
    context_type: str = Form("translated"),
    model: Optional[str] = Form(None),
    use_visual: bool = Form(False),
    target_language: Optional[str] = Form(None),
    source_language: Optional[str] = Form(None),
    use_source_language: bool = Form(False)
):
    """
    Initialize a new chat session with PDF context.
    
    Args:
        file: PDF file upload (optional if pdf_base64 provided)
        pdf_base64: Base64-encoded PDF (optional if file provided)
        context_type: "original" or "translated"
        model: Model name (optional, will use recommended if not provided)
        use_visual: Whether to use visual LLM
        
    Returns:
        Chat session information
    """
    import uuid
    from datetime import datetime
    
    # Get PDF data
    pdf_data = None
    if file:
        pdf_data = await file.read()
    elif pdf_base64:
        # For large base64 strings, we need to handle them carefully
        # If the base64 string is too large for form field, it will be truncated
        # So we'll read it in chunks if needed, or recommend file upload
        try:
            # Check if base64 string is complete (ends with padding or valid base64 chars)
            if len(pdf_base64) > 1024 * 1024:  # If larger than 1MB as base64 string
                raise HTTPException(
                    status_code=400,
                    detail="Base64 string too large for form field. Please use file upload instead for files larger than ~750KB."
                )
            pdf_data = base64.b64decode(pdf_base64)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid base64 PDF data: {str(e)}. For large files, please use file upload instead."
            )
    else:
        raise HTTPException(
            status_code=400,
            detail="Either file or pdf_base64 must be provided"
        )
    
    # Validate PDF
    if not pdf_data or len(pdf_data) == 0:
        raise HTTPException(status_code=400, detail="PDF data is empty")
    
    # Get PDF info
    try:
        pdf_info = pdf_context_service.get_pdf_info(pdf_data)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process PDF: {str(e)}"
        )
    
    # Always use visual model to support both text and images
    # This allows us to provide full context (text + images) for all PDFs
    use_visual = True
    recommended_model = chat_service.get_recommended_model(is_visual=True)
    
    # Use provided model or recommended
    selected_model = model or recommended_model
    
    # Detect target and source languages if not provided
    detected_target_language = target_language
    if not detected_target_language:
        try:
            # Try to detect from PDF text
            pdf_text = pdf_context_service.get_pdf_text(pdf_data, max_chars=2000)
            from app.services.language_detection import detect_language
            detected_target_language = detect_language(pdf_text)
            if detected_target_language == "unknown":
                detected_target_language = "en"  # Default to English
        except:
            detected_target_language = "en"  # Default to English
    
    detected_source_language = source_language or "en"  # Default to English if not provided
    
    # Determine chat language based on toggle
    # If use_source_language is True, chat in source language, otherwise use target language (default)
    chat_language = detected_source_language if use_source_language else detected_target_language
    
    # Create session
    session_id = str(uuid.uuid4())
    session = ChatSession(
        session_id=session_id,
        context_type=context_type,
        model=selected_model,
        use_visual=use_visual,
        messages=[],
        pdf_info=pdf_info,
        target_language=detected_target_language,
        source_language=detected_source_language,
        chat_language=chat_language
    )
    
    # Create friendly greeting message
    # Generate greeting in chat language using translation service
    base_greeting = f"Hello! I'm here to help you with your PDF document. This document has {pdf_info['pages']} page{'s' if pdf_info['pages'] != 1 else ''} and appears to be a {pdf_info['kind']} PDF. What would you like to know about it?"
    
    # Translate greeting to chat language if not English
    if chat_language and chat_language != "en":
        try:
            # Try to use Azure first, then fallback to LibreTranslate if Azure fails
            try:
                greeting = translate_text(base_greeting, chat_language, "en", provider="azure")
            except:
                # If Azure fails, try LibreTranslate
                try:
                    greeting = translate_text(base_greeting, chat_language, "en", provider="libretranslate")
                except:
                    # If both fail, use English
                    greeting = base_greeting
        except Exception:
            # If translation fails for any reason, use English
            greeting = base_greeting
    else:
        greeting = base_greeting
    
    # Add greeting as first message
    greeting_message = ChatMessage(
        role="assistant",
        content=greeting,
        timestamp=datetime.now().isoformat()
    )
    session.messages.append(greeting_message)
    
    # Store PDF data separately (for later use)
    # In production, store in Redis or database
    pdf_data_storage[session_id] = pdf_data
    chat_sessions[session_id] = session
    
    # Get available models
    try:
        available_models = chat_service.get_available_models()
    except:
        available_models = []
    
    return ChatStartResponse(
        session_id=session_id,
        available_models=available_models,
        recommended_model=recommended_model,
        pdf_info=pdf_info
    )


@app.post("/chat/message", response_model=ChatResponse)
async def send_chat_message(request: ChatMessageRequest):
    """
    Send a message in a chat session.
    
    Args:
        request: Chat message request
        
    Returns:
        Chat response
    """
    from datetime import datetime
    
    # Get session
    session = chat_sessions.get(request.session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Chat session {request.session_id} not found"
        )
    
    # Get PDF data from storage
    pdf_data = pdf_data_storage.get(request.session_id)
    if not pdf_data:
        raise HTTPException(
            status_code=400,
            detail="PDF data not available for this session"
        )
    
    # Add user message to history
    user_message = ChatMessage(
        role="user",
        content=request.message,
        timestamp=datetime.now().isoformat()
    )
    session.messages.append(user_message)
    
    # Prepare context with both text and images for full PDF context
    try:
        # Always use visual context to support both text and images
        # Get full text from PDF (no character limit for comprehensive context)
        pdf_text = pdf_context_service.get_pdf_text(pdf_data, max_chars=None)
        
        # Get PDF pages as images
        # For large PDFs, limit to first 15 pages for performance, but include full text
        pdf_info = session.pdf_info or {}
        total_pages = pdf_info.get("pages", 10)
        max_image_pages = min(15, total_pages)  # Limit images but not text
        
        images = pdf_context_service.get_pdf_pages_as_images(
            pdf_data,
            max_pages=max_image_pages
        )
        
        # Build language instruction - enforce responding ONLY in the selected chat language
        chat_lang = session.chat_language or session.target_language or "en"
        # Make the language instruction very explicit and strict
        language_instruction = f"\n\nIMPORTANT: You MUST respond ONLY in {chat_lang}. Do not use any other language. All your responses must be in {chat_lang}."
        
        # Prepare system prompt with both text and images
        # Limit text to 500k chars for prompt size
        text_for_prompt = pdf_text[:500000] if len(pdf_text) > 500000 else pdf_text
        
        system_content = f"""You are a helpful assistant that can analyze PDF documents. 
You have access to both the extracted text content and visual images of the PDF pages.
The extracted text from the PDF is:
{text_for_prompt}

You will also receive images of the PDF pages. Use both the text content and visual information to provide comprehensive answers.
Answer questions based on this content, and reference specific information from the document when possible.

{language_instruction}"""
        
        # Prepare messages for visual chat with text context
        messages = [
            {
                "role": "system",
                "content": system_content
            }
        ]
        
        # Add conversation history (excluding the greeting and current user message)
        # Skip the first message (greeting) and the last one (current user message)
        for msg in session.messages[1:-1]:  # Skip greeting (index 0) and current user message (last)
            messages.append({
                "role": msg.role,
                "content": msg.content
            })
        
        # Add current user message with images
        user_content = f"Here are the PDF page images. Please answer this question: {request.message}"
        messages.append({
            "role": "user",
            "content": user_content
        })
        
        # Get response using visual context (which includes both text and images)
        if request.stream:
            response_text = chat_service.chat_with_visual_context(
                messages=messages,
                images=images,
                model=session.model,
                stream=False
            )
        else:
            response_text = chat_service.chat_with_visual_context(
                messages=messages,
                images=images,
                model=session.model,
                stream=False
            )
        
        # Add assistant response to history
        assistant_message = ChatMessage(
            role="assistant",
            content=response_text,
            timestamp=datetime.now().isoformat()
        )
        session.messages.append(assistant_message)
        
        return ChatResponse(
            session_id=request.session_id,
            message=response_text,
            model=session.model,
            finish_reason="stop"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get chat response: {str(e)}"
        )


@app.get("/chat/session/{session_id}", response_model=ChatSession)
async def get_chat_session(session_id: str):
    """Get chat session history."""
    session = chat_sessions.get(session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Chat session {session_id} not found"
        )
    # Remove PDF data before returning (don't send binary data in response)
    session_dict = session.model_dump()
    return session_dict


@app.delete("/chat/session/{session_id}")
async def delete_chat_session(session_id: str):
    """Clear a chat session."""
    if session_id in chat_sessions:
        del chat_sessions[session_id]
    if session_id in pdf_data_storage:
        del pdf_data_storage[session_id]
    if session_id in chat_sessions or session_id in pdf_data_storage:
        return {"status": "deleted", "session_id": session_id}
    else:
        raise HTTPException(
            status_code=404,
            detail=f"Chat session {session_id} not found"
        ) 