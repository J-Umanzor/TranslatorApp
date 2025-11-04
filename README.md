# TranslatorApp
## Quick Start (Local Dev)

### 1) Backend - FastAPI

```bash
cd backend
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell
# .venv\Scripts\Activate.ps1

pip install -r requirements.txt

# Install Tesseract OCR (Required for scanned PDF processing)
# Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
# macOS: brew install tesseract
# Linux: sudo apt-get install tesseract-ocr

# Run the API
uvicorn app.main:app --reload --port 8000
```

* Health check: `GET /health` → `{ "status": "ok" }`

### 2) Frontend - Next.js

```bash
cd ../frontend

npm install
npm run dev
```



