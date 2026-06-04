import type { KeyboardEvent } from "react";
import { Link } from "react-router-dom";
import type { SearchHistoryEntry } from "../types";
import { SearchHistoryChips } from "./SearchHistoryChips";

function DeckSuggestIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-5 w-5"
      aria-hidden
    >
      <rect x="3" y="4" width="18" height="12" rx="1" />
      <path d="M7 8h10M7 12h6" />
      <path d="M8 20h8" />
    </svg>
  );
}

interface ComposerProps {
  value: string;
  topK: number;
  minMatchPercent: number;
  loading: boolean;
  searchHistory: SearchHistoryEntry[];
  onChange: (value: string) => void;
  onTopKChange: (value: number) => void;
  onMinMatchPercentChange: (value: number) => void;
  onSend: () => void;
  onRerunSearch: (entry: SearchHistoryEntry) => void;
  onClearSearchHistory: () => void;
}

export function Composer({
  value,
  topK,
  minMatchPercent,
  loading,
  searchHistory,
  onChange,
  onTopKChange,
  onMinMatchPercentChange,
  onSend,
  onRerunSearch,
  onClearSearchHistory,
}: ComposerProps) {
  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  return (
    <div className="shrink-0 border-t border-navy-200 bg-white p-3">
      <div className="flex gap-2">
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={2}
          disabled={loading}
          placeholder='e.g. "dashboard screenshots from Q3_Review.pptx"'
          className="flex-1 resize-none rounded-xl border border-navy-200 px-3 py-2 text-sm text-navy-900 shadow-inner focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100 disabled:opacity-60"
        />
        <Link
          to="/deck"
          title="Deck suggest"
          aria-label="Open deck suggest"
          className="self-end rounded-xl border border-navy-200 p-2 text-navy-600 transition hover:bg-navy-50 hover:text-brand-600"
        >
          <DeckSuggestIcon />
        </Link>
        <button
          type="button"
          onClick={onSend}
          disabled={loading || !value.trim()}
          className="self-end rounded-xl bg-brand-500 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-400 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "…" : "Send"}
        </button>
      </div>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
        <label className="flex items-center gap-2 text-xs text-navy-600">
          <span>Max results</span>
          <input
            type="range"
            min={1}
            max={30}
            value={topK}
            onChange={(e) => onTopKChange(Number(e.target.value))}
            className="accent-brand-600"
          />
          <span className="w-6 font-medium text-navy-800">{topK}</span>
        </label>
        <label className="flex items-center gap-2 text-xs text-navy-600">
          <span>Min match %</span>
          <input
            type="range"
            min={0}
            max={100}
            value={minMatchPercent}
            onChange={(e) => onMinMatchPercentChange(Number(e.target.value))}
            className="accent-brand-600"
          />
          <span className="w-8 font-medium text-navy-800">{minMatchPercent}</span>
        </label>
      </div>
      <SearchHistoryChips
        history={searchHistory}
        onSelect={onRerunSearch}
        onClear={onClearSearchHistory}
        maxItems={4}
        className="mt-2 border-t border-navy-100 pt-2"
      />
    </div>
  );
}
