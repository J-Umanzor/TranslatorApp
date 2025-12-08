"""
Chat Service Module
Handles interactions with Ollama and Google Gemini for PDF-based chat functionality
"""
import os
import base64
from typing import List, Optional, Dict, Any, Iterator
import ollama
from fastapi import HTTPException
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
backend_dir = Path(__file__).parent.parent.parent
env_path = backend_dir / '.env'
load_dotenv(dotenv_path=env_path)

# Try to import google-generativeai, fail gracefully if not installed
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL", "llama3.1:8b")
DEFAULT_VISUAL_LLM_MODEL = os.getenv("DEFAULT_VISUAL_LLM_MODEL", "llava")
DEFAULT_GEMINI_MODEL = os.getenv("DEFAULT_GEMINI_MODEL", "gemini-2.5-flash-lite")
DEFAULT_GEMINI_VISUAL_MODEL = os.getenv("DEFAULT_GEMINI_VISUAL_MODEL", "gemini-2.5-flash-lite")


class ChatService:
    """Service for handling chat interactions with Ollama and Google Gemini"""
    
    def __init__(self, base_url: str = None, gemini_api_key: str = None):
        """
        Initialize the chat service.
        
        Args:
            base_url: Optional custom Ollama base URL
            gemini_api_key: Optional Gemini API key (overrides env var)
        """
        self.base_url = base_url or OLLAMA_BASE_URL
        self.gemini_api_key = gemini_api_key or GEMINI_API_KEY
        
        # Configure ollama client
        ollama.Client(host=self.base_url)
        
        # Configure Gemini if available
        if GEMINI_AVAILABLE and self.gemini_api_key:
            try:
                genai.configure(api_key=self.gemini_api_key)
            except Exception as e:
                print(f"Warning: Failed to configure Gemini: {e}")
    
    def _get_ollama_client(self):
        """Get Ollama client instance"""
        return ollama.Client(host=self.base_url)
    
    def _get_gemini_model(self, model_name: str = None, is_visual: bool = False):
        """Get Gemini model instance"""
        if not GEMINI_AVAILABLE:
            raise HTTPException(
                status_code=503,
                detail="Google Generative AI library not installed. Install with: pip install google-generativeai"
            )
        if not self.gemini_api_key:
            raise HTTPException(
                status_code=503,
                detail="Gemini API key not configured. Set GEMINI_API_KEY environment variable."
            )
        
        model_name = model_name or (DEFAULT_GEMINI_VISUAL_MODEL if is_visual else DEFAULT_GEMINI_MODEL)
        try:
            return genai.GenerativeModel(model_name)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to load Gemini model '{model_name}': {str(e)}"
            )
    
    def get_available_models(self, provider: str = "ollama") -> List[Dict[str, Any]]:
        """
        Get list of available models for the specified provider.
        
        Args:
            provider: "ollama" or "gemini"
        
        Returns:
            List of model information dictionaries
        """
        if provider == "ollama":
            try:
                client = self._get_ollama_client()
                models = client.list()
                return [
                    {
                        "name": model.get("name", ""),
                        "model": model.get("model", ""),
                        "size": model.get("size", 0),
                        "digest": model.get("digest", ""),
                        "modified_at": model.get("modified_at", ""),
                    }
                    for model in models.get("models", [])
                ]
            except Exception as e:
                raise HTTPException(
                    status_code=503,
                    detail=f"Failed to connect to Ollama at {self.base_url}: {str(e)}. Please ensure Ollama is running."
                )
        elif provider == "gemini":
            if not GEMINI_AVAILABLE:
                raise HTTPException(
                    status_code=503,
                    detail="Google Generative AI library not installed. Install with: pip install google-generativeai"
                )
            if not self.gemini_api_key:
                raise HTTPException(
                    status_code=503,
                    detail="Gemini API key not configured. Set GEMINI_API_KEY environment variable."
                )
            
            try:
                # Get list of available Gemini models from the API
                models = genai.list_models()
                # Filter to only models that support generateContent
                available_models = []
                for model in models:
                    if "generateContent" in model.supported_generation_methods:
                        # Extract model name from full path (e.g., "models/gemini-2.5-flash" -> "gemini-2.5-flash")
                        model_name = model.name.split("/")[-1] if "/" in model.name else model.name
                        available_models.append({
                            "name": model_name,
                            "display_name": getattr(model, "display_name", model_name.replace("-", " ").title()),
                            "description": getattr(model, "description", ""),
                            "supported_generation_methods": list(model.supported_generation_methods),
                            "input_token_limit": getattr(model, "input_token_limit", None),
                            "output_token_limit": getattr(model, "output_token_limit", None),
                        })
                return available_models
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to list Gemini models: {str(e)}"
                )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported provider: {provider}. Use 'ollama' or 'gemini'"
            )
    
    def is_model_available(self, model_name: str, provider: str = "ollama") -> bool:
        """
        Check if a specific model is available.
        
        Args:
            model_name: Name of the model to check
            provider: "ollama" or "gemini"
            
        Returns:
            True if model is available, False otherwise
        """
        try:
            models = self.get_available_models(provider=provider)
            if provider == "ollama":
                model_names = [m.get("name", "") for m in models]
            else:  # gemini
                model_names = [m.get("name", "") for m in models]
            return model_name in model_names
        except:
            return False
    
    def get_recommended_model(self, is_visual: bool = False, provider: str = "ollama") -> str:
        """
        Get recommended model based on use case.
        
        Args:
            is_visual: Whether visual model is needed
            provider: "ollama" or "gemini"
            
        Returns:
            Recommended model name
        """
        if provider == "gemini":
            return DEFAULT_GEMINI_VISUAL_MODEL if is_visual else DEFAULT_GEMINI_MODEL
        
        # Ollama provider
        if is_visual:
            # Try visual models in order of preference
            visual_models = [DEFAULT_VISUAL_LLM_MODEL, "llava", "llava:latest", "bakllava"]
            for model in visual_models:
                if self.is_model_available(model, provider="ollama"):
                    return model
            # Fallback to text model if no visual model available
            return self.get_recommended_model(is_visual=False, provider="ollama")
        else:
            # Try text models in order of preference
            text_models = [DEFAULT_LLM_MODEL, "llama3.1:8b", "llama3.1:8b:latest", "llama3.2", "llama3.2:latest", "llama3", "llama2"]
            for model in text_models:
                if self.is_model_available(model, provider="ollama"):
                    return model
            # If no models available, return default (will fail gracefully)
            return DEFAULT_LLM_MODEL
    
    def chat_with_text_context(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        stream: bool = False,
        provider: str = "ollama"
    ) -> Any:
        """
        Chat using text context (extracted PDF text).
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            model: Model name (defaults to recommended text model)
            stream: Whether to stream the response
            provider: "ollama" or "gemini"
            
        Returns:
            Response from the provider (string if not streaming, iterator if streaming)
        """
        if provider == "gemini":
            return self._chat_with_gemini(messages, model, stream=stream, images=None)
        
        # Ollama provider
        if not model:
            model = self.get_recommended_model(is_visual=False, provider="ollama")
        
        if not self.is_model_available(model, provider="ollama"):
            raise HTTPException(
                status_code=400,
                detail=f"Model '{model}' is not available. Please ensure it's installed in Ollama."
            )
        
        try:
            client = self._get_ollama_client()
            if stream:
                return client.chat(
                    model=model,
                    messages=messages,
                    stream=True
                )
            else:
                response = client.chat(
                    model=model,
                    messages=messages
                )
                return response.get("message", {}).get("content", "")
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Chat request failed: {str(e)}"
            )
    
    def chat_with_visual_context(
        self,
        messages: List[Dict[str, Any]],
        images: List[str],
        model: Optional[str] = None,
        stream: bool = False,
        provider: str = "ollama"
    ) -> Any:
        """
        Chat using visual context (PDF page images).
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            images: List of base64-encoded image strings
            model: Model name (defaults to recommended visual model)
            stream: Whether to stream the response
            provider: "ollama" or "gemini"
            
        Returns:
            Response from the provider (string if not streaming, iterator if streaming)
        """
        if provider == "gemini":
            return self._chat_with_gemini(messages, model, stream=stream, images=images)
        
        # Ollama provider
        if not model:
            model = self.get_recommended_model(is_visual=True, provider="ollama")
        
        if not self.is_model_available(model, provider="ollama"):
            raise HTTPException(
                status_code=400,
                detail=f"Visual model '{model}' is not available. Please ensure it's installed in Ollama."
            )
        
        try:
            client = self._get_ollama_client()
            
            # Prepare messages with images
            # For visual models, images are included in the message content
            visual_messages = []
            for msg in messages:
                visual_msg = {
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                    "images": images if msg.get("role") == "user" else []
                }
                visual_messages.append(visual_msg)
            
            if stream:
                return client.chat(
                    model=model,
                    messages=visual_messages,
                    stream=True
                )
            else:
                response = client.chat(
                    model=model,
                    messages=visual_messages
                )
                return response.get("message", {}).get("content", "")
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Visual chat request failed: {str(e)}"
            )
    
    def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        is_visual: bool = False,
        images: Optional[List[str]] = None,
        provider: str = "ollama"
    ) -> Iterator[str]:
        """
        Stream chat responses.
        
        Args:
            messages: List of message dictionaries
            model: Model name
            is_visual: Whether to use visual model
            images: List of base64 images (required if is_visual=True)
            provider: "ollama" or "gemini"
            
        Yields:
            Response chunks as strings
        """
        try:
            if is_visual:
                if not images:
                    raise HTTPException(
                        status_code=400,
                        detail="Images are required for visual chat"
                    )
                stream = self.chat_with_visual_context(
                    messages=messages,
                    images=images,
                    model=model,
                    stream=True,
                    provider=provider
                )
            else:
                stream = self.chat_with_text_context(
                    messages=messages,
                    model=model,
                    stream=True,
                    provider=provider
                )
            
            if provider == "gemini":
                # Gemini streaming returns chunks directly
                for chunk in stream:
                    if hasattr(chunk, 'text'):
                        yield chunk.text
                    elif isinstance(chunk, str):
                        yield chunk
            else:
                # Ollama streaming
                for chunk in stream:
                    if chunk.get("message", {}).get("content"):
                        yield chunk["message"]["content"]
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Streaming failed: {str(e)}"
            )
    
    def _chat_with_gemini(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        stream: bool = False,
        images: Optional[List[str]] = None
    ) -> Any:
        """
        Internal method to chat with Gemini.
        
        Args:
            messages: List of message dictionaries
            model: Model name
            stream: Whether to stream the response
            images: Optional list of base64-encoded images
            
        Returns:
            Response from Gemini
        """
        if not GEMINI_AVAILABLE:
            raise HTTPException(
                status_code=503,
                detail="Google Generative AI library not installed. Install with: pip install google-generativeai"
            )
        
        if not self.gemini_api_key:
            raise HTTPException(
                status_code=503,
                detail="Gemini API key not configured. Set GEMINI_API_KEY environment variable."
            )
        
        # Get model
        is_visual = images is not None and len(images) > 0
        gemini_model = self._get_gemini_model(model, is_visual=is_visual)
        
        # Convert messages to Gemini format
        # Gemini uses "user" and "model" roles, and handles system messages differently
        gemini_history = []
        system_instruction = None
        current_message_parts = None
        
        # Process all messages - last user message goes to current, rest go to history
        for i, msg in enumerate(messages):
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                system_instruction = content
                continue
            
            # Convert "assistant" to "model" for Gemini
            gemini_role = "model" if role == "assistant" else "user"
            
            # Check if this is the last user message (which will get images if available)
            is_last_user_message = (i == len(messages) - 1 and role == "user")
            
            if is_last_user_message and images:
                # For the last user message with images, create a parts array
                parts = [content]
                for img_base64 in images:
                    # Remove data URL prefix if present
                    if img_base64.startswith("data:image"):
                        img_base64 = img_base64.split(",", 1)[1]
                    try:
                        img_data = base64.b64decode(img_base64)
                        parts.append({
                            "mime_type": "image/png",  # Assuming PNG from PDF
                            "data": img_data
                        })
                    except Exception as e:
                        # Skip invalid images
                        print(f"Warning: Failed to decode image: {e}")
                        continue
                current_message_parts = parts
            elif is_last_user_message:
                # Last user message without images
                current_message_parts = [content]
            else:
                # For history messages
                msg_parts = [content]
                gemini_history.append({"role": gemini_role, "parts": msg_parts})
        
        try:
            # Configure generation config
            generation_config = {
                "temperature": 0.7,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 8192,
            }
            
            # Use system instruction if available (for newer Gemini models)
            system_instruction_config = None
            system_instruction_used = False
            if system_instruction:
                try:
                    # Try to use system instruction (supported in gemini-1.5-pro and later)
                    system_instruction_config = system_instruction
                except:
                    # Fallback: prepend system instruction to first user message in history
                    if gemini_history and gemini_history[0]["role"] == "user":
                        gemini_history[0]["parts"][0] = f"{system_instruction}\n\n{gemini_history[0]['parts'][0]}"
            
            # Start chat with history
            if system_instruction_config:
                # For models that support system instructions
                try:
                    chat = gemini_model.start_chat(
                        history=gemini_history,
                        system_instruction=system_instruction_config
                    )
                    system_instruction_used = True
                except:
                    # Fallback if system_instruction not supported
                    chat = gemini_model.start_chat(history=gemini_history)
                    system_instruction_used = False
            else:
                chat = gemini_model.start_chat(history=gemini_history)
                system_instruction_used = False
            
            # Send current message (should always be set if we have messages)
            if not current_message_parts:
                # Fallback: use last message content if somehow current_message_parts wasn't set
                last_msg = messages[-1] if messages else None
                if last_msg and last_msg.get("role") != "system":
                    current_message_parts = [last_msg.get("content", "")]
                else:
                    current_message_parts = ["Hello"]
            
            # If system instruction wasn't used (either not supported or not provided), prepend it to current message
            # This ensures language requirements are always enforced, especially on first message
            if not system_instruction_used and system_instruction and current_message_parts:
                if isinstance(current_message_parts[0], str):
                    # Check if language instruction is already in the message
                    if "CRITICAL LANGUAGE REQUIREMENT" not in current_message_parts[0] and "MUST respond ONLY" not in current_message_parts[0]:
                        current_message_parts[0] = f"{system_instruction}\n\n{current_message_parts[0]}"
            
            message_to_send = current_message_parts
            response = chat.send_message(
                message_to_send,
                generation_config=generation_config,
                stream=stream
            )
            
            if stream:
                return response
            else:
                return response.text if hasattr(response, 'text') else str(response)
        
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Gemini chat request failed: {str(e)}"
            )

