"""
Chat Service Module
Handles interactions with Ollama for PDF-based chat functionality
"""
import os
from typing import List, Optional, Dict, Any, Iterator
import ollama
from fastapi import HTTPException
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables - check both project root and backend folder
backend_dir = Path(__file__).parent.parent.parent  # backend/
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

# Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL", "llama3.1:8b")
DEFAULT_VISUAL_LLM_MODEL = os.getenv("DEFAULT_VISUAL_LLM_MODEL", "llava")


class ChatService:
    """Service for handling chat interactions with Ollama"""
    
    def __init__(self, base_url: str = None):
        """
        Initialize the chat service.
        
        Args:
            base_url: Optional custom Ollama base URL
        """
        self.base_url = base_url or OLLAMA_BASE_URL
        # Configure ollama client
        ollama.Client(host=self.base_url)
    
    def _get_client(self):
        """Get Ollama client instance"""
        return ollama.Client(host=self.base_url)
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """
        Get list of available Ollama models.
        
        Returns:
            List of model information dictionaries
        """
        try:
            client = self._get_client()
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
    
    def is_model_available(self, model_name: str) -> bool:
        """
        Check if a specific model is available.
        
        Args:
            model_name: Name of the model to check
            
        Returns:
            True if model is available, False otherwise
        """
        try:
            models = self.get_available_models()
            model_names = [m.get("name", "") for m in models]
            return model_name in model_names
        except:
            return False
    
    def get_recommended_model(self, is_visual: bool = False) -> str:
        """
        Get recommended model based on use case.
        
        Args:
            is_visual: Whether visual model is needed
            
        Returns:
            Recommended model name
        """
        if is_visual:
            # Try visual models in order of preference
            visual_models = [DEFAULT_VISUAL_LLM_MODEL, "llava", "llava:latest", "bakllava"]
            for model in visual_models:
                if self.is_model_available(model):
                    return model
            # Fallback to text model if no visual model available
            return self.get_recommended_model(is_visual=False)
        else:
            # Try text models in order of preference
            text_models = [DEFAULT_LLM_MODEL, "llama3.1:8b", "llama3.1:8b:latest", "llama3.2", "llama3.2:latest", "llama3", "llama2"]
            for model in text_models:
                if self.is_model_available(model):
                    return model
            # If no models available, return default (will fail gracefully)
            return DEFAULT_LLM_MODEL
    
    def chat_with_text_context(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        stream: bool = False
    ) -> Any:
        """
        Chat using text context (extracted PDF text).
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            model: Model name (defaults to recommended text model)
            stream: Whether to stream the response
            
        Returns:
            Response from Ollama (string if not streaming, iterator if streaming)
        """
        if not model:
            model = self.get_recommended_model(is_visual=False)
        
        if not self.is_model_available(model):
            raise HTTPException(
                status_code=400,
                detail=f"Model '{model}' is not available. Please ensure it's installed in Ollama."
            )
        
        try:
            client = self._get_client()
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
        stream: bool = False
    ) -> Any:
        """
        Chat using visual context (PDF page images).
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            images: List of base64-encoded image strings
            model: Model name (defaults to recommended visual model)
            stream: Whether to stream the response
            
        Returns:
            Response from Ollama (string if not streaming, iterator if streaming)
        """
        if not model:
            model = self.get_recommended_model(is_visual=True)
        
        if not self.is_model_available(model):
            raise HTTPException(
                status_code=400,
                detail=f"Visual model '{model}' is not available. Please ensure it's installed in Ollama."
            )
        
        try:
            client = self._get_client()
            
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
        images: Optional[List[str]] = None
    ) -> Iterator[str]:
        """
        Stream chat responses.
        
        Args:
            messages: List of message dictionaries
            model: Model name
            is_visual: Whether to use visual model
            images: List of base64 images (required if is_visual=True)
            
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
                    stream=True
                )
            else:
                stream = self.chat_with_text_context(
                    messages=messages,
                    model=model,
                    stream=True
                )
            
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

