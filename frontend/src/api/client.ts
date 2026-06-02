import type {
  ChatResponse,
  ChatStreamCallbacks,
  ChatStreamMetadata,
  IngestResponse,
  ParsedQuery,
  StatusResponse,
  SuggestionsResponse,
} from "../types";

const API_BASE = "";

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? body.message ?? detail;
      if (Array.isArray(detail)) {
        detail = detail.map((d) => d.msg ?? JSON.stringify(d)).join("; ");
      }
    } catch {
      /* ignore */
    }
    throw new Error(String(detail));
  }
  return res.json() as Promise<T>;
}

export async function fetchStatus(): Promise<StatusResponse> {
  return request<StatusResponse>("/api/status");
}

export async function fetchSuggestions(
  recentTitles: string[],
  limit = 4,
): Promise<SuggestionsResponse> {
  return request<SuggestionsResponse>("/api/suggestions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ recent_titles: recentTitles, limit }),
  });
}

export async function sendChat(
  message: string,
  sessionId: string | null,
  topK: number,
  minMatchPercent: number,
): Promise<ChatResponse> {
  return request<ChatResponse>("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      top_k: topK,
      min_match_percent: minMatchPercent,
    }),
  });
}

type StreamEvent =
  | { type: "metadata"; session_id: string; results: ChatStreamMetadata["results"]; parsed_query?: ParsedQuery | null }
  | { type: "token"; text: string }
  | { type: "done"; assistant_message: string }
  | { type: "error"; detail: string };

function parseSseBuffer(
  buffer: string,
  onEvent: (event: StreamEvent) => void,
): string {
  const parts = buffer.split("\n\n");
  const remainder = parts.pop() ?? "";
  for (const part of parts) {
    const line = part
      .split("\n")
      .find((l) => l.startsWith("data: "));
    if (!line) continue;
    try {
      onEvent(JSON.parse(line.slice(6)) as StreamEvent);
    } catch {
      /* ignore malformed */
    }
  }
  return remainder;
}

export async function sendChatStream(
  message: string,
  sessionId: string | null,
  topK: number,
  minMatchPercent: number,
  callbacks: ChatStreamCallbacks,
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      top_k: topK,
      min_match_percent: minMatchPercent,
    }),
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? body.message ?? detail;
      if (Array.isArray(detail)) {
        detail = detail.map((d: { msg?: string }) => d.msg ?? JSON.stringify(d)).join("; ");
      }
    } catch {
      /* ignore */
    }
    callbacks.onError(String(detail));
    return;
  }

  const reader = res.body?.getReader();
  if (!reader) {
    callbacks.onError("No response body");
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";
  let streamError: string | null = null;

  const handleEvent = (event: StreamEvent) => {
    switch (event.type) {
      case "metadata":
        callbacks.onMetadata({
          session_id: event.session_id,
          results: event.results,
          parsed_query: event.parsed_query ?? null,
        });
        break;
      case "token":
        callbacks.onToken(event.text);
        break;
      case "done":
        callbacks.onDone(event.assistant_message);
        break;
      case "error":
        streamError = event.detail;
        break;
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    buffer = parseSseBuffer(buffer, handleEvent);
    if (streamError) break;
  }
  if (!streamError) {
    buffer += decoder.decode();
    parseSseBuffer(buffer + "\n\n", handleEvent);
  }
  if (streamError) {
    callbacks.onError(streamError);
  }
}

export async function resetSession(sessionId: string): Promise<void> {
  await request("/api/session/reset", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
}

export async function ingestFiles(
  files: File[],
  flags: { skipCaption: boolean; skipOcr: boolean; force: boolean },
): Promise<IngestResponse> {
  const form = new FormData();
  for (const f of files) {
    form.append("files", f);
  }
  form.append("skip_caption", String(flags.skipCaption));
  form.append("skip_ocr", String(flags.skipOcr));
  form.append("force", String(flags.force));
  return request<IngestResponse>("/api/ingest", {
    method: "POST",
    body: form,
  });
}
