import type { ResultCard as ResultCardType } from "../types";

interface ResultCardProps {
  card: ResultCardType;
}

export function ResultCard({ card }: ResultCardProps) {
  return (
    <article className="flex flex-col overflow-hidden rounded-xl bg-white shadow-md ring-1 ring-slate-200 transition hover:shadow-lg">
      <div className="relative aspect-video bg-slate-100">
        {card.has_image_file ? (
          <img
            src={card.image_url}
            alt={card.caption || card.provenance.source_name}
            className="h-full w-full object-contain"
            loading="lazy"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-xs text-slate-400">
            Image unavailable
          </div>
        )}
        <span className="absolute left-2 top-2 rounded-md bg-slate-900/75 px-2 py-0.5 text-xs font-medium text-white">
          #{card.rank}
        </span>
        <span
          className="absolute right-2 top-2 rounded-md bg-brand-600/90 px-2 py-0.5 text-xs font-semibold text-white"
          title="Calibrated relevance (display only); ranking uses raw model scores"
        >
          {card.match_percent}%
        </span>
      </div>
      <div className="flex flex-1 flex-col gap-2 p-3">
        <div className="flex flex-wrap gap-1">
          {card.provenance.chips.map((chip) => (
            <span
              key={chip}
              className="rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600"
            >
              {chip}
            </span>
          ))}
        </div>
        {card.caption && (
          <p className="line-clamp-3 text-xs leading-snug text-slate-700">
            {card.caption}
          </p>
        )}
        {card.match_hint && (
          <p
            className="mt-auto text-[10px] text-slate-400"
            title={card.match_hint}
          >
            {card.match_hint}
          </p>
        )}
      </div>
    </article>
  );
}
