# AI PDF Translator

Translate PDF documents while preserving formatting. Supports both digital and scanned PDFs with two translation providers: Azure Translator (cloud) and LibreTranslate (self-hosted, free & unlimited). Includes an AI chatbot powered by Ollama for interactive document Q&A.

## Prerequisites

- **Python 3.8+**
- **Node.js 18+** and npm
- **Tesseract OCR** (for scanned PDFs)
  - Windows: Download from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki)
  - macOS: `brew install tesseract`
  - Linux: `sudo apt-get install tesseract-ocr`
- **Ollama** (for chatbot feature - optional if using Gemini)
  - Download from [ollama.ai](https://ollama.ai)
  - Recommended model: `ollama pull llama3.1:8b`
- **Google Gemini API Key** (optional, for cloud-based chatbot)
  - Get from [Google AI Studio](https://makersuite.google.com/app/apikey)
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
OLLAMA_BASE_URL=http://localhost:11434
DEFAULT_LLM_MODEL=llama3.1:8b
GEMINI_API_KEY=your_gemini_api_key_here  # Optional, only needed for Gemini provider
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
.venv\Scripts\Activate.ps1
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

**Terminal 4 - Ollama (for chatbot):**
```bash
# Make sure Ollama is running (usually runs as a service)
# Download recommended model:
ollama pull llama3.1:8b
```

Open `http://localhost:3000` in your browser.


## Getting Azure Translator Credentials

1. Go to [Azure Portal](https://portal.azure.com/)
2. Create a "Translator" resource
3. Copy the API key, endpoint, and region to your `.env` file

**Note**: Azure credentials are only needed if using Azure Translator. LibreTranslate is free and unlimited when self-hosted.

## Chatbot Feature

The application includes an AI chatbot that supports two providers: **Ollama** (local, free) and **Google Gemini** (cloud, requires API key). The chatbot allows you to:
- Ask questions about your PDF documents
- Get summaries and extract information
- Chat in the translated PDF's language
- Use full PDF context (text + images)

### Option 1: Ollama (Local, Free)

**Setup:**
1. Install [Ollama](https://ollama.ai)
2. Pull the recommended model: `ollama pull llama3.1:8b`
3. Ensure Ollama is running (usually runs as a background service)
4. Set `provider=ollama` when starting a chat session

### Option 2: Google Gemini (Cloud)

**Setup:**
1. Get a Gemini API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Add to your `backend/.env` file:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   ```
3. Install the dependency: `pip install google-generativeai`
4. Set `provider=gemini` when starting a chat session

**Default Models:**
- Ollama: `llama3.1:8b` (text) or `llava` (visual)
- Gemini: `gemini-1.5-pro` (supports both text and visual)

You can override these by setting environment variables:
- `DEFAULT_LLM_MODEL` (Ollama text model)
- `DEFAULT_VISUAL_LLM_MODEL` (Ollama visual model)
- `DEFAULT_GEMINI_MODEL` (Gemini model)
- `DEFAULT_GEMINI_VISUAL_MODEL` (Gemini visual model)

The chatbot automatically uses visual capabilities to analyze both text content and page images for comprehensive document understanding.
