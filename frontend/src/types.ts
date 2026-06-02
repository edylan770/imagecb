export interface Provenance {
  source_name: string;
  source_type: string;
  slide_index?: number | null;
  page_index?: number | null;
  modified?: string | null;
  author?: string | null;
  chips: string[];
}

export interface ResultCard {
  rank: number;
  image_id: string;
  image_url: string;
  provenance: Provenance;
  caption: string;
  match_hint?: string | null;
  match_percent: number;
  has_image_file: boolean;
}

export interface ParsedQuery {
  semantic_query: string;
  must_have_keywords: string[];
  must_avoid_keywords: string[];
  source_filters: {
    file_types: string[];
    filename_contains: string[];
    authors: string[];
  };
  time_filter: { after?: string | null; before?: string | null };
  is_refinement: boolean;
  top_k: number;
  interpretation_notes?: string[];
}

export interface ChatResponse {
  session_id: string;
  assistant_message: string;
  results: ResultCard[];
  parsed_query?: ParsedQuery | null;
}

export interface ChatStreamMetadata {
  session_id: string;
  results: ResultCard[];
  parsed_query?: ParsedQuery | null;
}

export interface ChatStreamCallbacks {
  onMetadata: (data: ChatStreamMetadata) => void;
  onToken: (text: string) => void;
  onDone: (assistantMessage: string) => void;
  onError: (detail: string) => void;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  turnId?: string;
}

export interface ConversationTurn {
  id: string;
  userContent: string;
  assistantContent: string;
  results: ResultCard[];
  parsedQuery: ParsedQuery | null;
}

export interface Conversation {
  id: string;
  title: string;
  sessionId: string | null;
  createdAt: number;
  updatedAt: number;
  turns: ConversationTurn[];
}

export interface StatusResponse {
  indexed_count: number;
}

export interface SuggestionsResponse {
  suggestions: string[];
  cached: boolean;
}

export interface IngestResponse {
  message: string;
  indexed_count: number;
  stats: Record<string, number>;
}
