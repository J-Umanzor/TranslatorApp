# AI PDF Translator

Translate PDF documents while preserving formatting. Supports both digital and scanned PDFs with two translation providers: Azure Translator (cloud) and LibreTranslate (self-hosted, free & unlimited).

## Prerequisites

- **Python 3.8+**
- **Node.js 18+** and npm
- **Tesseract OCR** (for scanned PDFs)
  - Windows: Download from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki)
  - macOS: `brew install tesseract`
  - Linux: `sudo apt-get install tesseract-ocr`
- **Docker** (optional, only for LibreTranslate)

## Quick Start

### 1. Backend Setup

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows:
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Create .env file with your Azure Translator credentials
# (Only needed if using Azure Translator)
```

Create `backend/.env`:
```env
AZURE_TRANSLATOR_KEY=your_key_here
AZURE_TRANSLATOR_ENDPOINT=https://api.cognitive.microsofttranslator.com
AZURE_TRANSLATOR_REGION=your_region_here
LIBRETRANSLATE_URL=http://localhost:5000
```

### 2. Frontend Setup

```bash
cd frontend
npm install
```

### 3. Start LibreTranslate (Optional - for free unlimited translations)

```bash
docker run -ti --rm -p 5000:5000 libretranslate/libretranslate
```

### 4. Run the Application

**Terminal 1 - Backend:**
```bash
cd backend
source .venv/bin/activate  # or
 .venv\Scripts\Activate.ps1 on Windows
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

**Terminal 3 - LibreTranslate (if using):**
```bash
docker run -ti --rm -p 5000:5000 libretranslate/libretranslate
```

Open `http://localhost:3000` in your browser.


## Getting Azure Translator Credentials

1. Go to [Azure Portal](https://portal.azure.com/)
2. Create a "Translator" resource
3. Copy the API key, endpoint, and region to your `.env` file

**Note**: Azure credentials are only needed if using Azure Translator. LibreTranslate is free and unlimited when self-hosted.
