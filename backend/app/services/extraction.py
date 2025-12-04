import io
from typing import List, Dict, Tuple, Any

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


def extract_text_with_boxes_from_scanned_pdf(
    doc: fitz.Document, max_pages: int = 10
) -> List[List[Dict[str, Any]]]:
    """
    Extract text with bounding boxes from scanned PDF using OCR.
    
    Returns a list of pages, where each page contains a list of text blocks
    with their bounding boxes and formatting information.
    
    Each block is a dict with:
    - text: str
    - bbox: tuple (x0, y0, x1, y1) in PDF coordinates
    - confidence: float
    - font_size: float (estimated)
    """
    pages_data: List[List[Dict[str, Any]]] = []
    pages_to_process = min(len(doc), max_pages)
    
    for page_num in range(pages_to_process):
        page = doc[page_num]
        page_rect = page.rect
        
        # Render page at higher resolution for better OCR
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat)
        
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))
        
        try:
            # Get detailed OCR data with bounding boxes
            # Using image_to_data to get word-level bounding boxes
            ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            
            page_blocks = []
            current_line_blocks = []
            last_y = None
            last_x_end = None  # Track the right edge of the last word
            avg_font_size = 12  # Default font size
            avg_word_width = 0  # Track average word width for gap detection
            
            # Process OCR data to group words into lines and blocks
            for i in range(len(ocr_data['text'])):
                text = ocr_data['text'][i].strip()
                conf = int(ocr_data['conf'][i])
                
                # Skip empty text or low confidence
                if not text or conf < 30:
                    continue
                
                # Get bounding box in image coordinates (scaled by 2x)
                left = ocr_data['left'][i]
                top = ocr_data['top'][i]
                width = ocr_data['width'][i]
                height = ocr_data['height'][i]
                
                # Convert from image coordinates to PDF coordinates
                # Image is 2x scale, so divide by 2
                x0 = left / 2.0
                y0 = top / 2.0
                x1 = (left + width) / 2.0
                y1 = (top + height) / 2.0
                
                # Estimate font size from height
                font_size = max(8, min(height / 2.0, 24))
                word_width = x1 - x0
                
                # Group words into lines (similar y-coordinates)
                # Use average font size from current line or this word's font size
                line_threshold = avg_font_size * 0.5 if current_line_blocks else font_size * 0.5
                
                # Check if this is a new line (different y-coordinate)
                is_new_line = last_y is None or abs(y0 - last_y) > line_threshold
                
                # Check horizontal gap - if words are too far apart, start a new block
                # Calculate gap between last word's right edge and this word's left edge
                horizontal_gap = None
                if last_x_end is not None and not is_new_line:
                    horizontal_gap = x0 - last_x_end
                    # If gap is more than 3x the average word width, treat as separate blocks
                    # Also check if gap is more than 50 points (reasonable threshold for separate text blocks)
                    max_gap = max(avg_word_width * 3, 50)
                    if horizontal_gap > max_gap:
                        # Words are too far apart horizontally - start a new block
                        is_new_line = True
                
                if is_new_line:
                    # New line or separate block - save previous line if exists
                    if current_line_blocks:
                        # Merge line blocks into a single block
                        line_text = " ".join([b['text'] for b in current_line_blocks])
                        min_x = min([b['bbox'][0] for b in current_line_blocks])
                        min_y = min([b['bbox'][1] for b in current_line_blocks])
                        max_x = max([b['bbox'][2] for b in current_line_blocks])
                        max_y = max([b['bbox'][3] for b in current_line_blocks])
                        
                        # Calculate average font size for the line
                        line_font_size = sum([b['font_size'] for b in current_line_blocks]) / len(current_line_blocks)
                        
                        page_blocks.append({
                            'text': line_text,
                            'bbox': (min_x, min_y, max_x, max_y),
                            'confidence': sum([b['confidence'] for b in current_line_blocks]) / len(current_line_blocks),
                            'font_size': line_font_size,
                            'is_bold': False,  # OCR doesn't detect bold
                            'color': '#000000'  # Default black
                        })
                    current_line_blocks = []
                    last_y = y0
                    last_x_end = None
                    avg_font_size = font_size
                    avg_word_width = word_width
                
                current_line_blocks.append({
                    'text': text,
                    'bbox': (x0, y0, x1, y1),
                    'confidence': conf,
                    'font_size': font_size
                })
                
                # Update tracking variables
                last_x_end = x1  # Update to this word's right edge
                if current_line_blocks:
                    avg_font_size = sum([b['font_size'] for b in current_line_blocks]) / len(current_line_blocks)
                    # Update average word width for gap detection
                    avg_word_width = sum([b['bbox'][2] - b['bbox'][0] for b in current_line_blocks]) / len(current_line_blocks)
            
            # Add remaining line
            if current_line_blocks:
                line_text = " ".join([b['text'] for b in current_line_blocks])
                min_x = min([b['bbox'][0] for b in current_line_blocks])
                min_y = min([b['bbox'][1] for b in current_line_blocks])
                max_x = max([b['bbox'][2] for b in current_line_blocks])
                max_y = max([b['bbox'][3] for b in current_line_blocks])
                
                # Calculate average font size for the line
                line_font_size = sum([b['font_size'] for b in current_line_blocks]) / len(current_line_blocks)
                
                page_blocks.append({
                    'text': line_text,
                    'bbox': (min_x, min_y, max_x, max_y),
                    'confidence': sum([b['confidence'] for b in current_line_blocks]) / len(current_line_blocks),
                    'font_size': line_font_size,
                    'is_bold': False,
                    'color': '#000000'
                })
            
            pages_data.append(page_blocks)
            
        except pytesseract.TesseractNotFoundError as exc:
            raise HTTPException(
                status_code=500,
                detail="Tesseract OCR is not installed. Please install Tesseract OCR on your system.",
            ) from exc
        except Exception as exc:
            print(f"OCR failed for page {page_num + 1}: {exc}")
            pages_data.append([])  # Add empty page on error
            continue
    
    return pages_data

