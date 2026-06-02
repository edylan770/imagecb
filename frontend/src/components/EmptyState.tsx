const FALLBACK_SUGGESTIONS = [
  "Screenshots of dashboards from Q3_Review.pptx",
  "Charts showing revenue growth",
  "Only images modified this month",
  "Logos on white backgrounds",
];

interface EmptyStateProps {
  suggestions: string[];
  loading: boolean;
  onPickExample: (text: string) => void;
}

export function EmptyState({
  suggestions,
  loading,
  onPickExample,
}: EmptyStateProps) {
  const chips =
    !loading && suggestions.length > 0 ? suggestions : FALLBACK_SUGGESTIONS;
  const showSkeleton = loading;

  return (
    <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
      <div className="mb-4 rounded-2xl bg-brand-50 p-4 text-brand-600">
        <svg
          className="mx-auto h-10 w-10"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M21 21l-4.35-4.35M11 18a7 7 0 100-14 7 7 0 000 14z"
          />
        </svg>
      </div>
      <h2 className="text-lg font-semibold text-slate-800">
        Ask about your images
      </h2>
      <p className="mt-2 max-w-md text-sm text-slate-500">
        Describe what you are looking for in plain language. Refine across turns
        — results appear on the right.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-2">
        {showSkeleton
          ? Array.from({ length: 4 }, (_, i) => (
              <span
                key={i}
                className="h-8 w-36 animate-pulse rounded-full bg-slate-200"
                aria-hidden
              />
            ))
          : chips.map((ex) => (
              <button
                key={ex}
                type="button"
                onClick={() => onPickExample(ex)}
                className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-600 shadow-sm transition hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700"
              >
                {ex}
              </button>
            ))}
      </div>
    </div>
  );
}
