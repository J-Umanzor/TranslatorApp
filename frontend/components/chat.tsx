"use client";

import { useState, useEffect, useRef } from "react";
import { Card, CardBody } from "@heroui/card";
import { Button } from "@heroui/button";
import { Input } from "@heroui/input";
import { Select, SelectItem } from "@heroui/select";
import { Spinner } from "@heroui/spinner";
import { Switch } from "@heroui/switch";
import type { ChatMessage, ChatSession } from "@/types";
import {
  startChat,
  sendChatMessage,
  getAvailableModels,
  getChatSession,
} from "@/lib/chat-api";
import ChatSuggestions from "@/components/chat-suggestions";

interface ChatProps {
  pdfBase64: string;
  contextType?: "original" | "translated";
  targetLanguage?: string;
  sourceLanguage?: string;
  onError?: (error: string) => void;
  className?: string;
}

export default function Chat({
  pdfBase64,
  contextType = "translated",
  targetLanguage,
  sourceLanguage,
  onError,
  className = "",
}: ChatProps) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isInitializing, setIsInitializing] = useState(true);
  const [availableModels, setAvailableModels] = useState<
    Array<{ name: string; model: string }>
  >([]);
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [selectedProvider, setSelectedProvider] = useState<string>("ollama");
  const [useVisual, setUseVisual] = useState(false);
  const [useSourceLanguage, setUseSourceLanguage] = useState<boolean>(false);
  const [pdfBase64State, setPdfBase64State] = useState<string>(pdfBase64);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (pdfBase64 !== pdfBase64State) {
      setPdfBase64State(pdfBase64);
      setMessages([]);
    }
  }, [pdfBase64]);

  useEffect(() => {
    if (pdfBase64State) {
      initializeChat();
    }
  }, [pdfBase64State, contextType, useSourceLanguage, selectedProvider]);

  const initializeChat = async () => {
    setIsInitializing(true);
    try {
      // Get available models for selected provider
      const models = await getAvailableModels(selectedProvider);
      setAvailableModels(models);

      // Start chat session
      const response = await startChat(
        pdfBase64State,
        contextType,
        undefined,
        useVisual,
        targetLanguage,
        sourceLanguage,
        useSourceLanguage,
        selectedProvider
      );

      setSessionId(response.session_id);
      setSelectedModel(response.recommended_model);
      // Auto-detect if visual model should be used based on PDF type
      if (response.pdf_info?.kind === "scanned") {
        setUseVisual(true);
      }

      // Load existing messages if any
      if (response.session_id) {
        try {
          const session = await getChatSession(response.session_id);
          setMessages(session.messages || []);
        } catch (e) {
          // Session might be new, that's okay
          setMessages([]);
        }
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error
          ? error.message
          : `Failed to initialize chat with ${selectedProvider === "gemini" ? "Gemini" : "Ollama"}. Please ensure the service is configured and running.`;
      if (onError) {
        onError(errorMessage);
      } else {
        console.error("Chat initialization error:", errorMessage);
      }
    } finally {
      setIsInitializing(false);
    }
  };

  const handleSendMessage = async (messageText?: string) => {
    const messageToSend = messageText || inputMessage;
    if (!messageToSend.trim() || !sessionId || isLoading) {
      return;
    }

    const userMessage: ChatMessage = {
      role: "user",
      content: messageToSend,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputMessage("");
    setIsLoading(true);

    try {
      const response = await sendChatMessage(sessionId, messageToSend, false);
      const assistantMessage: ChatMessage = {
        role: "assistant",
        content: response.message,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      const errorMessage =
        error instanceof Error
          ? error.message
          : "Failed to send message";
      const errorChatMessage: ChatMessage = {
        role: "assistant",
        content: `Error: ${errorMessage}`,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorChatMessage]);
      if (onError) {
        onError(errorMessage);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    handleSendMessage(suggestion);
  };

  // Determine the current chat language
  const getCurrentChatLanguage = (): string => {
    if (sourceLanguage && targetLanguage) {
      return useSourceLanguage ? sourceLanguage : targetLanguage;
    }
    if (targetLanguage) {
      return targetLanguage;
    }
    if (sourceLanguage) {
      return sourceLanguage;
    }
    return "en"; // Default to English
  };


  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleLanguageToggle = (useSource: boolean) => {
    setUseSourceLanguage(useSource);
    setMessages([]); // Clear messages when changing language
    // Chat will reinitialize automatically via useEffect when useSourceLanguage changes
  };

  const handleModelChange = async (newModel: string) => {
    if (!newModel || newModel === selectedModel) {
      return;
    }
    
    const previousModel = selectedModel;
    setSelectedModel(newModel);
    setMessages([]); // Clear messages when changing model
    setIsInitializing(true);
    
    // Restart chat session with new model
    try {
      const response = await startChat(
        pdfBase64State,
        contextType,
        newModel, // Pass the selected model
        useVisual,
        targetLanguage,
        sourceLanguage,
        useSourceLanguage,
        selectedProvider
      );
      
      setSessionId(response.session_id);
    } catch (error) {
      const errorMessage =
        error instanceof Error
          ? error.message
          : "Failed to change model";
      if (onError) {
        onError(errorMessage);
      }
      // Revert to previous model on error
      setSelectedModel(previousModel);
    } finally {
      setIsInitializing(false);
    }
  };

  const handleProviderChange = async (newProvider: string) => {
    if (newProvider === selectedProvider) {
      return;
    }
    
    setSelectedProvider(newProvider);
    setSelectedModel(""); // Reset model selection
    setMessages([]); // Clear messages when changing provider
    // Chat will reinitialize automatically via useEffect when selectedProvider changes
  };

  if (isInitializing) {
    return (
      <Card className={className}>
        <CardBody className="p-6">
          <div className="flex items-center justify-center gap-3">
            <Spinner size="sm" />
            <p className="text-default-600">Initializing chat...</p>
          </div>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card className={className}>
      <CardBody className="p-6">
        <div className="flex flex-col h-full">
          {/* Header */}
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold">Chat with PDF</h3>
            <div className="flex gap-2 items-center">
              {/* Language Toggle */}
              {sourceLanguage && targetLanguage && (
                <div className="flex items-center gap-2 px-3 py-1 bg-default-100 rounded-lg">
                  <span className="text-xs text-default-600 whitespace-nowrap">
                    {useSourceLanguage ? "Source" : "Translated"}
                  </span>
                  <Switch
                    size="sm"
                    isSelected={useSourceLanguage}
                    onValueChange={handleLanguageToggle}
                    aria-label="Toggle chat language"
                    isDisabled={isLoading || isInitializing}
                  />
                  <span className="text-xs text-default-600 font-medium whitespace-nowrap">
                    {(() => {
                      const lang = useSourceLanguage ? sourceLanguage : targetLanguage;
                      try {
                        if (typeof Intl !== "undefined" && typeof Intl.DisplayNames === "function") {
                          const formatter = new Intl.DisplayNames(["en"], { type: "language" });
                          return formatter.of(lang) || lang.toUpperCase();
                        }
                      } catch {
                        // ignore formatter errors
                      }
                      return lang.toUpperCase();
                    })()}
                  </span>
                </div>
              )}
              {/* Provider Selector */}
              <Select
                size="sm"
                selectedKeys={selectedProvider ? [selectedProvider] : []}
                onSelectionChange={(keys) => {
                  const selected = Array.from(keys)[0] as string;
                  if (selected) {
                    handleProviderChange(selected);
                  }
                }}
                className="w-32"
                placeholder="Provider"
                isDisabled={isLoading || isInitializing}
              >
                <SelectItem key="ollama" value="ollama">
                  Ollama
                </SelectItem>
                <SelectItem key="gemini" value="gemini">
                  Gemini
                </SelectItem>
              </Select>
              {/* Model Selector */}
              <Select
                size="sm"
                selectedKeys={selectedModel ? [selectedModel] : []}
                onSelectionChange={(keys) => {
                  const selected = Array.from(keys)[0] as string;
                  if (selected) {
                    handleModelChange(selected);
                  }
                }}
                className="w-48"
                placeholder="Select model"
                isDisabled={isLoading || isInitializing || availableModels.length === 0}
              >
                {availableModels.map((model) => {
                  // Use display_name for Gemini, name for Ollama
                  const displayName = (model as any).display_name || model.name;
                  return (
                    <SelectItem key={model.name} value={model.name}>
                      {displayName}
                    </SelectItem>
                  );
                })}
              </Select>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto mb-4 space-y-4 min-h-[300px] max-h-[700px] border border-default-200 rounded-lg p-4 bg-default-50">
            {messages.length === 0 ? (
              <div className="text-center text-default-500 py-8">
                <p>Start a conversation about the PDF!</p>
                <p className="text-sm mt-2">
                  Ask questions, request summaries, or extract information.
                </p>
              </div>
            ) : (
              messages.map((message, index) => (
                <div
                  key={index}
                  className={`flex ${
                    message.role === "user" ? "justify-end" : "justify-start"
                  }`}
                >
                  <div
                    className={`max-w-[80%] rounded-lg p-3 ${
                      message.role === "user"
                        ? "bg-primary text-primary-foreground"
                        : "bg-default-100 text-default-900"
                    }`}
                  >
                    <p className="text-sm whitespace-pre-wrap">
                      {message.content}
                    </p>
                  </div>
                </div>
              ))
            )}
            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-default-100 rounded-lg p-3">
                  <Spinner size="sm" />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Chat Suggestions - Always visible */}
          {!isInitializing && sessionId && (
            <ChatSuggestions
              language={getCurrentChatLanguage()}
              onSuggestionClick={handleSuggestionClick}
              disabled={isLoading || !sessionId}
            />
          )}

          {/* Input */}
          <div className="flex gap-2">
            <Input
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Type your message..."
              isDisabled={isLoading || !sessionId}
              className="flex-1"
            />
            <Button
              color="primary"
              onPress={() => handleSendMessage()}
              isDisabled={isLoading || !sessionId || !inputMessage.trim()}
              isLoading={isLoading}
            >
              Send
            </Button>
          </div>

        </div>
      </CardBody>
    </Card>
  );
}

