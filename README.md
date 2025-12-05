# AI PDF Translator

Translate PDF documents while preserving formatting. Supports both digital and scanned PDFs with two translation providers: Azure Translator (cloud) and LibreTranslate (self-hosted, free & unlimited). Includes an AI chatbot powered by Ollama for interactive document Q&A.

## 🚀 Quick Start

### Option 1: One-Command Install (No Cloning Required)

**Linux/macOS:**
```bash
curl -fsSL https://raw.githubusercontent.com/J-Umanzor/TranslatorApp/docker/install.sh | bash
```

**Windows (PowerShell):**
```powershell
iwr -useb https://raw.githubusercontent.com/J-Umanzor/TranslatorApp/docker/install.ps1 | iex
```

**Or manually:**
```bash
# Download and run docker-compose
curl -fsSL https://raw.githubusercontent.com/J-Umanzor/TranslatorApp/docker/docker-compose.prod.yml -o docker-compose.prod.yml
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d
```

Then open `http://localhost:3000` in your browser!

### Option 2: Clone and Build from Source

1. **Install Docker Desktop** (if you don't have it): [Download Docker Desktop](https://www.docker.com/products/docker-desktop/)

2. **Clone this repository**:
   ```bash
   git clone https://github.com/J-Umanzor/TranslatorApp.git
   cd TranslatorApp
   git checkout docker  # Switch to docker branch
   ```

3. **Start the application**:
   ```bash
   docker-compose up -d
   ```

4. **Open your browser** and go to: `http://localhost:3000`

## Prerequisites

- **Docker Desktop** - [Download here](https://www.docker.com/products/docker-desktop/)
- **Ollama** (optional, for chatbot feature) - [Download here](https://ollama.ai)
  - After installing, run: `ollama pull llama3.1:8b`

## Optional Configuration

### Azure Translator (Optional)

**For Docker users (one-command install):**

The install script automatically creates a `.env` file template in the current directory. To use Azure Translator:

1. **Edit the `.env` file** that was created in the directory where you ran the install script:
   ```bash
   # On Linux/macOS
   nano .env
   
   # On Windows
   notepad .env
   ```

2. **Add your Azure credentials**:
   ```env
   AZURE_TRANSLATOR_KEY=your_key_here
   AZURE_TRANSLATOR_ENDPOINT=https://api.cognitive.microsofttranslator.com
   AZURE_TRANSLATOR_REGION=your_region_here
   ```

3. **Restart the containers** to apply changes:
   ```bash
   docker-compose -f docker-compose.prod.yml down
   docker-compose -f docker-compose.prod.yml up -d
   ```

**For users who cloned the repository:**

Create a `.env` file in either:
- **Project root** (recommended for Docker): `TranslatorApp/.env`
- **Backend folder** (for local development): `TranslatorApp/backend/.env`

The application will automatically check both locations.

```env
AZURE_TRANSLATOR_KEY=your_key_here
AZURE_TRANSLATOR_ENDPOINT=https://api.cognitive.microsofttranslator.com
AZURE_TRANSLATOR_REGION=your_region_here
OLLAMA_BASE_URL=http://host.docker.internal:11434
DEFAULT_LLM_MODEL=llama3.1:8b
```

**To get Azure Translator credentials:**
1. Go to [Azure Portal](https://portal.azure.com/)
2. Create a "Translator" resource
3. Copy the API key, endpoint, and region to your `.env` file

**Note**: Azure credentials are optional. LibreTranslate (included with Docker) is free and unlimited.

## Useful Commands

- **Stop the application**: `docker-compose down`
- **View logs**: `docker-compose logs -f`
- **Restart**: `docker-compose restart`
- **Rebuild** (after code changes): `docker-compose up --build`

## Chatbot Feature

The application includes an AI chatbot powered by Ollama that allows you to:
- Ask questions about your PDF documents
- Get summaries and extract information
- Chat in the translated PDF's language
- Use full PDF context (text + images)

**Setup:**
1. Install [Ollama](https://ollama.ai)
2. Pull the recommended model: `ollama pull llama3.1:8b`
3. Ensure Ollama is running (usually runs as a background service)
4. Access the chatbot from the results page or via the "Chat" link in the navbar

The chatbot automatically uses visual LLMs to analyze both text content and page images for comprehensive document understanding.
