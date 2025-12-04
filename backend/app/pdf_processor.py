"""
PDF Processing Module
Handles in-place PDF translation using PyMuPDF (fitz)
Uses "Redact and Replace" logic (same approach as argos-translate-files):

1. Detailed Extraction:
   - Uses page.get_text("dict") to capture text coordinates, font size, color, and flags
   - Span-level extraction preserves individual formatting

2. Clean Redaction:
   - Uses page.add_redact_annot(rect) to mark areas for removal
   - Uses page.apply_redactions() to actually remove text objects (not white box overlays)
   - Preserves background images while removing text

3. Styled Insertion:
   - Uses page.insert_htmlbox() with dynamic CSS for translated text
   - CSS constructed from extracted font size, color, and bold flags
   - Supports automatic text wrapping and styling

4. Additional Features:
   - Link preservation
   - Rectangle expansion based on translation length
"""
import fitz
from typing import List, Optional, Dict, Any
from pathlib import Path
from app.services.translation_service import translate_texts


def _decimal_to_hex_color(decimal_color: int) -> str:
    """Convert decimal color to hex format."""
    if decimal_color == 0:
        return '#000000'
    hex_color = hex(decimal_color)[2:]
    hex_color = hex_color.zfill(6)
    return f'#{hex_color}'




class PdfTranslator:
    """
    PDF Translator class that preserves formatting during translation.
    Based on argos-translate-files implementation.
    """
    
    def __init__(self, pdf_path: str, output_path: str, target_lang: str, provider: str = "azure"):
        self.pdf_path = pdf_path
        self.output_path = output_path
        self.target_lang = target_lang
        self.provider = provider
        self.doc = fitz.open(pdf_path)
        self.pages_data: List[List[List[Any]]] = []
    
    def translate_pdf(self):
        """Main translation workflow."""
        self._extract_text_from_pages()
        self._translate_pages_data()
        self._apply_translations_to_pdf()
        self._save_translated_pdf()
    
    def _extract_text_from_pages(self):
        """Extract text from all pages."""
        page_count = self.doc.page_count
        for page_num in range(page_count):
            self._extract_text_with_pymupdf(page_num)
    
    def _extract_text_with_pymupdf(self, page_num: int):
        """
        Extract text with formatting information from a page using get_text("dict").
        
        Uses structured dict format to capture:
        - Text coordinates (bbox)
        - Font size
        - Text color
        - Font flags (bold/italic)
        """
        # Ensure pages_data list is large enough
        while len(self.pages_data) <= page_num:
            self.pages_data.append([])
        
        page = self.doc.load_page(page_num)
        
        # Extract links for preservation
        links = page.get_links()
        link_map: Dict[fitz.Rect, Dict[str, Any]] = {}
        for link in links:
            rect = fitz.Rect(link["from"])
            link_map[rect] = {
                "uri": link.get("uri", ""),
                "page": link.get("page", -1),
                "to": link.get("to", None),
                "kind": link.get("kind", 0)
            }
        
        # Extract blocks with structured dict format to get font size, color, and flags
        blocks = page.get_text("dict")["blocks"]
        
        # Extract at span level to preserve individual formatting
        for block in blocks:
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        text = span.get("text", "").strip()
                        
                        # Skip empty text
                        if text:
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
                            self.pages_data[page_num].append([
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
    
    def _translate_pages_data(self):
        """Translate all extracted text spans."""
        try:
            # Collect all texts for batch translation
            all_texts = []
            text_indices = []  # Track (page_idx, block_idx) for each text
            
            for page_idx, page_blocks in enumerate(self.pages_data):
                for block_idx, block in enumerate(page_blocks):
                    all_texts.append(block[0])
                    text_indices.append((page_idx, block_idx))
            
            # Batch translate all texts
            if all_texts:
                translated_texts = translate_texts(all_texts, self.target_lang, provider=self.provider)
                
                # Assign translations back to blocks
                for (page_idx, block_idx), translated_text in zip(text_indices, translated_texts):
                    self.pages_data[page_idx][block_idx][2] = translated_text
        except Exception as e:
            # Fallback: use original text in case of translation errors
            for page_blocks in self.pages_data:
                for block in page_blocks:
                    block[2] = block[0]
    
    def _apply_translations_to_pdf(self):
        """
        Apply translations to the PDF using proper redaction and replace logic.
        
        Uses the "Redact and Replace" approach:
        1. Mark all text areas for redaction using add_redact_annot()
        2. Apply all redactions at once to actually remove text objects
        3. Insert translated text with HTML formatting
        """
        for page_index, blocks in enumerate(self.pages_data):
            if not blocks:
                continue
            
            page = self.doc.load_page(page_index)
            
            # Separate bold and normal blocks for proper styling
            normal_blocks = []
            bold_blocks = []
            
            # First pass: prepare all blocks and mark areas for redaction
            for block in blocks:
                coords = block[1]
                translated_text = block[2] if block[2] is not None else block[0]
                
                # Calculate expansion factor based on text length ratio
                original_text = block[0]
                len_ratio = min(1.05, max(1.01, len(translated_text) / max(1, len(original_text))))
                
                x0, y0, x1, y1 = coords
                width = x1 - x0
                height = y1 - y0
                
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
                # This marks the text for removal without actually removing it yet
                page.add_redact_annot(rect)
                
                is_bold = len(block) > 6 and block[6]
                if is_bold:
                    bold_blocks.append((block, enlarged_coords))
                else:
                    normal_blocks.append((block, enlarged_coords))
            
            # Apply all redactions for this page at once (clean removal of text objects)
            # This is the key improvement: removes text objects instead of just painting over them
            # The images parameter preserves background images while removing text
            try:
                # Try to use PDF_REDACT_IMAGE_NONE to preserve background images
                try:
                    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
                except (AttributeError, TypeError):
                    # If PDF_REDACT_IMAGE_NONE constant doesn't exist or parameter not supported
                    # Try without the images parameter
                    page.apply_redactions()
            except Exception as e:
                # If redaction fails, raise an error rather than falling back to white boxes
                raise Exception(f"Failed to apply redactions on page {page_index}: {str(e)}")
            
            # Insert text blocks with proper styling after redaction
            self._insert_styled_text_blocks(page, normal_blocks, is_bold=False)
            self._insert_styled_text_blocks(page, bold_blocks, is_bold=True)
    
    def _insert_styled_text_blocks(self, page: fitz.Page, blocks: List, is_bold: bool):
        """
        Insert text blocks with preserved styling using insert_htmlbox().
        
        Uses HTML insertion with CSS to support:
        - Font size preservation
        - Color preservation
        - Bold/italic styling
        - Automatic text wrapping
        - Link preservation
        """
        if not blocks:
            return
        
        font_weight = "bold" if is_bold else "normal"
        
        for block_data in blocks:
            block, enlarged_coords = block_data
            translated_text = block[2] if block[2] is not None else block[0]
            angle = block[3] if len(block) > 3 else 0
            color = block[4] if len(block) > 4 else '#000000'
            text_indent = block[5] if len(block) > 5 else 0
            font_size = block[7] if len(block) > 7 else 12
            link_info = block[8] if len(block) > 8 else None
            
            rect = fitz.Rect(*enlarged_coords)
            
            # Handle links
            if link_info:
                if link_info.get("uri"):
                    translated_text = f'<a href="{link_info["uri"]}" style="color: {color}; text-decoration: underline;">{translated_text}</a>'
                elif link_info.get("page", -1) >= 0:
                    page_num = link_info["page"]
                    translated_text = f'<a href="#page{page_num}" style="color: {color}; text-decoration: underline;">{translated_text}</a>'
            
            # CSS for styling - dynamically constructed from extracted font properties
            css = f"""
            * {{
                color: {color};
                font-weight: {font_weight};
                font-size: {font_size}px;
                text-indent: {text_indent}pt;
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
            html_content = f'<div style="font-size: {font_size}px; color: {color}; font-weight: {font_weight}; text-indent: {text_indent}pt; line-height: 1.2; word-wrap: break-word;">{translated_text}</div>'
            
            try:
                # Primary method: Use HTML insertion for better formatting and automatic wrapping
                page.insert_htmlbox(rect, html_content, css=css, rotate=angle)
                
                # Add link annotation if needed
                if link_info:
                    self._add_link_annotation(page, rect, link_info)
                    
            except Exception as e:
                # Fallback to simple text insertion only if HTML insertion fails
                # This is a last resort, not the primary method
                page.insert_text(rect.tl, translated_text, fontsize=font_size)
                
                # Add link annotation if needed
                if link_info:
                    self._add_link_annotation(page, rect, link_info)
    
    def _add_link_annotation(self, page: fitz.Page, rect: fitz.Rect, link_info: Dict[str, Any]):
        """Add link annotation to the page."""
        try:
            link_dict: Dict[str, Any] = {
                "kind": link_info.get("kind", 1),  # 1 = URI link, 2 = GoTo link
                "from": rect
            }
            
            if link_info.get("uri"):
                link_dict["uri"] = link_info["uri"]
                link_dict["kind"] = 1  # URI link
            elif link_info.get("page", -1) >= 0:
                link_dict["page"] = link_info["page"]
                link_dict["kind"] = 2
                if link_info.get("to"):
                    link_dict["to"] = link_info["to"]
            
            page.insert_link(link_dict)
        except Exception:
            pass  # Silently fail if link insertion fails
    
    def _save_translated_pdf(self):
        """Save the translated PDF."""
        new_doc = fitz.open()
        new_doc.insert_pdf(self.doc)
        new_doc.save(self.output_path, garbage=4, deflate=True)
        new_doc.close()
        self.doc.close()


def process_pdf(input_path: str, target_lang: str, provider: str = "azure") -> str:
    """
    Process a PDF file and translate text in-place using "Redact and Replace" logic.
    
    This function uses proper redaction (not white box overlays):
    1. Extracts text with formatting using page.get_text("dict")
    2. Marks text areas for redaction using page.add_redact_annot()
    3. Applies redactions to actually remove text objects using page.apply_redactions()
    4. Inserts translated text with HTML formatting using page.insert_htmlbox()
    
    Args:
        input_path: Path to the input PDF file
        target_lang: Target language code (e.g., 'es', 'fr', 'de')
        
    Returns:
        Path to the translated PDF file
        
    Raises:
        Exception: If PDF processing fails
    """
    # Generate output path
    input_file = Path(input_path)
    output_path = input_file.parent / f"{input_file.stem}_translated.pdf"
    
    # Create translator and process PDF
    translator = PdfTranslator(
        pdf_path=input_path,
        output_path=str(output_path),
        target_lang=target_lang,
        provider=provider
    )
    
    translator.translate_pdf()
    
    return str(output_path)
