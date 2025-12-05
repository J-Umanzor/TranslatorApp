import type {
  ChatStartRequest,
  ChatMessageRequest,
  ChatResponse,
  ChatStartResponse,
  ChatSession,
} from "@/types";

const API_BASE_URL = "http://127.0.0.1:8000";

export async function getAvailableModels() {
  try {
    const response = await fetch(`${API_BASE_URL}/chat/models`);
    if (!response.ok) {
      throw new Error("Failed to fetch models");
    }
    const data = await response.json();
    return data.models || [];
  } catch (error) {
    console.error("Error fetching models:", error);
    return [];
  }
}

export async function startChat(
  pdfBase64: string,
  contextType: "original" | "translated" = "translated",
  model?: string,
  useVisual: boolean = false,
  targetLanguage?: string,
  sourceLanguage?: string,
  useSourceLanguage: boolean = false
): Promise<ChatStartResponse> {
  const formData = new FormData();
  
  // Convert base64 to Blob and send as file to avoid form field size limits
  // This avoids the 1024KB limit on form fields
  try {
    const byteCharacters = atob(pdfBase64);
    const byteNumbers = new Array(byteCharacters.length);
    for (let i = 0; i < byteCharacters.length; i++) {
      byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    const byteArray = new Uint8Array(byteNumbers);
    const blob = new Blob([byteArray], { type: "application/pdf" });
    const file = new File([blob], "document.pdf", { type: "application/pdf" });
    
    formData.append("file", file);
  } catch (error) {
    // Fallback to base64 if conversion fails (for very small files)
    formData.append("pdf_base64", pdfBase64);
  }
  
  formData.append("context_type", contextType);
  if (model) {
    formData.append("model", model);
  }
  formData.append("use_visual", useVisual.toString());
  if (targetLanguage) {
    formData.append("target_language", targetLanguage);
  }
  if (sourceLanguage) {
    formData.append("source_language", sourceLanguage);
  }
  formData.append("use_source_language", useSourceLanguage.toString());

  const response = await fetch(`${API_BASE_URL}/chat/start`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to start chat");
  }

  return response.json();
}

export async function sendChatMessage(
  sessionId: string,
  message: string,
  stream: boolean = false
): Promise<ChatResponse> {
  const request: ChatMessageRequest = {
    session_id: sessionId,
    message,
    stream,
  };

  const response = await fetch(`${API_BASE_URL}/chat/message`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to send message");
  }

  return response.json();
}

export async function getChatSession(sessionId: string): Promise<ChatSession> {
  const response = await fetch(`${API_BASE_URL}/chat/session/${sessionId}`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to get chat session");
  }

  return response.json();
}

export async function deleteChatSession(sessionId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/chat/session/${sessionId}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to delete chat session");
  }
}

