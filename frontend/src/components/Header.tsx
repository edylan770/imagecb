import { AdminNavLink } from "./AdminNavLink";

interface HeaderProps {
  indexedCount: number;
  onOpenCorpus: () => void;
}

const ATLAS_ACRONYM = [
  "AI-powered",
  "Tagging",
  "Library",
  "Asset",
  "Search",
] as const;

export function Header({ indexedCount, onOpenCorpus }: HeaderProps) {
  return (
    <header className="border-b border-navy-800 bg-navy-900 text-white shadow-md">
      <div className="flex items-center justify-between gap-4 px-5 py-2.5">
        <div className="flex min-w-0 flex-wrap items-baseline gap-x-3 gap-y-1">
          <h1 className="shrink-0 text-xl font-bold tracking-[0.18em] text-white">
            ATLAS
          </h1>
          <span className="hidden text-[10px] font-medium uppercase tracking-widest text-white/45 sm:inline">
            Tista
          </span>
          <p className="text-xs font-medium text-brand-300">
            {ATLAS_ACRONYM.join(" · ")}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className="rounded-full bg-white/10 px-2.5 py-0.5 text-xs font-medium text-white ring-1 ring-white/20">
            {indexedCount} indexed
          </span>
          <button
            type="button"
            onClick={onOpenCorpus}
            className="rounded-lg bg-brand-500 px-3.5 py-1.5 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-400"
          >
            Add to corpus
          </button>
        </div>
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
        <AdminNavLink variant="header" />
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
