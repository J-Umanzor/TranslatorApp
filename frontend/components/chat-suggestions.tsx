"use client";

import { Chip } from "@heroui/chip";

interface ChatSuggestionsProps {
  language?: string;
  onSuggestionClick: (suggestion: string) => void;
  disabled?: boolean;
}

// Common chat suggestions in multiple languages
const SUGGESTIONS: Record<string, string[]> = {
  en: [
    "Summarize this document",
    "What are the main points?",
    "Extract key information",
    "Explain the content",
    "What is this document about?",
  ],
  es: [
    "Resumir este documento",
    "¿Cuáles son los puntos principales?",
    "Extraer información clave",
    "Explicar el contenido",
    "¿De qué trata este documento?",
  ],
  fr: [
    "Résumer ce document",
    "Quels sont les points principaux?",
    "Extraire les informations clés",
    "Expliquer le contenu",
    "De quoi parle ce document?",
  ],
  de: [
    "Dieses Dokument zusammenfassen",
    "Was sind die Hauptpunkte?",
    "Schlüsselinformationen extrahieren",
    "Den Inhalt erklären",
    "Worum geht es in diesem Dokument?",
  ],
  it: [
    "Riassumere questo documento",
    "Quali sono i punti principali?",
    "Estrarre informazioni chiave",
    "Spiegare il contenuto",
    "Di cosa parla questo documento?",
  ],
  pt: [
    "Resumir este documento",
    "Quais são os pontos principais?",
    "Extrair informações-chave",
    "Explicar o conteúdo",
    "Sobre o que é este documento?",
  ],
  ru: [
    "Резюмировать этот документ",
    "Каковы основные моменты?",
    "Извлечь ключевую информацию",
    "Объяснить содержание",
    "О чем этот документ?",
  ],
  ja: [
    "この文書を要約する",
    "主なポイントは何ですか？",
    "重要な情報を抽出する",
    "内容を説明する",
    "この文書は何についてですか？",
  ],
  ko: [
    "이 문서 요약하기",
    "주요 포인트는 무엇입니까?",
    "핵심 정보 추출하기",
    "내용 설명하기",
    "이 문서는 무엇에 관한 것입니까?",
  ],
  zh: [
    "总结这份文件",
    "主要要点是什么？",
    "提取关键信息",
    "解释内容",
    "这份文件是关于什么的？",
  ],
  ar: [
    "تلخيص هذه الوثيقة",
    "ما هي النقاط الرئيسية؟",
    "استخراج المعلومات الرئيسية",
    "شرح المحتوى",
    "ما هي هذه الوثيقة؟",
  ],
  hi: [
    "इस दस्तावेज़ को सारांशित करें",
    "मुख्य बिंदु क्या हैं?",
    "मुख्य जानकारी निकालें",
    "सामग्री समझाएं",
    "यह दस्तावेज़ किस बारे में है?",
  ],
  nl: [
    "Dit document samenvatten",
    "Wat zijn de hoofdpunten?",
    "Belangrijke informatie extraheren",
    "De inhoud uitleggen",
    "Waar gaat dit document over?",
  ],
  sv: [
    "Sammanfatta detta dokument",
    "Vad är huvudpunkterna?",
    "Extrahera nyckelinformation",
    "Förklara innehållet",
    "Vad handlar detta dokument om?",
  ],
  no: [
    "Oppsummer dette dokumentet",
    "Hva er hovedpunktene?",
    "Trekk ut nøkkelinformasjon",
    "Forklar innholdet",
    "Hva handler dette dokumentet om?",
  ],
  da: [
    "Opsummer dette dokument",
    "Hvad er hovedpunkterne?",
    "Uddrag nøgleinformation",
    "Forklar indholdet",
    "Hvad handler dette dokument om?",
  ],
};

export default function ChatSuggestions({
  language = "en",
  onSuggestionClick,
  disabled = false,
}: ChatSuggestionsProps) {
  // Get language code (e.g., "en" from "en-US" or "zh-CN")
  const langCode = language?.toLowerCase().split("-")[0] || "en";
  
  // Get suggestions for the language, fallback to English
  const suggestions = SUGGESTIONS[langCode] || SUGGESTIONS.en || [];

  if (suggestions.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-wrap gap-2 mb-4">
      {suggestions.map((suggestion, index) => (
        <Chip
          key={index}
          as="button"
          variant="flat"
          color="primary"
          className="cursor-pointer hover:opacity-80 transition-opacity"
          onClick={() => !disabled && onSuggestionClick(suggestion)}
          isDisabled={disabled}
        >
          {suggestion}
        </Chip>
      ))}
    </div>
  );
}

