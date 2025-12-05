import os
import platform
import pytesseract

MAX_BYTES = 50 * 1024 * 1024  # 50MB

WINDOWS_TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"C:\Users\{}\AppData\Local\Tesseract-OCR\tesseract.exe".format(os.getenv("USERNAME")),
]


def configure_tesseract() -> None:
    if platform.system() != "Windows":
        return

    try:
        pytesseract.get_tesseract_version()
        return
    except Exception:
        for path in WINDOWS_TESSERACT_PATHS:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                return

    raise RuntimeError(
        "Tesseract OCR is not installed. Please install Tesseract OCR on your system."
    )

