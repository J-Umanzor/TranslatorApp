# TranslatorApp (AI PDF Translator)

TranslatorApp is a full-stack application for translating PDF documents while preserving layout and formatting, with an integrated AI chat assistant for question answering over document content.

## What it does

- Upload and analyze PDF documents (digital and scanned)
- Detect source language from extracted text
- Translate content to a selected target language
- Generate a translated PDF when layout-preserving translation succeeds
- Support two translation providers:
  - **Azure Translator** (cloud)
  - **LibreTranslate** (self-hosted/local)
- Chat with document context using:
  - **Ollama** (local models)
  - **Google Gemini** (cloud models)

## Repository structure

```text
TranslatorApp/
├── backend/                    # FastAPI service (PDF processing + APIs)
│   ├── app/
│   │   ├── main.py             # API endpoints and orchestration
│   │   ├── models.py           # Request/response models
│   │   ├── pdf_processor.py    # Layout-preserving PDF translator class
│   │   ├── services/
│   │   │   ├── extraction.py
│   │   │   ├── translation_service.py
│   │   │   ├── chat_service.py
│   │   │   ├── pdf_context_service.py
│   │   │   └── language_detection.py
│   ├── fonts/                  # CJK font assets used for PDF text insertion
│   └── requirements.txt
├── frontend/                   # Next.js app (UI)
│   ├── app/                    # Home, results, and chat routes
│   ├── components/             # Shared UI components
│   ├── lib/chat-api.ts         # Frontend API client
│   └── package.json
└── README.md
```

## Tech stack

### Backend
- FastAPI + Uvicorn
- PyMuPDF (`fitz`) for PDF parsing/rendering/editing
- Tesseract OCR via `pytesseract` + Pillow for scanned PDFs
- Azure AI Translation SDK
- Requests for LibreTranslate API calls
- `langdetect` for language detection
- Ollama + Google Generative AI SDK for chat

### Frontend
- Next.js 15 + React 18 + TypeScript
- HeroUI components
- Tailwind CSS

## Prerequisites

- **Python 3.8+**
- **Node.js 18+** and npm
- **Tesseract OCR** installed and available in PATH
- Optional services:
  - Azure Translator credentials
  - LibreTranslate server (Docker/local)
  - Ollama runtime + local model(s)
  - Gemini API key

## Setup

## 1) Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate    # Linux/macOS
# .venv\Scripts\Activate.ps1  # Windows PowerShell
pip install -r requirements.txt
```

Create `backend/.env`:

```env
# Translation
AZURE_TRANSLATOR_KEY=your_key_here
AZURE_TRANSLATOR_ENDPOINT=https://api.cognitive.microsofttranslator.com
AZURE_TRANSLATOR_REGION=your_region_here
LIBRETRANSLATE_URL=http://localhost:5000

# Chat
OLLAMA_BASE_URL=http://localhost:11434
DEFAULT_LLM_MODEL=llama3.1:8b
DEFAULT_VISUAL_LLM_MODEL=llava
GEMINI_API_KEY=your_gemini_api_key_here
DEFAULT_GEMINI_MODEL=gemini-2.5-flash-lite
DEFAULT_GEMINI_VISUAL_MODEL=gemini-2.5-flash-lite
```

Run backend:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

## 2) Frontend

```bash
cd frontend
npm install
npm run dev
```

Open: `http://localhost:3000`

## 3) Optional local services

### LibreTranslate

```bash
docker run -ti --rm -p 5000:5000 libretranslate/libretranslate
```

### Ollama

```bash
ollama pull llama3.1:8b
ollama pull llava
```

## Application flow

1. User uploads a PDF on the home page.
2. Frontend calls `POST /extract` for language/type detection and preview.
3. User selects target language/provider and calls `POST /translate`.
4. Backend translates and returns text + optional translated PDF (base64).
5. Frontend stores text in `sessionStorage`, PDFs in `IndexedDB`, and navigates to `/results`.
6. User can open chat, start a session (`/chat/start`), and send messages (`/chat/message`) with PDF context.

## API summary

Backend base URL: `http://127.0.0.1:8000`

- `GET /health`
- `GET /health/libretranslate`
- `POST /upload` (file + target language, returns translated file response)
- `POST /extract` (PDF metadata + text preview + detected language)
- `POST /translate` (PDF + target language + provider)
- `GET /chat/models?provider=ollama|gemini`
- `POST /chat/start`
- `POST /chat/message`
- `GET /chat/session/{session_id}`
- `DELETE /chat/session/{session_id}`

For implementation details, see [`ARCHITECTURE.md`](./ARCHITECTURE.md).

## Development commands

Frontend:

```bash
cd frontend
npm run dev
npm run lint
npm run build
```

Backend (run server):

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

## Notes and limitations

- Max upload size is **50MB**.
- Chat sessions are stored **in-memory** in backend process state (non-persistent).
- Scanned PDFs use OCR and may have lower fidelity than digital PDFs.
- CJK rendering depends on available fonts in `backend/fonts`.
- Frontend uses Google fonts via `next/font/google`; restricted DNS/network to `fonts.googleapis.com` can break production builds.

## Troubleshooting

- **OCR error / Tesseract not found**: install Tesseract and verify executable is in PATH.
- **LibreTranslate unavailable**: start container or update `LIBRETRANSLATE_URL`.
- **Ollama unavailable/model missing**: ensure Ollama service is running and required models are pulled.
- **Gemini errors**: set valid `GEMINI_API_KEY` and ensure package is installed.
- **ESLint module error (`@eslint/compat`)**: ensure dependency exists in frontend dev dependencies before running lint.
