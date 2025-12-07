from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class ExtractResponse(BaseModel):
    pages: int
    kind: str
    language: str
    text_preview: str


class ChatStartRequest(BaseModel):
    pdf_data: Optional[str] = None  # Base64-encoded PDF or reference to existing
    context_type: str = "translated"  # "original" or "translated"
    model: Optional[str] = None
    use_visual: bool = False
    target_language: Optional[str] = None
    source_language: Optional[str] = None
    use_source_language: bool = False  # Toggle: if True, chat in source language, else target language
    provider: str = "ollama"  # "ollama" or "gemini"


class ChatMessageRequest(BaseModel):
    session_id: str
    message: str
    stream: bool = False
    provider: Optional[str] = None  # Optional override, uses session provider if not provided


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: Optional[str] = None


class ChatSession(BaseModel):
    session_id: str
    context_type: str
    model: str
    use_visual: bool
    messages: List[ChatMessage] = []
    pdf_info: Optional[Dict[str, Any]] = None
    target_language: Optional[str] = None
    source_language: Optional[str] = None
    chat_language: Optional[str] = None  # The language the chatbot should respond in
    provider: str = "ollama"  # "ollama" or "gemini"


class ChatResponse(BaseModel):
    session_id: str
    message: str
    model: str
    finish_reason: Optional[str] = None


class ChatStartResponse(BaseModel):
    session_id: str
    available_models: List[Dict[str, Any]]
    recommended_model: str
    pdf_info: Dict[str, Any]
    provider: str = "ollama"  # "ollama" or "gemini"

