import type { ResultCard as ResultCardType } from "../types";
import { ResultCard } from "./ResultCard";

interface ResultsGridProps {
  results: ResultCardType[];
}

export function ResultsGrid({ results }: ResultsGridProps) {
  if (results.length === 0) {
    return (
      <div className="flex min-h-0 flex-1 flex-col items-center justify-center p-8 text-center text-slate-400">
        <svg
          className="mb-3 h-12 w-12 opacity-40"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1}
            d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
          />
        </svg>
        <p className="text-sm">Results from your latest query appear here</p>
      </div>
    );
  }

  return (
    <div className="grid min-h-0 flex-1 auto-rows-min grid-cols-1 gap-4 overflow-y-auto p-4 sm:grid-cols-2">
      {results.map((card) => (
        <ResultCard key={card.image_id} card={card} />
      ))}
    </div>
  );
}
