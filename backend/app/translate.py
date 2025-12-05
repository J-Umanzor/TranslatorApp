"""
Azure Translator Service Module
Handles text translation using Azure AI Translation SDK
"""
import os
from typing import List
from azure.ai.translation.text import TextTranslationClient
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables - check both project root and backend folder
backend_dir = Path(__file__).parent.parent  # backend/
project_root = backend_dir.parent  # project root
# Try project root first (for Docker), then backend folder (for local dev)
env_paths = [project_root / '.env', backend_dir / '.env']
for env_path in env_paths:
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        break
else:
    # If neither exists, try loading from default locations (current directory, etc.)
    load_dotenv()

# Azure Translator configuration
AZURE_TRANSLATOR_KEY = os.getenv("AZURE_TRANSLATOR_KEY")
AZURE_TRANSLATOR_ENDPOINT = os.getenv("AZURE_TRANSLATOR_ENDPOINT")
AZURE_TRANSLATOR_REGION = os.getenv("AZURE_TRANSLATOR_REGION")


def get_translator_client() -> TextTranslationClient:
    """
    Initialize and return Azure Translator client using SDK.
    
    Returns:
        TextTranslationClient: Initialized Azure translator client
        
    Raises:
        ValueError: If credentials are not configured
    """
    if not AZURE_TRANSLATOR_KEY or not AZURE_TRANSLATOR_ENDPOINT:
        raise ValueError(
            "Azure Translator credentials not configured. "
            "Please set AZURE_TRANSLATOR_KEY, AZURE_TRANSLATOR_ENDPOINT, "
            "and AZURE_TRANSLATOR_REGION in your .env file."
        )
    
    credential = AzureKeyCredential(AZURE_TRANSLATOR_KEY)
    return TextTranslationClient(
        endpoint=AZURE_TRANSLATOR_ENDPOINT,
        credential=credential,
        region=AZURE_TRANSLATOR_REGION
    )


def translate_text_batch(texts: List[str], target_lang: str) -> List[str]:
    """
    Translate a batch of text strings using Azure Translator API.
    
    Args:
        texts: List of text strings to translate
        target_lang: Target language code (e.g., 'es', 'fr', 'de')
        
    Returns:
        List of translated text strings in the same order as input
        
    Raises:
        HttpResponseError: If Azure API returns an error
        Exception: For other translation failures
    """
    if not texts:
        return []
    
    # Clean texts - ensure all are strings
    cleaned_texts = [str(t) if t else "" for t in texts]
    
    try:
        client = get_translator_client()
        translated: List[str] = []
        
        # Azure Translator can handle up to 100 texts per request
        # But we'll use smaller chunks for better reliability
        chunk_size = 50
        
        for start in range(0, len(cleaned_texts), chunk_size):
            chunk = cleaned_texts[start:start + chunk_size]
            
            # Prepare request body
            body = [{"text": text} for text in chunk]
            
            # Call Azure Translator API
            response = client.translate(
                body=body,
                to_language=[target_lang]
            )
            
            # Extract translated texts
            for translation_result in response:
                if translation_result.translations and len(translation_result.translations) > 0:
                    translated.append(translation_result.translations[0].text)
                else:
                    # If translation failed for this item, keep empty string
                    translated.append("")
        
        return translated
        
    except HttpResponseError as e:
        raise HttpResponseError(f"Azure Translator API error: {str(e)}")
    except Exception as e:
        raise Exception(f"Translation failed: {str(e)}")

