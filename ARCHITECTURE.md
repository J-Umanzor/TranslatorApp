# TranslatorApp Architecture

## 1. System overview

TranslatorApp is a two-tier application:

- **Frontend (Next.js)**: user interface for PDF upload, translation workflow, result viewing, and chat interaction.
- **Backend (FastAPI)**: PDF analysis, OCR, translation orchestration, PDF reconstruction, and chat context generation.

External providers are used for translation and LLM functionality.

## 2. High-level component model

```text
[Browser / Next.js UI]
    |
    | HTTP (JSON + multipart form-data)
    v
[FastAPI Backend]
    |- extraction service (digital/scanned detection + OCR)
    |- translation service (Azure/LibreTranslate providers)
    |- PDF processors (digital redaction/replace, scanned overlay)
    |- chat service (Ollama/Gemini)
    |- PDF context service (text + page images)
    |
    +--> Azure Translator (optional)
    +--> LibreTranslate (optional, self-hosted)
    +--> Ollama (optional, local)
    +--> Google Gemini API (optional)
```

## 3. Frontend architecture

### 3.1 Routes

- `/` (`frontend/app/page.tsx`)
  - Uploads PDF
  - Calls `/extract` for detection and preview
  - Calls `/translate` to produce translated output
- `/results` (`frontend/app/results/page.tsx`)
  - Displays translation metadata and text
  - Renders translated PDF viewer
  - Embeds chat component for translated context
- `/chat` (`frontend/app/chat/page.tsx`)
  - Standalone chat-first page over uploaded PDF

### 3.2 State and storage

- **In-memory React state** for transient UI state (upload progress, errors, selected provider/model).
- **`sessionStorage`** for lightweight translation results:
  - `originalText`, `translatedText`, `metadata`
- **IndexedDB (`TranslationDB`, store `pdfs`)** for large PDF base64 payloads:
  - `originalPdf`, `translatedPdf`

### 3.3 API client

`frontend/lib/chat-api.ts` centralizes chat API calls:
- `getAvailableModels`
- `startChat`
- `sendChatMessage`
- `getChatSession`
- `deleteChatSession`

## 4. Backend architecture

### 4.1 API layer

`backend/app/main.py` defines endpoints and orchestrates services:

- Health:
  - `GET /health`
  - `GET /health/libretranslate`
- Translation pipeline:
  - `POST /extract`
  - `POST /translate`
  - `POST /upload` (file response variant)
- Chat pipeline:
  - `GET /chat/models`
  - `POST /chat/start`
  - `POST /chat/message`
  - `GET /chat/session/{session_id}`
  - `DELETE /chat/session/{session_id}`

### 4.2 Service modules

- `services/extraction.py`
  - Detects scanned vs digital PDFs
  - Extracts text directly for digital PDFs
  - Uses OCR for scanned PDFs
  - Provides OCR text blocks with bounding boxes

- `services/translation_service.py`
  - Provider abstraction (`TranslationProvider`)
  - Implementations:
    - `AzureTranslationProvider`
    - `LibreTranslateProvider`
  - Batch and single-text translation methods

- `pdf_processor.py`
  - `PdfTranslator` class for layout-preserving translation
  - Digital PDF strategy:
    - extract span-level text + formatting
    - redact source text objects
    - insert translated text with style and links

- `services/pdf_context_service.py`
  - Builds chat context from PDFs:
    - full/partial text extraction
    - page rasterization to base64 PNG images
    - PDF metadata summary

- `services/chat_service.py`
  - Provider abstraction at service method level for:
    - Ollama local models
    - Gemini cloud models
  - Model listing, selection, and chat execution (text/visual)

- `services/language_detection.py`
  - Language detection via `langdetect`

### 4.3 Data models

`backend/app/models.py` defines pydantic models for chat requests/responses and session/message structure.

## 5. Core processing flows

### 5.1 Extract flow (`POST /extract`)

1. Validate PDF content type and size (max 50MB).
2. Open PDF with PyMuPDF.
3. Detect scanned vs digital (`is_scanned`).
4. Extract preview text (OCR for scanned; native extraction for digital).
5. Detect language.
6. Return pages, kind, preview, and language.

### 5.2 Translate flow (`POST /translate`)

1. Validate input and provider.
2. Open PDF and detect type.
3. For **digital** PDFs:
   - extract span-level text/format
   - batch translate via provider
   - redact + insert translated text
4. For **scanned** PDFs:
   - OCR with bounding boxes
   - batch translate
   - overlay white boxes and reinsert translated text
5. Return metadata, original/translated text, and optional translated PDF base64.

### 5.3 Chat flow (`/chat/start`, `/chat/message`)

1. Start session with uploaded PDF or base64 payload.
2. Compute `pdf_info` and select/recommend model.
3. Persist session in in-memory maps:
   - `chat_sessions`
   - `pdf_data_storage`
4. On message:
   - append user message
   - build context (full text + page images)
   - call provider (Ollama/Gemini) with visual context
   - append assistant response

## 6. Integrations and boundaries

### 6.1 Translation providers

- **Azure Translator**
  - Requires key/endpoint/region in `.env`
  - Used as default provider in translation endpoints
- **LibreTranslate**
  - Self-hosted endpoint via `LIBRETRANSLATE_URL`
  - Connection checked before requests

### 6.2 LLM providers

- **Ollama**: local runtime (`OLLAMA_BASE_URL`)
- **Gemini**: cloud via API key (`GEMINI_API_KEY`)

### 6.3 OCR and fonts

- OCR uses Tesseract via `pytesseract`.
- CJK rendering paths depend on font files under `backend/fonts`.

## 7. Operational characteristics and constraints

- Max upload size: **50MB**
- Chat sessions are **process-local in-memory state** (not durable, not shared across replicas).
- Large PDFs in chat are constrained by image-page limits for performance.
- Build-time frontend dependency on Google Fonts network (`fonts.googleapis.com`).

## 8. Security and reliability notes

- Input validation is applied to file type/size and required fields.
- API errors are surfaced through explicit HTTP exceptions.
- No persistent database currently; restart clears chat session state.
- Production hardening opportunities:
  - move sessions to Redis/DB
  - add auth/rate limiting
  - add observability and structured logging
  - externalize configuration and secrets management

## 9. Suggested deployment topology

- **Frontend**: Vercel or Node hosting for Next.js
- **Backend**: containerized FastAPI/Uvicorn service
- **Optional services**:
  - Ollama host (GPU/CPU)
  - LibreTranslate container
- **Shared infrastructure (future)**:
  - Redis for chat session state
  - object storage for uploaded/generated PDFs
