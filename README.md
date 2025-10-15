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



