import type { KeyboardEvent } from "react";
import type { SearchHistoryEntry } from "../types";
import { SearchHistoryChips } from "./SearchHistoryChips";

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
    <div className="shrink-0 border-t border-slate-200 bg-white p-4">
      <div className="flex gap-2">
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={2}
          disabled={loading}
          placeholder='e.g. "dashboard screenshots from Q3_Review.pptx"'
          className="flex-1 resize-none rounded-xl border border-slate-200 px-3 py-2 text-sm shadow-inner focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100 disabled:opacity-60"
        />
        <button
          type="button"
          onClick={onSend}
          disabled={loading || !value.trim()}
          className="self-end rounded-xl bg-brand-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "…" : "Send"}
        </button>
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <label className="flex items-center gap-2 text-xs text-slate-500">
          <span>Max results</span>
          <input
            type="range"
            min={1}
            max={30}
            value={topK}
            onChange={(e) => onTopKChange(Number(e.target.value))}
            className="accent-brand-600"
          />
          <span className="w-6 font-medium text-slate-700">{topK}</span>
        </label>
        <label className="flex items-center gap-2 text-xs text-slate-500">
          <span>Min match %</span>
          <input
            type="range"
            min={0}
            max={100}
            value={minMatchPercent}
            onChange={(e) => onMinMatchPercentChange(Number(e.target.value))}
            className="accent-brand-600"
          />
          <span className="w-8 font-medium text-slate-700">{minMatchPercent}</span>
        </label>
      </div>
      <SearchHistoryChips
        history={searchHistory}
        onSelect={onRerunSearch}
        onClear={onClearSearchHistory}
        maxItems={6}
        className="mt-3 border-t border-slate-100 pt-3"
      />
    </div>
  );
}
