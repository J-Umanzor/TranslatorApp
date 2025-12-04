"""
Translation Service Module
Provides unified interface for multiple translation providers (Azure, LibreTranslate)
"""
import os
from typing import List, Optional
from abc import ABC, abstractmethod
import requests
from azure.ai.translation.text import TextTranslationClient
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from dotenv import load_dotenv
from pathlib import Path
from fastapi import HTTPException

# Load environment variables
backend_dir = Path(__file__).parent.parent.parent
env_path = backend_dir / '.env'
load_dotenv(dotenv_path=env_path)

# Configuration
AZURE_TRANSLATOR_KEY = os.getenv("AZURE_TRANSLATOR_KEY")
AZURE_TRANSLATOR_ENDPOINT = os.getenv("AZURE_TRANSLATOR_ENDPOINT")
AZURE_TRANSLATOR_REGION = os.getenv("AZURE_TRANSLATOR_REGION")
LIBRETRANSLATE_URL = os.getenv("LIBRETRANSLATE_URL", "http://localhost:5000")


class TranslationProvider(ABC):
    """Abstract base class for translation providers"""
    
    @abstractmethod
    def translate_text(self, text: str, target_lang: str, source_lang: str = "auto") -> str:
        """Translate a single text string"""
        pass
    
    @abstractmethod
    def translate_texts(self, texts: List[str], target_lang: str, source_lang: str = "auto") -> List[str]:
        """Translate multiple text strings"""
        pass


class AzureTranslationProvider(TranslationProvider):
    """Azure Translator API provider"""
    
    def __init__(self):
        if not AZURE_TRANSLATOR_KEY or not AZURE_TRANSLATOR_ENDPOINT:
            raise HTTPException(
                status_code=500,
                detail="Azure Translator credentials not configured. Please set AZURE_TRANSLATOR_KEY, AZURE_TRANSLATOR_ENDPOINT, and AZURE_TRANSLATOR_REGION in your .env file."
            )
        
        credential = AzureKeyCredential(AZURE_TRANSLATOR_KEY)
        self.client = TextTranslationClient(
            endpoint=AZURE_TRANSLATOR_ENDPOINT,
            credential=credential,
            region=AZURE_TRANSLATOR_REGION
        )
    
    def translate_text(self, text: str, target_lang: str, source_lang: str = "auto") -> str:
        """Translate a single text using Azure Translator"""
        if not text.strip():
            return ""
        
        try:
            # Azure Translator has a limit of 50,000 characters per request
            max_chunk_size = 45000
            text_chunks = []
            
            if len(text) > max_chunk_size:
                # Split by paragraphs
                sentences = text.split('\n\n')
                current_chunk = ""
                
                for sentence in sentences:
                    if len(current_chunk) + len(sentence) + 2 > max_chunk_size:
                        if current_chunk:
                            text_chunks.append(current_chunk)
                        current_chunk = sentence
                    else:
                        current_chunk += "\n\n" + sentence if current_chunk else sentence
                
                if current_chunk:
                    text_chunks.append(current_chunk)
            else:
                text_chunks = [text]
            
            # Translate each chunk
            translated_parts = []
            for chunk in text_chunks:
                if not chunk.strip():
                    continue
                
                response = self.client.translate(
                    body=[{"text": chunk}],
                    to_language=[target_lang]
                )
                
                if response and len(response) > 0:
                    for translation in response:
                        if translation.translations and len(translation.translations) > 0:
                            translated_parts.append(translation.translations[0].text)
            
            return "\n\n".join(translated_parts)
            
        except HttpResponseError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Azure Translator API error: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Translation failed: {str(e)}"
            )
    
    def translate_texts(self, texts: List[str], target_lang: str, source_lang: str = "auto") -> List[str]:
        """Translate multiple texts using Azure Translator"""
        cleaned_texts = [str(t) if t else "" for t in texts]
        if not cleaned_texts:
            return []
        
        translated = []
        chunk_size = 50
        
        try:
            for start in range(0, len(cleaned_texts), chunk_size):
                chunk = cleaned_texts[start:start + chunk_size]
                body = [{"text": text} for text in chunk]
                
                response = self.client.translate(body=body, to_language=[target_lang])
                
                for translation_result in response:
                    if translation_result.translations and len(translation_result.translations) > 0:
                        translated.append(translation_result.translations[0].text)
                    else:
                        translated.append("")
            
            return translated
            
        except HttpResponseError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Azure Translator API error: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Translation failed: {str(e)}"
            )


