import type { Conversation } from "../types";
import { AdminNavLink } from "./AdminNavLink";

interface ChatSidebarProps {
  conversations: Conversation[];
  activeId: string | null;
  collapsed: boolean;
  onToggleCollapsed: () => void;
  onSelect: (id: string) => void;
  onNewChat: () => void;
  onDelete: (id: string) => void;
}

function formatRelativeTime(ts: number): string {
  const diff = Date.now() - ts;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(ts).toLocaleDateString();
}

export function ChatSidebar({
  conversations,
  activeId,
  collapsed,
  onToggleCollapsed,
  onSelect,
  onNewChat,
  onDelete,
}: ChatSidebarProps) {
  const sorted = [...conversations].sort((a, b) => b.updatedAt - a.updatedAt);

  if (collapsed) {
    return (
      <div className="flex w-10 shrink-0 flex-col items-center border-r border-slate-200 bg-slate-50 py-2">
        <button
          type="button"
          onClick={onToggleCollapsed}
          title="Show chats"
          className="rounded-lg p-2 text-slate-500 hover:bg-slate-200 hover:text-slate-700"
        >
          »
        </button>
        <button
          type="button"
          onClick={onNewChat}
          title="New chat"
          className="mt-2 rounded-lg p-2 text-brand-600 hover:bg-brand-50"
        >
          +
        </button>
        <AdminNavLink variant="sidebarCollapsed" />
      </div>
    );
  }

  return (
    <aside className="flex w-52 shrink-0 flex-col border-r border-slate-200 bg-slate-50 lg:w-56">
      <div className="flex items-center justify-between gap-1 border-b border-slate-200 px-2 py-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Chats
        </span>
        <div className="flex gap-0.5">
          <button
            type="button"
            onClick={onNewChat}
            className="rounded-md px-2 py-1 text-xs font-medium text-brand-600 hover:bg-brand-50"
          >
            New
          </button>
          <button
            type="button"
            onClick={onToggleCollapsed}
            title="Hide chats"
            className="rounded-md px-1.5 py-1 text-xs text-slate-400 hover:bg-slate-200"
          >
            «
          </button>
        </div>
      </div>
      <ul className="flex-1 overflow-y-auto p-1">
        {sorted.length === 0 ? (
          <li className="px-2 py-3 text-xs text-slate-400">No chats yet</li>
        ) : (
          sorted.map((c) => {
            const active = c.id === activeId;
            return (
              <li key={c.id} className="group relative">
                <button
                  type="button"
                  onClick={() => onSelect(c.id)}
                  className={`w-full rounded-lg px-2 py-2 text-left text-sm transition ${
                    active
                      ? "bg-white font-medium text-slate-900 shadow-sm ring-1 ring-slate-200"
                      : "text-slate-600 hover:bg-white/80"
                  }`}
                >
                  <span className="line-clamp-2 leading-snug">{c.title}</span>
                  <span className="mt-0.5 block text-[10px] text-slate-400">
                    {formatRelativeTime(c.updatedAt)}
                  </span>
                </button>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(c.id);
                  }}
                  title="Delete chat"
                  className="absolute right-1 top-1 hidden rounded p-1 text-[10px] text-slate-400 hover:bg-red-50 hover:text-red-600 group-hover:block"
                >
                  ×
                </button>
              </li>
            );
          })
        )}
      </ul>
      <div className="mt-auto border-t border-slate-200 p-2">
        <AdminNavLink variant="sidebar" />
      </div>
    </aside>
  );
}
