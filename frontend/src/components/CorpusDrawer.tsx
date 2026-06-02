interface CorpusDrawerProps {
  open: boolean;
  onClose: () => void;
  skipCaption: boolean;
  skipOcr: boolean;
  force: boolean;
  onSkipCaptionChange: (v: boolean) => void;
  onSkipOcrChange: (v: boolean) => void;
  onForceChange: (v: boolean) => void;
  onIngest: (files: FileList | null) => void;
  ingestMessage: string | null;
  ingesting: boolean;
}

export function CorpusDrawer({
  open,
  onClose,
  skipCaption,
  skipOcr,
  force,
  onSkipCaptionChange,
  onSkipOcrChange,
  onForceChange,
  onIngest,
  ingestMessage,
  ingesting,
}: CorpusDrawerProps) {
  if (!open) return null;

  return (
    <>
      <button
        type="button"
        className="fixed inset-0 z-40 bg-slate-900/40"
        aria-label="Close drawer"
        onClick={onClose}
      />
      <aside className="fixed right-0 top-0 z-50 flex h-full w-full max-w-md flex-col bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <h2 className="text-lg font-semibold">Add to corpus</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-slate-500 hover:bg-slate-100"
          >
            ✕
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-5">
          <p className="mb-4 text-sm text-slate-500">
            Upload images, PDF, or PPTX files. Ingest runs Bedrock calls per
            extracted image and may take several minutes.
          </p>
          <input
            type="file"
            multiple
            accept=".png,.jpg,.jpeg,.webp,.gif,.bmp,.tif,.tiff,.pdf,.pptx"
            disabled={ingesting}
            onChange={(e) => onIngest(e.target.files)}
            className="mb-4 w-full text-sm"
          />
          <div className="space-y-2 text-sm">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={skipCaption}
                onChange={(e) => onSkipCaptionChange(e.target.checked)}
                disabled={ingesting}
              />
              Skip captions (faster, weaker search)
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={skipOcr}
                onChange={(e) => onSkipOcrChange(e.target.checked)}
                disabled={ingesting}
              />
              Skip OCR
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={force}
                onChange={(e) => onForceChange(e.target.checked)}
                disabled={ingesting}
              />
              Force re-ingest duplicates
            </label>
          </div>
          {ingesting && (
            <p className="mt-4 text-sm text-brand-600">Ingesting…</p>
          )}
          {ingestMessage && (
            <pre className="mt-4 whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-xs text-slate-700">
              {ingestMessage}
            </pre>
          )}
        </div>
      </aside>
    </>
  );
}