class LibreTranslateProvider(TranslationProvider):
    """LibreTranslate self-hosted provider"""
    
    def __init__(self, base_url: str = None):
        self.base_url = (base_url or LIBRETRANSLATE_URL).rstrip('/')
        self.timeout = 30  # 30 second timeout
    
    def _check_connection(self) -> bool:
        """Check if LibreTranslate server is available"""
        try:
            response = requests.get(f"{self.base_url}/languages", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def translate_text(self, text: str, target_lang: str, source_lang: str = "auto") -> str:
        """Translate a single text using LibreTranslate"""
        if not text.strip():
            return ""
        
        # Check connection first
        if not self._check_connection():
            raise HTTPException(
                status_code=503,
                detail=f"LibreTranslate server is not available at {self.base_url}. Please ensure LibreTranslate is running."
            )
        
        try:
            # LibreTranslate API endpoint
            url = f"{self.base_url}/translate"
            
            payload = {
                "q": text,
                "source": source_lang if source_lang != "auto" else "auto",
                "target": target_lang,
                "format": "text"
            }
            
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            
            result = response.json()
            return result.get("translatedText", text)
            
        except requests.exceptions.ConnectionError:
            raise HTTPException(
                status_code=503,
                detail=f"Could not connect to LibreTranslate at {self.base_url}. Please ensure LibreTranslate is running."
            )
        except requests.exceptions.Timeout:
            raise HTTPException(
                status_code=504,
                detail="LibreTranslate request timed out. The server may be overloaded."
            )
        except requests.exceptions.HTTPError as e:
            raise HTTPException(
                status_code=500,
                detail=f"LibreTranslate API error: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Translation failed: {str(e)}"
            )
    
    def translate_texts(self, texts: List[str], target_lang: str, source_lang: str = "auto") -> List[str]:
        """
        Translate multiple texts using LibreTranslate.
        
        Groups small text fragments together for better context, which prevents:
        - Missing words (short fragments lack context)
        - Extra spaces (each fragment treated as separate sentence)
        - Poor translation quality (no sentence-level context)
        """
        if not texts:
            return []
        
        # Initialize result list with placeholders
        translated = [""] * len(texts)
        
        # Group consecutive short fragments together for better translation context
        i = 0
        while i < len(texts):
            text = str(texts[i]).strip() if texts[i] else ""
            
            if not text:
                # Empty text - skip
                i += 1
                continue
            
            # Check if this is a short fragment that should be grouped
            # Short = less than 25 chars and doesn't end with sentence punctuation
            # Also check if it's a single word or very short phrase
            is_short = (len(text) < 25 and 
                       not any(text.rstrip().endswith(p) for p in ['.', '!', '?', ':', ';', '\n']) and
                       len(text.split()) <= 3)  # 3 words or less
            
            if is_short:
                # Group consecutive short fragments together
                group_texts = [text]
                group_indices = [i]
                group_lengths = [len(text.split())]  # Track word count per fragment
                i += 1
                
                # Collect consecutive short fragments (up to a reasonable limit)
                max_group_size = 50  # Don't group more than 50 fragments
                while i < len(texts) and len(group_texts) < max_group_size:
                    next_text = str(texts[i]).strip() if texts[i] else ""
                    if not next_text:
                        # Empty text - stop grouping
                        break
                    
                    next_is_short = (len(next_text) < 25 and 
                                    not any(next_text.rstrip().endswith(p) for p in ['.', '!', '?', ':', ';', '\n']) and
                                    len(next_text.split()) <= 3)
                    
                    if next_is_short:
                        group_texts.append(next_text)
                        group_indices.append(i)
                        group_lengths.append(len(next_text.split()))
                        i += 1
                    else:
                        # Next fragment is long enough - stop grouping
                        break
                
                # Translate the group as a single sentence
                grouped_text = " ".join(group_texts)
                try:
                    translated_group = self.translate_text(grouped_text, target_lang, source_lang)
                    
                    # Split the translated text back to individual fragments
                    # Use proportional distribution based on original word counts
                    translated_words = translated_group.split()
                    total_original_words = sum(group_lengths)
                    
                    if total_original_words > 0 and len(translated_words) > 0:
                        # Distribute words proportionally based on original word counts
                        word_idx = 0
                        for idx, orig_idx in enumerate(group_indices):
                            if word_idx >= len(translated_words):
                                # No more words to distribute
                                translated[orig_idx] = str(texts[orig_idx])
                                continue
                            
                            # Calculate proportion of words this fragment should get
                            proportion = group_lengths[idx] / total_original_words
                            num_words = max(1, int(len(translated_words) * proportion))
                            
                            # For the last fragment, give it all remaining words
                            if idx == len(group_indices) - 1:
                                num_words = len(translated_words) - word_idx
                            
                            # Make sure we don't exceed available words
                            remaining_words = len(translated_words) - word_idx
                            num_words = min(num_words, remaining_words)
                            
                            if num_words > 0:
                                fragment_words = translated_words[word_idx:word_idx + num_words]
                                translated[orig_idx] = " ".join(fragment_words)
                                word_idx += num_words
                            else:
                                # Fallback: use original if distribution fails
                                translated[orig_idx] = str(texts[orig_idx])
                    else:
                        # If translation is empty or no words, keep originals
                        for orig_idx in group_indices:
                            translated[orig_idx] = str(texts[orig_idx])
                        
                except Exception as e:
                    # If translation fails, try translating individually as fallback
                    for orig_idx in group_indices:
                        try:
                            translated[orig_idx] = self.translate_text(str(texts[orig_idx]), target_lang, source_lang)
                        except:
                            translated[orig_idx] = str(texts[orig_idx])  # Keep original on error
            else:
                # Long enough text - translate individually
                try:
                    translated[i] = self.translate_text(text, target_lang, source_lang)
                except Exception as e:
                    # On error, keep original text
                    translated[i] = text
                i += 1
        
        return translated


def get_translation_provider(provider: str = "azure") -> TranslationProvider:
    """
    Get a translation provider instance based on the provider name.
    
    Args:
        provider: Provider name ("azure" or "libretranslate")
        
    Returns:
        TranslationProvider instance
        
    Raises:
        HTTPException: If provider is not supported or configuration is invalid
    """
    provider = provider.lower().strip()
    
    if provider == "azure":
        return AzureTranslationProvider()
    elif provider == "libretranslate":
        return LibreTranslateProvider()
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported translation provider: {provider}. Supported providers: 'azure', 'libretranslate'"
        )


def translate_text(text: str, target_lang: str, source_lang: str = "auto", provider: str = "azure") -> str:
    """
    Convenience function to translate text using specified provider.
    
    Args:
        text: Text to translate
        target_lang: Target language code
        source_lang: Source language code (default: "auto")
        provider: Translation provider ("azure" or "libretranslate")
        
    Returns:
        Translated text
    """
    translation_provider = get_translation_provider(provider)
    return translation_provider.translate_text(text, target_lang, source_lang)


def translate_texts(texts: List[str], target_lang: str, source_lang: str = "auto", provider: str = "azure") -> List[str]:
    """
    Convenience function to translate multiple texts using specified provider.
    
    Args:
        texts: List of texts to translate
        target_lang: Target language code
        source_lang: Source language code (default: "auto")
        provider: Translation provider ("azure" or "libretranslate")
        
    Returns:
        List of translated texts
    """
    translation_provider = get_translation_provider(provider)
    return translation_provider.translate_texts(texts, target_lang, source_lang)

