import { SVGProps } from "react";

export type IconSvgProps = SVGProps<SVGSVGElement> & {
  size?: number;
};

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  timestamp?: string;
};

export type ChatSession = {
  session_id: string;
  context_type: "original" | "translated";
  model: string;
  use_visual: boolean;
  messages: ChatMessage[];
  pdf_info?: {
    pages: number;
    kind: "scanned" | "digital";
    has_text: boolean;
  };
};

export type ChatStartRequest = {
  pdf_base64?: string;
  context_type?: "original" | "translated";
  model?: string;
  use_visual?: boolean;
};

export type ChatMessageRequest = {
  session_id: string;
  message: string;
  stream?: boolean;
};

export type ChatResponse = {
  session_id: string;
  message: string;
  model: string;
  finish_reason?: string;
};

export type ChatStartResponse = {
  session_id: string;
  available_models: Array<{
    name: string;
    model: string;
    size: number;
    digest: string;
    modified_at: string;
  }>;
  recommended_model: string;
  pdf_info: {
    pages: number;
    kind: "scanned" | "digital";
    has_text: boolean;
  };
};