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
    <div className="flex flex-col items-center justify-center px-5 py-8 text-center">
      <div className="mb-3 rounded-2xl bg-navy-900 p-3 text-brand-300 ring-1 ring-navy-700">
        <svg
          className="mx-auto h-8 w-8"
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
      <h2 className="text-lg font-semibold text-navy-900">
        Search your asset library
      </h2>
      <p className="mt-2 max-w-md text-sm text-navy-600">
        Describe what you are looking for in plain language. Refine across turns
        — results appear on the right.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-2">
        {showSkeleton
          ? Array.from({ length: 4 }, (_, i) => (
              <span
                key={i}
                className="h-8 w-36 animate-pulse rounded-full bg-navy-100"
                aria-hidden
              />
            ))
          : chips.map((ex) => (
              <button
                key={ex}
                type="button"
                onClick={() => onPickExample(ex)}
                className="rounded-full border border-navy-200 bg-white px-3 py-1.5 text-xs text-navy-700 shadow-sm transition hover:border-brand-400 hover:bg-brand-50 hover:text-brand-700"
              >
                {ex}
              </button>
            ))}
      </div>
    </div>
  );
}
