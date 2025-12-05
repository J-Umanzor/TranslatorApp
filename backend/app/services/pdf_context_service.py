"""
PDF Context Service Module
Handles extraction of text and images from PDFs for chat context
"""
import base64
import io
from typing import List, Optional, Tuple
import fitz
from fastapi import HTTPException

from app.services.extraction import (
    extract_text,
    extract_text_from_scanned_pdf,
    is_scanned,
)


class PDFContextService:
    """Service for extracting context from PDFs for chat"""
    
    @staticmethod
    def get_pdf_text(
        pdf_data: bytes,
        max_chars: Optional[int] = None,
        use_ocr: bool = True
    ) -> str:
        """
        Extract full text from PDF.
        
        Args:
            pdf_data: PDF file bytes
            max_chars: Maximum characters to extract (None for all, or very high limit like 500000)
            use_ocr: Whether to use OCR for scanned PDFs
            
        Returns:
            Extracted text
        """
        try:
            doc = fitz.open(stream=pdf_data, filetype="pdf")
            scanned = is_scanned(doc)
            
            if scanned and use_ocr:
                # Use OCR for scanned PDFs
                text = extract_text_from_scanned_pdf(
                    doc,
                    max_chars=max_chars or 500000,  # Increased limit for full text
                    max_pages=len(doc)
                )
            else:
                # Extract text directly for digital PDFs
                # If max_chars is None, extract all text
                if max_chars is None:
                    # Extract all text from all pages
                    parts = []
                    for page in doc:
                        page_text = page.get_text("text")
                        if page_text:
                            parts.append(page_text)
                    text = "".join(parts)
                else:
                    text = extract_text(doc, max_chars=max_chars)
            
            doc.close()
            return text
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to extract text from PDF: {str(e)}"
            )
    
    @staticmethod
    def get_pdf_pages_as_images(
        pdf_data: bytes,
        max_pages: Optional[int] = None,
        dpi: int = 150
    ) -> List[str]:
        """
        Convert PDF pages to base64-encoded images.
        
        Args:
            pdf_data: PDF file bytes
            max_pages: Maximum number of pages to convert (None for all)
            dpi: Resolution for image conversion
            
        Returns:
            List of base64-encoded image strings
        """
        try:
            doc = fitz.open(stream=pdf_data, filetype="pdf")
            images = []
            
            pages_to_process = min(len(doc), max_pages or len(doc))
            
            # Calculate matrix for desired DPI (default 150 DPI)
            # PyMuPDF uses 72 DPI as base, so 150/72 = ~2.08
            zoom = dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)
            
            for page_num in range(pages_to_process):
                page = doc[page_num]
                
                # Render page as image
                pix = page.get_pixmap(matrix=mat)
                
                # Convert to PNG bytes
                img_bytes = pix.tobytes("png")
                
                # Encode as base64
                img_base64 = base64.b64encode(img_bytes).decode("utf-8")
                images.append(img_base64)
            
            doc.close()
            return images
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to convert PDF pages to images: {str(e)}"
            )
    
    @staticmethod
    def get_pdf_summary(
        pdf_data: bytes,
        max_chars: int = 2000
    ) -> str:
        """
        Get a summary of the PDF content (first portion of text).
        
        Args:
            pdf_data: PDF file bytes
            max_chars: Maximum characters for summary
            
        Returns:
            Summary text
        """
        text = PDFContextService.get_pdf_text(pdf_data, max_chars=max_chars)
        if len(text) > max_chars:
            return text[:max_chars] + "..."
        return text
    
    @staticmethod
    def get_pdf_info(pdf_data: bytes) -> dict:
        """
        Get basic information about the PDF.
        
        Args:
            pdf_data: PDF file bytes
            
        Returns:
            Dictionary with PDF metadata
        """
        try:
            doc = fitz.open(stream=pdf_data, filetype="pdf")
            scanned = is_scanned(doc)
            
            info = {
                "pages": len(doc),
                "kind": "scanned" if scanned else "digital",
                "has_text": False,
            }
            
            # Check if PDF has extractable text
            if not scanned:
                text = extract_text(doc, max_chars=100)
                info["has_text"] = len(text.strip()) > 0
            
            doc.close()
            return info
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get PDF info: {str(e)}"
            )

