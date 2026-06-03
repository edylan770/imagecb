export const ATLAS_ACRONYM = [
  "AI-powered",
  "Tagging",
  "Library",
  "Asset",
  "Search",
] as const;

export function AtlasWordmark({
  className = "",
  light = false,
}: {
  className?: string;
  light?: boolean;
}) {
  return (
    <span
      className={`shrink-0 text-xl font-bold tracking-[0.18em] ${
        light ? "text-navy-900" : "text-white"
      } ${className}`.trim()}
    >
      ATLAS
    </span>
  );
}

export function AtlasAcronymLine({ className = "" }: { className?: string }) {
  return (
    <p className={`text-xs font-medium text-brand-300 ${className}`.trim()}>
      {ATLAS_ACRONYM.join(" · ")}
    </p>
  );
}
