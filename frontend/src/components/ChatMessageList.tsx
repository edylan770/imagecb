import ReactMarkdown from "react-markdown";
import type { ChatMessage } from "../types";

interface ChatMessageListProps {
  messages: ChatMessage[];
  selectedTurnId: string | null;
  onSelectTurn: (turnId: string) => void;
}

export function ChatMessageList({
  messages,
  selectedTurnId,
  onSelectTurn,
}: ChatMessageListProps) {
  return (
    <div className="flex flex-col gap-3 p-4">
      {messages.map((m, i) => {
        const turnId = m.turnId;
        const selected = turnId != null && turnId === selectedTurnId;
        const clickable = turnId != null;

        return (
          <button
            key={`${turnId ?? "msg"}-${i}`}
            type="button"
            disabled={!clickable}
            onClick={() => turnId && onSelectTurn(turnId)}
            className={`max-w-[95%] rounded-2xl px-4 py-3 text-left text-sm leading-relaxed shadow-sm transition ${
              m.role === "user"
                ? `ml-auto bg-brand-600 text-white ${selected ? "ring-2 ring-brand-300" : ""}`
                : `mr-auto bg-white text-slate-700 ring-1 ring-slate-200 ${selected ? "ring-2 ring-brand-400" : ""} ${clickable ? "cursor-pointer hover:ring-brand-200" : ""}`
            } ${!clickable ? "cursor-default" : ""}`}
          >
            {m.role === "assistant" ? (
              <div className="prose-chat">
                <ReactMarkdown>{m.content}</ReactMarkdown>
              </div>
            ) : (
              m.content
            )}
          </button>
        );
      })}
    </div>
  );
}
