"""Step 2a: turn an uploaded paper (PDF or photo) into plain text.

Text PDFs: read directly with pdfplumber.
Scanned PDFs / photos: fall back to Tesseract OCR.
OCR needs Tesseract (and Poppler for PDFs) installed on your computer. See README.
"""
import io

import pdfplumber

MIN_CHARS_PER_PAGE = 40  # fewer than this and we assume the page is a scan


def _ocr_image(pil_image):
    import pytesseract
    return pytesseract.image_to_string(pil_image)


def _ocr_pdf_page(file_bytes, page_number):
    from pdf2image import convert_from_bytes
    images = convert_from_bytes(file_bytes, dpi=200, first_page=page_number, last_page=page_number)
    return _ocr_image(images[0]) if images else ""


def extract_text(filename, file_bytes):
    """Returns (text, used_ocr). Raises a readable error if nothing works."""
    name = filename.lower()
    if name.endswith((".png", ".jpg", ".jpeg")):
        from PIL import Image
        return _ocr_image(Image.open(io.BytesIO(file_bytes))), True

    if not name.endswith(".pdf"):
        raise ValueError(f"{filename}: only PDF, PNG and JPG files are supported.")

    pages, used_ocr = [], False
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if len(text.strip()) < MIN_CHARS_PER_PAGE:
                try:
                    text = _ocr_pdf_page(file_bytes, i)
                    used_ocr = True
                except Exception as e:  # OCR tools missing
                    raise RuntimeError(
                        f"{filename}: page {i} looks scanned but OCR failed ({e}). "
                        "Install Tesseract and Poppler, see README."
                    )
            pages.append(text)
    return "\n".join(pages), used_ocr
