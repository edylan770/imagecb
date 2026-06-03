import type { Conversation, ConversationTurn, SearchHistoryEntry } from "../types";

const STORAGE_KEY = "imagecb.conversations.v1";
const ACTIVE_KEY = "imagecb.activeConversationId.v1";
const SEARCH_HISTORY_KEY = "imagecb.searchHistory.v1";
const MAX_SEARCH_HISTORY = 30;

export interface StoredState {
  conversations: Conversation[];
  activeConversationId: string | null;
}

export function newConversationId(): string {
  return crypto.randomUUID();
}

export function newTurnId(): string {
  return crypto.randomUUID();
}

export function titleFromMessage(text: string, maxLen = 48): string {
  const t = text.trim().replace(/\s+/g, " ");
  if (!t) return "New chat";
  if (t.length <= maxLen) return t;
  return `${t.slice(0, maxLen - 1)}…`;
}

export function createConversation(): Conversation {
  const now = Date.now();
  return {
    id: newConversationId(),
    title: "New chat",
    sessionId: null,
    createdAt: now,
    updatedAt: now,
    turns: [],
  };
}

export function loadStoredState(): StoredState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const active = localStorage.getItem(ACTIVE_KEY);
    if (!raw) {
      return { conversations: [], activeConversationId: active };
    }
    const parsed = JSON.parse(raw) as Conversation[];
    const conversations = Array.isArray(parsed) ? parsed : [];
    return {
      conversations,
      activeConversationId: active,
    };
  } catch {
    return { conversations: [], activeConversationId: null };
  }
}

export function saveStoredState(state: StoredState): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state.conversations));
    if (state.activeConversationId) {
      localStorage.setItem(ACTIVE_KEY, state.activeConversationId);
    } else {
      localStorage.removeItem(ACTIVE_KEY);
    }
  } catch {
    /* quota or private mode */
  }
}

/** Server session ids are in-memory only; stale ids after API restart get a new session on next send. */
export function turnsToMessages(turns: ConversationTurn[]) {
  const messages: { role: "user" | "assistant"; content: string; turnId: string }[] =
    [];
  for (const turn of turns) {
    messages.push({ role: "user", content: turn.userContent, turnId: turn.id });
    messages.push({
      role: "assistant",
      content: turn.assistantContent,
      turnId: turn.id,
    });
  }
  return messages;
}

export function lastTurn(turns: ConversationTurn[]): ConversationTurn | null {
  return turns.length > 0 ? turns[turns.length - 1]! : null;
}

/** Recent conversation titles for dynamic empty-state suggestions. */
export function recentChatTitles(
  conversations: Conversation[],
  limit = 8,
): string[] {
  const sorted = [...conversations].sort((a, b) => b.updatedAt - a.updatedAt);
  const seen = new Set<string>();
  const out: string[] = [];
  for (const c of sorted) {
    const t = c.title.trim();
    if (!t || t.toLowerCase() === "new chat") continue;
    const key = t.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(t);
    if (out.length >= limit) break;
  }
  return out;
}

export function loadSearchHistory(): SearchHistoryEntry[] {
  try {
    const raw = localStorage.getItem(SEARCH_HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as SearchHistoryEntry[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveSearchHistory(entries: SearchHistoryEntry[]): void {
  try {
    localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(entries));
  } catch {
    /* quota or private mode */
  }
}

export function appendSearchHistory(
  entries: SearchHistoryEntry[],
  entry: SearchHistoryEntry,
): SearchHistoryEntry[] {
  const query = entry.query.trim();
  if (!query) return entries;
  const key = query.toLowerCase();
  const filtered = entries.filter((e) => e.query.trim().toLowerCase() !== key);
  const next = [{ ...entry, query }, ...filtered];
  return next.slice(0, MAX_SEARCH_HISTORY);
}
