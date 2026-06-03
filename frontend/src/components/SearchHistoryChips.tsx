import type { SearchHistoryEntry } from "../types";

interface SearchHistoryChipsProps {
  history: SearchHistoryEntry[];
  onSelect: (entry: SearchHistoryEntry) => void;
  onClear?: () => void;
  maxItems?: number;
  className?: string;
}

function truncateQuery(query: string, maxLen = 56): string {
  if (query.length <= maxLen) return query;
  return `${query.slice(0, maxLen - 1)}…`;
}

export function SearchHistoryChips({
  history,
  onSelect,
  onClear,
  maxItems = 8,
  className = "",
}: SearchHistoryChipsProps) {
  const items = history.slice(0, maxItems);
  if (items.length === 0) return null;

  return (
    <div className={className}>
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-navy-500">Recent searches</span>
        {onClear && (
          <button
            type="button"
            onClick={onClear}
            className="text-xs text-navy-400 transition hover:text-navy-600"
          >
            Clear
          </button>
        )}
      </div>
      <div className="flex flex-wrap gap-2">
        {items.map((entry) => (
          <button
            key={`${entry.timestamp}-${entry.query}`}
            type="button"
            onClick={() => onSelect(entry)}
            title={entry.query}
            className="rounded-full border border-navy-200 bg-white px-3 py-1.5 text-xs text-navy-600 shadow-sm transition hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700"
          >
            {truncateQuery(entry.query)}
          </button>
        ))}
      </div>
    </div>
  );
}
