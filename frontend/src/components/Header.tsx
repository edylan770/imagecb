import { AdminNavLink } from "./AdminNavLink";
import { AtlasAcronymLine, AtlasWordmark } from "./AtlasBranding";

interface HeaderProps {
  indexedCount: number;
  onOpenCorpus: () => void;
}

export function Header({ indexedCount, onOpenCorpus }: HeaderProps) {
  return (
    <header className="border-b border-navy-800 bg-navy-900 text-white shadow-md">
      <div className="flex items-center justify-between gap-4 px-5 py-2.5">
        <div className="flex min-w-0 flex-wrap items-baseline gap-x-3 gap-y-1">
          <AtlasWordmark />
          <span className="hidden text-[10px] font-medium uppercase tracking-widest text-white/45 sm:inline">
            Tista
          </span>
          <AtlasAcronymLine />
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <AdminNavLink variant="headerDark" />
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
      </div>
    </header>
  );
}
