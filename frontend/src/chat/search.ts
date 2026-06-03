import type { Conversation } from "../types";

export interface ConversationSearchMatch {
  conversationId: string;
  conversationTitle: string;
  updatedAt: number;
  snippet: string;
  turnId: string | null;
  matchLabel: string;
}

function plainText(content: string): string {
  return content
    .replace(/\*\*/g, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/#+\s/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function snippetAround(text: string, query: string, maxLen = 72): string {
  const normalized = text.replace(/\s+/g, " ").trim();
  if (!normalized) return "";
  const lower = normalized.toLowerCase();
  const q = query.toLowerCase();
  const idx = lower.indexOf(q);
  if (idx === -1) {
    return normalized.length <= maxLen
      ? normalized
      : `${normalized.slice(0, maxLen - 1)}…`;
  }
  const pad = Math.floor((maxLen - query.length) / 2);
  const start = Math.max(0, idx - pad);
  const end = Math.min(normalized.length, idx + query.length + pad);
  let out = normalized.slice(start, end).trim();
  if (start > 0) out = `…${out}`;
  if (end < normalized.length) out = `${out}…`;
  return out;
}

function matches(text: string, query: string): boolean {
  return plainText(text).toLowerCase().includes(query);
}

export function searchConversations(
  conversations: Conversation[],
  rawQuery: string,
): ConversationSearchMatch[] {
  const query = rawQuery.trim().toLowerCase();
  if (!query) return [];

  const results: ConversationSearchMatch[] = [];

  for (const c of conversations) {
    const title = c.title.trim() || "New chat";
    if (matches(title, query)) {
      results.push({
        conversationId: c.id,
        conversationTitle: title,
        updatedAt: c.updatedAt,
        snippet: snippetAround(title, query),
        turnId: c.turns[c.turns.length - 1]?.id ?? null,
        matchLabel: "Title",
      });
      continue;
    }

    for (const turn of c.turns) {
      if (matches(turn.userContent, query)) {
        results.push({
          conversationId: c.id,
          conversationTitle: title,
          updatedAt: c.updatedAt,
          snippet: snippetAround(turn.userContent, query),
          turnId: turn.id,
          matchLabel: "You",
        });
        break;
      }
      const assistant = plainText(turn.assistantContent);
      if (assistant && matches(assistant, query)) {
        results.push({
          conversationId: c.id,
          conversationTitle: title,
          updatedAt: c.updatedAt,
          snippet: snippetAround(assistant, query),
          turnId: turn.id,
          matchLabel: "Assistant",
        });
        break;
      }
    }
  }

  return results.sort((a, b) => b.updatedAt - a.updatedAt);
}
