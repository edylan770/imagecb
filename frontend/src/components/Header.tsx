interface HeaderProps {
  indexedCount: number;
  onOpenCorpus: () => void;
}

export function Header({ indexedCount, onOpenCorpus }: HeaderProps) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 bg-white px-6 py-4 shadow-sm">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          Imagecb
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-500">
          Conversational search over your image corpus — standalone files plus
          images inside PPTX and PDF.
        </p>
      </div>
      <div className="flex items-center gap-3">
        <span className="rounded-full bg-brand-50 px-3 py-1 text-sm font-medium text-brand-700 ring-1 ring-brand-100">
          {indexedCount} indexed
        </span>
        <button
          type="button"
          onClick={onOpenCorpus}
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-brand-700"
        >
          Add to corpus
        </button>
      </div>
    </header>
  );
}
